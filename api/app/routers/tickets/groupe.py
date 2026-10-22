"""Une affaire part sur le groupe de la résidence par ici, et par ici seulement.

## Pourquoi (22/10/2026)

Trois points d'envoi appelaient `diffuser` — la création d'une affaire
(`courriels`), sa Suite (`evolutions`) et l'actualité (`actualite`) —, et seul le
dernier transmettait la réserve. Une affaire « nouveau code de l'ascenseur »,
ciblée sur un bâtiment et que l'écran disait réservée au périmètre, a ainsi
envoyé son code à TOUS les résidents ; la diffusion a dû être coupée.

Ce module ne décide rien : `contenu_hors_du_groupe` (`utils/visibility`) dit si le
contenu peut partir, et le canal (`construire_message`) réduit alors le message
au titre, au périmètre et au lien, sans la photo. Il garantit seulement qu'aucun
appelant ne peut l'oublier : la réserve et le public visé sont lus sur l'affaire,
pas passés par qui l'envoie.

🔒 `test_groupe_affaire_reservee.py` refuse un appel à `diffuser` ailleurs dans le
paquet des affaires.
"""

from __future__ import annotations

from typing import Optional

from fastapi import BackgroundTasks

from app.models.core import Ticket
from app.utils.diffusion import diffuser
from app.utils.visibility import contenu_hors_du_groupe


def diffuser_l_affaire(
    background_tasks: BackgroundTasks,
    config: dict,
    ticket: Ticket,
    titre: str,
    contenu: str,
    *,
    urgente: bool,
    image_url: Optional[str] = None,
    lien: Optional[str] = None,
) -> None:
    """Programme le message de cette affaire sur le groupe, sa réserve appliquée."""
    diffuser(
        background_tasks,
        config,
        titre,
        contenu,
        urgente=urgente,
        perimetre_cible=ticket.perimetre_cible,
        image_url=image_url,
        public_cible=ticket.public_cible,
        confidentiel=contenu_hors_du_groupe(ticket),
        lien=lien,
    )
