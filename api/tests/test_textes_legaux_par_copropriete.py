"""Chaque copropriété nomme SON responsable de traitement, et sait si ses textes sont relus (#2065).

Une installation sert plusieurs syndicats de copropriétaires ; chacun est
responsable du traitement de ses données, l'opérateur de l'installation son
sous-traitant (RGPD art. 28). Le gabarit légal porte des `[[champs]]` que
`GET /config/legal` remplit de l'identité de la copropriété servie.

## Ce qu'il tient

1. **Deux copropriétés, deux responsables** : la politique et les mentions de A
   nomment le syndicat et le syndic de A, jamais ceux de B — et réciproquement.
   Cas zéro : chacune nomme bien les siens, sans quoi l'absence de l'autre ne
   prouverait rien. Le même texte source sert les deux.
2. **L'opérateur, commun** à l'installation, est nommé par les deux.
3. **Le constat se mesure** : une copropriété neuve est « à relire », l'identité
   d'exemple du seed comptée comme manquante ; la relecture d'un texte incomplet
   est refusée ; relu puis modifié, il redevient à relire.
4. **La source n'est pas le rendu** : l'écran d'édition reçoit les champs, jamais
   les noms qu'ils valent aujourd'hui.

## Ce qu'il ne voit pas

Que les textes servis en PRODUCTION soient justes : ceux de la référence sont en
base, écrits à la main, sans champs (`test_mentions_legales.py`, même limite).
"""

from __future__ import annotations

import re

import pytest
from sqlmodel import Session, select

from app import contexte
from app.auth.jwt import creer_jeton_acces
from app.config import get_settings
from app.models.copropriete import Copropriete
from app.models.core import RoleUtilisateur
from app.models.gouvernance import SyndicInfo
from app.seed.contenus_legaux import DEFAULT_LEGAL
from app.utils.limiter import limiter
from app.utils.textes_legaux.champs import A_RENSEIGNER, CHAMPS, inconnus, rendre
from app.utils.textes_legaux.identite import (
    CLE_CONTACT,
    COPROPRIETE_EXEMPLE,
    IdentiteLegale,
)
from app.utils.textes_legaux.relecture import CLE_RELECTURE
from tests.aides_base import compte
from tests.aides_coproprietes import ENTETE, client_par_entete, coproprietes_semees

#: Ce que chaque copropriété nomme — des mots qu'aucun libellé ne contient.
IDENTITES = {
    "a": {"copro": "Les Tilleulsq", "syndic": "Cabinet Alphaq", "contact": "donnees@a.example"},
    "b": {"copro": "Les Erablesq", "syndic": "Cabinet Betaq", "contact": "donnees@b.example"},
    #  Neuve : rien que le seed.
    "c": {},
}
OPERATEUR = "Operateur Gammaq"


def _preparer(nom: str, s: Session):
    admin = compte(s, prefixe=f"admin-{nom}", role=RoleUtilisateur.admin, roles_json="admin")
    jeton = creer_jeton_acces(admin.id, admin.hashed_password)
    ident = IDENTITES[nom]
    if ident:
        for fiche in s.exec(select(Copropriete)).all():
            fiche.nom, fiche.adresse = ident["copro"], f"1 place {nom.upper()}, 75001 Paris"
            s.add(fiche)
        s.add(SyndicInfo(nom_syndic=ident["syndic"], adresse=f"2 rue {nom.upper()}, 75002 Paris"))
        s.commit()
    return jeton


@pytest.fixture(scope="module")
def trois(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("textes-legaux")
    with coproprietes_semees(dossier, tuple(IDENTITES), _preparer) as semees:
        yield semees


@pytest.fixture()
def http(trois, monkeypatch):
    reglages = get_settings()
    monkeypatch.setattr(reglages, "operateur_nom", OPERATEUR)
    yield client_par_entete(monkeypatch, {nom: copro for nom, (copro, _j) in trois.items()})
    limiter.reset()


def _get(http, trois, nom: str, chemin: str):
    return http.get(chemin, headers={ENTETE: nom}, cookies={"access_token": trois[nom][1]})


def _envoyer(http, trois, nom: str, methode: str, chemin: str, corps=None):
    return http.request(
        methode, chemin, json=corps, headers={ENTETE: nom}, cookies={"access_token": trois[nom][1]}
    )


def _texte_nu(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


# ── 1 et 2. Deux copropriétés, deux responsables, un opérateur ───────────────


@pytest.mark.parametrize("cle", ["politique_confidentialite", "mentions_legales"])
def test_chaque_copropriete_nomme_son_responsable_et_jamais_celui_de_l_autre(http, trois, cle):
    for nom, autre in (("a", "b"), ("b", "a")):
        r = http.get("/config/legal", headers={ENTETE: nom})
        assert r.status_code == 200, r.text
        texte = _texte_nu(r.json()[cle])
        for quoi in ("copro", "syndic"):
            assert IDENTITES[nom][quoi] in texte, (
                f"{cle} de {nom} ne nomme pas son {quoi} ({IDENTITES[nom][quoi]})"
            )
            assert IDENTITES[autre][quoi] not in texte, (
                f"{cle} de {nom} nomme le {quoi} de {autre} : {IDENTITES[autre][quoi]}"
            )
        assert OPERATEUR in texte, f"{cle} de {nom} ne nomme pas l'opérateur, son sous-traitant"


def test_la_politique_dit_que_le_syndicat_est_responsable_et_l_operateur_sous_traitant(http, trois):
    texte = _texte_nu(
        http.get("/config/legal", headers={ENTETE: "a"}).json()["politique_confidentialite"]
    )
    responsable = texte[: texte.index("2. Données collectées")]
    assert "syndicat des copropriétaires" in responsable
    assert "sous-traitance" in responsable and "art. 28" in responsable.replace("\xa0", " ")
    assert "conseil syndical" not in responsable, (
        "le conseil syndical n'a pas la personnalité juridique : il n'est pas responsable"
    )


def test_chaque_texte_se_declare_modele_a_faire_relire_par_un_juriste(http, trois):
    """La relecture par un juriste se SIGNALE sur la page publique, jamais ne s'affirme."""
    for cle, texte in http.get("/config/legal", headers={ENTETE: "a"}).json().items():
        assert "à faire relire par un juriste" in _texte_nu(texte), f"{cle} ne se dit pas modèle"


def test_aucun_texte_ne_nomme_la_residence_de_reference():
    """Le gabarit sert toutes les copropriétés : il ne nomme jamais la référence."""
    gabarit = DEFAULT_LEGAL["mentions_legales"] + DEFAULT_LEGAL["politique_confidentialite"]
    assert "hostachy" not in gabarit.lower()


# ── 3. Le constat ─────────────────────────────────────────────────────────────


def test_une_copropriete_neuve_a_ses_textes_a_relire_et_l_exemple_du_seed_ne_compte_pas(
    http, trois
):
    r = _get(http, trois, "c", "/config/textes-legaux")
    assert r.status_code == 200, r.text
    etat = r.json()["etat"]
    assert etat["a_relire"] is True
    manques = " ".join(m for t in etat["textes"] for m in t["manques"])
    #  Le seed pose « Ma Résidence, 1 rue Exemple » : publié, il serait pire qu'un manque.
    assert "le nom de la copropriété" in manques and "l'adresse de la copropriété" in manques
    rendu = http.get("/config/legal", headers={ENTETE: "c"}).json()["mentions_legales"]
    assert COPROPRIETE_EXEMPLE["adresse"] not in rendu
    assert A_RENSEIGNER in rendu


def test_chaque_texte_porte_l_accord_de_son_titre(http, trois):
    """« Mentions légales relues » : l'accord se déclare avec le titre, l'écran ne le devine pas."""
    textes = _get(http, trois, "c", "/config/textes-legaux").json()["etat"]["textes"]
    accords = {t["titre"]: t["participe_relu"] for t in textes}
    assert accords == {"Mentions légales": "relues", "Politique de confidentialité": "relue"}


def test_une_valeur_vide_ne_laisse_ni_none_ni_trou(http, trois):
    """La copropriété neuve n'a ni syndic, ni contact, ni hébergeur : chaque champ vide se
    dit « À RENSEIGNER », jamais « None », un paragraphe vide ou des parenthèses vides."""
    for cle, texte in http.get("/config/legal", headers={ENTETE: "c"}).json().items():
        nu = _texte_nu(texte)
        for trou in ("None", "()", "( )", ", ,"):
            assert trou not in nu, f"{cle} rend {trou!r} pour un champ vide"
        assert "<p></p>" not in texte and "[[" not in texte, cle


def test_la_relecture_d_un_texte_incomplet_est_refusee(http, trois):
    r = _envoyer(http, trois, "c", "POST", "/config/textes-legaux/relecture")
    assert r.status_code == 409, r.text
    assert "Renseignez d'abord" in r.json()["detail"]


def _completer(http, trois, nom: str, monkeypatch) -> dict:
    """Les réglages de l'installation, le contact, et des textes sans « À RENSEIGNER »."""
    reglages = get_settings()
    for champ, val in {
        "operateur_adresse": "3 avenue Gamma, 69001 Lyon",
        "operateur_contact": "contact@operateur.example",
        "hebergeur": "Hebergeur Deltaq, 4 quai Delta, 33000 Bordeaux",
        "hebergeur_pays": "France",
    }.items():
        monkeypatch.setattr(reglages, champ, val)
    textes = {
        cle: DEFAULT_LEGAL[cle].replace(f"<strong>{A_RENSEIGNER}</strong>", "Rédigé")
        for cle in ("mentions_legales", "politique_confidentialite")
    }
    corps = {**textes, CLE_CONTACT: IDENTITES[nom]["contact"]}
    r = _envoyer(http, trois, nom, "PUT", "/config", corps)
    assert r.status_code == 200, r.text
    return textes


def test_relu_puis_modifie_un_texte_redevient_a_relire(http, trois, monkeypatch):
    textes = _completer(http, trois, "a", monkeypatch)
    avant = _get(http, trois, "a", "/config/textes-legaux").json()["etat"]
    assert avant["a_relire"] is True and not any(t["relu"] for t in avant["textes"])
    assert all(t["complet"] for t in avant["textes"]), avant

    r = _envoyer(http, trois, "a", "POST", "/config/textes-legaux/relecture")
    assert r.status_code == 200, r.text
    assert r.json()["a_relire"] is False

    corps = {"mentions_legales": textes["mentions_legales"] + "<p>Ajout.</p>"}
    assert _envoyer(http, trois, "a", "PUT", "/config", corps).status_code == 200
    apres = {
        t["cle"]: t
        for t in _get(http, trois, "a", "/config/textes-legaux").json()["etat"]["textes"]
    }
    assert apres["mentions_legales"]["relu"] is False
    assert apres["politique_confidentialite"]["relu"] is True
    #  B n'a rien relu : la relecture de A ne la couvre pas.
    assert _get(http, trois, "b", "/config/textes-legaux").json()["etat"]["a_relire"] is True


def test_la_relecture_ne_s_ecrit_pas_a_la_main(http, trois):
    r = _envoyer(http, trois, "b", "PUT", "/config", {CLE_RELECTURE: "{}"})
    assert r.status_code == 422, r.text
    assert CLE_RELECTURE not in _get(http, trois, "b", "/config/admin").json()


def test_le_constat_est_reserve_a_l_administrateur(http, trois):
    assert http.get("/config/textes-legaux", headers={ENTETE: "a"}).status_code == 401
    assert http.post("/config/textes-legaux/relecture", headers={ENTETE: "a"}).status_code == 401


# ── 4. La source n'est pas le rendu ───────────────────────────────────────────


def test_l_ecran_d_edition_recoit_les_champs_et_non_les_noms(http, trois):
    r = _get(http, trois, "b", "/config/textes-legaux").json()
    assert "[[syndic]]" in r["textes"]["politique_confidentialite"]
    assert IDENTITES["b"]["syndic"] not in r["textes"]["politique_confidentialite"]
    valeurs = {c["nom"]: c["valeur"] for c in r["champs"]}
    assert valeurs["syndic"] == IDENTITES["b"]["syndic"]
    assert set(valeurs) == {c.nom for c in CHAMPS}


# ── Le rendu, seul ────────────────────────────────────────────────────────────


def test_une_valeur_est_echappee_et_un_courriel_devient_un_lien():
    rendu = rendre(
        "[[copropriete]] [[contact]]",
        IdentiteLegale(copropriete="<script>x</script>", contact="a@b.example"),
    )
    assert "<script>" not in rendu and "&lt;script&gt;" in rendu
    assert '<a href="mailto:a@b.example">' in rendu


def test_un_champ_inconnu_reste_visible_et_se_signale():
    assert rendre("[[sindic]]", IdentiteLegale()) == "[[sindic]]"
    assert inconnus("[[sindic]] [[syndic]]") == ["sindic"]


def test_le_gabarit_n_emploie_que_des_champs_connus_et_les_emploie_tous():
    """Cas zéro du registre : un champ déclaré que rien n'emploie est mort."""
    gabarit = DEFAULT_LEGAL["mentions_legales"] + DEFAULT_LEGAL["politique_confidentialite"]
    assert inconnus(gabarit) == []
    employes = set(re.findall(r"\[\[([a-z_]+)\]\]", gabarit))
    assert employes == {c.nom for c in CHAMPS}, {c.nom for c in CHAMPS} - employes


def test_le_contexte_de_la_copropriete_est_celui_de_la_requete(trois):
    """Témoin de la fixture : les trois bases sont distinctes."""
    noms = set()
    for copro, _ in trois.values():
        with contexte.dans(copro), Session(contexte.moteur()) as s:
            noms.add(s.exec(select(Copropriete)).first().nom)
    assert noms == {IDENTITES["a"]["copro"], IDENTITES["b"]["copro"], COPROPRIETE_EXEMPLE["nom"]}
