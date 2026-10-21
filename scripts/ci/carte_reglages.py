#!/usr/bin/env python3
"""Régénère `docs/carte-reglages.md` — la carte des réglages, GÉNÉRÉE (#2061).

Le document se déduit du code (`api/app/utils/reglages_carte.py` et les registres
qu'il lit) ; `api/tests/test_carte_reglages.py` échoue s'il diffère de ce que ce
script produit. Même modèle que `licences_tierces.py --ecrire`.

Usage : python scripts/ci/carte_reglages.py [--ecrire]
    sans option : compare, 0 = à jour, 1 = à régénérer
    --ecrire    : réécrit le document (LF, sans BOM)
"""

from __future__ import annotations

import os
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RACINE = pathlib.Path(__file__).resolve().parents[2]
DOCUMENT = RACINE / "docs" / "carte-reglages.md"

#  Le rendu importe l'application : il lui faut une configuration qui ne mène
#  nulle part (aucune connexion n'est ouverte).
os.environ.setdefault("SECRET_KEY", "x" * 40)
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://essai@127.0.0.1:1/sans-serveur")
sys.path.insert(0, str(RACINE / "api"))


def main(argv: list[str]) -> int:
    from app.utils.reglages_carte_rendu import rendre_document

    attendu = rendre_document()
    if "--ecrire" in argv:
        DOCUMENT.write_bytes(attendu.encode("utf-8"))
        print(f"{DOCUMENT.relative_to(RACINE)} réécrit ({len(attendu.splitlines())} lignes).")
        return 0
    actuel = DOCUMENT.read_bytes().decode("utf-8") if DOCUMENT.exists() else ""
    if actuel != attendu:
        print(
            "docs/carte-reglages.md diffère du code : python scripts/ci/carte_reglages.py --ecrire"
        )
        return 1
    print("docs/carte-reglages.md est à jour.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
