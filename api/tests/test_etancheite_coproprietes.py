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

## L'installation commune RÉELLE

Elle a son fichier, `test_etancheite_installation_commune.py` : ses deux
fixtures de module basculaient le processus entier dans un mode que celles-ci
refusent, et ne tenaient ensemble que par l'ordre d'écriture des tests (#2223).

## Ce qu'il ne voit pas — dit, pour ne pas le croire plus large

- les routes d'**écriture** (`POST`, `PATCH`, `DELETE`) : elles ne rendent pas
  de données à lire, et les appeler à l'aveugle poserait des objets factices ;
- le **service** des fichiers `/uploads/*` : il est à Caddy, hors du processus.
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import contexte
from app.auth.deps import get_current_user
from app.models.core import Utilisateur
from app.utils.limiter import limiter
from tests.aides_coproprietes import ENTETE, client_par_entete, coproprietes_semees
from tests.aides_etancheite import (
    MARQUE_A,
    MARQUE_B,
    MINIMUM_LECTURES_B,
    MINIMUM_REPONSES_200,
    MINIMUM_ROUTES,
    chemins_get,
    fuites,
    temoins_dans,
)


@pytest.fixture(scope="module")
def deux(tmp_path_factory):
    """Deux copropriétés semées, aux identifiants identiques. Rend `{nom: (copro, jeton, id)}`."""

    dossier = tmp_path_factory.mktemp("etancheite")
    with coproprietes_semees(dossier, ("a", "b"), temoins_dans) as semees:
        yield {nom: (copro, *rendu) for nom, (copro, rendu) in semees.items()}


@pytest.fixture()
def http(deux, monkeypatch):
    """Un client dont chaque requête est servie pour la copropriété de son en-tête."""
    yield client_par_entete(monkeypatch, {nom: copro for nom, (copro, _j, _i) in deux.items()})
    limiter.reset()


def _appel(http, chemin: str, copro: str, jeton: str):
    return http.get(chemin, headers={ENTETE: copro}, cookies={"access_token": jeton})


def _balayer(http, deux) -> dict[str, object]:
    _copro, jeton_b, _id = deux["b"]
    return {chemin: _appel(http, chemin, "b", jeton_b) for chemin in chemins_get()}


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
