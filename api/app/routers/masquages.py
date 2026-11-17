"""Masquer ce que publie un autre résident — pour soi (#2861).

`GET /masquages` liste mes masques (Profil), `POST /masquages` en pose un depuis une
publication, `DELETE /masquages/{auteur_id}` le retire. La règle — qui masque, qui ne
se masque pas, où le filtre s'applique — vit dans `utils/masquage`.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Utilisateur
from app.models.masquages import MasquageAuteur
from app.utils.masquage import masques_de, motif_de_refus
from app.utils.noms import nom_auteur
from app.utils.recuperer import ou_404

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
        auteur=nom_auteur(session.get(Utilisateur, m.auteur_id)),
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
def masquer(
    body: MasquageCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    auteur = ou_404(session, Utilisateur, body.auteur_id, "Compte")
    motif = motif_de_refus(user, auteur)
    if motif:
        raise HTTPException(422, motif)
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
