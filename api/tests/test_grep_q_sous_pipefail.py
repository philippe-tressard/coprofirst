"""Aucun `grep -q` au bout d'un tube qui écrit en flux, dans un script sous `pipefail` (#1820).

`grep -q` sort au premier accord et ferme le tube ; la commande d'amont (`tar`,
`find`, `cat`…), qui écrit encore, meurt en SIGPIPE — et `set -o pipefail` fait
échouer le tube entier. Le test rend donc FAUX précisément parce qu'il a trouvé.

Deux fois dans ce dépôt, chaque fois sur la vérification d'une sauvegarde :
l'export hors site le 04/08/2026 (une archive saine écartée), puis la mise à jour
nocturne d'une réplique le 10/10/2026 (une sauvegarde saine jugée invalide, la
mise à jour refusée). La règle était écrite dans le socle (`standards/10` §5.2)
depuis la première fois : seul un contrôle tient.

Ce qui passe : lire le listing une fois, hors du tube (`liste=$(tar -tzf …)`),
puis `listing_contient` ; ou un `grep` qui lit TOUT (`grep … >/dev/null`).

Limite assumée : un tube coupé par `\\` sur plusieurs lignes n'est pas lu. Le
défaut, les deux fois, tenait sur une ligne.

Second défaut de la même famille : un `grep` qui FILTRE (ou compte) et ne
trouve rien sort en 1. Au bout d'un tube affecté à une variable
(`x=$(… | grep …)`), sous `set -e` et `pipefail`, l'affectation échoue et le
script meurt sans un mot — même quand la valeur obtenue était juste. Le rappel
de retard de `replica` est ainsi tombé deux nuits de suite, les 19 et
20/10/2026, dès que `replica` a porté la dernière version (la liste filtrée
devenait vide). Ce qui passe : `|| true` (ou tout `||`) derrière le `grep`, ou
une affectation par `local`/`export`/`readonly`/`declare`, qui masque le code.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

#: Les commandes dont la sortie peut dépasser ce que le tube absorbe.
PRODUCTEURS_EN_FLUX = {
    "tar",
    "find",
    "cat",
    "zcat",
    "ls",
    "docker",
    "curl",
    "journalctl",
    "git",
    "ssh",
    "psql",
    "awk",
    "sed",
    "sort",
    "gzip",
    "unzip",
}

_GREP_Q = re.compile(r"\|\s*grep\s+(?:-[A-Za-z]*q[A-Za-z]*\b|--quiet\b)")
#: Ce qui ouvre une commande avant la tête du tube.
_DEBUT = re.compile(r"(?:\$\(|\bif\s+|!\s+|&&|\|\||;|\{\s|\bthen\s+|\bwhile\s+|\buntil\s+|\bdo\s+)")


def _tete_du_tube(avant: str) -> str:
    """Le premier mot de la commande qui alimente le tube."""
    debut = 0
    for m in _DEBUT.finditer(avant):
        debut = m.end()
    mots = re.findall(r"[A-Za-z0-9_./-]+", avant[debut:])
    return Path(mots[0]).name if mots else ""


def fautes(texte: str) -> list[str]:
    """Les lignes où `grep -q` ferme un tube alimenté par un producteur en flux."""
    trouvees = []
    for n, ligne in enumerate(texte.splitlines(), 1):
        if ligne.lstrip().startswith("#"):
            continue
        for m in _GREP_Q.finditer(ligne):
            avant = ligne[: m.start()]
            if "<<<" in avant:
                continue
            tete = _tete_du_tube(avant.split("|")[0] if "|" in avant else avant)
            if tete in PRODUCTEURS_EN_FLUX:
                trouvees.append(f"{n}: {ligne.strip()}")
    return trouvees


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


def test_le_controle_reconnait_le_defaut():
    """Témoin : les deux écritures fautives de l'histoire du dépôt sont vues."""
    assert fautes("tar -tzf \"$f\" | grep -qx './base-export.tar.gz' && echo oui")
    assert fautes("if tar -tzf x | grep -q base-export.tar.gz; then :; fi")
    assert fautes('VOLUMES=$(ls "$S"/*.tar.gz | grep -v base | grep -q . && echo oui)')
    #  …et pas ce qui est sûr.
    assert not fautes("printf '%s' \"$v\" | grep -qE '^[0-9]+$'")
    assert not fautes('grep -qF -- "$motif" <<<"$out"')
    assert not fautes('liste=$(tar -tzf "$f")  # puis listing_contient')
    assert not fautes("# tar -tzf x | grep -q base-export  — l'exemple d'un commentaire")


def test_aucun_script_sous_pipefail_ne_coupe_un_flux():
    scripts = _scripts_sous_pipefail()
    #  Cas zéro : une lecture qui ne trouverait aucun script rendrait un faux vert.
    assert len(scripts) >= 20, f"seulement {len(scripts)} scripts sous pipefail lus"
    erreurs = {
        str(s.relative_to(RACINE)): f
        for s in scripts
        if (f := fautes(s.read_text(encoding="utf-8", errors="replace")))
    }
    assert not erreurs, (
        "`grep -q` ferme un tube qui écrit en flux, sous pipefail — le test rendra "
        f"faux quand il a TROUVÉ (standards/10 §5.2) : {erreurs}"
    )


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
