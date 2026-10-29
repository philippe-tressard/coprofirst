"""Une seule majeure de Node, paire, partout où le dépôt en déclare une.

## Pourquoi (#1413, 29/10/2026)

Node est déclaré en cinq endroits : les deux `FROM` de `front/Dockerfile`, celui
de `whatsapp-bridge/Dockerfile`, et chaque `setup-node` des workflows. Le front et
le bridge montent **ensemble** — une seule image de base à rafraîchir sur le
daemon (commentaire du Dockerfile du bridge) —, et la CI avec eux : un front
construit en 26 et testé en 22 ne prouve rien de ce qui part en production.

Cette règle n'était écrite que dans un commentaire de `.github/dependabot.yml` et
dans le ticket. Rien ne refusait qu'une PR Dependabot n'en monte qu'un : c'était
la PR #1290, qui proposait Node 25 pour le seul bridge.

**Paire** : une majeure impaire n'est jamais LTS, et sa fin de vie arrive en
quelques mois.

Le badge du README suit la CI : `test_documentation.py`.
"""

from __future__ import annotations

import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]

DOCKERFILES = ("front/Dockerfile", "whatsapp-bridge/Dockerfile")
_FROM = re.compile(r"^\s*FROM\s+node:(\d+)", re.M)
_SETUP_NODE = re.compile(r"""node-version:\s*['"]?(\d+)""")


def majeures_declarees(racine: pathlib.Path) -> dict[str, list[int]]:
    """Chaque fichier qui déclare Node → les majeures qu'il déclare."""
    trouvees: dict[str, list[int]] = {}
    for chemin in DOCKERFILES:
        source = (racine / chemin).read_text(encoding="utf-8")
        trouvees[chemin] = [int(m) for m in _FROM.findall(source)]
    for workflow in sorted((racine / ".github" / "workflows").glob("*.yml")):
        majeures = [int(m) for m in _SETUP_NODE.findall(workflow.read_text(encoding="utf-8"))]
        if majeures:
            trouvees[workflow.relative_to(racine).as_posix()] = majeures
    return trouvees


def ecarts(trouvees: dict[str, list[int]]) -> list[str]:
    """Ce qui viole la règle, en phrases ; vide si elle tient."""
    toutes = {m for majeures in trouvees.values() for m in majeures}
    motifs = []
    if len(toutes) > 1:
        detail = ", ".join(f"{f} → {sorted(set(m))}" for f, m in trouvees.items())
        motifs.append(f"plusieurs majeures de Node : {detail}")
    motifs += [f"Node {m} est impair, donc jamais LTS" for m in sorted(toutes) if m % 2]
    return motifs


def test_le_controle_lit_chaque_declaration():
    """Cas zéro (socle 04 §2) : un motif qui ne lit plus rien rendrait le test vert."""
    trouvees = majeures_declarees(_RACINE)
    for chemin in DOCKERFILES:
        assert trouvees[chemin], f"aucun `FROM node:N` lu dans {chemin}"
    assert len(trouvees["front/Dockerfile"]) == 2, "le front a deux étapes : builder et runner"
    assert "ci.yml" in " ".join(trouvees), "aucun `node-version` lu dans ci.yml"


def test_une_seule_majeure_paire():
    assert ecarts(majeures_declarees(_RACINE)) == []


def test_l_ecart_se_voit():
    """Le contrôle refuse ce qu'il doit refuser — la PR #1290, puis une impaire."""
    pr_1290 = {"front/Dockerfile": [22, 22], "whatsapp-bridge/Dockerfile": [25]}
    assert any("plusieurs majeures" in m for m in ecarts(pr_1290))
    assert any("impair" in m for m in ecarts(pr_1290))
    assert ecarts({"front/Dockerfile": [26, 26], ".github/workflows/ci.yml": [26]}) == []
