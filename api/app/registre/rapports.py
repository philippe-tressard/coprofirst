"""Les rapports nocturnes reçus par la référence (R3 #1879, spec §4.11).

Le rapport ne porte pas de clé publique : il est signé par la clé que la référence
CONNAÎT déjà pour l'identifiant qu'il annonce (`Installation.cle_publique`). Un
rapport d'une installation inconnue, ou signé d'une autre clé, est refusé — une
copie de l'état d'une installation ne parle pas en son nom.

Ce module porte la règle ; la route vit avec les autres (`registre/routeur.py`).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from pydantic import ValidationError
from sqlmodel import Session, delete

from app.registre.contrat import Rapport
from app.registre.modeles import Installation, RapportInstallation
from app.utils import horloge

logger = logging.getLogger("hostachy.registre")  # le journal du registre, comme ses voisins

#: Combien de temps un rapport se garde (arbitré le 13/10/2026 avec R3) : assez pour
#: voir une tendance et les alertes de R4, sans tenir l'historique d'une installation.
CONSERVATION = timedelta(days=30)


def ranger(session: Session, inst: Installation, rapport: Rapport) -> RapportInstallation:
    """Range le rapport validé, met à jour l'installation, retire ce qui a vieilli."""
    maintenant = horloge.maintenant()
    ligne = RapportInstallation(
        installation_id=inst.id,
        recu_le=maintenant,
        version_logicielle=rapport.identite.version_logicielle,
        corps=rapport.model_dump_json(),
    )
    session.add(ligne)
    inst.version_logicielle = rapport.identite.version_logicielle
    inst.vue_le = maintenant
    session.add(inst)
    session.exec(
        delete(RapportInstallation).where(
            RapportInstallation.installation_id == inst.id,
            RapportInstallation.recu_le < maintenant - CONSERVATION,
        )
    )
    return ligne


def relire(ligne: Optional[RapportInstallation]) -> Optional[Rapport]:
    """Un rapport rangé, relu contre le contrat — illisible, il se tait et se journalise.

    La seule lecture (#2949) : les alertes du registre et la fiche d'une
    installation (`routers/admin/installations`) la recopiaient chacune.
    """
    if ligne is None:
        return None
    try:
        return Rapport.model_validate_json(ligne.corps)
    except ValidationError:
        logger.warning("registre : rapport %s illisible au contrat en vigueur", ligne.id)
        return None
