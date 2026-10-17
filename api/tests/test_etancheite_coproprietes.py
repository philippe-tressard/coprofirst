"""Deux copropriétés dans un processus : rien de l'une ne paraît chez l'autre (#1746).

Chantier multi-copropriétés, spec §5.1 et §5.3 — le garde-fou permanent de
l'étanchéité. Deux copropriétés factices, deux bases, et des identifiants
IDENTIQUES : l'administrateur porte le n° 1 dans les deux. Une donnée de A
marquée d'un témoin (`MARQUE_A`) ne doit paraître dans AUCUNE réponse servie
pour B — c'est la fuite que la spec décrit (§4.5) : l'utilisateur n° 12 de A lu
dans le cache de l'utilisateur n° 12 de B.

## Comment il regarde

- La copropriété d'une requête se résout à l'ENTRÉE, par
  `contexte.ResolutionCopropriete` ; le test remplace `contexte.resoudre` pour la
  choisir par un en-tête d'essai. En production, c'est le nom d'hôte (P2-9).
- Chaque route `GET` montée est appelée pour B, par l'administrateur de B, ses
  paramètres de chemin valant 1 — l'identifiant que A et B partagent.
- **Cas zéro** : un nombre minimal de routes appelées ET de réponses 200 — un
  balayage qui ne lirait rien serait vert sur rien (`standards/04` §2).
- **Témoin** : une application d'essai montée avec le même intergiciel porte une
  route qui garde un cache de module indexé par `user_id` — la fuite type. Le
  même détecteur doit la voir ; la même route sur `contexte.etat` ne fuit pas.
- **Jeton de A présenté à B** (§5.3) : refusé, le secret de signature diffère ;
  présenté à A, il passe — sans quoi le refus ne prouverait rien.

## L'installation commune RÉELLE, de bout en bout (#2053)

La seconde moitié du fichier ne remplace plus rien : une déclaration
(`COPROPRIETES_FICHIER`), deux vraies bases préparées par `utils/preparer_bases`,
semées par le démarrage (`app/demarrage`), et la copropriété résolue par le seul
en-tête `Host` — l'adresse dérivée de chacune. Une troisième, à la base
injoignable, est le témoin de l'isolement : 503 pour son hôte seul, les deux
autres servent, ses tâches sont sautées. Cas zéro : chacune se lit elle-même.

## Ce qu'il ne voit pas — dit, pour ne pas le croire plus large

- les routes d'**écriture** (`POST`, `PATCH`, `DELETE`) : elles ne rendent pas
  de données à lire, et les appeler à l'aveugle poserait des objets factices ;
- le **service** des fichiers `/uploads/*` : il est à Caddy, hors du processus.
"""

from __future__ import annotations

import re

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import contexte
from app.auth.deps import get_current_user
from app.auth.jwt import creer_jeton_acces

from app.demarrage import preparer_les_coproprietes
from app.installation_commune.bases_pretes import INDISPONIBLE
from app.main import app
from app.models.copropriete import Copropriete
from app.models.core import RoleUtilisateur, Utilisateur
from app.models.tickets import Ticket
from app.utils import preparer_bases
from app.utils.limiter import limiter
from tests.aides_base import adresse_de_test, compte
from tests.aides_installation_commune import HOTE_COMMUN, installation_commune
from tests.aides_coproprietes import ENTETE, client_par_entete, coproprietes_semees
from tests.aides_sources import operations_montees

#: Le témoin planté dans A : un mot qu'aucun libellé de l'application ne contient.
MARQUE_A = "Fuitezq"
MARQUE_B = "Temoinb"

#: Les routes GET que le balayage n'appelle pas, avec leur raison.
ROUTES_ECARTEES = {
    "/health": "sans base ni copropriété : la sonde de Caddy",
}

#: Le cas zéro — des ordres de grandeur, pas des valeurs figées.
MINIMUM_ROUTES = 120
MINIMUM_REPONSES_200 = 40
#: Les routes qui rendent le témoin de B pour B (quatre au 10/10/2026).
MINIMUM_LECTURES_B = 3


def _temoins_dans(nom: str, s: Session) -> tuple[str, int]:
    """Dans la base `s` : un administrateur, la fiche et une affaire n° 1, tous marqués
    du témoin de `nom`. Rend (jeton de l'administrateur, son identifiant)."""
    marque = MARQUE_A if nom == "a" else MARQUE_B
    admin = compte(
        s,
        prefixe=marque.lower(),
        prenom=marque,
        nom=f"{marque} Gestionnaire",
        role=RoleUtilisateur.admin,
        roles_json="admin",
    )
    ident = admin.id
    jeton = creer_jeton_acces(ident, admin.hashed_password)
    #  Le témoin aussi dans la fiche de la copropriété et dans une
    #  affaire n° 1 : plus de tables marquées, plus de routes qui lisent.
    for fiche in s.exec(select(Copropriete)).all():
        fiche.nom = f"Residence {marque}"
        s.add(fiche)
    s.add(
        Ticket(
            numero=f"TK-{nom}-1",
            titre=f"Affaire {marque}",
            description=f"Description {marque}",
            auteur_id=ident,
        )
    )
    s.commit()
    return jeton, ident


@pytest.fixture(scope="module")
def deux(tmp_path_factory):
    """Deux copropriétés semées, aux identifiants identiques. Rend `{nom: (copro, jeton, id)}`."""

    dossier = tmp_path_factory.mktemp("etancheite")
    with coproprietes_semees(dossier, ("a", "b"), _temoins_dans) as semees:
        yield {nom: (copro, *rendu) for nom, (copro, rendu) in semees.items()}


@pytest.fixture()
def http(deux, monkeypatch):
    """Un client dont chaque requête est servie pour la copropriété de son en-tête."""
    yield client_par_entete(monkeypatch, {nom: copro for nom, (copro, _j, _i) in deux.items()})
    limiter.reset()


def _appel(http, chemin: str, copro: str, jeton: str):
    return http.get(chemin, headers={ENTETE: copro}, cookies={"access_token": jeton})


def _chemins_get() -> list[str]:
    chemins = {
        re.sub(r"\{[^}]+\}", "1", chemin)
        for methode, chemin, _route in operations_montees(app)
        if methode == "GET" and chemin not in ROUTES_ECARTEES
    }
    return sorted(chemins)


def fuites(reponses: dict[str, object], marque: str) -> list[str]:
    """Les chemins dont la réponse porte `marque` — le détecteur, témoin compris."""
    return sorted(c for c, r in reponses.items() if marque in r.text)


def _balayer(http, deux) -> dict[str, object]:
    _copro, jeton_b, _id = deux["b"]
    return {chemin: _appel(http, chemin, "b", jeton_b) for chemin in _chemins_get()}


def test_les_deux_copropriétés_partagent_leurs_identifiants(deux):
    """Sans identifiants identiques, l'essai ne mettrait pas la fuite type à l'épreuve."""
    assert deux["a"][2] == deux["b"][2]
    for nom, (copro, _jeton, ident) in deux.items():
        with contexte.dans(copro), Session(contexte.moteur()) as s:
            assert s.exec(select(Utilisateur).where(Utilisateur.id == ident)).one().prenom == (
                MARQUE_A if nom == "a" else MARQUE_B
            )


def test_aucune_reponse_servie_pour_B_ne_porte_les_donnees_de_A(http, deux):
    reponses = _balayer(http, deux)
    appelees = len(reponses)
    reussies = sum(1 for r in reponses.values() if r.status_code == 200)
    assert appelees >= MINIMUM_ROUTES, f"cas zéro : {appelees} route(s) GET balayées seulement"
    assert reussies >= MINIMUM_REPONSES_200, (
        f"cas zéro : {reussies} réponse(s) 200 sur {appelees} — le balayage ne lit presque rien"
    )
    #  B se lit bien lui-même : sans quoi l'absence de A ne prouverait rien.
    lectures_b = fuites(reponses, MARQUE_B)
    assert len(lectures_b) >= MINIMUM_LECTURES_B, (
        f"témoin : {len(lectures_b)} réponse(s) seulement portent les données de B"
    )
    assert not fuites(reponses, MARQUE_A), (
        "Donnée de la copropriété A servie pour B (#1746, spec §4.5) :\n  "
        + "\n  ".join(fuites(reponses, MARQUE_A))
    )


def test_le_jeton_de_A_est_refuse_par_B_et_accepte_par_A(http, deux):
    """Spec §5.3 : le secret de signature diffère d'une copropriété à l'autre."""
    _copro, jeton_a, _id = deux["a"]
    chez_a = _appel(http, "/auth/me", "a", jeton_a)
    assert chez_a.status_code == 200 and MARQUE_A in chez_a.text, chez_a.text
    chez_b = _appel(http, "/auth/me", "b", jeton_a)
    assert chez_b.status_code == 401, chez_b.text
    assert MARQUE_A not in chez_b.text


# ── Le témoin : la fuite type, que le détecteur doit voir ───────────────────

#: Le cache de module, indexé par le seul `user_id` : exactement ce que
#: `test_etat_module_par_copropriete.py` refuse dans `app/`.
_cache_fuyant: dict[int, str] = {}


def _application_temoin() -> FastAPI:
    essai = FastAPI()
    essai.add_middleware(contexte.ResolutionCopropriete)

    @essai.get("/fuyante")
    def fuyante(user: Utilisateur = Depends(get_current_user)) -> dict:
        return {"nom": _cache_fuyant.setdefault(user.id, user.prenom)}

    @essai.get("/etanche")
    def etanche(user: Utilisateur = Depends(get_current_user)) -> dict:
        return {"nom": contexte.etat("essai-etancheite").setdefault(user.id, user.prenom)}

    return essai


def test_le_detecteur_voit_la_fuite_type_et_pas_l_etat_par_copropriete(http, deux):
    _cache_fuyant.clear()
    client = TestClient(_application_temoin(), raise_server_exceptions=False)
    for nom in ("a", "b"):
        _copro, jeton, _id = deux[nom]
        reponses = {c: _appel(client, c, nom, jeton) for c in ("/fuyante", "/etanche")}
        assert all(r.status_code == 200 for r in reponses.values()), reponses
    #  Lu pour A d'abord, puis pour B : seule la route au cache de module rend A à B.
    assert fuites(reponses, MARQUE_A) == ["/fuyante"]


# ── L'installation commune RÉELLE : déclaration, deux bases, l'hôte seul (#2053) ──

#: Deux copropriétés servies, et une troisième dont la base ne répond pas.
INJOIGNABLE = "postgresql+psycopg://personne:x@127.0.0.1:9/aucune?connect_timeout=1"


def _hote(code_postal: str, nom: str) -> str:
    return f"{code_postal}-{nom}.{HOTE_COMMUN}"


HOTES = {
    "a": _hote("75001", "essai-a"),
    "b": _hote("75002", "essai-b"),
    "c": _hote("75003", "essai-c"),
}


def _declaree(nom: str, racine: str) -> dict:
    cle = f"ESSAI_{nom.upper()}"
    return {
        "identifiant": f"essai-{nom}",
        "code_postal": {"a": "75001", "b": "75002", "c": "75003"}[nom],
        "nom": f"Essai {nom.upper()}",
        "base": f"{cle}_BASE",
        "secret": f"{cle}_SECRET",
        "racine_fichiers": f"{racine}/{nom}",
        "expediteur": f"contact@essai-{nom}.example",
    }


@pytest.fixture(scope="module")
def commune(tmp_path_factory):
    """La déclaration, les bases préparées et semées comme au démarrage de l'API.

    Rend `{nom: (jeton, identifiant)}` pour A et B, et le journal de la préparation.
    """
    dossier = tmp_path_factory.mktemp("commune")
    #  Un chemin ABSOLU au sens du conteneur (Linux), que la déclaration exige.
    racine = "/" + dossier.as_posix().split(":", 1)[-1].lstrip("/") + "/fichiers"
    adresses, retraits = {}, []
    for nom in ("a", "b"):
        adresses[nom], retirer = adresse_de_test()
        retraits.append(retirer)
    adresses["c"] = INJOIGNABLE
    with pytest.MonkeyPatch.context() as mp:
        for nom, url in adresses.items():
            mp.setenv(f"ESSAI_{nom.upper()}_BASE", url)
            mp.setenv(f"ESSAI_{nom.upper()}_SECRET", nom * 40)
        mp.setattr(preparer_bases, "DELAI_SECONDES", 1)
        mp.setattr(preparer_bases, "DELAI_SUIVANTES", 1)
        declarees = [_declaree(n, racine) for n in ("c", "a", "b")]
        with installation_commune(dossier, mp, coproprietes=declarees):
            journal: list[str] = []
            code = preparer_bases.preparer_commune(contexte.coproprietes(), ecrire=journal.append)
            preparer_les_coproprietes()
            temoins = {}
            for nom in ("a", "b"):
                with contexte.dans(contexte.par_identifiant(f"essai-{nom}")):
                    with Session(contexte.moteur()) as s:
                        temoins[nom] = _temoins_dans(nom, s)
            limiter.reset()
            yield {"temoins": temoins, "journal": journal, "code": code}
            limiter.reset()
            for nom in ("a", "b"):
                with contexte.dans(contexte.par_identifiant(f"essai-{nom}")):
                    contexte.moteur().dispose()
    for retirer in retraits:
        retirer()


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _sous(client, chemin: str, nom: str, jeton: str | None = None):
    cookies = {"access_token": jeton} if jeton else {}
    return client.get(chemin, headers={"host": HOTES[nom]}, cookies=cookies)


def test_chaque_base_est_preparee_et_la_mauvaise_ne_bloque_pas(commune):
    """`start.sh` : la base injoignable, déclarée la première, n'arrête pas les autres."""
    assert commune["journal"][:3] == [
        "copropriete essai-c : illisible",
        "copropriete essai-a : posee",
        "copropriete essai-b : posee",
    ]
    assert commune["code"] == 0


def test_l_hote_seul_choisit_la_copropriete_cas_zero_et_temoin(commune):
    client = _client()
    for nom, marque in (("a", MARQUE_A), ("b", MARQUE_B)):
        jeton, _ident = commune["temoins"][nom]
        reponse = _sous(client, "/auth/me", nom, jeton)
        assert reponse.status_code == 200 and marque in reponse.text, reponse.text
    #  Les identifiants sont identiques, les jetons ne passent pas d'une base à l'autre.
    assert commune["temoins"]["a"][1] == commune["temoins"]["b"][1]
    jeton_a, _ = commune["temoins"]["a"]
    chez_b = _sous(client, "/auth/me", "b", jeton_a)
    assert chez_b.status_code == 401 and MARQUE_A not in chez_b.text


def test_aucune_reponse_servie_sous_l_hote_de_B_ne_porte_A(commune):
    client = _client()
    jeton_b, _ = commune["temoins"]["b"]
    reponses = {c: _sous(client, c, "b", jeton_b) for c in _chemins_get()}
    reussies = sum(1 for r in reponses.values() if r.status_code == 200)
    assert reussies >= MINIMUM_REPONSES_200, f"cas zéro : {reussies} réponse(s) 200"
    assert len(fuites(reponses, MARQUE_B)) >= MINIMUM_LECTURES_B, "témoin : B ne se lit pas"
    assert not fuites(reponses, MARQUE_A), (
        "Donnée de A servie sous l'hôte de B (#2053) :\n  "
        + "\n  ".join(fuites(reponses, MARQUE_A))
    )


def test_la_base_injoignable_n_isole_que_son_hote(commune):
    client = _client()
    chez_c = _sous(client, "/config", "c")
    assert chez_c.status_code == 503 and chez_c.json() == {"detail": INDISPONIBLE}
    assert _sous(client, "/config", "a").status_code == 200
    sante = client.get("/health", headers={"host": HOTE_COMMUN})
    assert sante.status_code == 200 and sante.json()["status"] == "degrade"
    assert "essai" not in sante.text  # ni nom ni identifiant : la route répond à tout hôte


def test_l_hote_commun_et_un_hote_inconnu_ne_servent_rien(commune):
    client = _client()
    jeton_a, _ = commune["temoins"]["a"]
    for hote in (HOTE_COMMUN, "inconnu.example", "localhost"):
        reponse = client.get("/auth/me", headers={"host": hote}, cookies={"access_token": jeton_a})
        assert reponse.status_code == 421, hote


def test_une_tache_tourne_pour_chacune_et_saute_la_base_injoignable(commune):
    vues: list[str] = []
    contexte.pour_chaque_copropriete(
        lambda: vues.append(contexte.courante().identifiant), "essai"
    )()
    assert vues == ["essai-a", "essai-b"]


def test_hors_requete_aucune_copropriete_n_est_devinee(commune):
    with pytest.raises(contexte.HorsCopropriete):
        contexte.courante()


def test_les_mesures_de_l_installation_ne_supposent_aucune_copropriete(commune):
    """Le rapport nocturne mesure l'installation hors requête : il nomme ses
    copropriétés une à une, il ne s'en remet pas à une « courante » (#2053)."""
    from app.inscription import rapport

    assert rapport.hebergement().moteur_base == "postgresql"
    assert rapport.posture().secret_suffisant is True
