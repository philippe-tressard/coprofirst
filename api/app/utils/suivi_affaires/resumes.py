"""Le résumé de chaque affaire en cours par l'assistant — l'usage
`synthese_affaires_en_cours` (16/10/2026, refait par #2035).

Geste MANUEL : « ✨ Résumer les affaires » du Suivi des affaires, réservé au
conseil syndical et à l'administration (l'appel est facturé). UN appel rédige le
résumé de toutes les affaires du relevé, une ou deux phrases chacune.

Le résumé est GARDÉ sur l'affaire (`Ticket.resume_ia`) : l'écran, le PDF et le
courriel de relance le lisent sans rappeler le modèle. Seules les affaires du
relevé reçoivent le leur — un numéro que le modèle inventerait n'écrit rien.

Ce qui part, pour chaque affaire : numéro, catégorie, périmètre, titre, date
d'ouverture, ancienneté, état, description et fil daté (`rassemblement.fil_date` :
états, relances, Suites et messages non internes, chaque personne par son rôle).
Jamais un nom, jamais une pièce jointe, jamais un message interne au conseil.

🔴 La synthèse d'ENSEMBLE de #2034 n'existe plus (retirée par Philippe le
16/10/2026) : ce qui sert est l'état de chaque affaire, sous son titre.
"""

from __future__ import annotations

import logging

from sqlmodel import Session, col, select

from app.models.tickets import Ticket
from app.utils import horloge
from app.utils.dates_fr import date_courte
from app.utils.description_format import ReponseIllisible
from app.utils.llm import ErreurLLM, config_llm, demander
from app.utils.suivi_affaires.format import (
    FORMAT_REPONSE,
    USAGE_SYNTHESE_AFFAIRES_EN_COURS,
    construire_message,
    lire_reponse,
)
from app.utils.suivi_affaires.releve import Releve
from app.utils.synthese_affaire.rassemblement import fil_date, reconnaisseur_syndic

logger = logging.getLogger("hostachy.assistant")


def message_du_releve(session: Session, r: Releve) -> str:
    """Le message de l'assistant : chaque affaire du relevé, et son fil."""
    #  Import différé, comme `releve` : les libellés vivent chez les routeurs.
    from app.routers.tickets.commun import STATUT_LABELS

    tickets = {
        t.id: t
        for t in session.exec(
            select(Ticket).where(col(Ticket.id).in_([a.id for a in r.affaires]))
        ).all()
    }
    est_syndic = reconnaisseur_syndic(session)
    return construire_message(
        date_courte(r.jour),
        [
            {
                "numero": a.numero,
                "libelle_categorie": a.libelle_categorie,
                "perimetre": a.perimetre,
                "titre": a.titre,
                "ouverte_le": date_courte(a.ouverte_le),
                "age_jours": a.age_jours,
                "libelle_statut": a.libelle_statut,
                "descriptif": a.descriptif,
                "fil": fil_date(session, tickets[a.id], STATUT_LABELS, est_syndic)
                if a.id in tickets
                else "",
            }
            for a in r.affaires
        ],
    )


async def rediger(session: Session, r: Releve, *, demandeur: int) -> dict[str, str]:
    """Pose le relevé au modèle et rend le résumé de chaque affaire, par numéro.

    N'enregistre rien : l'appelant garde les résumés par `enregistrer_resumes`.
    """
    if not r.affaires:
        raise ErreurLLM("Aucune affaire ouverte : rien à résumer.")
    cfg = config_llm(session, USAGE_SYNTHESE_AFFAIRES_EN_COURS)
    #  Le prompt de l'administrateur D'ABORD, le format du code ENSUITE.
    consigne = cfg.prompt.rstrip() + "\n\n" + FORMAT_REPONSE
    reponse = await demander(
        session,
        usage=USAGE_SYNTHESE_AFFAIRES_EN_COURS,
        consigne=consigne,
        message=message_du_releve(session, r),
        demandeur=demandeur,
    )
    try:
        return lire_reponse(reponse.texte)
    except ReponseIllisible as exc:
        logger.warning("Résumé des affaires en cours : %s", exc)
        raise ErreurLLM("Le modèle n'a pas répondu dans le format attendu — réessayez.") from exc


def enregistrer_resumes(session: Session, r: Releve, par_affaire: dict[str, str]) -> int:
    """Garde sur chaque affaire DU RELEVÉ le résumé que le modèle lui a rédigé.

    `mis_a_jour_le` n'est pas touché : il date la dernière avancée, que la relance
    du syndic mesure — un résumé n'en est pas une. Rend le nombre d'affaires écrites.
    """
    ids = {a.numero: a.id for a in r.affaires if par_affaire.get(a.numero)}
    if not ids:
        return 0
    maintenant = horloge.maintenant()
    for ticket in session.exec(select(Ticket).where(col(Ticket.id).in_(ids.values()))).all():
        ticket.resume_ia = par_affaire[ticket.numero]
        ticket.resume_ia_le = maintenant
        session.add(ticket)
    session.commit()
    return len(ids)


def disponible(session: Session) -> bool:
    """Le ✨ a-t-il un sens ? — c'est le SERVEUR qui le dit (`ConfigLLM.pret`)."""
    return config_llm(session, USAGE_SYNTHESE_AFFAIRES_EN_COURS).pret
