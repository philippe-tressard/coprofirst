"""Une PR fermée sans fusion emporte sa branche distante (#2978).

`delete_branch_on_merge` ne vaut que pour une FUSION. Quand un lot reprend une
montée de Dependabot, la PR est fermée à la main (`reprendre-dependabot.py
--fermer`) : sans `--delete-branch`, sa branche restait sur le dépôt — sept
l'étaient le 23/11/2026, et faisaient croire des montées encore en attente.

Le contrôle lit chaque script suivi par git (`scripts/`, `.githooks/`,
`.github/`) : une ligne qui ferme une PR par `gh pr close` — commande shell ou
liste d'arguments Python — porte `--delete-branch` sur la même instruction.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

RACINE = pathlib.Path(__file__).resolve().parents[2]
PORTEE = ("scripts", ".githooks", ".github")

#: `gh pr close`, écrit en shell (`gh pr close 12`) ou en liste (`['gh', 'pr', 'close', …]`).
FERMETURE = re.compile(r"""\bgh['"]?\s*,?\s*['"]?pr['"]?\s*,?\s*['"]?close\b""")


def fermetures_sans_suppression(texte: str) -> list[int]:
    """Les lignes qui ferment une PR sans emporter sa branche. PURE.

    Une instruction peut se couper sur plusieurs lignes (`subprocess.run([…],` puis
    la suite) : on lit la ligne et les deux suivantes.
    """
    lignes = texte.splitlines()
    return [
        i + 1
        for i, ligne in enumerate(lignes)
        if FERMETURE.search(ligne)
        and not ligne.lstrip().startswith("#")
        and "--delete-branch" not in " ".join(lignes[i : i + 3])
    ]


def _scripts() -> list[pathlib.Path]:
    sortie = subprocess.run(
        ["git", "ls-files", "-z", "--", *PORTEE],
        cwd=RACINE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [RACINE / f for f in sortie.split("\0") if f.endswith((".py", ".sh", ".yml", ".yaml"))]


def test_le_controle_sait_REFUSER():
    assert fermetures_sans_suppression("gh pr close 12 --comment x") == [1]
    assert fermetures_sans_suppression(
        "subprocess.run(['gh', 'pr', 'close', n,\n  '--comment', m])"
    ) == [1]
    assert fermetures_sans_suppression("gh pr close 12 --delete-branch") == []
    assert fermetures_sans_suppression("run(['gh', 'pr', 'close', n,\n '--delete-branch'])") == []
    assert fermetures_sans_suppression("# gh pr close : à la main") == []


def test_toute_fermeture_de_pr_emporte_sa_branche():
    scripts = _scripts()
    assert len(scripts) > 50, f"{len(scripts)} script(s) lus — la portée a bougé"
    fautes = [
        f"{p.relative_to(RACINE)}:{n}"
        for p in scripts
        for n in fermetures_sans_suppression(p.read_text(encoding="utf-8", errors="replace"))
    ]
    assert not fautes, (
        "`gh pr close` sans `--delete-branch` — la branche distante survivrait à sa PR "
        f"(#2978) : {fautes}"
    )
    vus = [p for p in scripts if FERMETURE.search(p.read_text(encoding="utf-8", errors="replace"))]
    assert vus, "aucune fermeture de PR lue : le témoin (reprendre-dependabot.py) a disparu"
