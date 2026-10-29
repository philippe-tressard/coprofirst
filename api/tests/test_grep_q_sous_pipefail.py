"""Aucune affectation `x=$(… | grep …)` ne tue un script sous `set -e` et `pipefail` (#1820).

Un `grep` qui FILTRE (ou compte) et ne trouve rien sort en 1. Au bout d'un tube
affecté à une variable (`x=$(… | grep …)`), sous `set -e` et `pipefail`,
l'affectation échoue et le script meurt sans un mot — même quand la valeur
obtenue était juste. Le rappel de retard de `replica` (retiré depuis, #2319) est
ainsi tombé deux nuits de suite, les 19 et 20/10/2026, dès que `replica` a porté la
dernière version (la liste filtrée devenait vide). Ce qui passe : `|| true` (ou
tout `||`) derrière le `grep`, ou une affectation par `local`/`export`/`readonly`/
`declare`, qui masque le code.

Le défaut jumeau — `grep -q` au bout d'un tube, qui donne 141 au producteur — a son
contrôle à part, sur tout producteur : `scripts/ci/pipe_grep_quiet.py` (#2298).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

#: `NOM=$(` — sauf derrière un mot-clé qui rend son propre code (0), pas celui de `$(…)`.
_AFFECTATION = re.compile(
    r"(?:^|[;&|\s])(?<!local )(?<!export )(?<!readonly )(?<!declare )[A-Za-z_]\w*=\$\("
)
_GREP = re.compile(r"\|\s*grep\b")


def fautes_grep_vide(texte: str) -> list[str]:
    """Les lignes où `x=$(… | grep …)` tue le script quand le `grep` ne trouve rien."""
    trouvees = []
    for n, ligne in enumerate(texte.splitlines(), 1):
        if ligne.lstrip().startswith("#"):
            continue
        for m in _AFFECTATION.finditer(ligne):
            reste = ligne[m.end() :]
            g = _GREP.search(reste)
            if g and "||" not in reste[g.end() :]:
                trouvees.append(f"{n}: {ligne.strip()}")
                break
    return trouvees


def _scripts_sous_pipefail(avec_set_e: bool = False) -> list[Path]:
    noms = subprocess.run(
        ["git", "ls-files", "--", "*.sh"], cwd=RACINE, capture_output=True, text=True, check=True
    ).stdout.split()
    retenus = []
    for nom in noms:
        texte = (RACINE / nom).read_text(encoding="utf-8", errors="replace")
        if not re.search(r"^\s*set\s+-[a-z]*o\s+pipefail|^\s*set\s+-o\s+pipefail", texte, re.M):
            continue
        if avec_set_e and not re.search(r"^\s*set\s+-[a-z]*e", texte, re.M):
            continue
        retenus.append(RACINE / nom)
    return retenus


def test_le_controle_reconnait_le_grep_vide():
    """Témoin : l'écriture qui a fait tomber le rappel de replica est vue."""
    assert fautes_grep_vide(
        """retard=$(git tag -l 'v*' --contains "$r" | grep -vxF "v$v" | mineures "$v")"""
    )
    assert fautes_grep_vide("""    n=$(tar -tzf "$archive" | grep -cv '/$')""")
    #  …et pas ce qui est sûr.
    assert not fautes_grep_vide("""n=$(tar -tzf "$a" | grep -cv '/$' || true)""")
    assert not fautes_grep_vide(
        """v=$(ls x | grep -v b | grep . >/dev/null && echo oui || echo non)"""
    )
    assert not fautes_grep_vide("""    local n=$(printf '%s' "$x" | grep -c .)""")
    assert not fautes_grep_vide("""retard=$(retard_de_replica "$r" "$v")""")
    assert not fautes_grep_vide("""# x=$(cat f | grep motif) — l'exemple d'un commentaire""")


def test_aucune_affectation_ne_meurt_d_un_grep_vide():
    scripts = _scripts_sous_pipefail(avec_set_e=True)
    #  Cas zéro : une lecture qui ne trouverait aucun script rendrait un faux vert.
    assert len(scripts) >= 10, f"seulement {len(scripts)} scripts sous set -e et pipefail lus"
    erreurs = {
        str(s.relative_to(RACINE)): f
        for s in scripts
        if (f := fautes_grep_vide(s.read_text(encoding="utf-8", errors="replace")))
    }
    assert not erreurs, (
        "`x=$(… | grep …)` sans `|| true`, sous set -e et pipefail : un grep qui ne "
        f"trouve rien sort en 1 et tue le script sans un mot (standards/10 §5.2) : {erreurs}"
    )
