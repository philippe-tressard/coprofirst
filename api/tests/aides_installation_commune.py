"""Une installation COMMUNE à trois copropriétés factices, déclarée pour un test (#1894).

- « Les Tilleuls » (75015), sans domaine propre, qui a changé de nom : l'ancien
  alias `75015-tilleuls` doit rediriger ;
- « Résidence des Chênes » (69003), avec son propre domaine ;
- « Les Érables » (13001), SUSPENDUE : jamais une destination.

L'hôte commun est celui de l'`ORIGIN` : `acces.example`.
"""

from __future__ import annotations

import json
from contextlib import contextmanager

from app.config import get_settings
from app.installation_commune import declaration as module_declaration
from tests.aides_processus import SERVEUR_INJOIGNABLE

HOTE_COMMUN = "acces.example"

COPROPRIETES = [
    {
        "identifiant": "tilleuls",
        "code_postal": "75015",
        "nom": "Les Tilleuls",
        "anciens_alias": ["75015-tilleuls"],
        "base": "TILLEULS_BASE",
        "secret": "TILLEULS_SECRET",
        "racine_fichiers": "/srv/uploads/tilleuls",
        "expediteur": "contact@tilleuls.example",
    },
    {
        "identifiant": "chenes",
        "code_postal": "69003",
        "nom": "Résidence des Chênes",
        "hotes": ["residence-chenes.example"],
        "base": "CHENES_BASE",
        "secret": "CHENES_SECRET",
        "racine_fichiers": "/srv/uploads/chenes",
        "expediteur": "contact@residence-chenes.example",
    },
    {
        "identifiant": "erables",
        "code_postal": "13001",
        "nom": "Les Érables",
        "anciens_alias": ["13001-erables"],
        "suspendue": True,
        "base": "ERABLES_BASE",
        "secret": "ERABLES_SECRET",
        "racine_fichiers": "/srv/uploads/erables",
        "expediteur": "contact@erables.example",
    },
]

#: Les variables d'environnement que la déclaration NOMME : bases et secrets.
ENVIRONNEMENT = {
    "TILLEULS_BASE": f"postgresql+psycopg://tilleuls@{SERVEUR_INJOIGNABLE}/tilleuls",
    "TILLEULS_SECRET": "t" * 40,
    "CHENES_BASE": f"postgresql+psycopg://chenes@{SERVEUR_INJOIGNABLE}/chenes",
    "CHENES_SECRET": "c" * 40,
    "ERABLES_BASE": f"postgresql+psycopg://erables@{SERVEUR_INJOIGNABLE}/erables",
    "ERABLES_SECRET": "e" * 40,
}


@contextmanager
def installation_commune(dossier, monkeypatch, coproprietes=None, origine=None):
    """Déclare l'installation commune le temps du bloc ; rend le chemin du fichier."""
    fichier = dossier / "coproprietes.json"
    fichier.write_text(
        json.dumps({"coproprietes": COPROPRIETES if coproprietes is None else coproprietes}),
        encoding="utf-8",
    )
    for nom, valeur in ENVIRONNEMENT.items():
        monkeypatch.setenv(nom, valeur)
    s = get_settings()
    monkeypatch.setattr(s, "origin", origine or f"https://{HOTE_COMMUN}")
    monkeypatch.setattr(s, "coproprietes_fichier", str(fichier))
    module_declaration._lue.clear()
    try:
        yield fichier
    finally:
        module_declaration._lue.clear()
