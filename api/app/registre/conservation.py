"""La CONSERVATION de ce que le registre sait d'une installation résiliée (conditions v1 §4).

Les conditions d'inscription promettent deux durées, comptées depuis la résiliation :

| Donnée | Gardée | Pourquoi |
|---|---|---|
| coordonnées de l'administrateur (`ContactInstallation`) | 12 mois au plus | le service n'en a plus l'usage |
| archive du contrat accepté (`AcceptationConditions`) | 5 ans, puis effacée | la preuve de ce qui a été convenu — prescription de droit commun (C. civ., art. 2224) |

Deux gestes les tiennent :

1. **Supprimer** (l'opérateur, `supprimer`) — une installation RÉSILIÉE quitte la
   liste, et ce qu'aucune obligation ne garde s'efface tout de suite : coordonnées,
   rapports, services. L'archive du contrat reste jusqu'à ses 5 ans, et le journal
   — des identifiants, aucun nom — dit qui a supprimé, quand et pourquoi.
2. **Purger** (chaque nuit, `purger`) — les échéances arrivées s'effacent, que
   l'installation ait été supprimée ou non. Une durée sans purge est une durée
   fictive (`standards/14`).

🔴 La ligne `installation` ne se supprime JAMAIS : son numéro fait l'identifiant
`CF-…` (`modeles.identifiant_de`), et un numéro libéré se réattribuerait — une autre
installation hériterait du journal, du bail et de la détection de clone d'une
ancienne. La même clé qui revient retrouve la même ligne (`routeur._reinscrire`).

La date de résiliation se lit au JOURNAL — la ligne « resilier » —, et nulle part
ailleurs : c'est lui qui dit quand.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, delete, func, select

from app.registre import base, decisions
from app.registre.modeles import (
    AcceptationConditions,
    ContactInstallation,
    DecisionRegistre,
    EtatInscription,
    Installation,
    RapportInstallation,
)
from app.utils import horloge

logger = logging.getLogger("hostachy.registre")

#: Combien d'années après la résiliation chaque donnée s'efface (conditions v1 §4).
ANNEES_COORDONNEES = 1
ANNEES_CONTRAT = 5

#: Les lignes que la purge écrit au journal — l'écran les nomme.
GESTE_COORDONNEES_EFFACEES = "coordonnees_effacees"
GESTE_CONTRAT_EFFACE = "contrat_efface"


def plus_annees(instant: datetime, annees: int) -> datetime:
    """Le même instant `annees` plus tard ; un 29 février tombe au 1er mars."""
    try:
        return instant.replace(year=instant.year + annees)
    except ValueError:
        return instant.replace(year=instant.year + annees, month=3, day=1)


def resiliee_le(session: Session, inst: Installation) -> Optional[datetime]:
    """Quand l'installation a été résiliée — au journal, la dernière ligne « resilier »."""
    return session.exec(
        select(func.max(DecisionRegistre.cree_le)).where(
            DecisionRegistre.installation_id == inst.id,
            DecisionRegistre.geste == "resilier",
        )
    ).one()


def _effacer(session: Session, modele, inst: Installation) -> int:
    """Retire les lignes de `modele` rattachées à `inst` ; rend leur nombre."""
    return session.exec(delete(modele).where(modele.installation_id == inst.id)).rowcount


def supprimer(session: Session, inst: Installation, motif: str, auteur: str) -> DecisionRegistre:
    """Retire une installation résiliée de la liste et efface ce qu'aucune obligation ne garde."""
    if not decisions.supprimable(inst):
        raise decisions.DecisionRefusee(
            "Seule une installation résiliée se supprime — et la référence jamais."
        )
    motif = decisions.exiger_motif(motif)
    _effacer(session, ContactInstallation, inst)
    _effacer(session, RapportInstallation, inst)
    inst.services_autorises = "[]"
    inst.effacee_le = inst.mis_a_jour_le = horloge.maintenant()
    session.add(inst)
    return decisions.consigner(session, inst, decisions.GESTE_SUPPRIMER, motif, auteur)


def purger(session: Session, maintenant: datetime) -> dict[str, int]:
    """Efface ce dont l'échéance est passée, et l'inscrit au journal. Rend le bilan."""
    bilan = {GESTE_COORDONNEES_EFFACEES: 0, GESTE_CONTRAT_EFFACE: 0}
    resiliees = session.exec(
        select(Installation).where(Installation.etat == EtatInscription.resiliee)
    ).all()
    for inst in resiliees:
        depuis = resiliee_le(session, inst)
        if depuis is None:
            continue
        echeances = (
            (ANNEES_COORDONNEES, ContactInstallation, GESTE_COORDONNEES_EFFACEES),
            (ANNEES_CONTRAT, AcceptationConditions, GESTE_CONTRAT_EFFACE),
        )
        for annees, modele, geste in echeances:
            if maintenant >= plus_annees(depuis, annees) and _effacer(session, modele, inst):
                decisions.consigner(
                    session, inst, geste, f"{annees} an(s) après la résiliation — conditions §4"
                )
                bilan[geste] += 1
    return bilan


def run_conservation_registre() -> None:
    """La purge nocturne — sans objet hors de la référence dont le registre est allumé."""
    if not base.registre_actif():
        return
    try:
        with Session(base.moteur()) as session:
            bilan = purger(session, horloge.maintenant())
            session.commit()
    except SQLAlchemyError as exc:
        logger.warning("registre : purge des échéances non faite (%s)", type(exc).__name__)
        return
    if any(bilan.values()):
        logger.info("registre : échéances de conservation appliquées %s", bilan)


def enregistrer(scheduler) -> None:
    """Pose la purge à 04:10 — après la sauvegarde du registre (03:30)."""
    scheduler.add_job(
        run_conservation_registre, "cron", hour=4, minute=10, id="conservation_registre"
    )
