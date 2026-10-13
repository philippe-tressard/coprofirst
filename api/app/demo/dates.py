"""Les dates du jeu de démo, toujours RELATIVES au jour du chargement (spec §6.1).

Une archive figée vieillirait : dans un mois, le calendrier et les échéances
n'afficheraient que du passé. Le jeu se recharge chaque nuit, et chaque date s'y
calcule depuis l'horloge du projet — jamais `datetime.now()` (`utils/horloge`).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.utils import horloge


def il_y_a(jours: int, heures: int = 0) -> datetime:
    """Un instant passé, en UTC naïf comme la base."""
    return horloge.maintenant() - timedelta(days=jours, hours=heures)


def dans(jours: int, heure: int = 18, minute: int = 0) -> datetime:
    """Un rendez-vous à venir, posé à l'heure murale de Paris, rendu en UTC naïf."""
    jour = horloge.aujourd_hui() + timedelta(days=jours)
    return horloge.de_paris(datetime.combine(jour, time(heure, minute)))


def jour(decalage: int) -> date:
    """Une date civile (contrats, AG), à `decalage` jours d'aujourd'hui à Paris."""
    return horloge.aujourd_hui() + timedelta(days=decalage)
