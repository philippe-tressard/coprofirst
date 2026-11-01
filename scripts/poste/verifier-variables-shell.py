#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Philippe Tressard
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Variables non assignées dans un script `set -u` — le défaut qui tue en production.

## Pourquoi ce contrôle existe

**Deux fois** un script d'infra est mort à l'exécution sur une variable jamais
définie, et **deux fois** la CI était verte :

| Date | Script | Variable | Ce que la CI voyait |
|---|---|---|---|
| 11/08/2026 | `check-reliability.sh` | `$R` sorti des quotes | `bash -n` OK, `--selftest` rendait la main avant |
| 06/09/2026 | `export-hors-site.sh` | `RPI1_IP` (n'a jamais existé) | idem — le rattrapage de #775 n'a jamais tourné |

Le second a été trouvé **en lançant le script**, pas par un contrôle. Même
classe, à un mois d'écart : `bash -n` valide la syntaxe, pas l'existence d'un
nom ; et un `--selftest` placé avant le code réel donne un vert qui ne prouve
rien (`standards/04` §2).

🔴 **ShellCheck ne couvre PAS ce cas** — mesuré le 06/09/2026 sur le défaut
réel : SC2154 (« referenced but not assigned ») s'abstient délibérément pour les
noms **tout en majuscules**, présumés venir de l'environnement. Or c'est
exactement la convention de nommage de tous les scripts d'ici. Un contrôle
générique qui ne voit pas le défaut du jour n'est pas le garde-fou de ce défaut.

## Ce qu'il vérifie

Pour chaque `*.sh` versionné qui active `set -u` : toute variable en MAJUSCULES
référencée **sans repli** (`$VAR`, `${VAR}`, `${VAR#…}`) doit être assignée —
dans le fichier, ou dans un module qu'il source. Une référence avec repli
(`${VAR:-}`, `${VAR:?msg}`, `${VAR:=x}`) est sûre sous `set -u` : jamais
signalée, et c'est la forme à employer pour ce qui vient vraiment de
l'environnement.

⚠️ Le `--selftest` exerce **`analyser_source()`, la fonction qui sert** — pas une
copie de sa logique. C'est la leçon du 11/08 appliquée au contrôle lui-même :
un gate qui n'emprunte pas le chemin réel valide un code mort.

Les faux positifs se déclarent dans `EXCEPTIONS`, avec leur motif — une
exception non écrite n'est pas une exception, c'est un oubli qui ressemble à une
décision (`CLAUDE.md`, règle du front n° 1).

Usage :  python scripts/poste/verifier-variables-shell.py [--selftest]
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_console import console_utf8  # noqa: E402

console_utf8()

RACINE = Path(__file__).resolve().parents[2]

# Variables fournies par bash lui-même ou par l'environnement d'exécution :
# les référencer nues est légitime, elles sont toujours définies.
INTEGREES = {
    "BASH", "BASHPID", "BASH_ARGV0", "BASH_COMMAND", "BASH_REMATCH",
    "BASH_SOURCE", "BASH_SUBSHELL", "BASH_VERSION", "EPOCHSECONDS",
    "EUID", "FUNCNAME", "GROUPS", "HOME", "HOSTNAME", "HOSTTYPE", "IFS",
    "LANG", "LINENO", "LOGNAME", "MACHTYPE", "OLDPWD", "OPTARG", "OPTIND",
    "OSTYPE", "PATH", "PIPESTATUS", "PPID", "PWD", "RANDOM", "REPLY",
    "SECONDS", "SHELL", "SHLVL", "TERM", "TMPDIR", "UID", "USER",
    "_",  # dernier argument de la commande précédente
}

# Exceptions déclarées : {(fichier, variable): motif}.
EXCEPTIONS: dict[tuple[str, str], str] = {}

RE_SET_U = re.compile(r"^\s*set\s+-[a-z]*u", re.M)
RE_ASSIGN = re.compile(
    r"(?:^|[;&|(]|\bthen\b|\bdo\b|\belse\b|\s)\s*([A-Za-z_][A-Za-z0-9_]*)\+?="
)
RE_DECLARE = re.compile(
    r"\b(?:export|declare|local|readonly|typeset)\s+(?:-[A-Za-z]+\s+)*"
    r"([A-Za-z_][A-Za-z0-9_]*)"
)
RE_FOR = re.compile(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b")
# ⚠️ Seuls ces drapeaux de `read` prennent un argument. Accepter `-[a-z] <mot>`
# pour tous faisait lire `read -r ECRIT EXTRAIT` comme « drapeau -r d'argument
# ECRIT » : la variable disparaissait, et le contrôle la signalait (06/09/2026).
RE_READ = re.compile(
    r"\bread\b((?:\s+-[adeinNpstu](?:\s+\S+)?|\s+-[rs]+)*)"
    r"((?:\s+[A-Za-z_][A-Za-z0-9_]*)+)"
)
# La ligne ENTIÈRE, pas le premier mot : `. "$(dirname "$0")/../lib/lib-$_mod.sh"`
# s'arrêtait à `"$(dirname` — un nom qui ne finit pas par `.sh`, donc un module
# jamais lu et un `$COLLECT` signalé à tort (06/09/2026).
RE_SOURCE = re.compile(r"^\s*(?:source|\.)\s+(.+)$", re.M)
RE_NOM_SH = re.compile(r"[\w.${}*-]+\.sh")
# Le nom est capturé ENTIER puis filtré : `$S_cronscripts` tronqué à `S_` par une
# classe `[A-Z0-9_]*` produisait un signalement sur une variable qui n'existe pas.
RE_REF = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)([^}]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)"
)

# Formes d'expansion qui fournissent une valeur de repli : sûres sous `set -u`.
REPLIS = (":-", ":?", ":=", ":+", "-", "?", "=", "+")


# Ce qui peut précéder un `#` pour qu'il ouvre un commentaire, et non un
# dépouillement `${VAR#…}` ni un `#` littéral au milieu d'un mot.
DEBUTS_COMMENTAIRE = " \t\n;&|("


def sans_bruit(source: str) -> str:
    """Retire ce qui ne s'exécute pas : commentaires, quotes simples, `\\$`.

    🔴 **Les commentaires se retirent AVANT les quotes, et c'est tout le sujet.**
    Ce corpus est commenté en français : « l'archive », « n'échoue », « qu'on »
    portent une apostrophe **non appariée**. Traitée comme une quote shell, elle
    avale le fichier jusqu'à la suivante — et le contrôle a signalé 23 variables
    parfaitement assignées à sa première exécution (06/09/2026). Un contrôle qui
    crie sur du code sain est désarmé dans la semaine.

    D'où l'automate : il faut connaître l'état (hors quotes / entre guillemets)
    pour savoir si un caractère ouvre un commentaire, une chaîne, ou rien.
    """
    out: list[str] = []
    i, n = 0, len(source)
    dans_guillemets = False
    while i < n:
        c = source[i]
        if c == "\\" and i + 1 < n:  # `\$` n'est pas une référence locale
            i += 2
            continue
        if dans_guillemets:
            if c == '"':
                dans_guillemets = False
            out.append(c)  # les `$VAR` entre guillemets sont bien des références
            i += 1
            continue
        if c == "#" and (not out or out[-1] in DEBUTS_COMMENTAIRE):
            j = source.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "'":  # quotes simples : littéral, souvent du shell distant
            j = source.find("'", i + 1)
            i = n if j < 0 else j + 1
            continue
        if c == '"':
            dans_guillemets = True
        out.append(c)
        i += 1
    return "".join(out)


def assignees(source: str) -> set[str]:
    """Tout ce que ce texte définit : affectation, déclaration, `for`, `read`."""
    noms: set[str] = set(RE_ASSIGN.findall(source))
    noms |= set(RE_DECLARE.findall(source))
    noms |= set(RE_FOR.findall(source))
    for _drapeaux, cibles in RE_READ.findall(source):
        noms |= set(cibles.split())
    return noms


def referencees(source: str) -> set[str]:
    """Références en MAJUSCULES sans repli — les seules dangereuses sous `set -u`.

    Le filtre « tout en majuscules » porte sur le nom ENTIER : `S_cronscripts`
    est un nom mixte, fabriqué par `eval` dans `check-reliability.sh`, et aucune
    analyse statique ne peut le voir assigné. Le signaler serait un faux positif
    permanent — donc un contrôle qu'on apprend à ignorer.
    """
    trouvees: set[str] = set()
    for accolade, suite, nue in RE_REF.findall(source):
        nom = nue or accolade
        if not nom or nom != nom.upper():
            continue
        if nue or not suite.startswith(REPLIS):
            trouvees.add(nom)
    return trouvees


def analyser_source(brut: str, rel: str = "", modules: list[str] | None = None) -> list[str]:
    """Le cœur du contrôle — c'est CETTE fonction que le `--selftest` exerce.

    `brut` est le texte du script, `modules` les textes des fichiers qu'il source.
    """
    if not RE_SET_U.search(brut):
        return []  # sans `set -u`, une variable absente vaut la chaîne vide
    source = sans_bruit(brut)
    connues = assignees(source) | INTEGREES
    for texte in modules or []:
        connues |= assignees(sans_bruit(texte))
    return sorted(
        v for v in referencees(source) - connues if (rel, v) not in EXCEPTIONS
    )


_TROUVES: dict[tuple[Path, str], list[Path]] = {}


def _trouver(racine: Path, motif: str) -> list[Path]:
    """Les fichiers du dépôt qui portent ce nom — un parcours par motif, pas par appel."""
    cle = (racine, motif)
    if cle not in _TROUVES:
        _TROUVES[cle] = [p for p in racine.rglob(motif) if ".git" not in p.parts]
    return _TROUVES[cle]


def modules_sources(
    brut: str, racine: Path = RACINE, vus: set[Path] | None = None
) -> list[Path]:
    """Modules sourcés qu'on sait résoudre dans le dépôt — et ceux qu'ILS sourcent.

    🔴 Transitif depuis #2367 (01/11/2026) : `durcir-noeud.sh` source
    `lib-durcissement.sh`, qui source `lib-durcissement-sortant.sh` ; ses
    constantes étaient lues « jamais assignées », alors que le shell les a bien
    en portée. `vus` coupe les cycles et les doublons.

    ⚠️ Un nom PARTIELLEMENT variable est résolu par joker : `check-reliability.sh`
    charge ses huit modules par `. "…/lib-$_mod.sh"` dans une boucle, et le nom
    exact n'existe qu'à l'exécution. Remplacer la variable par `*` décrit
    fidèlement ce que le shell fait — c'est plus large que la réalité d'un tour
    de boucle, mais l'union des tours est bien ce que le script finit par avoir
    en portée. Un nom ENTIÈREMENT variable, lui, n'est pas résolu du tout.
    """
    vus = set() if vus is None else vus
    resolus: list[Path] = []
    for ligne in RE_SOURCE.findall(brut):
        noms = RE_NOM_SH.findall(ligne.replace('"', ""))
        if not noms:
            continue
        motif = re.sub(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?", "*", Path(noms[-1]).name)
        if motif.startswith("*"):
            continue  # rien d'ancré : on ne devine pas
        for p in _trouver(racine, motif):
            if p in vus:
                continue
            vus.add(p)
            resolus.append(p)
            texte = p.read_text(encoding="utf-8", errors="replace")
            resolus += modules_sources(texte, racine, vus)
    return resolus


def analyser(chemin: Path) -> list[str]:
    brut = chemin.read_text(encoding="utf-8", errors="replace")
    modules = [
        m.read_text(encoding="utf-8", errors="replace") for m in modules_sources(brut)
    ]
    return analyser_source(brut, chemin.relative_to(RACINE).as_posix(), modules)


CAS = [
    ("variable inventée", 'set -u\nAUTRE="$RPI1_IP"\n', [], ["RPI1_IP"]),
    ("assignée avant", 'set -u\nRPI1_IP=x\nAUTRE="$RPI1_IP"\n', [], []),
    ("assignée par un module sourcé", 'set -u\nsource lib.sh\necho "$TABLE"\n',
     ["TABLE=x"], []),
    ("module sourcé qui ne la définit pas", 'set -u\nsource lib.sh\necho "$TABLE"\n',
     ["AUTRE=x"], ["TABLE"]),
    ("repli :- est sûr", 'set -u\necho "${EXPORT_DEST:-/c/Backup}"\n', [], []),
    ("repli :? est sûr", 'set -u\necho "${CLE:?manquante}"\n', [], []),
    ("dépouillement ${VAR#…} n'est PAS un repli", 'set -u\necho "${LIGNE#CLE=}"\n',
     [], ["LIGNE"]),
    ("intégrée bash", 'set -u\necho "$HOME $BASH_SOURCE"\n', [], []),
    ("minuscule ignorée", 'set -u\necho "$inconnue"\n', [], []),
    ("quotes simples = shell distant", "set -u\nssh h 'echo $DISTANTE'\n", [], []),
    ("dollar échappé", 'set -u\nssh h "echo \\$DISTANTE"\n', [], []),
    ("commentaire", "set -u\n# $JAMAIS_DEFINIE\n", [], []),
    ("sans set -u → rien", 'AUTRE="$RPI1_IP"\n', [], []),
    ("set -uo pipefail", 'set -uo pipefail\necho "$ABSENTE"\n', [], ["ABSENTE"]),
    ("for", 'set -u\nfor NOM in a b; do echo "$NOM"; done\n', [], []),
    ("read -r", 'set -u\nwhile IFS=: read -r h ROLE i; do echo "$ROLE"; done\n', [], []),
    ("export", 'set -u\nexport CIBLE=x\necho "$CIBLE"\n', [], []),
    ("substitution de commande", 'set -u\nSRC=$(date)\necho "$SRC"\n', [], []),
    # 🔴 Le défaut du contrôle lui-même, trouvé sur le corpus réel le 06/09/2026 :
    # ces trois cas manquaient, et leur absence produisait 23 faux positifs.
    ("apostrophe française dans un commentaire",
     "set -u\n# on lit l'archive du jour\nCIBLE=x\necho \"$CIBLE\"\n", [], []),
    ("guillemets : la référence compte quand même",
     'set -u\necho "$ABSENTE"\n', [], ["ABSENTE"]),
    ("# au milieu d'un mot n'ouvre pas de commentaire",
     'set -u\nV=a#b\necho "$V"\n', [], []),
    ("read -r VAR : -r ne prend PAS d'argument",
     'set -u\nread -r ECRIT EXTRAIT <<< "a b"\necho "$ECRIT $EXTRAIT"\n', [], []),
    ("read -d '' VAR : -d, si", 'set -u\nread -d "" VAL <<< "x"\necho "$VAL"\n', [], []),
    ("nom mixte fabriqué par eval : hors périmètre",
     'set -u\necho "$S_cronscripts"\n', [], []),
    ("cas zéro : fichier vide", "", [], []),
]


def selftest() -> int:
    echecs = 0
    for nom, contenu, modules, attendu in CAS:
        obtenu = analyser_source(contenu, "", modules)
        ok = obtenu == attendu
        echecs += 0 if ok else 1
        print(f"{'PASS' if ok else 'ÉCHEC'}  {nom}  → {obtenu}")

    # Le contrôle doit aussi savoir LIRE un fichier et suivre son `source` :
    # `analyser_source` seule ne prouve pas que `analyser` compose bien.
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "cas.sh").write_text('set -u\necho "$SANS_DEFINITION"\n', encoding="utf-8")
        chemin = Path(tmp) / "cas.sh"
        brut = chemin.read_text(encoding="utf-8")
        obtenu = analyser_source(brut, "cas.sh", [])
        ok = obtenu == ["SANS_DEFINITION"]
        echecs += 0 if ok else 1
        print(f"{'PASS' if ok else 'ÉCHEC'}  lecture d'un vrai fichier  → {obtenu}")

        #  Un module qui en source un autre (#2367) : la constante du second est en
        #  portée du script ; un module qui source un module qui le source ne boucle pas.
        racine = Path(tmp)
        (racine / "lib-a.sh").write_text('. "$(dirname "$0")/lib-b.sh"\n', encoding="utf-8")
        (racine / "lib-b.sh").write_text(
            'LOINTAINE=x\n. "$(dirname "$0")/lib-a.sh"\n', encoding="utf-8"
        )
        brut = 'set -u\n. "$(dirname "$0")/lib-a.sh"\necho "$LOINTAINE"\n'
        modules = [m.read_text(encoding="utf-8") for m in modules_sources(brut, racine)]
        obtenu = analyser_source(brut, "cas.sh", modules)
        ok = obtenu == [] and len(modules) == 2
        echecs += 0 if ok else 1
        print(f"{'PASS' if ok else 'ÉCHEC'}  module sourcé par un module  → {obtenu}")

    print("== TOUS OK ==" if not echecs else f"== {echecs} ÉCHEC(S) ==")
    return 0 if not echecs else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    fichiers = subprocess.run(
        ["git", "ls-files", "*.sh"],
        cwd=RACINE, capture_output=True, text=True, check=True,
    ).stdout.split()
    if not fichiers:
        # Cas zéro : une liste vide n'est pas un vert (`standards/04` §2).
        print("INCONNU : aucun script trouvé — `git ls-files *.sh` n'a rien rendu.")
        return 2
    total = 0
    for rel in fichiers:
        for var in analyser(RACINE / rel):
            print(
                f"{rel}: ${var} référencée sans repli et jamais assignée "
                f"— sous `set -u`, le script meurt là."
            )
            total += 1
    if total:
        print(f"\n❌ {total} variable(s) non assignée(s) sur {len(fichiers)} script(s).")
        print("   Corriger, ou écrire `${VAR:-défaut}` si elle vient de l'environnement.")
        return 1
    print(f"✅ {len(fichiers)} scripts : aucune variable non assignée sous `set -u`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
