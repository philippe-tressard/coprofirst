"""L'application démarre sur une installation COMMUNE (#3108, 24/11/2026).

POURQUOI — `app/main.py` créait à l'import la racine des fichiers par
`stockage().racine`, qui lit `contexte.courante()` : sur une installation commune,
hors `contexte.dans(...)`, elle lève `HorsCopropriete`. Uvicorn ne chargeait donc
l'application sur AUCUNE installation commune, quelle que soit sa déclaration.

Rien ne le voyait : les tests de l'installation commune posent
`coproprietes_fichier` APRÈS l'import de `app.main`. Trouvé par l'essai de mise à
jour en mode commune (#3007), sur l'image publiée.

Ce test importe l'application dans un processus NEUF, la déclaration posée AVANT,
comme le fait le conteneur : absente ou vide (l'API démarre, `/health` dira 503),
et valide (la racine de chaque copropriété déclarée existe).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1]

_IMPORTER = "import app.main; print('IMPORT_OK')"


def _demarrer(tmp_path: Path, declaration: str | None) -> subprocess.CompletedProcess:
    fichier = tmp_path / "coproprietes.json"
    if declaration is not None:
        fichier.write_text(declaration, encoding="utf-8")
    env = dict(os.environ)
    base = (
        env.get("TESTS_BASE_URL") or env.get("DATABASE_URL") or "postgresql+psycopg://x@127.0.0.1/x"
    )
    env.update(
        COPROPRIETES_FICHIER=str(fichier),
        ORIGIN="http://essai.test",
        SECRET_KEY="k" * 64,
        ESSAI_A_DATABASE_URL=base,
        ESSAI_A_SECRET_KEY="s" * 64,
        UPLOADS_DIR=str(tmp_path / "uploads"),
    )
    return subprocess.run(
        [sys.executable, "-c", _IMPORTER],
        cwd=API,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _une_copropriete(racine: Path) -> str:
    return json.dumps(
        {
            "coproprietes": [
                {
                    "identifiant": "essai-a",
                    "code_postal": "75011",
                    "nom": "Essai a",
                    "anciens_alias": [],
                    "hotes": [],
                    "suspendue": False,
                    "base": "ESSAI_A_DATABASE_URL",
                    "secret": "ESSAI_A_SECRET_KEY",
                    "racine_fichiers": str(racine),
                    "expediteur": "contact@exemple.test",
                    "nom_expediteur": "Essai a",
                }
            ]
        }
    )


@pytest.mark.parametrize(
    "declaration",
    [None, '{"coproprietes": []}'],
    ids=["absente", "vide"],
)
def test_une_declaration_qui_ne_sert_pas_n_empeche_pas_le_demarrage(tmp_path, declaration):
    res = _demarrer(tmp_path, declaration)
    assert "IMPORT_OK" in res.stdout, res.stderr[-2000:]


def test_chaque_copropriete_declaree_a_sa_racine_au_demarrage(tmp_path):
    racine = tmp_path / "essai-a"
    res = _demarrer(tmp_path, _une_copropriete(racine))
    assert "IMPORT_OK" in res.stdout, res.stderr[-2000:]
    assert racine.is_dir(), "la racine des fichiers de la copropriété déclarée n'a pas été créée"
