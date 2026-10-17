"""Une installation commune RÉELLE, pour un essai : la déclaration, trois bases (#2053).

Extraite de `test_etancheite_coproprietes.py` quand un second essai en a eu besoin —
les fichiers `/uploads/*` servis par l'API (`test_installation_commune_fichiers.py`).

Trois copropriétés déclarées : A et B ont chacune une vraie base (un schéma neuf du
serveur des tests), C une base injoignable — le témoin de l'isolement. Les bases sont
préparées par `utils/preparer_bases` et semées par le démarrage (`app/demarrage`),
comme `start.sh` et le `lifespan` le font ; la copropriété d'une requête se choisit
par le seul en-tête `Host` : l'adresse dérivée de chacune (`HOTES`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from sqlmodel import Session

from app import contexte
from app.demarrage import preparer_les_coproprietes
from app.utils import preparer_bases
from app.utils.limiter import limiter
from tests.aides_base import adresse_de_test
from tests.aides_installation_commune import HOTE_COMMUN, installation_commune

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


@contextmanager
def installation_commune_reelle(
    dossier: Path, temoins_dans: Callable[[str, Session], Any]
) -> Iterator[dict]:
    """La déclaration, les bases préparées et semées comme au démarrage de l'API.

    `temoins_dans(nom, session)` complète les bases de A et B ; rend `{"temoins": {nom:
    ce qu'il a rendu}, "journal": lignes de la préparation, "code": son code de sortie}`.
    """
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
                        temoins[nom] = temoins_dans(nom, s)
            limiter.reset()
            yield {"temoins": temoins, "journal": journal, "code": code}
            limiter.reset()
            for nom in ("a", "b"):
                with contexte.dans(contexte.par_identifiant(f"essai-{nom}")):
                    contexte.moteur().dispose()
    for retirer in retraits:
        retirer()


def sous(client, chemin: str, nom: str, jeton: str | None = None):
    """`GET chemin` sous l'hôte de la copropriété `nom`, à la session `jeton`."""
    cookies = {"access_token": jeton} if jeton else {}
    return client.get(chemin, headers={"host": HOTES[nom]}, cookies=cookies)
