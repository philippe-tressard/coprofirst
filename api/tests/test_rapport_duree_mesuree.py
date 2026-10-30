"""Une durée de rapport est MESURÉE, ou elle part en `null` — jamais un zéro écrit.

Admin › Maintenance › Contrôles de fiabilité affichait « 0 s » sur chaque ligne
(#2199, 23/10/2026). Personne n'avait chronométré quoi que ce soit : le `0` était
écrit en dur dans l'appel de `rapporter_verdicts`, alors qu'un passage dure 15 à
40 s. L'écran sait dire « — » pour une durée inconnue (`taches-colonnes.ts`) ; un
zéro, lui, se lit comme une mesure (`standards/04` §1).

Ce test lit chaque appel de `rapport_payload` dans les scripts et refuse un `0`
littéral en cinquième argument (la durée). Les autotests, qui fabriquent des
charges d'exemple, sont hors de sa portée (`aides_shell`).

Il appelle aussi la vraie fonction : une durée OMISE part en `null`, pas en `0` —
le défaut de `rapport_payload` était le même zéro, caché dans une valeur par défaut.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess

import pytest

from tests.aides_shell import lignes_hors_autotest
from tests.conftest import racine_depot, scripts_shell_versionnes

#: Un appel — ni sa définition, ni un `command -v rapport_payload >/dev/null`.
_APPEL = re.compile(r"(?<!-v )\brapport_payload\s+(?!>)(.*)")


def _arguments(texte: str) -> list[str]:
    try:
        return shlex.split(texte, posix=True)
    except ValueError:  # un `"$(…` ouvert sur la ligne : les mots suffisent
        return texte.split()


def _appels() -> list[tuple[str, list[str]]]:
    """(fichier:ligne, arguments) de chaque appel de `rapport_payload` hors autotest."""
    racine, trouves = racine_depot(), []
    for chemin in scripts_shell_versionnes():
        lignes = lignes_hors_autotest(chemin)
        for i, (no, ligne) in enumerate(lignes):
            m = _APPEL.search(ligne)
            if not m or "rapport_payload()" in ligne:
                continue
            #  Les continuations `\` se recollent : une durée peut tomber à la ligne suivante.
            texte, j = m.group(1), i
            while texte.rstrip().endswith("\\") and j + 1 < len(lignes):
                j += 1
                texte = texte.rstrip()[:-1] + " " + lignes[j][1]
            ou = f"{chemin.relative_to(racine).as_posix()}:{no}"
            trouves.append((ou, _arguments(texte)))
    return trouves


def test_les_appels_sont_trouves():
    """Cas zéro : un balayage qui ne voit rien rendrait le test suivant vert à vide."""
    taches = {args[0] for _, args in _appels() if args}
    #  Les contrôles de fiabilité et l'audit de sécurité nocturne passent par le
    #  même appel, la tâche posée par l'appelant (`$NOTIFICATION_TACHE`,
    #  lib-notification.sh, 30/10/2026) : c'est ce mot-là que le balayage voit.
    assert {'"$NOTIFICATION_TACHE"', "maintenance", "bascule", "export_hors_site"} <= taches, taches


def test_aucune_duree_ecrite_a_zero():
    fautifs = [ou for ou, args in _appels() if len(args) >= 5 and args[4] == "0"]
    assert not fautifs, (
        "durée `0` écrite en dur dans un rapport — mesurer le passage (`$SECONDS`), "
        f"ou passer `null` si la durée n'est pas connue (#2199) : {fautifs}"
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash absent")
def test_une_duree_omise_part_en_null():
    lib = racine_depot() / "scripts" / "lib" / "lib-rapport.sh"
    res = subprocess.run(
        ["bash", "-c", f"source '{lib.as_posix()}'\nrapport_payload t n"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert res.returncode == 0, res.stderr
    assert '"duree_secondes":null' in res.stdout, res.stdout
