"""Lire un script shell comme il s'exécute en production — sans ses autotests.

Un bloc `--selftest` fabrique des données d'exemple (une charge à durée `0`, un
champ du pair simulé) : un contrôle qui le lirait refuserait ses propres témoins.
Le bloc va de son `if … "--selftest"` en colonne 0 au `fi` qui le ferme ; un
fichier `*.selftest.sh` n'est fait que de cas d'essai.

La portée des scripts, elle, reste `conftest.scripts_shell_versionnes()`.
"""

from __future__ import annotations

import pathlib
import re

_DEBUT_AUTOTEST = re.compile(r'^if .*"--selftest"')
_FIN_DE_BLOC = re.compile(r"^fi\b")


def lignes_hors_autotest(chemin: pathlib.Path) -> list[tuple[int, str]]:
    """(numéro, ligne) du script, autotests et commentaires écartés."""
    if chemin.name.endswith(".selftest.sh"):
        return []
    gardees, dans_autotest = [], False
    for no, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), start=1):
        if _DEBUT_AUTOTEST.match(ligne):
            dans_autotest = True
        elif dans_autotest and _FIN_DE_BLOC.match(ligne):
            dans_autotest = False
            continue
        if not dans_autotest and not ligne.lstrip().startswith("#"):
            gardees.append((no, ligne))
    return gardees
