"""Supprimer un `Document` : un geste, une écriture (#1178, 24/09/2026).

`#lib/gestes-document.supprimerDocument` porte la confirmation, l'appel et le
message. Il était écrit TROIS fois — Résidence (qui l'avait déjà factorisé pour
ses trois sections), Prestataires, et la carte d'une actualité en avait besoin
à son tour. Trois copies de ce geste avaient déjà divergé sur ce qu'elles
annonçaient (« Plan supprimé » contre « Supprimé »).

Le contrôle suit les ALIAS : le client s'importe `documents as docsApi`,
`documents as documentsApi`… — un motif sur un seul nom ne verrait rien.
"""

from __future__ import annotations

import pathlib
import re

_FRONT = pathlib.Path(__file__).resolve().parents[2] / "front" / "src"
_SOURCE = _FRONT / "lib" / "gestes-document.ts"
_ALIAS = re.compile(r"\bdocuments\s+as\s+(\w+)")


def _appels_de_suppression() -> dict[str, int]:
    trouves: dict[str, int] = {}
    for f in list(_FRONT.rglob("*.svelte")) + list(_FRONT.rglob("*.ts")):
        texte = f.read_text(encoding="utf-8")
        for alias in set(_ALIAS.findall(texte)):
            n = len(re.findall(rf"\b{alias}\.delete\(", texte))
            if n:
                trouves[str(f.relative_to(_FRONT))] = n
    return trouves


def test_un_seul_lieu_supprime_un_document():
    appels = _appels_de_suppression()
    #  Cas zéro : sans la source, le contrôle ne mesurerait rien.
    assert str(_SOURCE.relative_to(_FRONT)) in appels, (
        "la source unique n'appelle plus la suppression"
    )
    ailleurs = {f: n for f, n in appels.items() if pathlib.Path(_FRONT / f) != _SOURCE}
    assert not ailleurs, (
        f"suppression de document recopiée — appeler `supprimerDocument` : {ailleurs}"
    )
