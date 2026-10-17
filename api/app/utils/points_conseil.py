"""Les règles du **point conseil syndical / syndic** (#2041) — écrites UNE fois.

Le modèle est dans `app/models/points_conseil.py` ; les routes, dans
`routers/points_conseil.py`, ne font qu'appeler ce module.

## La liste d'un point est celle de son mode

Un point traite les affaires que montre le mode du rapport où il est ouvert :
`RELEVES` associe à chaque mode la fonction qui les relève. Il n'y a PAS de
seconde règle d'entrée — une affaire hors du relevé ne reçoit pas de compte
rendu (`exiger_affaire_du_point`).

## La reprise à moins de deux heures (arbitré le 17/10/2026)

Un point ouvert dans un mode moins de `REPRISE_HEURES` heures après l'ouverture
d'un point d'un AUTRE mode en reprend le Quand, le Où et le Qui : c'est la même
réunion, qui passe des affaires à l'entretien. Chaque point garde son propre CR.

## Les non traitées sont FIGÉES à « Terminer »

Tant que le point est en cours, les non traitées sont lues dans le relevé du
jour. À « Terminer », elles sont écrites sur le point : le CR qu'on valide ne
doit pas changer parce qu'une affaire a été close entre-temps.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.models.core import Utilisateur
from app.models.copropriete import Copropriete
from app.models.gouvernance import MembreCS, MembreSyndic, SyndicInfo
from app.models.points_conseil import (
    A_VALIDER,
    EN_COURS,
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
from app.utils.recuperer import ou_404, present_ou_404
from app.utils.syndic import nom_du_syndic
from app.utils.suivi_affaires.releve import Releve, releve

#: Le relevé de chaque mode qui porte un point. Un mode neuf s'ajoute ICI.
RELEVES: dict[str, Callable[[Session, Utilisateur], Releve]] = {
    MODE_AFFAIRES: releve,
    #  Le Suivi des entretiens périodiques (#2043) porte le même point.
    MODE_ENTRETIEN: lambda session, user: releve(session, user, MODE_ENTRETIEN),
}

#: En deçà, un point d'un autre mode est la même réunion : on reprend son Qui/Quand/Où.
REPRISE_HEURES = 2

#: Les derniers lieux saisis proposés à l'ouverture d'un point.
DERNIERS_LIEUX = 5


def exiger_mode(mode: str) -> str:
    """Le mode, s'il porte un point — 422 sinon."""
    if mode not in RELEVES:
        raise HTTPException(422, "Mode du rapport inconnu")
    return mode


def releve_du_point(session: Session, point: PointConseil, user: Utilisateur) -> Releve:
    return RELEVES[point.mode](session, user)


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
    """Le nom d'un présent : prénom et nom, sinon l'entreprise, sinon « Invité »."""
    return " ".join(x for x in (p.prenom, p.nom) if x) or (p.entreprise or "Invité")


def copie_des_presents(presents: list[PresentPoint]) -> list[PresentPoint]:
    """PURE. Les présents d'un point, recopiés pour un autre (la reprise)."""
    return [
        PresentPoint(**p.model_dump(exclude={"id", "point_id"}))
        for p in presents
        if p.nature in (PRESENT_CS, PRESENT_SYNDIC, PRESENT_INVITE)
    ]


# ── Le Où ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LieuPropose:
    libelle: str
    adresse: str


def lieux_proposes(session: Session) -> list[LieuPropose]:
    """La copropriété, le cabinet du syndic, puis les derniers lieux saisis.

    Rien n'est demandé à un service extérieur : les adresses viennent de la
    fiche copropriété et de la fiche du syndic, déjà en base.
    """
    lieux: list[LieuPropose] = []
    copro = session.exec(select(Copropriete)).first()
    if copro and (copro.adresse or "").strip():
        lieux.append(LieuPropose("Copropriété", copro.adresse.strip()))
    info = session.exec(select(SyndicInfo)).first()
    if info and (info.adresse or "").strip():
        lieux.append(
            LieuPropose(nom_du_syndic(session) or "Cabinet du syndic", info.adresse.strip())
        )
    deja = {lieu.adresse for lieu in lieux}
    for lieu in _derniers_lieux(session):
        if lieu not in deja:
            deja.add(lieu)
            lieux.append(LieuPropose("Dernier lieu", lieu))
    return lieux


def _derniers_lieux(session: Session) -> list[str]:
    vus: list[str] = []
    for lieu in session.exec(
        select(PointConseil.lieu)
        .where(col(PointConseil.lieu).is_not(None))
        .order_by(col(PointConseil.cree_le).desc())
    ).all():
        propre = (lieu or "").strip()
        if propre and propre not in vus:
            vus.append(propre)
        if len(vus) >= DERNIERS_LIEUX:
            break
    return vus


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
    CORRECTION d'un CR déjà saisi, jamais vidé — dans le rapport seulement (#2042)."""
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


def lire_non_traitees(point: PointConseil) -> list[AffaireCitee]:
    try:
        lues = json.loads(point.non_traitees_json or "[]")
    except ValueError:
        return []
    return [AffaireCitee(int(a["id"]), str(a["numero"]), str(a["titre"])) for a in lues]


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
    return CrGlobal(point, presents_du_point(session, point.id), abordees, non_traitees)


def terminer(session: Session, point: PointConseil, user: Utilisateur) -> PointConseil:
    """« Terminer le point » : les non traitées se figent, le CR passe à valider."""
    exiger_en_cours(point)
    cr = compte_rendu(session, point, user)
    point.non_traitees_json = json.dumps(
        [{"id": a.id, "numero": a.numero, "titre": a.titre} for a in cr.non_traitees],
        ensure_ascii=False,
    )
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
