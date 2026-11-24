"""La synthèse d'une affaire close — la lire, et les gestes du conseil (#1643).

| Route | Qui | Ce qu'elle fait |
|---|---|---|
| `GET …/synthese` | qui lit l'affaire | la synthèse lisible (brouillon : conseil seul), et si l'on peut en produire une |
| `PATCH …/synthese` | conseil, admin | « Modifier » les trois textes, brouillon ou validée — les métriques ne s'éditent pas |
| `DELETE …/synthese` | conseil, admin | « Supprimer » la synthèse et sa Suite, brouillon ou validée — « Produire » reste offert |
| `POST …/synthese/relancer` | conseil, admin | PROPOSE une rédaction, avec un complément au prompt |
| `POST …/synthese/recommencer` | conseil, admin | PROPOSE une rédaction, sans complément |
| `POST …/propositions/{id}/appliquer` | conseil, admin | la rédaction proposée remplace le texte |
| `POST …/synthese/valider` | conseil, admin | le brouillon devient lisible de tous les lecteurs de l'affaire, et du carnet |
| `POST …/synthese/produire` | conseil, admin | une affaire du carnet close sans synthèse — celles d'avant la mise en service |

Le droit est `est_moderateur` (arbitré) : conseil syndical ou administration.
Les règles vivent dans `utils/synthese_affaire/` ; ce routeur décide qui entre.

Les trois routes qui appellent l'assistant portent `LIMITE_APPEL_FACTURE` : un
appel se facture (`test_limite_appel_facture.py`).
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.auth.appartenance import exiger_objet_autorise
from app.auth.deps import est_moderateur, exiger_moderateur, get_current_user
from app.database import get_session
from app.models.core import Ticket, TicketEvolution, Utilisateur
from app.models.synthese import (
    A_PRODUIRE,
    ANNULEE,
    BROUILLON,
    VALIDEE,
    SyntheseAffaire,
    TentativeSynthese,
)
from app.schemas_synthese import SyntheseLue

from .synthese_schemas import (
    PropositionSynthese,
    SyntheseEtat,
    SyntheseModification,
    SyntheseRelance,
)
from app.utils import horloge
from app.utils.limiter import LIMITE_APPEL_FACTURE, limiter
from app.utils.synthese_affaire.lecture import lisible, synthese_courante, synthese_lue
from app.utils.recuperer import ou_404
from app.utils.synthese_affaire.production import (
    appliquer_tentative,
    envoyer_avis,
    peut_etre_produite,
    produire,
)
from app.utils.visibility import ticket_visible

router = APIRouter()


#: Le refus des gestes de la synthèse — posé par la porte centrale (`exiger_moderateur`, #2942).
_RESERVE = "Réservé au conseil syndical et à l'administration"


def _courante(session: Session, ticket: Ticket) -> SyntheseAffaire:
    """La synthèse affichée de l'affaire — brouillon ou validée."""
    synthese = synthese_courante(session, ticket.id)
    if synthese is None:
        raise HTTPException(409, "Cette affaire n'a pas de synthèse à modifier")
    return synthese


def _brouillon(session: Session, ticket: Ticket) -> SyntheseAffaire:
    """La synthèse en brouillon — seule forme que l'assistant relance et que l'on valide.

    Le texte, lui, se corrige et la synthèse se supprime à tout état (`_courante`)."""
    synthese = _courante(session, ticket)
    if synthese.statut != BROUILLON:
        raise HTTPException(409, "Cette synthèse est validée : elle n'est plus à relire")
    return synthese


def _en_attente(session: Session, ticket: Ticket) -> bool:
    return (
        session.exec(
            select(SyntheseAffaire).where(
                SyntheseAffaire.ticket_id == ticket.id,
                SyntheseAffaire.statut == A_PRODUIRE,
            )
        ).first()
        is not None
    )


@router.get("/{ticket_id}/synthese", response_model=SyntheseEtat)
def lire_synthese(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    synthese = synthese_courante(session, ticket.id)
    conseil = est_moderateur(user)
    lue = (
        synthese_lue(session, synthese, conseil=conseil)
        if synthese and lisible(synthese, ticket, user)
        else None
    )
    attente = conseil and _en_attente(session, ticket)
    return SyntheseEtat(
        synthese=lue,
        produisible=conseil and synthese is None and not attente and peut_etre_produite(ticket),
        en_attente=attente,
    )


@router.patch("/{ticket_id}/synthese", response_model=SyntheseLue)
def modifier_synthese(
    ticket_id: int,
    body: SyntheseModification,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_moderateur(user, _RESERVE)
    synthese = _courante(
        session, exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    )
    corrections = {c: (v or "").strip() for c, v in body.model_dump(exclude_unset=True).items()}
    #  Une synthèse validée est lue de tous et versée au carnet : elle ne se vide pas.
    if synthese.statut == VALIDEE and not corrections.get("synthese", synthese.synthese):
        raise HTTPException(422, "La synthèse validée ne peut pas être vide : supprimez-la plutôt")
    for champ, texte in corrections.items():
        setattr(synthese, champ, texte)
    synthese.mis_a_jour_le = horloge.maintenant()
    session.add(synthese)
    session.commit()
    session.refresh(synthese)
    return synthese_lue(session, synthese, conseil=True)


@router.delete("/{ticket_id}/synthese", status_code=204)
def supprimer_synthese(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Retire la synthèse affichée et sa Suite du fil.

    La ligne reste, `annulee` — « gardée, plus affichée », comme une synthèse
    remplacée : elle ne bloque pas une nouvelle production (`STATUTS_VIVANTS`),
    et « Produire la synthèse » redevient offert au conseil."""
    exiger_moderateur(user, _RESERVE)
    synthese = _courante(
        session, exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    )
    evolution = (
        session.get(TicketEvolution, synthese.evolution_id) if synthese.evolution_id else None
    )
    if evolution is not None:
        session.delete(evolution)
    synthese.evolution_id = None
    synthese.statut = ANNULEE
    synthese.mis_a_jour_le = horloge.maintenant()
    session.add(synthese)
    session.commit()


async def _proposer(session: Session, synthese: SyntheseAffaire, user, complement):
    """Une rédaction PROPOSÉE — le texte relu reste en place jusqu'à « Appliquer »."""
    resultat = await produire(session, synthese, auteur_id=user.id, complement=complement)
    if not resultat.redigee:
        raise HTTPException(502, resultat.motif or "L'assistant n'a pas rendu de synthèse")
    tentative = session.get(TentativeSynthese, resultat.tentative_id)
    session.refresh(synthese)
    return PropositionSynthese(
        tentative_id=tentative.id,
        synthese=tentative.synthese or "",
        difficultes=tentative.difficultes or "",
        amelioration=tentative.amelioration or "",
        prompt_complement=tentative.prompt_complement,
        actuelle=synthese_lue(session, synthese, conseil=True),
    )


@router.post("/{ticket_id}/synthese/relancer", response_model=PropositionSynthese)
@limiter.limit(LIMITE_APPEL_FACTURE)
async def relancer_synthese(
    request: Request,
    ticket_id: int,
    body: SyntheseRelance,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_moderateur(user, _RESERVE)
    synthese = _brouillon(
        session, exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    )
    return await _proposer(session, synthese, user, body.prompt_complement)


@router.post("/{ticket_id}/synthese/recommencer", response_model=PropositionSynthese)
@limiter.limit(LIMITE_APPEL_FACTURE)
async def recommencer_synthese(
    request: Request,
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Arbitré : « Recommencer » propose sans complément — l'appliquer l'efface ;
    l'historique des tentatives reste."""
    exiger_moderateur(user, _RESERVE)
    synthese = _brouillon(
        session, exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    )
    return await _proposer(session, synthese, user, None)


@router.post(
    "/{ticket_id}/synthese/propositions/{tentative_id}/appliquer", response_model=SyntheseLue
)
def appliquer_proposition(
    ticket_id: int,
    tentative_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """« Appliquer » : la rédaction proposée par une relance remplace le texte."""
    exiger_moderateur(user, _RESERVE)
    synthese = _brouillon(
        session, exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    )
    tentative = ou_404(
        session, TentativeSynthese, tentative_id, "Proposition", sous={"synthese_id": synthese.id}
    )
    if not (tentative.synthese or "").strip():
        raise HTTPException(409, "Cette tentative n'a pas rendu de rédaction")
    appliquer_tentative(session, synthese, tentative)
    session.refresh(synthese)
    return synthese_lue(session, synthese, conseil=True)


@router.post("/{ticket_id}/synthese/valider", response_model=SyntheseLue)
def valider_synthese(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_moderateur(user, _RESERVE)
    synthese = _brouillon(
        session, exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    )
    if not (synthese.synthese or "").strip():
        raise HTTPException(422, "La synthèse est vide : rédigez-la avant de la valider")
    maintenant = horloge.maintenant()
    synthese.statut = VALIDEE
    synthese.validee_le = maintenant
    synthese.validee_par_id = user.id
    synthese.mis_a_jour_le = maintenant
    session.add(synthese)
    session.commit()
    session.refresh(synthese)
    return synthese_lue(session, synthese, conseil=True)


@router.post("/{ticket_id}/synthese/produire", response_model=SyntheseLue, status_code=201)
@limiter.limit(LIMITE_APPEL_FACTURE)
async def produire_synthese(
    request: Request,
    ticket_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """« Produire la synthèse » — une affaire du carnet close qui n'en a pas."""
    exiger_moderateur(user, _RESERVE)
    ticket = exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    if not peut_etre_produite(ticket):
        raise HTTPException(422, "Seule une affaire close du carnet d'entretien a une synthèse")
    if synthese_courante(session, ticket.id) is not None or _en_attente(session, ticket):
        raise HTTPException(409, "Cette affaire a déjà une synthèse")
    demande = SyntheseAffaire(ticket_id=ticket.id, statut=A_PRODUIRE, cloture_le=ticket.ferme_le)
    session.add(demande)
    #  Validée AVANT l'appel : le journal des appels écrit dans sa propre
    #  transaction, qu'une écriture en cours ici verrouillerait (#1469).
    session.commit()
    session.refresh(demande)
    resultat = await produire(session, demande, auteur_id=user.id)
    if resultat.a_aviser:
        background_tasks.add_task(envoyer_avis, None, demande.id)
    session.refresh(demande)
    return synthese_lue(session, demande, conseil=True)
