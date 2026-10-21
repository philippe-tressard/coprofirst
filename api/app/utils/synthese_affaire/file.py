"""La file des synthèses à produire — l'inscription, et la tâche qui la vide (#1643).

## Pourquoi une table, et pas `BackgroundTasks`

Une tâche de fond meurt avec la requête et part tout de suite. La synthèse doit
attendre **trente minutes** après la clôture : le conseil écrit souvent la Suite
de clôture juste après avoir changé l'état, et un récit produit sans elle
raconterait une affaire inachevée. Il n'y avait aucune file de travaux différés
dans le dépôt — seul APScheduler tourne ; d'où une ligne `a_produire` et une
tâche permanente déclarée dans `TACHES_PERMANENTES`.

## Ce qui inscrit une demande

- l'affaire **passe** en résolu ou annulé, quelle que soit sa catégorie —
  depuis la fiche, une Suite ou la validation d'un point CS / Syndic ;
- jamais l'affaire « Points annexes » annulée d'office, restée vide
  (`points_conseil_seance.annuler_annexe_vide`) : il n'y a rien à raconter ;
- jamais une simple correction d'une affaire close : une affaire close avant la
  mise en service ne se produit que par le bouton « Produire la synthèse ».

Une demande par clôture : une affaire rouverte puis close à nouveau en reçoit
une neuve, qui remplacera la synthèse précédente à sa production.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Optional

from sqlmodel import Session, col, select

from app.models.core import Ticket
from app.models.synthese import A_PRODUIRE, STATUTS_VIVANTS, SyntheseAffaire
from app.models.tickets import STATUTS_TICKET_CLOS
from app.utils import horloge
from app.utils.synthese_affaire.production import envoyer_avis, peut_etre_produite, produire
from app.utils.valeurs import valeur

logger = logging.getLogger("hostachy.synthese")

#: Le délai de grâce entre la clôture et la production.
DELAI_DE_GRACE = timedelta(minutes=30)
#: L'identifiant de la tâche permanente (`main.py`, `TACHES_PERMANENTES`).
ID_TACHE = "synthese_affaires"


def inscrire_si_eligible(
    session: Session,
    ticket: Ticket,
    *,
    statut_avant: object,
) -> Optional[SyntheseAffaire]:
    """Inscrit une demande si l'affaire du carnet vient d'être close. N'écrit
    que dans la session de l'appelant, qui valide.

    L'équipement n'y entre plus (v2.99.2) : il ne décide pas de l'éligibilité,
    le poser après la clôture ne change donc rien à la file."""
    if not peut_etre_produite(ticket):
        return None
    if valeur(statut_avant) in STATUTS_TICKET_CLOS:
        return None
    deja = session.exec(
        select(SyntheseAffaire).where(
            SyntheseAffaire.ticket_id == ticket.id,
            col(SyntheseAffaire.statut).in_(STATUTS_VIVANTS),
            SyntheseAffaire.cloture_le == ticket.ferme_le,
        )
    ).first()
    if deja is not None:
        return None
    demande = SyntheseAffaire(ticket_id=ticket.id, statut=A_PRODUIRE, cloture_le=ticket.ferme_le)
    session.add(demande)
    return demande


def traiter_file(session: Optional[Session] = None) -> dict[str, int]:
    """La tâche permanente : produit les demandes dont le délai de grâce est passé.

    ⚠️ Ne lève jamais : sous le planificateur, une exception tuerait le job pour
    de bon. Une demande qui échoue est journalisée et retentée au passage
    suivant ; elle ne bloque pas les autres.
    """
    from app import contexte

    propre = session is None
    session = session or contexte.nouvelle_session()
    compte = {"produites": 0, "perimees": 0, "echecs": 0}
    try:
        limite = horloge.maintenant() - DELAI_DE_GRACE
        demandes = session.exec(
            select(SyntheseAffaire)
            .where(SyntheseAffaire.statut == A_PRODUIRE, SyntheseAffaire.cree_le <= limite)
            .order_by(col(SyntheseAffaire.cree_le))
        ).all()
        for demande in demandes:
            try:
                resultat = asyncio.run(produire(session, demande))
                if not resultat.produite:
                    compte["perimees"] += 1
                    continue
                compte["produites"] += 1
                if resultat.a_aviser:
                    asyncio.run(envoyer_avis(session, demande.id))
            except Exception as exc:  # une demande ne bloque pas la file
                session.rollback()
                compte["echecs"] += 1
                logger.warning("Synthèse d'affaire %s non produite : %s", demande.id, exc)
        #  Une trace à CHAQUE passage, file vide comprise : un battement qu'on
        #  n'entend pas ne se distingue pas d'une tâche morte (`standards/07`).
        logger.info(
            "Synthèses d'affaires : %d produite(s), %d périmée(s), %d en échec",
            compte["produites"],
            compte["perimees"],
            compte["echecs"],
        )
    except Exception as exc:  # pragma: no cover - la tâche ne meurt pas
        logger.warning("File des synthèses non traitée : %s", exc)
    finally:
        if propre:
            session.close()
    return compte


__all__ = ["DELAI_DE_GRACE", "ID_TACHE", "inscrire_si_eligible", "traiter_file"]
