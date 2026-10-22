"""Diffuser sur le canal de la résidence — le registre des canaux (#1060, 28/09/2026).

## Pourquoi

Un appelant veut « prévenir le groupe de la résidence », pas « envoyer un
WhatsApp ». Cinq routeurs écrivaient pourtant le transport en toutes lettres —
lire la configuration WhatsApp, vérifier qu'elle est active, programmer
`envoyer_whatsapp_avec_log` avec neuf arguments positionnels. Changer de
messagerie (Telegram, Signal, Matrix : une décision de copropriété, pas
d'implémentation) aurait demandé de les rouvrir un à un.

## Ce que ce module est — et ce qu'il n'est pas

Un **registre**, comme `llm_usages` l'est pour l'assistant IA : un canal déclare
son code, son libellé, ses clés de configuration et les trois fonctions de son
adaptateur. Il n'en existe qu'UN — WhatsApp, dont le bridge (`POST /send`) est
l'adaptateur —, et c'est voulu : une interface conçue sans second implémenteur
se révèle fausse le jour où il arrive (`standards/02` §4 quater). Le geste utile
aujourd'hui est la couture, pas une couche générique.

⚠️ Ce qui reste nommé d'après le transport, et le sera jusqu'au second canal :
les clés `whatsapp_*` de la configuration et la table `whatsapp_log`. Les
renommer demande une migration et l'écran d'administration — un lot à part.

🔒 `test_diffusion_canal.py` refuse qu'un module hors de l'adaptateur importe
les gestes du transport.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Callable, Optional

from app.utils.services import SERVICE_DIFFUSION, service_actif
from app.utils.whatsapp import (
    CLES_CONFIG,
    config_whatsapp,
    envoyer_whatsapp_avec_log,
)


@dataclass(frozen=True)
class Canal:
    """Un canal de diffusion et les trois gestes de son adaptateur."""

    code: str
    libelle: str
    cles_config: frozenset[str]
    lire_config: Callable[..., dict]
    est_actif: Callable[[dict], bool]
    envoyer: Callable[..., None]


CANAUX: dict[str, Canal] = {
    "whatsapp": Canal(
        code="whatsapp",
        libelle="Groupe WhatsApp de la résidence",
        cles_config=CLES_CONFIG,
        lire_config=config_whatsapp,
        #  L'activation du canal est celle du SERVICE (#1718) : une règle, au registre.
        est_actif=partial(service_actif, code=SERVICE_DIFFUSION),
        envoyer=envoyer_whatsapp_avec_log,
    ),
}

#  Le canal de la résidence. Un second canal s'ajoute à `CANAUX` ; ce choix
#  deviendra alors un réglage de l'administration.
CANAL_RESIDENCE = "whatsapp"


def canal_residence() -> Canal:
    return CANAUX[CANAL_RESIDENCE]


def config_diffusion(session, *cles_en_plus: str) -> Optional[dict]:
    """La configuration du canal de la résidence, ou `None` s'il est éteint.

    `cles_en_plus` : des clés de configuration du site que l'appelant veut lire
    en même temps (`reference_copro`, `site_nom`…).
    """
    canal = canal_residence()
    config = canal.lire_config(session, *cles_en_plus)
    return config if canal.est_actif(config) else None


def diffuser(
    background_tasks,
    config: dict,
    titre: str,
    contenu: str,
    *,
    public_cible: Optional[str],
    confidentiel: bool,
    urgente: bool = False,
    perimetre_cible: Optional[str] = None,
    image_url: Optional[str] = None,
    lien: Optional[str] = None,
) -> None:
    """Programme la diffusion en tâche de fond — elle est journalisée par l'adaptateur.

    `config` est celle que `config_diffusion` a rendue : l'appelant l'a déjà lue
    pour décider, et y trouve l'adresse du site pour composer son lien.

    🔴 **La réserve n'a pas de défaut** (22/10/2026, `standards/03` §2 bis) :
    `public_cible` et `confidentiel` valaient `None` et `False`, si bien qu'un
    appelant qui ne pensait pas à les passer envoyait tout au groupe — deux envois
    d'affaire sur trois, puis le sondage. Elles se lisent sur l'OBJET, dans sa
    porte (`diffuser_l_affaire`, `diffuser_le_sondage`, le partage d'une affiche),
    et `test_groupe_portes.py` refuse tout autre appelant.
    """
    background_tasks.add_task(
        canal_residence().envoyer,
        titre,
        contenu,
        urgente,
        perimetre_cible,
        image_url,
        config,
        public_cible,
        confidentiel,
        lien=lien,
    )
