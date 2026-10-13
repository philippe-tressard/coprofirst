"""La santé de la PLATEFORME — ce qui n'appartient à aucune copropriété (#1814).

Chantier multi-copropriétés, suite de P2-3 (#1745, spec §4.6). Le contrôle de
06:00 (`health_monitor.run_health_check`) tourne une fois PAR copropriété, et il
mêlait deux natures :

- WhatsApp, les sauvegardes, la référence de copropriété : des données de CHAQUE
  copropriété — elles y restent ;
- le **disque** du serveur : une donnée de la PLATEFORME. Avec N copropriétés,
  « disque < 15 % » serait parti N fois, chaque fois à des gens qui ne gèrent pas
  le serveur.

## Ce qui ne change pas avec UNE copropriété — l'installation d'aujourd'hui

Son administrateur EST l'opérateur : le disque reste dans le contrôle de la
copropriété (`disque_par_la_plateforme` rend faux). Un seul courriel à 06:00,
et l'écran « Relancer le contrôle » d'Admin › Maintenance le montre toujours.

## À partir de la DEUXIÈME

Le disque quitte le contrôle des copropriétés et se juge ici, une fois, par une
tâche de la plateforme (`TACHES_DE_LA_PLATEFORME`).

**Son destinataire est l'opérateur de l'installation** (arbitré le 13/10/2026,
#1814) : un RÉGLAGE de l'installation, `COURRIEL_OPERATEUR`, et non les comptes
opérateurs des copropriétés — les trouver ferait ouvrir toutes les bases pour
une adresse (D5). Le message part par le SMTP de l'INSTALLATION (`MAIL_*`) : le
SMTP en base est celui d'une copropriété (D6), et aucune n'est servie ici.

Sans adresse, ou sans SMTP de l'installation, l'alerte se JOURNALISE en
`WARNING` avec ce qu'il faut régler — jamais un silence. L'infrastructure
surveille déjà le disque des nœuds de son côté (`check-reliability.sh`, C9) :
ce contrôle-ci est celui de l'APPLICATION, celui qui partira avec une
installation sur un autre hébergeur.
"""

from __future__ import annotations

import asyncio
import logging
import shutil

from app import contexte
from app.config import get_settings
from app.utils import horloge
from app.utils.dates_fr import datetime_longue
from app.utils.plateforme import NOM_PLATEFORME

logger = logging.getLogger(__name__)

#: En dessous de ce pourcentage d'espace libre, le disque est signalé.
SEUIL_DISQUE_LIBRE_PCT = 15

#: L'identifiant de la tâche — déclaré dans `utils/taches`.
TACHE = "sante_plateforme"


def probleme_disque(chemin: str = "/") -> list[str]:
    """Une alerte si l'espace disque est faible, sinon rien."""
    try:
        usage = shutil.disk_usage(chemin)
    except OSError as exc:
        logger.warning("Impossible de vérifier l'espace disque : %s", exc)
        return []
    pct_libre = (usage.free / usage.total) * 100
    if pct_libre >= SEUIL_DISQUE_LIBRE_PCT:
        return []
    return [
        f"Espace disque faible : {pct_libre:.1f}% libre ({usage.free / (1024**3):.1f} Go). "
        f"Vérifier et nettoyer si nécessaire."
    ]


def disque_par_la_plateforme() -> bool:
    """Le disque se juge-t-il hors des copropriétés ? À partir de la DEUXIÈME."""
    return len(contexte.coproprietes()) > 1


def destinataire_alertes_plateforme() -> str | None:
    """L'adresse de l'opérateur de l'installation (`COURRIEL_OPERATEUR`), ou None."""
    return get_settings().courriel_operateur.strip() or None


def _message(problemes: list[str]) -> tuple[str, str]:
    """Le sujet et le corps — écrits ici : les modèles en base sont ceux d'une copropriété."""
    quand = datetime_longue(horloge.a_paris(horloge.maintenant()))
    sujet = f"[{NOM_PLATEFORME}] Alerte de la plateforme — {len(problemes)} problème(s)"
    lignes = "\n".join(f"• {p}" for p in problemes)
    corps = (
        f"Contrôle de la plateforme du {quand}.\n\n{lignes}\n\n"
        "Ce message s'adresse à l'opérateur de l'installation (COURRIEL_OPERATEUR) : il ne "
        "concerne aucune copropriété en particulier."
    )
    return sujet, corps


def _envoyer(destinataire: str, problemes: list[str]) -> None:
    """Le message, par le SMTP de l'INSTALLATION (`MAIL_*`) — jamais celui d'une copropriété."""
    from fastapi_mail import FastMail, MessageSchema, MessageType

    from app.utils.smtp import connexion_smtp

    s = get_settings()
    cfg = connexion_smtp({"smtp_from_name": NOM_PLATEFORME}, expediteur=s.mail_from_plateforme)
    sujet, corps = _message(problemes)
    message = MessageSchema(
        subject=sujet, recipients=[destinataire], body=corps, subtype=MessageType.plain
    )
    asyncio.run(FastMail(cfg).send_message(message))


def alerter(problemes: list[str]) -> bool:
    """Prévenir l'opérateur — ou dire, en toutes lettres, pourquoi on ne le peut pas.

    Rend vrai si le message est parti. L'adresse n'est JAMAIS journalisée (#777).
    """
    destinataire = destinataire_alertes_plateforme()
    s = get_settings()
    if destinataire is None or not s.mail_enabled or not s.mail_from_plateforme.strip():
        manque = (
            "COURRIEL_OPERATEUR"
            if destinataire is None
            else "MAIL_ENABLED"
            if not s.mail_enabled
            else "MAIL_FROM_PLATEFORME"
        )
        logger.warning(
            "Alerte de PLATEFORME non envoyée — %s n'est pas réglé dans le .env de "
            "l'installation : %s",
            manque,
            " | ".join(problemes),
        )
        return False
    try:
        _envoyer(destinataire, problemes)
    except Exception as exc:  # noqa: BLE001 — l'échec se dit, la tâche continue
        logger.warning(
            "Alerte de PLATEFORME non envoyée — SMTP de l'installation en échec (%s) : %s",
            type(exc).__name__,
            " | ".join(problemes),
        )
        return False
    logger.info("Alerte de plateforme envoyée à l'opérateur (%d problème(s)).", len(problemes))
    return True


def run_controle_plateforme() -> None:
    """Tâche de la plateforme : le disque, une fois pour toutes les copropriétés."""
    if not disque_par_la_plateforme():
        return  # une seule copropriété : son contrôle de 06:00 le juge
    problemes = probleme_disque()
    if not problemes:
        logger.info("Contrôle de la plateforme : tout est OK.")
        return
    alerter(problemes)


def enregistrer(scheduler) -> None:
    """Pose la tâche dans le planificateur — appelé par `main.py`, à 06:00."""
    scheduler.add_job(run_controle_plateforme, "cron", hour=6, minute=0, id="sante_plateforme")
