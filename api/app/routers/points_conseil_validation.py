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
| `POST /points-conseil/{id}/presents/{present_id}/derogation` | admin | valider POUR un présent qui a donné son accord (#2082) |
| `POST /points-conseil/{id}/pdf` | CS / admin | le PDF d'un CR validé — celui qui a été rangé et envoyé (#2082) |
| `POST /points-conseil/{id}/apercu` | CS / admin | l'aperçu du PDF, à tout instant : « Projet — révision N » (#2082) |
| `PATCH /points-conseil/comptes-rendus/{id}` | CS / admin | « CS et présents » d'un CR |
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
from sqlmodel import Session, col, select

from app.auth.appartenance import exiger_objet_autorise
from app.auth.deps import get_current_user, require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.models.points_conseil import VALIDE, CompteRenduAffaire, PointConseil, PresentPoint
from app.models.tickets import Ticket
from app.utils import points_conseil as regles
from app.utils import points_conseil_expedition as expedition
from app.utils import points_conseil_validation as validation
from app.utils.lecture import lire_objet
from app.utils.lecture_affaire import CS, lecture_courte
from app.utils.limiter import LIMITE_SESSION, limiter
from app.utils.points_conseil_ou import ou_du_point
from app.utils.recuperer import ou_404
from app.utils.stockage import stockage
from app.utils.visibility import ticket_visible

router = APIRouter(prefix="/points-conseil", tags=["points-conseil"])


class AffaireLienRead(BaseModel):
    numero: str
    titre: str
    contenu: str
    #: « CS et présents » : lu des présents, masqué ailleurs (#2082).
    conseil_seul: bool = False
    #: « Modifié en révision N », ou rien (#2082).
    marque: Optional[str] = None
    #: « Qui la lit », le libellé de la pastille de la page Affaires (#2089).
    lecture: str = ""


class LienRead(BaseModel):
    """Ce que le porteur du lien lit : le CR entier — « CS et présents » compris (#2082)."""

    class Config:
        from_attributes = True

    etat: str
    debut: datetime
    fin: Optional[datetime] = None
    a_distance: bool
    lieu: Optional[str] = None
    #: Le Où tel que le CR l'écrit (`ou_du_point`).
    ou: str
    presents: list[str]
    abordees: list[AffaireLienRead]
    non_traitees: list[str]
    #: A-t-il déjà validé ? — un second clic ne change rien.
    deja_valide: bool
    echeance: Optional[datetime] = None
    #: La révision que le présent relit (#2082).
    revision: int = 0


class CommentaireEntree(BaseModel):
    contenu: str = Field(min_length=1, max_length=4000)


class DerogationEntree(BaseModel):
    #: Ce que l'administrateur écrit de l'accord recueilli — facultatif.
    commentaire: Optional[str] = Field(default=None, max_length=4000)


class ConfidentialiteEntree(BaseModel):
    conseil_seul: bool


class CrPublieRead(BaseModel):
    point_id: int
    debut: datetime
    a_distance: bool
    lieu: Optional[str] = None
    ou: str
    contenu: str
    conseil_seul: bool
    cr_id: int
    #: Le lien vers le PDF du CR (#2082, précisé le 21/10/2026) : sur une affaire
    #: lue du SEUL conseil (« qui la lit » = CS) — ses lecteurs peuvent l'ouvrir.
    #: Une affaire lue au-delà n'en a pas : ses autres lecteurs n'y ont pas accès.
    pdf_disponible: bool = False


# ── Le lien d'un présent ──────────────────────────────────────────────────


def _lien_read(session: Session, jeton: str) -> LienRead:
    present = validation.present_par_jeton(session, jeton)
    point = session.get(PointConseil, present.point_id)
    cr = regles.compte_rendu(session, point, None)
    etat = validation.etat_validation(
        point, cr.presents, validation.commentaires_du_point(session, point.id)
    )
    revision = validation.revision_du_document(point, [c for _, c in cr.abordees])
    tickets = {
        t.id: t
        for t in session.exec(
            select(Ticket).where(col(Ticket.id).in_([a.id for a, _ in cr.abordees]))
        ).all()
    }
    return lire_objet(
        LienRead,
        point,
        ou=ou_du_point(point),
        presents=[regles.nom_present(p) for p in cr.presents],
        abordees=[
            AffaireLienRead(
                numero=a.numero,
                titre=a.titre,
                contenu=c.contenu,
                conseil_seul=c.conseil_seul,
                marque=validation.marque_revision(c, revision),
                lecture=lecture_courte(tickets[a.id]) if a.id in tickets else "",
            )
            for a, c in cr.abordees
        ],
        revision=revision,
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
async def valider_par_lien(request: Request, jeton: str, session: Session = Depends(get_session)):
    point = validation.valider_par_present(session, validation.present_par_jeton(session, jeton))
    session.commit()
    #  Le dernier « Je valide » valide le CR : son PDF se range et part (#2082).
    if point.etat == VALIDE and point.pdf_cle is None:
        await expedition.expedier(session, point)
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
async def valider(
    point_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    point = validation.exiger_a_valider(ou_404(session, PointConseil, point_id, "Point"))
    validation.valider_point(session, point, user)
    session.commit()
    await expedition.expedier(session, point)


@router.post(
    "/{point_id}/presents/{present_id}/derogation",
    status_code=204,
    summary="Valider pour un présent qui a donné son accord (Admin)",
)
async def derogation(
    point_id: int,
    present_id: int,
    body: DerogationEntree,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """La dérogation (#2082) : l'administrateur seul, et c'est journalisé."""
    present = ou_404(session, PresentPoint, present_id, "Présent", sous={"point_id": point_id})
    point = validation.valider_pour(session, present, admin, body.commentaire)
    session.commit()
    if point.etat == VALIDE:
        await expedition.expedier(session, point)


def _reponse_pdf(contenu: bytes, nom: str) -> Response:
    return Response(
        content=contenu,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )


@router.post("/{point_id}/pdf", summary="Le PDF d'un CR validé (CS/Admin)")
def pdf(
    point_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Celui qui a été rangé à la validation et envoyé ; un point validé avant
    #2082, qui n'en a pas, le reçoit rendu à la demande."""
    point = ou_404(session, PointConseil, point_id, "Point")
    if point.etat != VALIDE:
        raise HTTPException(409, "Le PDF n'existe qu'une fois le compte rendu validé")
    range_ = stockage().fichier_de(point, "pdf")
    contenu = range_.read_bytes() if range_ else expedition.pdf_du_point(session, point, user)
    return _reponse_pdf(contenu, expedition.nom_du_fichier(point))


@router.post("/{point_id}/apercu", summary="L'aperçu du PDF, à tout instant (CS/Admin)")
def apercu(
    point_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    point = ou_404(session, PointConseil, point_id, "Point")
    contenu = expedition.pdf_du_point(session, point, user, projet=point.etat != VALIDE)
    return _reponse_pdf(contenu, f"projet-{expedition.nom_du_fichier(point)}")


@router.patch(
    "/comptes-rendus/{cr_id}", status_code=204, summary="« CS et présents » d'un CR (CS/Admin)"
)
def confidentialite(
    cr_id: int,
    body: ConfidentialiteEntree,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    cr = ou_404(session, CompteRenduAffaire, cr_id, "Compte rendu")
    cr.conseil_seul = body.conseil_seul
    #  En relecture, le changement rejoint la révision suivante (#2082).
    validation.marquer_modifie(session.get(PointConseil, cr.point_id), cr)
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
    du_seul_conseil = lecture_courte(ticket) == CS
    return [
        CrPublieRead(
            point_id=p.id,
            debut=p.debut,
            a_distance=p.a_distance,
            lieu=p.lieu,
            ou=ou_du_point(p),
            contenu=c.contenu,
            conseil_seul=c.conseil_seul,
            cr_id=c.id,
            pdf_disponible=du_seul_conseil,
        )
        for p, c in validation.crs_lisibles(session, ticket, user)
    ]
