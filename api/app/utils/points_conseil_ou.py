"""Le OÙ d'un point CS / Syndic (#2041) — le moyen, le lieu, les lieux proposés.

Sorti de `utils/points_conseil` (#2082) pour que ce module reste sous 500
lignes : le Où ne dépend de rien d'autre du point, et quatre appelants le lisent
(les deux routeurs, le PDF, le courriel de validation).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.models.copropriete import Copropriete
from app.models.gouvernance import SyndicInfo
from app.models.points_conseil import (
    MOYEN_HYBRIDE,
    MOYEN_SUR_PLACE,
    MOYEN_TELEPHONE,
    MOYEN_VISIO,
    PointConseil,
)
from app.utils.syndic import nom_du_syndic

#: Les derniers lieux saisis proposés à l'ouverture d'un point.
DERNIERS_LIEUX = 5


# ── Le Où ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Moyen:
    cle: str
    libelle: str
    #: Quelqu'un est sur place : le lieu se saisit, et se lit au CR.
    avec_lieu: bool


#: Le MOYEN d'un point, dans l'ordre de la liste (arbitré le 17/10/2026, liste
#: « A »). La seule liste : le formulaire la lit par `GET /points-conseil/participants`.
MOYENS: tuple[Moyen, ...] = (
    Moyen(MOYEN_SUR_PLACE, "Sur place", True),
    Moyen(MOYEN_VISIO, "Visioconférence", False),
    Moyen(MOYEN_TELEPHONE, "Téléphone", False),
    Moyen(MOYEN_HYBRIDE, "Sur place et à distance", True),
)
_MOYENS = {m.cle: m for m in MOYENS}


def exiger_moyen(moyen: str) -> Moyen:
    """Le moyen, s'il est connu — 422 sinon."""
    if moyen not in _MOYENS:
        raise HTTPException(422, "Moyen de réunion inconnu")
    return _MOYENS[moyen]


def poser_ou(point: PointConseil, moyen: Optional[str], lieu: Optional[str]) -> None:
    """Écrit le Où : le moyen, `a_distance` qui s'en déduit, et le lieu s'il en porte un.

    Sans moyen (un client d'avant le moyen), `a_distance` reste tel qu'envoyé.
    """
    lieu = (lieu or "").strip() or None
    if moyen is not None:
        m = exiger_moyen(moyen)
        point.moyen = m.cle
        point.a_distance = m.cle != MOYEN_SUR_PLACE
        lieu = lieu if m.avec_lieu else None
    point.lieu = lieu


def ou_du_point(point: PointConseil) -> str:
    """PURE. Le Où tel que le CR, le PDF et le courriel l'écrivent :
    « Sur place — Cabinet du syndic », « Visioconférence ».

    Un point saisi avant le moyen se lit par `a_distance`.
    """
    m = _MOYENS.get(point.moyen or "")
    if m:
        libelle, lieu = m.libelle, point.lieu if m.avec_lieu else None
    else:
        libelle, lieu = ("À distance" if point.a_distance else "Sur place"), point.lieu
    return f"{libelle} — {lieu}" if lieu else libelle


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
