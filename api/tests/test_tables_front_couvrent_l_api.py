"""Deux tables du front indexées par un vocabulaire de l'API — confrontées à lui.

## Pourquoi (24/11/2026, #2947)

| Table du front | Liste de l'API | Ce qui arrivait sur une clé de plus |
|---|---|---|
| `COLONNE_PORTEUR` (`#lib/api/documents.ts`) | `PORTEURS` (`utils/annexes.py`) | une annexe rattachée par une colonne que l'autre côté ne lit pas |
| `TEINTE_TRANSCRIPTION` (`#lib/reglement.ts`) | `STATUTS` (`question_reglement/transcription.py`) | une pastille sans teinte : `TEINTE_TRANSCRIPTION[t.statut]` est lue sans repli |

Les deux concordaient. Le commentaire de `COLONNE_PORTEUR` disait « les clés sont
celles de `PORTEURS` », et aucun test ne lisait les deux : une promesse écrite n'est
pas un contrôle. Comparées dans les deux sens (`standards/11` §13).
"""

from __future__ import annotations

from app.utils.annexes import PORTEURS
from app.utils.question_reglement.transcription import STATUTS
from tests.aides_tables_front import table_plate


def test_les_porteurs_d_annexes_et_leur_colonne_sont_les_memes():
    front = table_plate("api/documents.ts", "COLONNE_PORTEUR")
    assert front == PORTEURS, (
        f"Le front rattache {front}, l'API {PORTEURS} : une annexe se rattacherait par une "
        "colonne que l'autre côté ne lit pas."
    )


def test_chaque_statut_de_transcription_a_sa_teinte():
    front = table_plate("reglement.ts", "TEINTE_TRANSCRIPTION")
    assert set(front) == set(STATUTS), (
        f"Statuts de l'API sans teinte : {sorted(set(STATUTS) - set(front))} ; teintes "
        f"sans statut : {sorted(set(front) - set(STATUTS))}."
    )
