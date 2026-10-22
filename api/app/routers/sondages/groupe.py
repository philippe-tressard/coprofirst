"""Un sondage part sur le groupe de la résidence par ici, et par ici seulement.

## Pourquoi (22/10/2026)

La création d'un sondage appelait `diffuser` avec sa question et sa description,
sans rien de son ciblage : un sondage « Bât. 4 › propriétaires », que seuls ses
destinataires peuvent lire et voter, envoyait sa description en entier au groupe
de TOUTE la résidence. Même classe que la fuite des affaires du même jour
(`tickets/groupe.diffuser_l_affaire`).

Ce module ne décide rien : `sondage_hors_du_groupe` (`utils/visibility`) dit si la
description peut partir, et le canal (`construire_message`) réduit alors le
message à la question, au périmètre et au lien. La réserve, le périmètre et le
public sont lus sur le sondage, jamais passés par qui l'envoie.

🔒 `test_groupe_sondage_reserve.py` lit le texte reçu ; `test_groupe_portes.py`
refuse un appel à `diffuser` hors des portes déclarées.
"""

from __future__ import annotations

from fastapi import BackgroundTasks

from app.models.core import Sondage
from app.utils.diffusion import diffuser
from app.utils.liens import lien_sondage
from app.utils.visibility import sondage_hors_du_groupe


def diffuser_le_sondage(background_tasks: BackgroundTasks, config: dict, sondage: Sondage) -> None:
    """Programme l'annonce de ce sondage sur le groupe, sa réserve appliquée."""
    diffuser(
        background_tasks,
        config,
        f"📊 Nouveau sondage : {sondage.question}",
        sondage.description or "",
        perimetre_cible=sondage.perimetre_cible,
        public_cible=sondage.public_cible,
        confidentiel=sondage_hors_du_groupe(sondage),
        lien=lien_sondage(sondage.id),
    )
