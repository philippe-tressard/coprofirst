"""Le **point conseil syndical / syndic** du Reporting CS (#2041, maquettes A1 et C1).

Un membre du CS ouvre un point pendant une réunion avec le syndic et prend le
compte rendu en direct, affaire par affaire. Toutes les routes sont réservées au
conseil syndical et à l'administration. Les règles vivent dans
`utils/points_conseil` ; ce routeur ne fait que les appeler.

| Route | Ce qu'elle fait |
|---|---|
| `GET /points-conseil/participants` | l'annuaire du CS et du syndic, les lieux proposés |
| `GET /points-conseil/courant?mode=` | le point du mode, son CR global, et le point à reprendre |
| `GET /points-conseil/historique?mode=` | les points validés du mode, avec leur PDF (#2082) |
| `POST /points-conseil` | ouvrir un point |
| `PATCH /points-conseil/{id}` | corriger son Quand, son Où, son Qui |
| `PUT /points-conseil/{id}/affaires/{ticket_id}` | écrire le CR d'une affaire (vide : le retirer) |
| `POST /points-conseil/{id}/affaires` | ouvrir une affaire en séance : elle rejoint la liste du point (#2084) |
| `POST /points-conseil/{id}/terminer` | terminer : le CR passe à valider et part aux présents (#2042) |
| `DELETE /points-conseil/{id}` | abandonner un point ouvert par erreur |
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.models.points_conseil import (
    EN_COURS,
    NATURES_PRESENT,
    PRESENT_INVITE,
    VALIDE,
    CompteRenduAffaire,
    PointConseil,
    PresentPoint,
)
from app.routers.points_conseil_schemas import (
    AbordeeRead,
    AffaireCiteeRead,
    AffaireSeanceEntree,
    CategorieRead,
    CommentaireRead,
    CompteRenduRead,
    CourantRead,
    CrEntree,
    CrRead,
    EtatRead,
    LieuRead,
    MembreRead,
    MoyenRead,
    ParticipantsRead,
    PointCreate,
    PointHistoriqueRead,
    PointRead,
    PointUpdate,
    PresentEntree,
    PresentRead,
    RepriseRead,
    ValidationRead,
)
from app.utils import horloge
from app.utils import points_conseil as regles
from app.utils import points_conseil_ou as ou
from app.utils import points_conseil_validation as validation
from app.utils.points_conseil_etats import ETATS_A_LA_VALIDATION, exiger_etat_cible
from app.utils import points_conseil_seance as seance
from app.utils.annuaire import membres_du_conseil, membres_du_syndic
from app.utils.lecture import lire_objet
from app.utils.recuperer import ou_404
from app.routers.tickets.commun import STATUT_LABELS

router = APIRouter(prefix="/points-conseil", tags=["points-conseil"])

# ── Lectures ─────────────────────────────────────────────────────────────


def _presents_read(presents: list[PresentPoint]) -> list[PresentRead]:
    return [
        lire_objet(
            PresentRead,
            p,
            destinataire=validation.est_destinataire(p),
            par_derogation=p.valide_par_id is not None,
        )
        for p in presents
    ]


def _point_read(point: PointConseil) -> PointRead:
    return lire_objet(
        PointRead, point, ou=ou.ou_du_point(point), pdf_range=point.pdf_cle is not None
    )


def _compte_rendu_read(session: Session, point: PointConseil, user: Utilisateur):
    cr = regles.compte_rendu(session, point, user)
    commentaires = validation.commentaires_du_point(session, point.id)
    noms = {p.id: p for p in cr.presents}
    revision = validation.revision_du_document(point, [c for _, c in cr.abordees])
    return CompteRenduRead(
        point=_point_read(cr.point),
        presents=_presents_read(cr.presents),
        abordees=[
            AbordeeRead(
                affaire=AffaireCiteeRead.model_validate(a),
                cr=CrRead.model_validate(c),
                marque=validation.marque_revision(c, revision),
            )
            for a, c in cr.abordees
        ],
        revision=revision,
        non_traitees=[AffaireCiteeRead.model_validate(a) for a in cr.non_traitees],
        validation=ValidationRead.model_validate(
            validation.etat_validation(point, cr.presents, commentaires)
        ),
        commentaires=[
            CommentaireRead(
                auteur=regles.nom_present(noms[c.present_id]) if c.present_id in noms else "",
                contenu=c.contenu,
                cree_le=c.cree_le,
                par_derogation=c.saisi_par_id is not None,
            )
            for c in commentaires
        ],
    )


@router.get(
    "/participants", response_model=ParticipantsRead, summary="Annuaire et lieux (CS/Admin)"
)
def participants(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return ParticipantsRead(
        conseil=[MembreRead(**m) for m in membres_du_conseil(session)],
        syndic=[MembreRead(**m) for m in membres_du_syndic(session)],
        lieux=[LieuRead.model_validate(lieu) for lieu in ou.lieux_proposes(session)],
        moyens=[MoyenRead.model_validate(m) for m in ou.MOYENS],
        etats_validation=[
            EtatRead(cle=e, libelle=STATUT_LABELS.get(e, e)) for e in ETATS_A_LA_VALIDATION
        ],
        categories_seance=[
            CategorieRead(cle=c, libelle=nom) for c, nom in seance.categories_seance()
        ],
    )


@router.get("/courant", response_model=CourantRead, summary="Le point du mode (CS/Admin)")
def courant(
    mode: str,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    regles.exiger_mode(mode)
    point = regles.point_courant(session, mode)
    reprise = regles.point_a_reprendre(session, mode)
    return CourantRead(
        compte_rendu=_compte_rendu_read(session, point, user) if point else None,
        reprise=(
            RepriseRead(
                **lire_objet(PointRead, reprise, ou="").model_dump(
                    include={"mode", "debut", "fin", "moyen", "a_distance", "lieu", "cree_le"}
                ),
                presents=_presents_read(regles.presents_du_point(session, reprise.id)),
            )
            if reprise
            else None
        ),
    )


@router.get(
    "/historique",
    response_model=list[PointHistoriqueRead],
    summary="Les points validés du mode (CS/Admin)",
)
def historique(
    mode: str,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """L'historique des CR, le plus récent en tête — plié par défaut à l'écran (#2082)."""
    regles.exiger_mode(mode)
    points = session.exec(
        select(PointConseil)
        .where(PointConseil.mode == mode, PointConseil.etat == VALIDE)
        .order_by(col(PointConseil.debut).desc())
    ).all()
    nombres = regles.nombres_abordees(session, [p.id for p in points])
    return [
        PointHistoriqueRead(
            id=p.id,
            debut=p.debut,
            ou=ou.ou_du_point(p),
            valide_le=p.valide_le,
            abordees=nombres.get(p.id, 0),
            pdf_range=p.pdf_cle is not None,
        )
        for p in points
    ]


# ── Gestes ───────────────────────────────────────────────────────────────


def _present(session: Session, entree: PresentEntree) -> PresentPoint:
    if entree.nature not in NATURES_PRESENT:
        raise HTTPException(422, "Nature de présent inconnue")
    if entree.nature != PRESENT_INVITE:
        return regles.present_depuis_annuaire(session, entree.nature, entree.membre_id)
    champs = entree.model_dump(exclude={"nature", "membre_id"})
    return PresentPoint(
        nature=PRESENT_INVITE, **{k: (v or "").strip() or None for k, v in champs.items()}
    )


@router.post(
    "", response_model=CompteRenduRead, status_code=201, summary="Ouvrir un point (CS/Admin)"
)
def ouvrir(
    body: PointCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    regles.exiger_mode(body.mode)
    courant_ = regles.point_courant(session, body.mode)
    if courant_ and courant_.etat == EN_COURS:
        raise HTTPException(409, "Un point est déjà en cours pour ce rapport")
    presents = [_present(session, p) for p in body.presents]
    point = PointConseil(
        mode=body.mode,
        debut=body.debut,
        fin=body.fin,
        a_distance=body.a_distance,
        auteur_id=user.id,
    )
    ou.poser_ou(point, body.moyen, body.lieu)
    #  La liste à traiter se fige à l'ouverture (#2082).
    regles.figer_affaires_initiales(session, point, user)
    session.add(point)
    session.flush()
    regles.remplacer_presents(session, point, presents)
    session.flush()
    #  L'affaire « Points annexes » du Suivi affaires, dès l'ouverture (#2084).
    seance.ouvrir_annexe(session, point, user)
    session.commit()
    session.refresh(point)
    return _compte_rendu_read(session, point, user)


@router.patch("/{point_id}", response_model=CompteRenduRead, summary="Corriger le point (CS/Admin)")
def corriger(
    point_id: int,
    body: PointUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    point = regles.exiger_en_cours(ou_404(session, PointConseil, point_id, "Point"))
    champs = body.model_dump(exclude_unset=True, exclude={"presents", "moyen", "lieu"})
    for cle, valeur in champs.items():
        setattr(point, cle, valeur)
    if "a_distance" in body.model_fields_set and "moyen" not in body.model_fields_set:
        point.moyen = None  # un client d'avant le moyen : `a_distance` fait foi
    if {"moyen", "lieu"} & body.model_fields_set:
        ou.poser_ou(
            point,
            body.moyen if "moyen" in body.model_fields_set else point.moyen,
            body.lieu if "lieu" in body.model_fields_set else point.lieu,
        )
    if body.presents is not None:
        regles.remplacer_presents(session, point, [_present(session, p) for p in body.presents])
    point.mis_a_jour_le = horloge.maintenant()
    session.add(point)
    session.commit()
    session.refresh(point)
    return _compte_rendu_read(session, point, user)


@router.put(
    "/{point_id}/affaires/{ticket_id}",
    response_model=CompteRenduRead,
    summary="Écrire le CR d'une affaire (CS/Admin)",
)
def ecrire_cr(
    point_id: int,
    ticket_id: int,
    body: CrEntree,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    point = ou_404(session, PointConseil, point_id, "Point")
    regles.exiger_affaire_du_point(session, point, ticket_id, user)
    cr = regles.exiger_cr_modifiable(
        point, regles.cr_de(session, point.id, ticket_id), body.contenu
    )
    exiger_etat_cible(body.etat_cible)
    if not body.contenu.strip():
        if cr:
            session.delete(cr)
    else:
        cr = cr or CompteRenduAffaire(point_id=point.id, ticket_id=ticket_id)
        cr.contenu = body.contenu
        cr.brouillon = body.brouillon
        cr.conseil_seul = body.conseil_seul
        cr.etat_cible = body.etat_cible
        cr.auteur_id = user.id
        validation.marquer_modifie(point, cr)
        cr.mis_a_jour_le = horloge.maintenant()
        session.add(cr)
    point.mis_a_jour_le = horloge.maintenant()
    session.add(point)
    session.commit()
    session.refresh(point)
    return _compte_rendu_read(session, point, user)


@router.post(
    "/{point_id}/affaires",
    response_model=CompteRenduRead,
    status_code=201,
    summary="Ouvrir une affaire en séance (CS/Admin)",
)
def ouvrir_affaire(
    point_id: int,
    body: AffaireSeanceEntree,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Elle rejoint la liste du point, en fin de tableau (#2084)."""
    point = regles.exiger_en_cours(ou_404(session, PointConseil, point_id, "Point"))
    seance.creer_affaire(
        session,
        point,
        user,
        titre=body.titre,
        categorie=body.categorie,
        description=body.description,
    )
    session.commit()
    session.refresh(point)
    return _compte_rendu_read(session, point, user)


@router.post(
    "/{point_id}/terminer", response_model=CompteRenduRead, summary="Terminer le point (CS/Admin)"
)
async def terminer(
    point_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Le CR passe à valider, et part aux présents joignables (#2042)."""
    point = regles.terminer(session, ou_404(session, PointConseil, point_id, "Point"), user)
    session.commit()
    await validation.envoyer_pour_validation(session, point, user)
    session.refresh(point)
    return _compte_rendu_read(session, point, user)


@router.delete("/{point_id}", status_code=204, summary="Abandonner un point en cours (CS/Admin)")
def abandonner(
    point_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    point = regles.exiger_en_cours(ou_404(session, PointConseil, point_id, "Point"))
    #  Son affaire annexe restée vide est annulée, jamais supprimée (#2084).
    seance.annuler_annexe_vide(session, point, user)
    regles.supprimer_point(session, point)
    session.commit()
