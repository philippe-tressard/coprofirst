"""Plusieurs copropriétés dans un processus, pour un essai : leurs bases et un client.

Extrait de `test_etancheite_coproprietes.py` (#1746) quand un second essai en a eu
besoin — le rendu des textes légaux par copropriété (#2065). Chaque copropriété a
sa base (un schéma neuf, semé), sa racine de fichiers et son secret ; le client
sert chaque requête pour la copropriété que nomme l'en-tête `ENTETE`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import contexte
from app.main import app
from app.seed import seed
from app.utils.limiter import limiter
from tests.aides_base import adresse_de_test

#: L'en-tête d'essai qui choisit la copropriété servie — le nom d'hôte en production.
ENTETE = "x-copropriete-essai"


def _copropriete(base: contexte.Copropriete, nom: str, dossier: Path, adresse: str):
    (dossier / nom).mkdir()
    return replace(
        base,
        identifiant=f"essai-{nom}",
        url_base=adresse,
        racine_fichiers=dossier / nom,
        secret=nom * 40,
    )


@contextmanager
def coproprietes_semees(
    dossier: Path, noms: tuple[str, ...], preparer: Callable[[str, Session], Any]
) -> Iterator[dict[str, tuple[contexte.Copropriete, Any]]]:
    """Une base semée par copropriété, que `preparer(nom, session)` complète.

    Rend `{nom: (copropriété, ce que preparer a rendu)}` ; à la sortie, les moteurs
    sont libérés puis les schémas retirés.
    """
    base = contexte.courante()
    rendus: dict[str, tuple[contexte.Copropriete, Any]] = {}
    retraits = []
    try:
        for nom in noms:
            adresse, retirer = adresse_de_test()
            retraits.append(retirer)
            copro = _copropriete(base, nom, dossier, adresse)
            with contexte.dans(copro):
                seed()
                with Session(contexte.moteur()) as s:
                    rendus[nom] = (copro, preparer(nom, s))
        yield rendus
    finally:
        for copro, _ in rendus.values():
            with contexte.dans(copro):
                contexte.moteur().dispose()
        for retirer in retraits:
            retirer()


def client_par_entete(monkeypatch, par_nom: dict[str, contexte.Copropriete]) -> TestClient:
    """Un client dont chaque requête est servie pour la copropriété de son en-tête."""

    def resoudre(scope):
        entetes = dict(scope.get("headers") or [])
        return par_nom[entetes[ENTETE.encode()].decode()]

    monkeypatch.setattr(contexte, "resoudre", resoudre)
    monkeypatch.setattr(contexte, "coproprietes", lambda: tuple(par_nom.values()))
    limiter.reset()
    return TestClient(app, raise_server_exceptions=False)
