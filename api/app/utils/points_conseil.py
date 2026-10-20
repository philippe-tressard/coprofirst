"""Les règles du **point conseil syndical / syndic** (#2041) — écrites UNE fois.

Le modèle est dans `app/models/points_conseil.py` ; les routes, dans
`routers/points_conseil.py`, ne font qu'appeler ce module.

## La liste d'un point est celle de son mode

Un point traite les affaires que montre le mode du rapport où il est ouvert :
`MODES` dit lesquels en portent un ; le relevé du mode les liste. Il n'y a PAS de
seconde règle d'entrée — une affaire hors du relevé ne reçoit pas de compte
rendu (`exiger_affaire_du_point`).

## La reprise à moins de deux heures (arbitré le 17/10/2026)

Un point ouvert dans un mode moins de `REPRISE_HEURES` heures après l'ouverture
d'un point d'un AUTRE mode en reprend le Quand, le Où et le Qui : c'est la même
réunion, qui passe des affaires à l'entretien. Chaque point garde son propre CR.

## La liste du point est FIGÉE à l'ouverture (#2082, arbitré le 20/10/2026)

Les affaires du relevé, au moment où le point s'ouvre, s'écrivent sur lui
(`affaires_initiales_json`) : une affaire close ailleurs pendant le point y
reste — au tableau, au CR, au PDF — jusqu'à la validation. Le relevé du point
est donc celui du mode, PLUS ces affaires-là (`releve_du_point`) ; un point
d'avant, sans liste, lit le relevé du jour.

## Les non traitées sont FIGÉES à « Terminer »

Tant que le point est en cours, les non traitées se lisent dans le relevé du
point. À « Terminer », elles sont écrites sur lui : le CR qu'on valide ne doit
pas changer parce qu'une affaire a été close entre-temps.

## Un CR validé ne se modifie plus (#2082)

Terminé, un CR se CORRIGE (#2042) — jusqu'à la validation, et plus après.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models.core import Utilisateur
from app.models.gouvernance import MembreCS, MembreSyndic
from app.models.points_conseil import (
    A_VALIDER,
    EN_COURS,
    VALIDE,
    MODE_AFFAIRES,
    MODE_ENTRETIEN,
    PRESENT_CS,
    PRESENT_INVITE,
    PRESENT_SYNDIC,
    CompteRenduAffaire,
    PointConseil,
    PresentPoint,
)
from app.models.tickets import Ticket
from app.utils import horloge
from app.utils.noms import nom_affiche
from app.utils.recuperer import ou_404, present_ou_404
from app.utils.syndic import nom_du_syndic
from app.utils.suivi_affaires.releve import Releve, releve

#: Les modes qui portent un point — un mode neuf s'ajoute ICI, et le relevé
#: (`utils/suivi_affaires/releve`) le connaît déjà.
MODES = (MODE_AFFAIRES, MODE_ENTRETIEN)

#: En deçà, un point d'un autre mode est la même réunion : on reprend son Qui/Quand/Où.
REPRISE_HEURES = 2


def exiger_mode(mode: str) -> str:
    """Le mode, s'il porte un point — 422 sinon."""
    if mode not in MODES:
        raise HTTPException(422, "Mode du rapport inconnu")
    return mode


def releve_du_point(session: Session, point: PointConseil, user: Optional[Utilisateur]) -> Releve:
    """Le relevé du mode, plus les affaires figées à l'ouverture du point."""
    return releve(
        session, user, point.mode, inclure=[a.id for a in affaires_initiales(point) or []]
    )


# ── La liste initiale, figée à l'ouverture ────────────────────────────────


def _lire_citees(texte: Optional[str]) -> list["AffaireCitee"]:
    try:
        lues = json.loads(texte or "[]")
    except ValueError:
        return []
    return [AffaireCitee(int(a["id"]), str(a["numero"]), str(a["titre"])) for a in lues]


def _ecrire_citees(affaires) -> str:
    return json.dumps(
        [{"id": a.id, "numero": a.numero, "titre": a.titre} for a in affaires], ensure_ascii=False
    )


def affaires_initiales(point: PointConseil) -> Optional[list["AffaireCitee"]]:
    """Les affaires à traiter, figées à l'ouverture — `None` pour un point d'avant."""
    if point.affaires_initiales_json is None:
        return None
    return _lire_citees(point.affaires_initiales_json)


def figer_affaires_initiales(session: Session, point: PointConseil, user: Utilisateur) -> None:
    """Écrit sur le point les affaires que son mode montre à l'ouverture."""
    point.affaires_initiales_json = _ecrire_citees(releve(session, user, point.mode).affaires)


def ajouter_affaire_initiale(point: PointConseil, ticket: Ticket) -> None:
    """Une affaire ouverte en séance rejoint la liste du point (#2084)."""
    citees = affaires_initiales(point) or []
    if ticket.id not in {a.id for a in citees}:
        point.affaires_initiales_json = _ecrire_citees(
            [*citees, AffaireCitee(ticket.id, ticket.numero, ticket.titre)]
        )


# ── Le point en cours, et celui à reprendre ───────────────────────────────


def point_courant(session: Session, mode: str) -> Optional[PointConseil]:
    """Le point en cours du mode, sinon le dernier à valider — ce que l'écran montre."""
    for etat in (EN_COURS, A_VALIDER):
        point = session.exec(
            select(PointConseil)
            .where(PointConseil.mode == mode, PointConseil.etat == etat)
            .order_by(col(PointConseil.cree_le).desc())
        ).first()
        if point:
            return point
    return None


def a_reprendre(
    candidats: list[PointConseil], mode: str, maintenant: datetime
) -> Optional[PointConseil]:
    """PURE. Le point d'un AUTRE mode ouvert depuis moins de deux heures, le plus récent."""
    limite = maintenant - timedelta(hours=REPRISE_HEURES)
    retenus = [p for p in candidats if p.mode != mode and p.cree_le >= limite]
    return max(retenus, key=lambda p: p.cree_le, default=None)


def point_a_reprendre(session: Session, mode: str) -> Optional[PointConseil]:
    maintenant = horloge.maintenant()
    candidats = session.exec(
        select(PointConseil).where(
            PointConseil.cree_le >= maintenant - timedelta(hours=REPRISE_HEURES)
        )
    ).all()
    return a_reprendre(list(candidats), mode, maintenant)


def exiger_en_cours(point: PointConseil) -> PointConseil:
    """Un point terminé ne se modifie plus ici (la correction suit la validation, #2042)."""
    if point.etat != EN_COURS:
        raise HTTPException(409, "Ce point est terminé : il ne se modifie plus")
    return point


# ── Le Qui ────────────────────────────────────────────────────────────────


def present_depuis_annuaire(
    session: Session, nature: str, membre_id: Optional[int]
) -> PresentPoint:
    """Un membre du CS ou du syndic, son nom et sa fonction FIGÉS depuis l'annuaire."""
    if nature == PRESENT_CS:
        m = ou_404(session, MembreCS, membre_id, "Membre du conseil syndical")
        return PresentPoint(nature=nature, membre_cs_id=m.id, prenom=m.prenom, nom=m.nom)
    m = ou_404(session, MembreSyndic, membre_id, "Membre du syndic")
    return PresentPoint(
        nature=nature,
        membre_syndic_id=m.id,
        prenom=m.prenom,
        nom=m.nom,
        fonction=m.fonction,
        entreprise=nom_du_syndic(session) or None,
    )


def remplacer_presents(session: Session, point: PointConseil, presents: list[PresentPoint]) -> None:
    """Le Qui se remplace d'un bloc : l'écran envoie la liste entière."""
    for ancien in session.exec(select(PresentPoint).where(PresentPoint.point_id == point.id)).all():
        session.delete(ancien)
    for p in presents:
        p.point_id = point.id
        session.add(p)


def presents_du_point(session: Session, point_id: int) -> list[PresentPoint]:
    return list(
        session.exec(
            select(PresentPoint).where(PresentPoint.point_id == point_id).order_by(PresentPoint.id)
        ).all()
    )


def nom_present(p: PresentPoint) -> str:
    """Le nom d'un présent : « Prénom NOM » (`nom_affiche`), sinon l'entreprise, sinon « Invité »."""
    return nom_affiche(p.prenom, p.nom) or (p.entreprise or "Invité")


def copie_des_presents(presents: list[PresentPoint]) -> list[PresentPoint]:
    """PURE. Les présents d'un point, recopiés pour un autre (la reprise)."""
    return [
        PresentPoint(**p.model_dump(exclude={"id", "point_id"}))
        for p in presents
        if p.nature in (PRESENT_CS, PRESENT_SYNDIC, PRESENT_INVITE)
    ]


# ── Le CR d'une affaire ───────────────────────────────────────────────────


def exiger_affaire_du_point(
    session: Session, point: PointConseil, ticket_id: int, user: Utilisateur
) -> Ticket:
    """L'affaire, si le relevé du mode la montre à `user` — 404 sinon, sans rien dire de plus."""
    du_rapport = {a.id for a in releve_du_point(session, point, user).affaires}
    present_ou_404(ticket_id if ticket_id in du_rapport else None, "Affaire absente de ce rapport")
    return ou_404(session, Ticket, ticket_id, "Affaire")


def exiger_cr_modifiable(
    point: PointConseil, cr: Optional[CompteRenduAffaire], contenu: str
) -> Optional[CompteRenduAffaire]:
    """Ce qu'on peut écrire : tout, tant que le point est en cours ; ensuite, la
    CORRECTION d'un CR déjà saisi, jamais vidé — dans le rapport seulement (#2042) ;
    plus rien une fois le CR validé (#2082)."""
    if point.etat == VALIDE:
        raise HTTPException(409, "Ce compte rendu est validé : il ne se modifie plus")
    if point.etat == EN_COURS:
        return cr
    if cr is None or not contenu.strip():
        raise HTTPException(409, "Ce point est terminé : seuls ses comptes rendus se corrigent")
    return cr


def cr_de(session: Session, point_id: int, ticket_id: int) -> Optional[CompteRenduAffaire]:
    return session.exec(
        select(CompteRenduAffaire).where(
            CompteRenduAffaire.point_id == point_id, CompteRenduAffaire.ticket_id == ticket_id
        )
    ).first()


def nombres_abordees(session: Session, point_ids: list[int]) -> dict[int, int]:
    """Le nombre d'affaires abordées de chaque point, lu UNE fois pour une liste
    — le fil et l'historique des CR (#2082)."""
    if not point_ids:
        return {}
    return dict(
        session.exec(
            select(CompteRenduAffaire.point_id, func.count(CompteRenduAffaire.id))
            .where(col(CompteRenduAffaire.point_id).in_(point_ids))
            .group_by(CompteRenduAffaire.point_id)
        ).all()
    )


def crs_du_point(session: Session, point_id: int) -> list[CompteRenduAffaire]:
    return list(
        session.exec(
            select(CompteRenduAffaire).where(CompteRenduAffaire.point_id == point_id)
        ).all()
    )


# ── Le CR global (maquette C1) ────────────────────────────────────────────


@dataclass(frozen=True)
class AffaireCitee:
    id: int
    numero: str
    titre: str


@dataclass
class CrGlobal:
    point: PointConseil
    presents: list[PresentPoint]
    #: (l'affaire, son CR), dans l'ordre d'ouverture des affaires.
    abordees: list[tuple[AffaireCitee, CompteRenduAffaire]] = field(default_factory=list)
    non_traitees: list[AffaireCitee] = field(default_factory=list)
    #: La liste à traiter, figée à l'ouverture (#2082) — vide pour un point d'avant.
    initiales: list[AffaireCitee] = field(default_factory=list)


def lire_non_traitees(point: PointConseil) -> list[AffaireCitee]:
    return _lire_citees(point.non_traitees_json)


def compte_rendu(session: Session, point: PointConseil, user: Optional[Utilisateur]) -> CrGlobal:
    """Le CR global : le point, ses présents, les affaires abordées, les non traitées.

    `user` ne sert qu'à un point EN COURS — ses non traitées se lisent dans le
    relevé de qui regarde. Terminé, le point les porte figées : le porteur d'un
    lien de validation, qui n'a pas de compte, passe `None`.
    """
    crs = {cr.ticket_id: cr for cr in crs_du_point(session, point.id)}
    tickets = (
        session.exec(
            select(Ticket).where(col(Ticket.id).in_(list(crs))).order_by(Ticket.cree_le, Ticket.id)
        ).all()
        if crs
        else []
    )
    abordees = [(AffaireCitee(t.id, t.numero, t.titre), crs[t.id]) for t in tickets]
    if point.etat == EN_COURS and user is not None:
        non_traitees = [
            AffaireCitee(a.id, a.numero, a.titre)
            for a in releve_du_point(session, point, user).affaires
            if a.id not in crs
        ]
    else:
        non_traitees = lire_non_traitees(point)
    return CrGlobal(
        point,
        presents_du_point(session, point.id),
        abordees,
        non_traitees,
        affaires_initiales(point) or [],
    )


def terminer(session: Session, point: PointConseil, user: Utilisateur) -> PointConseil:
    """« Terminer le point » : les non traitées se figent, le CR passe à valider."""
    exiger_en_cours(point)
    cr = compte_rendu(session, point, user)
    point.non_traitees_json = _ecrire_citees(cr.non_traitees)
    point.etat = A_VALIDER
    point.termine_le = point.mis_a_jour_le = horloge.maintenant()
    session.add(point)
    return point


def supprimer_point(session: Session, point: PointConseil) -> None:
    """Abandonner un point ouvert par erreur — en cours seulement."""
    exiger_en_cours(point)
    for cr in crs_du_point(session, point.id):
        session.delete(cr)
    for p in presents_du_point(session, point.id):
        session.delete(p)
    session.delete(point)
