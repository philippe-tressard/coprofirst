"""Chaque module de l'API s'importe SEUL, dans un interpréteur neuf (#2241).

## Pourquoi

`python scripts/ci/carte_reglages.py --ecrire` — la commande que `CLAUDE.md`
donne pour régénérer `docs/carte-reglages.md` — levait le 25/10/2026 :

    ImportError: cannot import name 'nom_lisible' from partially initialized
    module 'app.utils.fichiers' (most likely due to a circular import)

`utils/fichiers` importait en tête `app.models.fichiers_recus` ; importer un
module du paquet `models` exécute d'abord `models/__init__`, qui charge toutes
les tables, dont `evenement` → `saisi_pour` → `corrections_texte` →
`fichiers.nom_lisible` — à moitié chargé.

🔴 La suite restait verte : pytest a déjà tout importé quand un test commence,
et un cycle ne casse que pour **qui entre par le mauvais module**. C'est donc
l'ordre d'arrivée qui décide, et l'interpréteur des tests ne peut pas le juger :
il faut un processus neuf par module mis en cause.

## Comment

1. Le graphe des imports **de niveau module** de `app/` (ceux d'une fonction
   s'exécutent à l'appel, et ne forment pas de cycle au chargement ; ceux sous
   `TYPE_CHECKING` ne s'exécutent jamais). Importer `a.b.c` exécute aussi les
   paquets `a.b` et `a` : l'arête va vers eux — sauf depuis l'un de leurs
   propres sous-modules, que le paquet a déjà commencé à charger.
2. Ses composantes fortement connexes : les modules qui peuvent se rencontrer à
   moitié chargés.
3. Chacun d'eux s'importe en premier dans un interpréteur neuf. Un cycle dont
   chaque entrée réussit — `export_copropriete` ⇄ `import_copropriete` le
   25/10/2026 — passe : c'est le comportement qui juge, pas la forme.

Mesuré avant le correctif : cinq modules tombaient (`fichiers`, `saisi_pour`,
`corrections_texte`, `llm_connexion`, `llm_modeles`).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

RACINE_API = Path(__file__).resolve().parents[1]
RACINE_DEPOT = RACINE_API.parent


def _modules(racine: Path) -> dict[str, Path]:
    modules = {}
    for chemin in racine.rglob("*.py"):
        parties = list(chemin.relative_to(racine.parent).with_suffix("").parts)
        if parties[-1] == "__init__":
            parties = parties[:-1]
        modules[".".join(parties)] = chemin
    return modules


def _imports_au_chargement(arbre: ast.Module):
    """Les imports qui s'exécutent quand le module se charge."""
    for noeud in arbre.body:
        if isinstance(noeud, (ast.Import, ast.ImportFrom)):
            yield noeud
        elif isinstance(noeud, ast.If) and "TYPE_CHECKING" in ast.unparse(noeud.test):
            continue
        elif isinstance(noeud, (ast.If, ast.Try)):
            yield from (n for n in ast.walk(noeud) if isinstance(n, (ast.Import, ast.ImportFrom)))


def _graphe(modules: dict[str, Path]) -> dict[str, set[str]]:
    graphe: dict[str, set[str]] = {m: set() for m in modules}
    for module, chemin in modules.items():
        for noeud in _imports_au_chargement(ast.parse(chemin.read_text(encoding="utf-8"))):
            if isinstance(noeud, ast.Import):
                cibles = [a.name for a in noeud.names]
            elif noeud.module and noeud.level == 0:
                cibles = [noeud.module] + [f"{noeud.module}.{a.name}" for a in noeud.names]
            else:
                cibles = []
            for cible in cibles:
                if cible not in modules:
                    continue
                morceaux = cible.split(".")
                for i in range(1, len(morceaux) + 1):
                    paquet = ".".join(morceaux[:i])
                    if (
                        paquet in modules
                        and paquet != module
                        and not module.startswith(paquet + ".")
                    ):
                        graphe[module].add(paquet)
    return graphe


def _cycles(graphe: dict[str, set[str]]) -> list[list[str]]:
    """Composantes fortement connexes de plus d'un module (Tarjan, itératif)."""
    index: dict[str, int] = {}
    bas: dict[str, int] = {}
    pile: list[str] = []
    sur_pile: set[str] = set()
    composantes: list[list[str]] = []
    for depart in graphe:
        if depart in index:
            continue
        travail = [(depart, iter(sorted(graphe[depart])))]
        index[depart] = bas[depart] = len(index)
        pile.append(depart)
        sur_pile.add(depart)
        while travail:
            v, voisins = travail[-1]
            w = next(voisins, None)
            if w is not None:
                if w not in index:
                    index[w] = bas[w] = len(index)
                    pile.append(w)
                    sur_pile.add(w)
                    travail.append((w, iter(sorted(graphe[w]))))
                elif w in sur_pile:
                    bas[v] = min(bas[v], index[w])
                continue
            travail.pop()
            if travail:
                bas[travail[-1][0]] = min(bas[travail[-1][0]], bas[v])
            if bas[v] == index[v]:
                composante = []
                while True:
                    w = pile.pop()
                    sur_pile.discard(w)
                    composante.append(w)
                    if w == v:
                        break
                if len(composante) > 1:
                    composantes.append(sorted(composante))
    return composantes


def _echec_import_seul(module: str) -> str | None:
    sortie = subprocess.run(
        [sys.executable, "-W", "ignore", "-c", f"import {module}"],
        cwd=RACINE_API,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return None if sortie.returncode == 0 else sortie.stderr.strip().splitlines()[-1]


def test_le_detecteur_voit_un_cycle_et_ignore_le_paquet_parent(tmp_path):
    """Témoin : un cycle posé exprès est trouvé ; un sous-module qui importe son
    paquet ne l'est pas ; un import de fonction ou sous TYPE_CHECKING non plus."""
    paquet = tmp_path / "pq"
    paquet.mkdir()
    (paquet / "__init__.py").write_text("from pq import a\n", encoding="utf-8")
    (paquet / "a.py").write_text("import pq\nfrom pq.b import y\nx = 1\n", encoding="utf-8")
    (paquet / "b.py").write_text("from pq.a import x\ny = 2\n", encoding="utf-8")
    (paquet / "c.py").write_text(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n    from pq.d import z\n"
        "def f():\n    from pq.d import z\n",
        encoding="utf-8",
    )
    (paquet / "d.py").write_text("from pq.c import f\nz = 3\n", encoding="utf-8")
    assert _cycles(_graphe(_modules(paquet))) == [["pq.a", "pq.b"]]


def test_chaque_module_d_un_cycle_s_importe_seul():
    modules = _modules(RACINE_API / "app")
    #  Cas zéro : une racine fausse rendrait un graphe vide, donc aucun cycle.
    assert len(modules) > 400, f"seulement {len(modules)} module(s) relevé(s) sous app/"
    en_cause = sorted({m for c in _cycles(_graphe(modules)) for m in c})
    echecs = {m: e for m in en_cause if (e := _echec_import_seul(m))}
    assert not echecs, (
        "Ces modules ne s'importent pas en premier — un cycle d'import les rencontre "
        "à moitié chargés. Couper l'arête par un import dans la fonction qui s'en sert "
        "(le motif de `saisi_pour.py`) :\n" + "\n".join(f"  {m} : {e}" for m, e in echecs.items())
    )


def test_la_carte_des_reglages_se_verifie_dans_un_processus_neuf():
    """La commande que `CLAUDE.md` donne, lancée comme on la lance (#2241)."""
    sortie = subprocess.run(
        [sys.executable, "-W", "ignore", "scripts/ci/carte_reglages.py"],
        cwd=RACINE_DEPOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert sortie.returncode == 0, sortie.stderr[-800:] or sortie.stdout[-800:]
