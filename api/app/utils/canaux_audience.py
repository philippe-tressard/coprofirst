"""Les CANAUX d'accès de la mesure d'audience : le site web, l'app Apple, l'app Android.

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

## L'APPAREIL, second niveau (#2774, demandé le 15/11/2026)

À l'intérieur de chaque canal, le client peut dire la CLASSE de son appareil
(`appareil`) : jamais son modèle, sa version de système ni la chaîne User-Agent — une
classe, pas une empreinte. Les classes sont fermées PAR CANAL (`APPAREILS_PAR_CANAL`) :
une combinaison hors liste est refusée (422). Absente, c'est « non précisé » : les
clients d'avant restent valides, et les vues d'avant le lot le sont toutes. La liste
est publiée aux apps (`app/contrat/constantes_clients`), qui la génèrent.
"""

from __future__ import annotations

from typing import Literal

#: Les canaux, dans l'ordre où l'écran les range. `android` est celui de l'app
#: Android, qui l'envoie ; il n'apparaît à l'écran qu'avec ses premières vues.
CANAUX = ("site", "ios", "android")
Canal = Literal["site", "ios", "android"]

#: Le canal d'une vue qui ne dit pas le sien : le site, seul client avant ce lot.
CANAL_PAR_DEFAUT: Canal = "site"

_LIBELLES = {
    "site": "Web",
    #  « App Apple », pas « App iPhone » (#2877) : l'app est universelle — iPad, Mac à
    #  puce Apple, Vision Pro, et demain Apple TV et Apple Watch (`APPAREILS_PAR_CANAL`).
    #  Ni « App iOS » : le Mac, la TV, la montre et le casque n'ont pas iOS. Symétrique
    #  d'« App Android », qui couvre aussi tablette, TV et montre. Le CODE `ios` reste.
    "ios": "App Apple",
    "android": "App Android",
}


def libelle_canal(canal: str) -> str:
    """Le libellé d'un canal pour une personne — le code lui-même s'il est inconnu."""
    return _LIBELLES.get(canal, canal)


def rang_canal(canal: str) -> int:
    """La place d'un canal à l'écran : l'ordre de `CANAUX`, l'inconnu en dernier."""
    return CANAUX.index(canal) if canal in CANAUX else len(CANAUX)


#: Les classes d'appareil de chaque canal, dans l'ordre où l'écran les range (#2774).
APPAREILS_PAR_CANAL: dict[str, tuple[str, ...]] = {
    "site": ("ordinateur", "telephone", "tablette"),
    "ios": ("iphone", "ipad", "mac", "apple_tv", "apple_watch", "vision"),
    "android": ("telephone", "tablette", "tv", "montre", "voiture", "ordinateur"),
}

#: La vue d'un client qui ne dit pas son appareil — et toutes celles d'avant #2774.
APPAREIL_NON_PRECISE = "non_precise"

_LIBELLES_APPAREIL = {
    "ordinateur": "Ordinateur",
    "telephone": "Téléphone",
    "tablette": "Tablette",
    "iphone": "iPhone",
    "ipad": "iPad",
    "mac": "Mac",
    "apple_tv": "Apple TV",
    "apple_watch": "Apple Watch",
    "vision": "Apple Vision",
    "tv": "Télévision",
    "montre": "Montre",
    "voiture": "Voiture",
    APPAREIL_NON_PRECISE: "Non précisé",
}


def appareil_admis(canal: str, appareil: str | None) -> bool:
    """L'appareil est-il une classe de ce canal ? Absent : toujours (« non précisé »)."""
    return appareil is None or appareil in APPAREILS_PAR_CANAL.get(canal, ())


def libelle_appareil(appareil: str | None) -> str:
    """Le libellé d'une classe d'appareil — le code lui-même s'il est inconnu."""
    code = appareil or APPAREIL_NON_PRECISE
    return _LIBELLES_APPAREIL.get(code, code)


def rang_appareil(canal: str, appareil: str | None) -> int:
    """La place d'un appareil sous son canal : l'ordre déclaré, « non précisé » en dernier."""
    ordre = APPAREILS_PAR_CANAL.get(canal, ())
    return ordre.index(appareil) if appareil in ordre else len(ordre)
