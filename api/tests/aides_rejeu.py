"""Ce que le rejeu local de la CI doit savoir de pytest : les tests SAUTÉS (#1734).

`scripts/poste/rejouer-ci.sh` rendait « Run pytest — OK » sur un lot qui cassait
deux tests de rendu PDF : ils portent `@besoin_weasyprint`, et WeasyPrint ne
s'installe pas sur le poste. La CI GitHub, elle, les joue — et les a vus échouer.
Un saut n'est pas une faute ; son silence, si : le rejeu disait « mesuré » de ce
qu'il n'avait pas mesuré.

Quand le rejeu pose `REJEU_SAUTS` (un chemin), le crochet de `conftest.py` y
écrit une ligne par test sauté — `nœud<TAB>raison` — et le rejeu les résume sur
la ligne de l'étape (`lib-ci-replay.ci_resumer_sauts`). Hors rejeu, la variable
est absente et rien n'est écrit : la CI n'en sait rien.
"""

from __future__ import annotations

import os

#: La variable que pose `rejouer-ci.sh` — le fichier où consigner les sauts.
VARIABLE = "REJEU_SAUTS"


def ligne_de_saut(report) -> str | None:
    """`nœud<TAB>raison` pour un test sauté, `None` sinon. PURE.

    pytest range la raison dans `longrepr`, un triplet (fichier, ligne,
    « Skipped: raison ») pour un saut ; on n'en garde que la raison.
    """
    if not getattr(report, "skipped", False):
        return None
    #  Sous `pytest -n` (#2223), le maître RELAIE le rapport de chaque worker, et
    #  le crochet le voit deux fois : chez le worker, puis chez le maître — qui y
    #  a posé `node`, le worker d'origine. Seul l'original se consigne : sinon
    #  chaque saut comptait double (9 sauts → 17 lignes, mesuré le 24/10/2026).
    if getattr(report, "node", None) is not None:
        return None
    longrepr = getattr(report, "longrepr", None)
    raison = longrepr[2] if isinstance(longrepr, tuple) and len(longrepr) == 3 else str(longrepr)
    raison = raison.removeprefix("Skipped: ").replace("\t", " ").replace("\n", " ").strip()
    return f"{report.nodeid}\t{raison or 'sans raison'}"


def consigner_saut(report) -> None:
    """Écrit la ligne du saut dans le fichier du rejeu, s'il en a désigné un."""
    chemin = os.environ.get(VARIABLE)
    ligne = ligne_de_saut(report)
    if chemin and ligne:
        with open(chemin, "a", encoding="utf-8") as f:
            f.write(ligne + "\n")
