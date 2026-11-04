"""Ce que font les résidents sur un sondage : voter, commenter.

Extrait de `sondages.py` le 17/08/2026 (cf. `__init__.py`). Chemins NUS : le
préfixe `/sondages` est posé par le paquet, qui monte ce module avant `crud`
pour que `/{sondage_id}/voter` soit reconnu avant `/{sondage_id}`.
"""

from app.utils import horloge
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.utils.liens import lien_sondage
from app.auth.appartenance import exiger_objet_autorise
from app.auth.deps import exiger_non_externe, get_current_user, peut_commenter
from app.database import get_session
from app.models.core import (
    CommentaireSondage,
    OptionSondage,
    Sondage,
    Utilisateur,
    VoteSondage,
)
from app.utils.reponses import auteur_meta, notifier_nouvelle_reponse
from app.utils.visibility import sondage_accessible, sondage_clos
from app.utils.communaute import exiger_acces
from app.utils.recuperer import ou_404
from app.schemas_communaute import MessageRead, ReponseCommunauteRead


router = APIRouter()


class VoteBody(BaseModel):
    option_id: int
    commentaire: Optional[str] = None
    reponse_libre: Optional[str] = None


@router.post("/{sondage_id}/voter", status_code=201, response_model=MessageRead)
def voter(
    sondage_id: int,
    body: VoteBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    exiger_non_externe(user, "voter")
    s = ou_404(session, Sondage, sondage_id, "Sondage")
    if not sondage_accessible(s, user):
        raise HTTPException(403, "Vous n'êtes pas autorisé à participer à ce sondage")
    if sondage_clos(s, horloge.maintenant()):
        raise HTTPException(400, "Ce sondage est clôturé")

    existant = session.exec(
        select(VoteSondage).where(
            VoteSondage.sondage_id == sondage_id,
            VoteSondage.user_id == user.id,
        )
    ).first()
    if existant:
        raise HTTPException(400, "Vous avez déjà voté")

    opt = session.get(OptionSondage, body.option_id)
    if not opt or opt.sondage_id != sondage_id:
        raise HTTPException(400, "Option invalide")

    reponse_libre_val = body.reponse_libre.strip() if body.reponse_libre else None
    session.add(
        VoteSondage(
            sondage_id=sondage_id,
            option_id=body.option_id,
            user_id=user.id,
            reponse_libre=reponse_libre_val,
        )
    )

    if body.commentaire and body.commentaire.strip():
        contenu = body.commentaire.strip()
        session.add(
            CommentaireSondage(
                sondage_id=sondage_id,
                auteur_id=user.id,
                contenu=contenu,
            )
        )
        notifier_nouvelle_reponse(
            session,
            background_tasks,
            createur_id=s.auteur_id,
            auteur=user,
            rubrique_label="votre sondage",
            sujet=s.question,
            extrait=contenu,
            lien_path=lien_sondage(sondage_id),
        )

    session.commit()
    return {"message": "Vote enregistré"}


class CommentaireBody(BaseModel):
    contenu: str


@router.post("/{sondage_id}/commenter", status_code=201, response_model=ReponseCommunauteRead)
def commenter(
    sondage_id: int,
    body: CommentaireBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_acces(user)
    s = exiger_objet_autorise(session, Sondage, sondage_id, "Sondage", user, sondage_accessible)
    if not body.contenu.strip():
        raise HTTPException(400, "Le commentaire ne peut pas être vide")
    contenu = body.contenu.strip()
    c = CommentaireSondage(sondage_id=sondage_id, auteur_id=user.id, contenu=contenu)
    session.add(c)
    notifier_nouvelle_reponse(
        session,
        background_tasks,
        createur_id=s.auteur_id,
        auteur=user,
        rubrique_label="votre sondage",
        sujet=s.question,
        extrait=contenu,
        lien_path=lien_sondage(sondage_id),
    )
    session.commit()
    session.refresh(c)
    return {
        "id": c.id,
        "contenu": c.contenu,
        "cree_le": c.cree_le,
        "auteur_id": c.auteur_id,
        **auteur_meta(user, session),
        "peut_supprimer": peut_commenter(c, user),
    }


@router.delete("/{sondage_id}/commentaires/{commentaire_id}", status_code=204)
def supprimer_commentaire(
    sondage_id: int,
    commentaire_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    c = ou_404(
        session, CommentaireSondage, commentaire_id, "Commentaire", sous={"sondage_id": sondage_id}
    )
    #  L'auteur, ou un modérateur — règle du module central.
    if not peut_commenter(c, user):
        raise HTTPException(403, "Non autorisé")
    session.delete(c)
    session.commit()
