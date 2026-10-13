"""Les rapports nocturnes reçus par la référence (R3 #1879, spec §4.11).

Le rapport ne porte pas de clé publique : il est signé par la clé que la référence
CONNAÎT déjà pour l'identifiant qu'il annonce (`Installation.cle_publique`). Un
rapport d'une installation inconnue, ou signé d'une autre clé, est refusé — une
copie de l'état d'une installation ne parle pas en son nom.

Ce module porte la règle ; la route vit avec les autres (`registre/routeur.py`).
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, delete

from app.registre.contrat import Rapport
from app.registre.modeles import Installation, RapportInstallation
from app.utils import horloge

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
