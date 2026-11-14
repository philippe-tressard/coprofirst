"""Les CANAUX d'accès de la mesure d'audience : le site web, l'app iPhone, l'app Android.

Demandé le 14/11/2026 : « comprendre comment l'appli est consommée » — pour une page
consultée, savoir si elle l'a été depuis le site ou depuis l'application. Jusque-là,
seul le site envoyait ses pages vues (`front/src/lib/telemetry.ts`) ; l'app iOS ne
faisait que LIRE le tableau de bord.

Le client DIT son canal dans le lot qu'il poste à `/telemetry/collect` (`canal`) ;
absent, c'est le site — le front n'a rien à envoyer, et toute vue enregistrée avant
ce lot venait du site, faute d'autre client qui collecte. Une valeur hors de la liste
est refusée (422), comme tout lot hors norme : un client inconnu ne s'invente pas
un canal.

Les libellés sont servis par l'API (`libelle_canal`) : le site et l'app affichent la
même répartition, la règle d'affichage se calcule ici (`standards/09` §8).
"""

from __future__ import annotations

from typing import Literal

#: Les canaux, dans l'ordre où l'écran les range. `android` est réservé : aucun
#: client ne l'envoie encore, il n'apparaît à l'écran qu'avec ses premières vues.
CANAUX = ("site", "ios", "android")
Canal = Literal["site", "ios", "android"]

#: Le canal d'une vue qui ne dit pas le sien : le site, seul client avant ce lot.
CANAL_PAR_DEFAUT: Canal = "site"

_LIBELLES = {
    "site": "Site web",
    "ios": "App iPhone",
    "android": "App Android",
}


def libelle_canal(canal: str) -> str:
    """Le libellé d'un canal pour une personne — le code lui-même s'il est inconnu."""
    return _LIBELLES.get(canal, canal)


def rang_canal(canal: str) -> int:
    """La place d'un canal à l'écran : l'ordre de `CANAUX`, l'inconnu en dernier."""
    return CANAUX.index(canal) if canal in CANAUX else len(CANAUX)
