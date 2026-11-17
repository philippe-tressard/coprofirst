"""Ce que la politique de confidentialité dit de l'ACCÈS utilisé — site ou application (14/11/2026).

Une puce, écrite UNE fois : le gabarit (`contenus_legaux.CONTENUS`) et la migration
0336, qui l'insère dans le texte servi juste après `TELEMETRIE_ARRIVEES`, la lisent
ici. Elle dit ce que fait le code : chaque page vue garde le canal d'accès que son
client déclare (`utils/canaux_audience`) et, depuis le 17/11/2026 (#2774, migration
0345), la CLASSE de son appareil — jamais son modèle ni sa version de système.

Rangée hors de `contenus_legaux.py`, qui approche des 500 lignes (`standards/02` §6),
comme les notifications avant elle.
"""

from __future__ import annotations

TELEMETRIE_ACCES = (
    "<li><strong>Accès utilisé et type d'appareil\xa0:</strong> pour chaque page consultée, "
    "si vous l'avez ouverte depuis le site web ou depuis l'application (iPhone, Android), et "
    "le type d'appareil\xa0: téléphone, tablette, ordinateur, télévision, montre — jamais le "
    "modèle de l'appareil, la version de son système ni un identifiant qui lui serait "
    "propre. Ils sont joints à la page consultée, comme le reste de la mesure d'audience "
    "rattachée à votre compte, et conservés avec elle. Ils servent à savoir comment le site "
    "et l'application sont utilisés. Votre refus de la mesure d'audience les coupe aussi.</li>"
)
