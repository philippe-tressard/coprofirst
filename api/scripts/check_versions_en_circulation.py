#!/usr/bin/env python3
"""Garde-fou : chaque version distribuée d'une app est déclarée, et chaque contrat
figé est la référence de son plancher (#2919, #2970).

## Pourquoi

L'iOS 1.1 est sortie le 18/11/2026 sans entrée dans `EN_CIRCULATION` : neuf PR ont
touché le contrat, jugées contre la seule 1.0. La déclaration reposait sur une
mémoire — rien ne la demandait. Ce contrôle la demande : il lit les étiquettes
`vX.Y.Z` des dépôts des apps (`circulation.APPS`, dépôts publics) et refuse celle
qui n'a pas d'entrée. Il relit aussi chaque contrat figé contre la référence de
l'étiquette du serveur qu'il nomme : un contrat figé recopié d'un autre plancher
jugerait l'app contre ce qu'elle n'a pas compilé.

🔴 Un dépôt illisible ou une étiquette du serveur introuvable rend **INCONNU** et
sort en **2** — jamais OK (`standards/04` §1).

Usage (depuis `api/`, dans la CI : job « Tests Python ») :
    python scripts/check_versions_en_circulation.py
    0 = conforme · 1 = écart · 2 = INCONNU
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contrat import circulation as circ  # noqa: E402

DEPOT_DES_APPS = "https://github.com/philippe-tressard/{app}.git"
REFERENCE = "api/app/contrat/reference.json"


class Inconnu(Exception):
    pass


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise Inconnu(f"git {' '.join(args)} : {r.stderr.strip() or r.returncode}")
    return r.stdout


def etiquettes(app: str) -> list[str]:
    sortie = _git("ls-remote", "--tags", "--refs", DEPOT_DES_APPS.format(app=app))
    return [
        ligne.split("refs/tags/", 1)[1] for ligne in sortie.splitlines() if "refs/tags/" in ligne
    ]


def reference_au_plancher(plancher: str) -> dict:
    """La référence du serveur à l'étiquette `plancher` — récupérée si le clone ne l'a pas
    (la CI clone sans étiquettes)."""
    try:
        _git("cat-file", "-e", f"{plancher}^{{commit}}")
    except Inconnu:
        _git(
            "fetch",
            "--quiet",
            "--depth=1",
            "--no-tags",
            "origin",
            f"refs/tags/{plancher}:refs/tags/{plancher}",
        )
    return json.loads(_git("show", f"{plancher}:{REFERENCE}"))


def planchers_faux() -> list[str]:
    return [
        f"{v.nom} : le contrat figé n'est pas la référence de {v.plancher} ({v.fichier.name})"
        for v in circ.EN_CIRCULATION
        if circ.contrat_fige(v) != reference_au_plancher(v.plancher)
    ]


def main() -> int:
    try:
        lues = {app: etiquettes(app) for app in circ.APPS}
        ecarts = circ.etiquettes_non_declarees(lues) + planchers_faux()
    except (Inconnu, subprocess.TimeoutExpired, OSError) as e:
        print(f"INCONNU — {e}")
        return 2
    for e in ecarts:
        print(f"ÉCART — {e}")
    if ecarts:
        return 1
    print(
        f"OK — {len(circ.EN_CIRCULATION)} version(s) en circulation, étiquettes et planchers concordants"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
