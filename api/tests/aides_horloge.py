"""Dater un objet « il y a N jours » comme l'application compte les jours (#2257).

L'application compte l'ancienneté en **jours civils de Paris** : `aujourd_hui() -
jour_civil(cree_le)`. Un test qui pose `maintenant() - timedelta(days=N)` pose N × 24 h
en UTC naïf, et ce n'est pas N jours civils : entre 22 h et 23 h UTC, l'instant d'il y a
N × 24 h tombe, de l'autre côté d'un changement d'heure, le lendemain à Paris — N − 1 jours
(ou N + 1 dans l'autre sens). Quatre tests d'ancienneté ont échoué ainsi chaque soir entre
23 h et minuit, sans qu'aucun code ne change.

`il_y_a_jours(N)` pose midi de Paris, N jours civils avant aujourd'hui : aucun changement
d'heure ne le déplace d'un jour. Pour une ancienneté que l'application compte en jours
civils, c'est la seule écriture admise (`test_anciennete_jours_civils.py`).
"""

from datetime import datetime, time, timedelta

from app.utils import horloge

#: Les deux instants où 24 h × N et N jours civils diffèrent : le soir d'hiver (23 h 30 à
#: Paris, 22 h 30 UTC) devant un passé d'été, et la nuit d'été (0 h 30) devant un passé d'hiver.
INSTANTS_HOSTILES = {
    "hiver-23h30": datetime(2026, 12, 15, 22, 30),
    "ete-00h30": datetime(2027, 7, 15, 22, 30),
}


def il_y_a_jours(jours: int) -> datetime:
    """Midi de Paris, `jours` jours civils avant aujourd'hui — en UTC naïf, comme la base."""
    jour = horloge.aujourd_hui() - timedelta(days=jours)
    return horloge.de_paris(datetime.combine(jour, time(12)))
