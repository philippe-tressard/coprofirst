"""Une requête `text()` dont les dates se comparent comme la base les stocke (#1298).

`text()` ne connaît pas le type des colonnes : un paramètre lié y part tel quel.
Un seuil passé en `datetime.isoformat()` part donc en TEXTE, comparé à un
horodatage — ce que le serveur refuse, ou qu'il interprète à sa façon. Le jour du
seuil, une purge avait ainsi effacé des jetons de session encore valides.

Ici, un `datetime` est lié avec le type `DateTime` : SQLAlchemy l'envoie comme
l'horodatage qu'il écrit en base. Les dates passées doivent être en
UTC NAÏF (`horloge.maintenant()`), la forme de toutes les dates stockées.

🔒 `tests/test_purge_dates_liees.py` refuse un `.isoformat()` passé comme
valeur à une requête, et vérifie qu'un jeton encore valide survit à la purge.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, bindparam, text
from sqlalchemy.sql.elements import TextClause


def requete_liee(sql: str, **params) -> TextClause:
    """`text(sql)` avec ses paramètres liés — les `datetime` au type `DateTime`."""
    return text(sql).bindparams(
        *(
            bindparam(nom, valeur, type_=DateTime())
            if isinstance(valeur, datetime)
            else bindparam(nom, valeur)
            for nom, valeur in params.items()
        )
    )
