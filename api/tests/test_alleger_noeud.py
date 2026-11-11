"""`alleger-noeud.sh` s'exécute jusqu'à sa mesure, en simulation (#2692).

Son `--selftest` ne juge que la transaction d'apt : il sort avant le chemin réel.
Ce chemin est resté mort de v2.127.0 (#1783) au 11/11/2026 — `ICI` lu avant d'être
posé, sous `set -u` —, et personne ne l'a vu : le script ne se lance qu'à la main,
en root, sur le standby. Ce test le lance en simulation (`SIM=1`), `docker`,
`dpkg-query`, `dpkg` et `apt-get` remplacés par des bouchons muets : un nœud déjà
allégé, sans conteneur, doit répondre « Rien à retirer » et sortir en 0.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "scripts" / "exploitation" / "alleger-noeud.sh"


def test_noeud_deja_allege_rien_a_retirer(tmp_path: Path) -> None:
    bouchons = tmp_path / "bin"
    bouchons.mkdir()
    for outil in ("docker", "dpkg-query", "dpkg", "apt-get"):
        chemin = bouchons / outil
        chemin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        chemin.chmod(0o755)
    env = {**os.environ, "SIM": "1", "PATH": f"{bouchons}{os.pathsep}{os.environ['PATH']}"}
    r = subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60, check=False
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Rien à retirer" in r.stdout, r.stdout + r.stderr
