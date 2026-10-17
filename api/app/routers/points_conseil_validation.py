"""La VALIDATION du compte rendu d'un point CS / Syndic (#2042).

À part de `routers/points_conseil` (la saisie) : ce routeur porte ce qui suit
« Terminer le point ». Les règles vivent dans `utils/points_conseil_validation`.

| Route | Qui | Ce qu'elle fait |
|---|---|---|
| `GET /points-conseil/lien/{jeton}` | le porteur du lien | le CR, à lire — n'engage rien |
| `POST /points-conseil/lien/{jeton}/valider` | le porteur du lien | « Je valide » |
| `POST /points-conseil/lien/{jeton}/commentaire` | le porteur du lien | répondre ; suspend les 7 jours |
| `POST /points-conseil/{id}/renvoyer` | CS / admin | renvoyer le CR corrigé aux présents |
| `POST /points-conseil/{id}/valider` | CS / admin | valider en l'état |
| `POST /points-conseil/{id}/pdf` | CS / admin | le PDF d'un CR validé (comme celui du Suivi) |
| `PATCH /points-conseil/comptes-rendus/{id}` | CS / admin | « Conseil seul » d'un CR |
| `GET /points-conseil/affaires/{ticket_id}` | qui lit l'affaire | ses CR validés (rubrique « Comptes rendus ») |

🔴 Le lien d'un présent est PUBLIC — un membre du syndic n'a souvent pas de
compte : le jeton seul l'identifie. L'ouvrir ne consomme rien (`standards/03`
§5 bis) ; un jeton inconnu, ou remplacé par un envoi plus récent, rend 404.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth.appartenance import exiger_objet_autorise
from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.models.points_conseil import VALIDE, CompteRenduAffaire, PointConseil
from app.models.tickets import Ticket
from app.utils import points_conseil as regles
from app.utils import points_conseil_validation as validation
from app.utils.config_site import config_site
from app.utils.lecture import lire_objet
from app.utils.limiter import LIMITE_SESSION, limiter
from app.utils.liens import nom_site
from app.utils.logo import logo_televerse_png
from app.utils.points_conseil_pdf import generer_pdf
from app.utils.recuperer import ou_404
from app.utils.visibility import ticket_visible

router = APIRouter(prefix="/points-conseil", tags=["points-conseil"])


class AffaireLienRead(BaseModel):
    numero: str
    titre: str
    contenu: str


class LienRead(BaseModel):
    """Ce que le porteur du lien lit : le CR, sans ce qui est « Conseil seul »."""

    class Config:
        from_attributes = True

    etat: str
    debut: datetime
    fin: Optional[datetime] = None
    a_distance: bool
    lieu: Optional[str] = None
    presents: list[str]
    abordees: list[AffaireLienRead]
    non_traitees: list[str]
    #: A-t-il déjà validé ? — un second clic ne change rien.
    deja_valide: bool
    echeance: Optional[datetime] = None


class CommentaireEntree(BaseModel):
    contenu: str = Field(min_length=1, max_length=4000)


class ConfidentialiteEntree(BaseModel):
    conseil_seul: bool


class CrPublieRead(BaseModel):
    point_id: int
    debut: datetime
    a_distance: bool
    lieu: Optional[str] = None
    contenu: str
    conseil_seul: bool
    cr_id: int


# ── Le lien d'un présent ──────────────────────────────────────────────────


def _lien_read(session: Session, jeton: str) -> LienRead:
    present = validation.present_par_jeton(session, jeton)
    point = session.get(PointConseil, present.point_id)
    cr = regles.compte_rendu(session, point, None)
    etat = validation.etat_validation(
        point, cr.presents, validation.commentaires_du_point(session, point.id)
    )
    return lire_objet(
        LienRead,
        point,
        presents=[regles.nom_present(p) for p in cr.presents],
        abordees=[
            AffaireLienRead(numero=a.numero, titre=a.titre, contenu=c.contenu)
            for a, c in cr.abordees
            if not c.conseil_seul
        ],
        non_traitees=[f"{a.numero} {a.titre}" for a in cr.non_traitees],
        deja_valide=present.valide_le is not None or point.etat == VALIDE,
        echeance=etat.echeance,
    )


@router.get("/lien/{jeton}", response_model=LienRead, summary="Le CR, par le lien d'un présent")
@limiter.limit(LIMITE_SESSION)
def lire_par_lien(request: Request, jeton: str, session: Session = Depends(get_session)):
    return _lien_read(session, jeton)


@router.post("/lien/{jeton}/valider", response_model=LienRead, summary="« Je valide »")
@limiter.limit(LIMITE_SESSION)
def valider_par_lien(request: Request, jeton: str, session: Session = Depends(get_session)):
    validation.valider_par_present(session, validation.present_par_jeton(session, jeton))
    session.commit()
    return _lien_read(session, jeton)


@router.post("/lien/{jeton}/commentaire", response_model=LienRead, summary="Commenter le CR")
@limiter.limit(LIMITE_SESSION)
def commenter_par_lien(
    request: Request,
    jeton: str,
    body: CommentaireEntree,
    session: Session = Depends(get_session),
):
    validation.commenter(session, validation.present_par_jeton(session, jeton), body.contenu)
    session.commit()
    return _lien_read(session, jeton)


# ── Les gestes du conseil ─────────────────────────────────────────────────


@router.post("/{point_id}/renvoyer", summary="Renvoyer le CR aux présents (CS/Admin)")
async def renvoyer(
    point_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    point = validation.exiger_a_valider(ou_404(session, PointConseil, point_id, "Point"))
    return {"envoyes": await validation.envoyer_pour_validation(session, point, user)}


@router.post("/{point_id}/valider", status_code=204, summary="Valider le CR en l'état (CS/Admin)")
def valider(
    point_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    point = validation.exiger_a_valider(ou_404(session, PointConseil, point_id, "Point"))
    validation.valider_point(session, point, user)
    session.commit()


@router.post("/{point_id}/pdf", summary="Le PDF d'un CR validé (CS/Admin)")
def pdf(
    point_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    point = ou_404(session, PointConseil, point_id, "Point")
    if point.etat != VALIDE:
        raise HTTPException(409, "Le PDF n'existe qu'une fois le compte rendu validé")
    site = config_site(session)
    contenu = generer_pdf(
        regles.compte_rendu(session, point, user),
        site_nom=nom_site(site.get("site_nom")),
        logo_png=logo_televerse_png(session),
    )
    nom = f"compte-rendu-point-cs-syndic-{point.debut:%Y-%m-%d}.pdf"
    return Response(
        content=contenu,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )


@router.patch(
    "/comptes-rendus/{cr_id}", status_code=204, summary="« Conseil seul » d'un CR (CS/Admin)"
)
def confidentialite(
    cr_id: int,
    body: ConfidentialiteEntree,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    cr = ou_404(session, CompteRenduAffaire, cr_id, "Compte rendu")
    cr.conseil_seul = body.conseil_seul
    session.add(cr)
    session.commit()


# ── La rubrique « Comptes rendus » d'une affaire ──────────────────────────


@router.get(
    "/affaires/{ticket_id}",
    response_model=list[CrPublieRead],
    summary="Les CR validés d'une affaire",
)
def crs_de_l_affaire(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = exiger_objet_autorise(session, Ticket, ticket_id, "Affaire", user, ticket_visible)
    return [
        CrPublieRead(
            point_id=p.id,
            debut=p.debut,
            a_distance=p.a_distance,
            lieu=p.lieu,
            contenu=c.contenu,
            conseil_seul=c.conseil_seul,
            cr_id=c.id,
        )
        for p, c in validation.crs_lisibles(session, ticket, user)
    ]
