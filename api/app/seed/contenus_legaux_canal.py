"""Ce que la politique de confidentialité dit de l'ACCÈS utilisé — site ou application (14/11/2026).

Une puce, écrite UNE fois : le gabarit (`contenus_legaux.CONTENUS`) et la migration
0336, qui l'insère dans le texte servi juste après `TELEMETRIE_ARRIVEES`, la lisent
ici. Elle dit ce que fait le code : chaque page vue garde le canal d'accès que son
client déclare (`utils/canaux_audience`), rien de l'appareil.

Rangée hors de `contenus_legaux.py`, qui approche des 500 lignes (`standards/02` §6),
comme les notifications avant elle.
"""

from __future__ import annotations

TELEMETRIE_ACCES = (
    "<li><strong>Accès utilisé\xa0:</strong> pour chaque page consultée, si vous l'avez "
    "ouverte depuis le site web ou depuis l'application pour téléphone (iPhone, puis "
    "Android) — jamais le modèle de l'appareil ni un identifiant qui lui serait propre. "
    "Il est joint à la page consultée, comme le reste de la mesure d'audience rattachée à "
    "votre compte, et conservé avec elle. Il sert à savoir comment le site et "
    "l'application sont utilisés. Votre refus de la mesure d'audience le coupe aussi.</li>"
)
