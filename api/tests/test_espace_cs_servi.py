"""Espace CS : ce que l'API SERT à l'app iOS comme au site (#2522).

L'app iOS porte les trois premiers onglets de l'Espace CS — Comptes & accès, Badges
& télécommandes, Annuaire — et ne recopie aucune règle du front (`standards/09` §8,
règle 1). Ce qui manquait au serveur pour qu'elle dise la même chose que le site :

1. des réponses TYPÉES — le contrat les déclarait `{}`, l'app les relisait « en
   miroir » d'après le front ;
2. l'ANNONCE d'une validation de compte, composée par le front seul (« 3 lot(s)
   résolu(s) automatiquement », « ⚠️ Aucun lot trouvé dans l'import ») ;
3. le RANG d'un badge par porteur (nom puis prénom), et un export CSV déclaré CSV ;
4. les règles de l'annuaire que seul l'écran tenait : le rapprochement par le nom,
   « au moins un téléphone », un seul président, un seul interlocuteur principal.

Chaque test pose d'abord le CAS FAUTIF : ce que l'app ne pouvait pas savoir, ou ce
que le serveur acceptait parce que seul l'écran refusait.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.models.copropriete import Batiment, Copropriete, Lot, TypeLot
from app.models.core import (
    LotImport,
    MembreCS,
    MembreSyndic,
    RoleUtilisateur,
    StatutUtilisateur,
    Telecommande,
    Utilisateur,
    Vigik,
)
from app.models.gouvernance import GenreCivilite
from app.utils.annonce_compte import annonce_relance, annonce_validation
from tests.aides_base import compte
from tests.aides_http import base_http, client_http

CS = RoleUtilisateur.conseil_syndical


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


# ── 1. Des réponses typées ───────────────────────────────────────────────────

#: Les routes que l'app relisait « en miroir » faute de schéma.
ROUTES_TYPEES = [
    ("get", "/admin/commandes-acces"),
    ("post", "/admin/commandes-acces/{cmd_id}/traiter"),
    ("get", "/admin/annuaire/cs"),
    ("put", "/admin/annuaire/cs"),
    ("get", "/admin/annuaire/syndic"),
    ("put", "/admin/annuaire/syndic"),
    ("get", "/admin/annuaire/rapprochement"),
    ("post", "/admin/utilisateurs/{user_id}/accueil-arrivant"),
    ("post", "/admin/me/accueil-arrivant"),
    ("post", "/admin/utilisateurs/{user_id}/auto-match"),
]


@pytest.fixture(scope="module")
def schema():
    from app.main import app

    return app.openapi()


def _reponse(schema, methode, chemin) -> dict:
    prefixe = next(p for p in schema["paths"] if p.endswith(chemin))
    return schema["paths"][prefixe][methode]["responses"]


@pytest.mark.parametrize(("methode", "chemin"), ROUTES_TYPEES)
def test_les_reponses_de_l_espace_cs_sont_typees(schema, methode, chemin):
    reponses = _reponse(schema, methode, chemin)
    corps = next(r for code, r in reponses.items() if code.startswith("2"))
    forme = corps["content"]["application/json"]["schema"]
    assert forme, f"{methode.upper()} {chemin} : réponse libre (`{{}}`) au contrat"


def test_l_export_du_parc_est_declare_en_csv(schema):
    contenu = _reponse(schema, "get", "/acces/admin/{type_cle}/export.csv")["200"]["content"]
    assert "text/csv" in contenu, sorted(contenu)
    assert "application/json" not in contenu


# ── 2. L'annonce d'une validation de compte ─────────────────────────────────


def _compte(statut=None, **champs):
    return Utilisateur(email="x@exemple.test", prenom="Élise", nom="Morel", statut=statut, **champs)


COPRO = StatutUtilisateur.copropriétaire_résident
LOCATAIRE = StatutUtilisateur.locataire
AIDANT = StatutUtilisateur.aidant


@pytest.mark.parametrize(
    ("auto", "utilisateur", "ton", "texte"),
    [
        (
            {
                "aide_match": {
                    "aide_trouve": True,
                    "aide_nom": "Paul MARTIN",
                    "lots": 2,
                    "tc": 1,
                    "vigik": 0,
                    "delegation": True,
                }
            },
            _compte(AIDANT),
            "success",
            "Compte activé — aidé(e) : Paul MARTIN — 2 lot(s) — 1 TC — délégation créée",
        ),
        (
            {
                "aide_match": {
                    "aide_trouve": False,
                    "lots": 0,
                    "tc": 0,
                    "vigik": 0,
                    "delegation": False,
                }
            },
            _compte(AIDANT, prenom_aide="Paul", nom_aide="martin"),
            "warning",
            "Compte activé — ⚠️ Copropriétaire aidé(e) « Paul MARTIN » non trouvé(e). "
            "Affectation manuelle requise.",
        ),
        (
            {"lots_d_office": 2},
            _compte(LOCATAIRE),
            "success",
            "Compte activé — rattaché d'office à 2 lot(s) du fichier des lots, badges remis.",
        ),
        (
            {},
            _compte(LOCATAIRE),
            "warning",
            "Compte activé — ⚠️ aucun lot désigné sans ambiguïté : il le déclarera dans "
            "« Mes lots », ou à rattacher à la main.",
        ),
        (
            {"lots_resolus": 3, "lots": 3},
            _compte(COPRO),
            "success",
            "Compte activé — 3 lot(s) résolu(s) automatiquement.",
        ),
        (
            {"lots": 2},
            _compte(COPRO),
            "success",
            "Compte activé — 2 lot(s) trouvé(s) dans l'import.",
        ),
        ({}, _compte(COPRO), "warning", "Compte activé — ⚠️ Aucun lot trouvé dans l'import."),
        ({}, _compte(StatutUtilisateur.syndic), "success", "Compte activé."),
    ],
)
def test_l_annonce_de_validation_dit_ce_que_le_site_disait(auto, utilisateur, ton, texte):
    annonce = annonce_validation(auto, utilisateur)
    assert (annonce.ton, annonce.texte) == (ton, texte)


@pytest.mark.parametrize(
    ("auto", "statut", "ton", "texte"),
    [
        ({"badges_remis": 2}, LOCATAIRE, "success", "Élise MOREL — 2 badge(s) de ses lots remis."),
        (
            {"lots_resolus": 1},
            COPRO,
            "success",
            "Élise MOREL — 1 lot(s) résolu(s) automatiquement.",
        ),
        (
            {"lots": 2},
            COPRO,
            "success",
            "Élise MOREL — 2 lot(s) matché(s) (en attente de résolution).",
        ),
        ({}, COPRO, "info", "Élise MOREL — Aucun import trouvé pour ce nom."),
    ],
)
def test_l_annonce_d_une_relance_d_appariement(auto, statut, ton, texte):
    annonce = annonce_relance(auto, _compte(statut))
    assert (annonce.ton, annonce.texte) == (ton, texte)


def test_la_validation_rend_son_annonce(moteur):
    http, _ = client_http(moteur, CS)
    with Session(moteur) as s:
        attente = compte(s, prefixe="attente", actif=False, statut=StatutUtilisateur.syndic)
    r = http.post(f"/admin/comptes/{attente.id}/traiter", json={"action": "valider"})
    assert r.status_code == 200, r.text
    assert r.json()["annonce"] == {"ton": "success", "texte": "Compte activé."}


# ── 3. Le parc des accès : le rang par porteur ──────────────────────────────


def test_le_rang_d_un_badge_suit_le_nom_puis_le_prenom(moteur):
    """« Alain FAURE » se range à F, pas à A : le rang vient du nom de famille."""
    http, _ = client_http(moteur, CS)
    with Session(moteur) as s:
        alain = compte(s, prefixe="alain", prenom="Alain", nom="Faure")
        claire = compte(s, prefixe="claire", prenom="Claire", nom="Dupont")
        zoe = compte(s, prefixe="zoe", prenom="Zoé", nom="Faure")
        s.add_all(
            [
                Vigik(code="V1", user_id=alain.id),
                Vigik(code="V2", user_id=claire.id),
                Vigik(code="V3", user_id=zoe.id),
                Vigik(code="V4"),
                Telecommande(code="T1", user_id=zoe.id),
            ]
        )
        s.commit()
    r = http.get("/acces/admin/vigiks")
    assert r.status_code == 200, r.text
    rangs = {a["code"]: a["porteur_rang"] for a in r.json()}
    assert rangs["V2"] < rangs["V1"] < rangs["V3"] < rangs["V4"], rangs
    #  L'écran mêle les deux listes dans une table : leurs rangs se comparent.
    (t1,) = http.get("/acces/admin/telecommandes").json()
    assert t1["porteur_rang"] == rangs["V3"]


# ── 4. L'annuaire : les règles que seul l'écran tenait ──────────────────────


def _syndic(*membres):
    return {"nom_syndic": "", "adresse": "", "site_web": None, "membres": list(membres)}


def _membre_syndic(nom, telephone="0102030405", principal=False):
    return {
        "genre": "Mme",
        "prenom": "Ana",
        "nom": nom,
        "telephone": telephone,
        "est_principal": principal,
    }


def test_un_interlocuteur_du_syndic_sans_telephone_est_refuse(moteur):
    http, _ = client_http(moteur, CS)
    r = http.put("/admin/annuaire/syndic", json=_syndic(_membre_syndic("Petit", telephone=" ")))
    assert r.status_code == 422, r.text
    assert "téléphone" in r.json()["detail"]
    with Session(moteur) as s:
        assert s.exec(select(MembreSyndic)).all() == []


def test_deux_interlocuteurs_principaux_sont_refuses(moteur):
    http, _ = client_http(moteur, CS)
    r = http.put(
        "/admin/annuaire/syndic",
        json=_syndic(
            _membre_syndic("Petit", principal=True), _membre_syndic("Grand", principal=True)
        ),
    )
    assert r.status_code == 400, r.text


def test_deux_presidents_sont_refuses(moteur):
    http, _ = client_http(moteur, CS)
    membre = {"genre": "Mme", "prenom": "Ana", "nom": "Petit", "est_president": True}
    r = http.put("/admin/annuaire/cs", json={"membres": [membre, {**membre, "nom": "Grand"}]})
    assert r.status_code == 400, r.text


def _residence(s: Session) -> int:
    copro = Copropriete(nom="Résidence d'essai", adresse="1 rue d'essai")
    s.add(copro)
    s.commit()
    bat = Batiment(copropriete_id=copro.id, numero="4")
    s.add(bat)
    s.commit()
    appart = Lot(numero="41", type=TypeLot.appartement, etage=1, batiment_id=bat.id)
    cave = Lot(numero="C9", type=TypeLot.cave, batiment_id=bat.id)
    s.add_all([appart, cave])
    s.commit()
    s.add_all(
        [
            LotImport(
                numero="C9",
                type_raw="CA",
                etage_raw="1SS",
                lot_id=cave.id,
                nom_coproprietaire="BERNARD Luc",
            ),
            LotImport(
                numero="41",
                type_raw="AP",
                etage_raw="1ER",
                lot_id=appart.id,
                nom_coproprietaire="BERNARD Luc",
            ),
        ]
    )
    s.commit()
    return bat.id


def test_le_nom_saisi_lie_l_inscrit_et_localise_le_membre(moteur):
    """Le cas fautif : l'app enregistre un membre par son nom, le serveur n'en fait rien."""
    http, _ = client_http(moteur, CS)
    with Session(moteur) as s:
        bat_id = _residence(s)
        luc_id = compte(s, prefixe="luc", prenom="Luc", nom="Bernard").id
    membre = {"genre": "Mr", "prenom": "Luc", "nom": "bernard"}
    r = http.put("/admin/annuaire/cs", json={"membres": [membre]})
    assert r.status_code == 200, r.text
    rendu = r.json()["membres"][0]
    #  L'appartement l'emporte sur la cave, et l'étage vient du registre.
    assert (rendu["user_id"], rendu["batiment_id"], rendu["etage"]) == (luc_id, bat_id, 1)
    assert rendu["batiment_nom"] == "4"
    assert r.json()["ok"] is True


def test_la_saisie_du_conseil_prime_sur_le_registre(moteur):
    """Un étage SAISI dans la même requête n'est pas écrasé par celui du registre."""
    http, _ = client_http(moteur, CS)
    with Session(moteur) as s:
        _residence(s)
    membre = {"genre": "Mr", "prenom": "Luc", "nom": "Bernard", "etage": 3}
    r = http.put("/admin/annuaire/cs", json={"membres": [membre]})
    assert r.json()["membres"][0]["etage"] == 3


def test_un_membre_inchange_n_est_pas_relocalise(moteur):
    """Seul un nom SAISI se rapproche : une correction à la main survit au PUT suivant."""
    http, _ = client_http(moteur, CS)
    with Session(moteur) as s:
        _residence(s)
        s.add(MembreCS(genre=GenreCivilite.mr, prenom="Luc", nom="Bernard", etage=5))
        s.commit()
        ident = s.exec(select(MembreCS)).one().id
    membre = {"id": ident, "genre": "Mr", "prenom": "Luc", "nom": "Bernard", "etage": 5}
    r = http.put("/admin/annuaire/cs", json={"membres": [membre]})
    assert r.json()["membres"][0]["etage"] == 5


def test_le_rapprochement_se_demande_avant_d_enregistrer(moteur):
    """L'écran (et l'app) montrent le lien et le logement dès la frappe du nom."""
    http, _ = client_http(moteur, CS)
    with Session(moteur) as s:
        bat_id = _residence(s)
        luc_id = compte(s, prefixe="luc", prenom="Luc", nom="Bernard").id
    r = http.get("/admin/annuaire/rapprochement", params={"nom": "BERNARD"})
    assert r.status_code == 200, r.text
    assert r.json() == {
        "user_id": luc_id,
        "batiment_id": bat_id,
        "batiment_nom": "4",
        "etage": 1,
        #  En clair, comme la fiche du membre : l'écran le lit (#2633).
        "etage_libelle": "1er étage",
    }
    vide = http.get("/admin/annuaire/rapprochement", params={"nom": "B"}).json()
    assert vide == {
        "user_id": None,
        "batiment_id": None,
        "batiment_nom": None,
        "etage": None,
        "etage_libelle": "",
    }


def test_le_rapprochement_reste_au_conseil(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    assert http.get("/admin/annuaire/rapprochement", params={"nom": "Bernard"}).status_code == 403
