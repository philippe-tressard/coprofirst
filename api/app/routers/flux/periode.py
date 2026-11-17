"""Le fil d'une PÉRIODE — `GET /flux?du=&au=` (#2834, décision du 17/11/2026).

Le carnet des apps (iPhone pliable, Android, puis le web) montre le fil une semaine par
double page. La semaine est servie ICI, une fois pour tous les clients : chacun qui
regrouperait les échéances de son côté recalculerait la règle du fil, et n'y mettrait
que les affaires datées.

## Le jour d'une carte

- son **échéance** quand elle en porte une : la section « Quand » de l'affaire
  (`meta.affaire.debut`, et `fin` si elle dure) — c'est aussi par là que passent les
  événements du calendrier, qui sont des affaires de nature Calendrier ;
- sa **publication** sinon (`date`).

Au jour civil de Paris (`horloge.jour_civil`), bornes `du` et `au` incluses.

## Une carte qui dure plusieurs jours

Elle paraît **une fois par jour couvert** compris dans la période (décision de
Philippe, 17/11/2026, « 2834 b ») : le mercredi, le jeudi et le vendredi d'une coupure
qui les couvre. Son `id` se répète donc d'un jour à l'autre : un client distingue ses
lignes par `(id, jour)`.

## Plusieurs cartes d'une même affaire

Les cartes d'une affaire (ouverture, réponse, commentaire, changement d'état) portent
toutes son échéance. Rangées à son jour, l'affaire y paraîtrait autant de fois : seule
la carte la plus RÉCENTE d'une affaire est gardée pour un jour donné. Les cartes rangées
à leur publication ne sont pas concernées.

Les règles du fil (masquage, droits, « me concerne ») s'appliquent AVANT, au même point
d'assemblage (`__init__.get_flux`) : une période ne montre rien que le fil n'aurait pas
montré. 🔒 `tests/test_flux_periode.py`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal, Optional

from fastapi import HTTPException

from app.utils import horloge

from .schemas import FluxItem

#: Une période ne dépasse pas un mois : au-delà, le carnet n'en a pas l'usage, et la
#: réponse grossirait sans borne.
JOURS_MAX = 31

Rattachement = Literal["echeance", "publication"]


def valider(du: Optional[date], au: Optional[date]) -> Optional[tuple[date, date]]:
    """La période demandée, ou `None` sans paramètre. 422 si elle est mal formée."""
    if du is None and au is None:
        return None
    if du is None or au is None:
        raise HTTPException(422, "Une période se donne par ses deux bornes : du et au.")
    if au < du:
        raise HTTPException(422, "La fin de la période (au) précède son début (du).")
    if (au - du).days + 1 > JOURS_MAX:
        raise HTTPException(422, f"Une période compte {JOURS_MAX} jours au plus.")
    return du, au


def _instant(valeur) -> Optional[datetime]:
    if isinstance(valeur, datetime):
        return valeur
    if isinstance(valeur, str) and valeur:
        try:
            return datetime.fromisoformat(valeur)
        except ValueError:
            return None
    return None


def jours_de(item: FluxItem) -> tuple[Rattachement, date, date]:
    """PURE. Comment la carte se range : (rattachement, premier jour, dernier jour)."""
    affaire = (item.meta or {}).get("affaire") or {}
    debut = _instant(affaire.get("debut"))
    if debut is not None:
        fin = _instant(affaire.get("fin"))
        premier = horloge.jour_civil(debut)
        dernier = max(premier, horloge.jour_civil(fin)) if fin is not None else premier
        return "echeance", premier, dernier
    jour = horloge.jour_civil(item.date)
    return "publication", jour, jour


def ranger(items: list[FluxItem], du: date, au: date) -> list[FluxItem]:
    """PURE. Les cartes de la période, une par jour couvert, triées par jour puis heure."""
    par_cle: dict[tuple, FluxItem] = {}
    for item in items:
        rattachement, premier, dernier = jours_de(item)
        jour = max(premier, du)
        while jour <= min(dernier, au):
            ticket_id = (item.meta or {}).get("ticket_id")
            cle = (
                ("affaire", ticket_id, jour)
                if rattachement == "echeance" and ticket_id is not None
                else ("carte", item.id, jour, len(par_cle))
            )
            garde = par_cle.get(cle)
            if garde is None or item.date > garde.date:
                par_cle[cle] = item.model_copy(update={"jour": jour, "rattachement": rattachement})
            jour += timedelta(days=1)
    return sorted(par_cle.values(), key=lambda i: (i.jour, i.date))


__all__ = ["JOURS_MAX", "jours_de", "ranger", "valider"]
