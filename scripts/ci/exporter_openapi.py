#!/usr/bin/env python3
"""Exporter le contrat de l'API — `openapi.json` — sans réseau ni base (#2456).

    python scripts/ci/exporter_openapi.py [--sortie openapi.json]
        écrit le schéma publié (`app.contrat.contrat_publie(app.openapi())`) ;
        sans `--sortie`, sur la sortie standard.
    python scripts/ci/exporter_openapi.py --ecrire-reference
        régénère `api/app/contrat/reference.json` et en calcule la version
        (`app/contrat/__init__.py`) ; refuse, sans rien écrire, un retrait non
        annoncé ou une entrée requise neuve.

Le schéma se génère DANS le processus : importer l'application ne se connecte à
rien (le moteur SQLAlchemy est paresseux, le démarrage — `lifespan` — ne tourne
pas). Les réglages obligatoires reçoivent ici des valeurs jetables, POSÉES et non
lues dans l'environnement : une vraie `DATABASE_URL` ne sert jamais à exporter.
À la release, il s'exécute dans l'image publiée de la version, `--network none`
(`lib-contrat-version.sh`) : c'est le contrat de ce qui est servi.

`--api DIR` désigne le dossier de l'API (défaut : `api/` du dépôt ; `/app` dans
l'image).
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path

#  `.parent` et non `parents[2]` : dans l'image, le script vit à `/ci`, sans racine de dépôt.
_RACINE = Path(__file__).resolve().parent.parent.parent

#  Un port que rien n'écoute : l'export ne doit jamais ouvrir la base.
_BASE_INJOIGNABLE = "postgresql+psycopg://contrat@127.0.0.1:1/contrat"


def _application(dossier_api: Path):
    os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
    os.environ["DATABASE_URL"] = _BASE_INJOIGNABLE
    os.environ["PLATEFORME_DATABASE_URL"] = ""
    os.environ["UPLOADS_DIR"] = tempfile.mkdtemp(prefix="contrat-")
    sys.path.insert(0, str(dossier_api))
    from app.main import app

    return app


def _version_app() -> str:
    return json.loads((_RACINE / "front" / "package.json").read_text(encoding="utf-8"))["version"]


def ecrire_reference(schema: dict) -> int:
    from app import contrat
    from app.contrat import inventaire as inv
    from app.contrat.retraits import RETRAITS

    reference = contrat.lire_reference()
    courant = inv.inventaire(schema)
    ecarts = inv.comparer(reference["operations"], courant)
    refus = inv.refus(ecarts, RETRAITS, _version_app())
    refus += [
        f"{a} : annoncé au retrait, mais servi sans être déprécié dans le contrat"
        for a in inv.annonces_non_marquees(courant, RETRAITS)
    ]
    if refus:
        print("✗ Référence NON écrite — ce lot casserait un client du contrat :", file=sys.stderr)
        for message in refus:
            print(f"  · {message}", file=sys.stderr)
        return 1
    #  La première référence garde la version qu'on lui a donnée.
    version = (
        inv.version_suivante(reference["version"], ecarts)
        if reference["operations"]
        else reference["version"]
    )
    nouvelle = {"version": version, "empreinte": inv.empreinte(courant), "operations": courant}
    #  Une ligne par opération : un écart se lit dans le diff, opération par opération.
    lignes = ",\n".join(
        f"  {json.dumps(cle, ensure_ascii=False)}: {json.dumps(op, ensure_ascii=False, sort_keys=True)}"
        for cle, op in courant.items()
    )
    texte = (
        "{\n"
        f'"version": {json.dumps(nouvelle["version"])},\n'
        f'"empreinte": {json.dumps(nouvelle["empreinte"])},\n'
        f'"operations": {{\n{lignes}\n}}\n'
        "}\n"
    )
    assert json.loads(texte) == nouvelle
    contrat.FICHIER_REFERENCE.write_text(texte, encoding="utf-8", newline="\n")
    print(f"Contrat {reference['version']} → {version} ({len(courant)} opérations).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", type=Path, default=_RACINE / "api")
    parser.add_argument("--sortie", type=Path)
    parser.add_argument("--ecrire-reference", action="store_true")
    args = parser.parse_args()
    app = _application(args.api)
    if args.ecrire_reference:
        return ecrire_reference(app.openapi())
    from app.contrat import contrat_publie

    texte = json.dumps(contrat_publie(app.openapi()), ensure_ascii=False, indent=1) + "\n"
    if args.sortie:
        args.sortie.write_text(texte, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
