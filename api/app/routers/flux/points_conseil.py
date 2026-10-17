"""Flux — rubrique Point CS / Syndic : un compte rendu validé (#2042).

UNE entrée par point validé — jamais une par affaire : arbitré le 17/10/2026,
pour qu'une réunion de vingt affaires ne noie pas le fil. Elle paraît à la
VALIDATION (`valide_le`) et ne se lit que du conseil syndical et des comptes du
syndic (`lit_les_points_conseil`) ; elle mène au Reporting, que le conseil seul
ouvre — le syndic lit la carte, sans lien.
"""

from sqlalchemy import func
from sqlmodel import col, select

from app.models.points_conseil import VALIDE, CompteRenduAffaire, PointConseil
from app.auth.deps import est_moderateur
from app.utils.dates_fr import date_longue
from app.utils.liens import lien_element
from app.utils.points_conseil_validation import lit_les_points_conseil

from .commun import ContexteFlux
from .schemas import FluxItem


def collecter(ctx: ContexteFlux) -> list[FluxItem]:
    if not lit_les_points_conseil(ctx.user):
        return []
    points = ctx.session.exec(
        select(PointConseil)
        .where(PointConseil.etat == VALIDE, col(PointConseil.valide_le) >= ctx.since)
        .order_by(col(PointConseil.valide_le).desc())
    ).all()
    lien = est_moderateur(ctx.user)
    #  Le nombre d'affaires de chaque point, lu UNE fois pour la liste.
    nombres = (
        dict(
            ctx.session.exec(
                select(CompteRenduAffaire.point_id, func.count(CompteRenduAffaire.id))
                .where(col(CompteRenduAffaire.point_id).in_([p.id for p in points]))
                .group_by(CompteRenduAffaire.point_id)
            ).all()
        )
        if points
        else {}
    )
    items = []
    for p in points:
        n = nombres.get(p.id, 0)
        items.append(
            FluxItem(
                id=f"pcs_{p.id}",
                type="point_conseil",
                date=p.valide_le,
                cree_le=p.valide_le,
                titre=f"Point CS / Syndic du {date_longue(p.debut)}",
                detail=f"Compte rendu validé — {n} affaire{'s' if n > 1 else ''} abordée"
                f"{'s' if n > 1 else ''}.",
                icon="🤝",
                lien=lien_element("point-cs", p.id) if lien else None,
                meta={"point_id": p.id},
            )
        )
    return items
