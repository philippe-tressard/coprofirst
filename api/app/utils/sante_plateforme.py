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

🔴 **Son destinataire n'est pas décidé** (arbitrage du 12/10/2026 : « je verrai
quand le premier cas se produira »). Tout ce qui en dépend est dans
`destinataire_alertes_plateforme`, et nulle part ailleurs. Deux voies :

1. un réglage de l'INSTALLATION (une variable d'environnement lue par
   `Settings`) — l'opérateur supervise l'installation, sa coordonnée lui
   appartient ; c'est la recommandation de #1814 ;
2. les comptes opérateurs de chaque copropriété (P2-8, #1750), dédoublonnés —
   ce qui fait ouvrir toutes les bases pour une adresse (risque D5 de la spec).

Tant que la décision manque, l'alerte se JOURNALISE, en `WARNING`, avec ce
qu'il faut faire — jamais un silence. L'infrastructure surveille déjà le disque
des nœuds de son côté (`check-reliability.sh`, point 14 du pré-check) : ce
contrôle-ci est celui de l'APPLICATION, celui qui partira avec une installation
sur un autre hébergeur.
"""

from __future__ import annotations

import logging
import shutil

from app import contexte

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
    """L'adresse de l'opérateur pour une alerte de plateforme — NON DÉCIDÉE (#1814).

    Rend `None` tant que l'une des deux voies de l'en-tête n'est pas choisie. Le
    jour où elle l'est, c'est cette fonction qu'on écrit, et `alerter` qui
    envoie — rien d'autre ne bouge.
    """
    return None


def alerter(problemes: list[str]) -> None:
    """Prévenir l'opérateur — ou dire, en toutes lettres, qu'on ne le peut pas."""
    if destinataire_alertes_plateforme() is None:
        logger.warning(
            "Alerte de PLATEFORME non envoyée — aucun destinataire décidé (#1814, "
            "`utils/sante_plateforme.destinataire_alertes_plateforme`) : %s",
            " | ".join(problemes),
        )
        return
    raise NotImplementedError("l'envoi suit la décision du destinataire (#1814)")


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
