"""La suite ne lit pas le `.env` de développement du poste (#2539, 05/11/2026).

## Le défaut

`Settings` lit `env_file = ".env"`, relatif au répertoire courant : la suite, lancée
depuis `api/`, prenait le `api/.env` du poste. Sur le Mac, il pose
`COOKIE_SECURE=false` (développement en HTTP) : `test_client_hors_navigateur`
échouait au rejeu, et passait en CI, qui n'a pas de `.env`. Un faux rouge de poste
coûte un rejeu complet ; un faux VERT, pire, ferait passer au poste ce que la CI
refuse.

## Ce que ce test vérifie

Pendant la suite, `Settings` ne lit aucun fichier `.env` : un `.env` posé dans le
répertoire courant, qui demande `COOKIE_SECURE=false`, reste sans effet. Le conftest
pose `HOSTACHY_ENV_FILE` vers un fichier vide avant d'importer l'application ; en
production, la variable est absente et `.env` reste lu.
"""

from __future__ import annotations

import os

from app.config import Settings


def test_un_env_du_repertoire_courant_est_ignore(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("COOKIE_SECURE=false\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    assert Settings().cookie_secure is True


def test_le_fichier_lu_pendant_la_suite_est_vide():
    fichier = os.environ.get("HOSTACHY_ENV_FILE")
    assert fichier, "le conftest doit poser HOSTACHY_ENV_FILE avant d'importer l'application"
    assert os.path.getsize(fichier) == 0
