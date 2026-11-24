"""Masquer ce que publie un autre résident — pour soi (#2861).

`GET /masquages` liste mes masques (Profil), `POST /masquages` en pose un depuis une
publication, `DELETE /masquages/{auteur_id}` le retire. La règle — qui masque, qui ne
se masque pas, où le filtre s'applique — vit dans `utils/masquage`.

🔒 Le geste ne vise que l'auteur d'une publication signée que le lecteur lit
(`auteur_lu_par`) ; un autre compte répond comme un compte absent. Il a sa limite
de débit (`LIMITE_PREFERENCE` : un choix pour soi seul, qui se défait).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import est_moderateur, get_current_user
from app.database import get_session
from app.models.core import Utilisateur
from app.models.masquages import MasquageAuteur
from app.utils.limiter import LIMITE_PREFERENCE, limiter
from app.utils.masquage import (
    REFUS_MODERATEUR_CIBLE,
    auteur_lu_par,
    masques_de,
    motif_de_refus,
)
from app.utils.noms import nom_auteur
from app.utils.recuperer import ou_404, ou_rien

router = APIRouter(prefix="/masquages", tags=["masquages"])


class MasquageCreate(BaseModel):
    auteur_id: int


class MasquageRead(BaseModel):
    auteur_id: int
    #: Le nom tel que l'affichent ses publications.
    auteur: str
    cree_le: datetime


def _lu(m: MasquageAuteur, session: Session) -> MasquageRead:
    return MasquageRead(
        auteur_id=m.auteur_id,
        auteur=nom_auteur(ou_rien(session, Utilisateur, m.auteur_id)),
        cree_le=m.cree_le,
    )


def _le_mien(session: Session, user: Utilisateur, auteur_id: int):
    return session.exec(
        select(MasquageAuteur).where(
            MasquageAuteur.masque_par_id == user.id, MasquageAuteur.auteur_id == auteur_id
        )
    ).first()


@router.get("", response_model=list[MasquageRead])
def lister_masquages(
    session: Session = Depends(get_session), user: Utilisateur = Depends(get_current_user)
):
    return [_lu(m, session) for m in masques_de(session, user)]


@router.post("", response_model=MasquageRead, status_code=201)
@limiter.limit(LIMITE_PREFERENCE)
def masquer(
    request: Request,
    body: MasquageCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    motif = motif_de_refus(user, body.auteur_id)
    if motif:
        raise HTTPException(422, motif)
    #  Un compte dont ce lecteur ne lit aucune publication signée se lit comme
    #  absent : même réponse, aucun nom (`utils/masquage`).
    identifiant = body.auteur_id if auteur_lu_par(session, user, body.auteur_id) else None
    auteur = ou_404(session, Utilisateur, identifiant, "Compte")
    if est_moderateur(auteur):
        raise HTTPException(422, REFUS_MODERATEUR_CIBLE)
    #  Le geste se rejoue sans doublon : un second appui rend le masque posé.
    masque = _le_mien(session, user, auteur.id)
    if masque is None:
        masque = MasquageAuteur(masque_par_id=user.id, auteur_id=auteur.id)
        session.add(masque)
        session.commit()
        session.refresh(masque)
    return _lu(masque, session)


@router.delete("/{auteur_id}", status_code=204, response_class=Response)
def demasquer(
    auteur_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    masque = _le_mien(session, user, auteur_id)
    if masque is not None:
        session.delete(masque)
        session.commit()
    return Response(status_code=204)
