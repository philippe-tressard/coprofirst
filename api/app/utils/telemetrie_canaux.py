"""La RÉPARTITION des vues par canal d'accès — écrite par l'agrégation, lue par le tableau.

Demandé le 14/11/2026 (`utils/canaux_audience`). Trois sources, celles des vues
du tableau, pour que la répartition tombe sur le même total que l'indicateur
« Pages vues » :

| Portée | Vues | Visiteurs par canal |
|---|---|---|
| `jour` | les évènements d'aujourd'hui | les évènements d'aujourd'hui |
| `mois` | `audience_canal_jour` sur 30 jours | les évènements (30 jours) |
| `annee`, `total` | `audience_canal_mois` + le journalier du mois en cours | — |

Les VUES s'additionnent d'un canal à l'autre ; les visiteurs NON — qui vient par le
site et par l'app compte dans les deux. Au-delà des 30 jours d'évènements, personne
ne sait plus qui est venu par où : `visiteurs` est absent, et l'écran ne montre que
les vues.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, delete, select

from app.models.core import TelemetryEvent
from app.models.telemetrie import AudienceCanalJour, AudienceCanalMois
from app.utils.canaux_audience import libelle_canal, rang_canal

#: page → canal → vues
ParPage = dict[str, dict[str, int]]


# ── L'écriture, appelée par `telemetry_aggregation` ──────────────────────────


def agreger_jour(session: Session, jour: str, fenetre: tuple, serie) -> None:
    """(Ré)écrit la répartition d'UN jour depuis ses évènements — idempotent.

    `fenetre` et `serie` sont ceux de l'agrégat journalier : mêmes bornes, même
    drapeau du gestionnaire.
    """
    session.exec(delete(AudienceCanalJour).where(AudienceCanalJour.jour == jour))
    lignes = session.exec(
        select(TelemetryEvent.page, TelemetryEvent.canal, serie, func.count())
        .where(*fenetre)
        .group_by(TelemetryEvent.page, TelemetryEvent.canal, serie)
    ).all()
    for page, canal, gestionnaire, vues in lignes:
        session.add(
            AudienceCanalJour(
                jour=jour, page=page, canal=canal, gestionnaire=bool(gestionnaire), vues=vues
            )
        )


def agreger_mois(session: Session, mois: str) -> None:
    """(Ré)écrit la répartition d'UN mois depuis le journalier — idempotent."""
    session.exec(delete(AudienceCanalMois).where(AudienceCanalMois.mois == mois))
    lignes = session.exec(
        select(
            AudienceCanalJour.page,
            AudienceCanalJour.canal,
            AudienceCanalJour.gestionnaire,
            func.sum(AudienceCanalJour.vues),
        )
        .where(AudienceCanalJour.jour.startswith(mois))
        .group_by(AudienceCanalJour.page, AudienceCanalJour.canal, AudienceCanalJour.gestionnaire)
    ).all()
    for page, canal, gestionnaire, vues in lignes:
        if vues:
            session.add(
                AudienceCanalMois(
                    mois=mois, page=page, canal=canal, gestionnaire=gestionnaire, vues=vues
                )
            )


# ── La lecture, appelée par `telemetrie_tableau` ─────────────────────────────


def _par_page(lignes) -> ParPage:
    par_page: ParPage = defaultdict(lambda: defaultdict(int))
    for page, canal, vues in lignes:
        par_page[page][canal] += vues or 0
    return par_page


def vues_evenements(session: Session, conditions: list) -> ParPage:
    """Les vues par page et par canal, lues sur les évènements (portée Jour)."""
    return _par_page(
        session.exec(
            select(TelemetryEvent.page, TelemetryEvent.canal, func.count())
            .where(*conditions)
            .group_by(TelemetryEvent.page, TelemetryEvent.canal)
        ).all()
    )


def vues_agregees(session: Session, modele, conditions: list) -> ParPage:
    """Les vues par page et par canal, lues sur `AudienceCanalJour` ou `AudienceCanalMois`."""
    return _par_page(
        session.exec(
            select(modele.page, modele.canal, func.sum(modele.vues))
            .where(*conditions)
            .group_by(modele.page, modele.canal)
        ).all()
    )


def fusionner(*parts: ParPage) -> ParPage:
    """Additionne des répartitions — le mensuel et le journalier du mois en cours."""
    total: ParPage = defaultdict(lambda: defaultdict(int))
    for part in parts:
        for page, canaux in part.items():
            for canal, vues in canaux.items():
                total[page][canal] += vues
    return total


def visiteurs_par_canal(session: Session, conditions: list) -> dict[str, int]:
    """Les comptes distincts venus par chaque canal — sur les évènements seulement."""
    return dict(
        session.exec(
            select(TelemetryEvent.canal, func.count(func.distinct(TelemetryEvent.user_id)))
            .where(*conditions, TelemetryEvent.user_id.isnot(None))
            .group_by(TelemetryEvent.canal)
        ).all()
    )


def _pourcent(part: int, total: int) -> int:
    return round(100 * part / total) if total else 0


def servir(
    par_page: ParPage, top_pages: list[dict], visiteurs: Optional[dict[str, int]]
) -> list[dict]:
    """La répartition du tableau ; pose aussi, sur chaque ligne de `top_pages`, ses `canaux`.

    La part (`part`, en pour cent des vues) se calcule ICI : le site et l'app
    l'affichent, elle ne se recalcule pas dans chacun (`standards/09` §8). Seuls
    les canaux qui ont des vues sont listés.
    """
    totaux: dict[str, int] = defaultdict(int)
    for canaux in par_page.values():
        for canal, vues in canaux.items():
            totaux[canal] += vues
    ensemble = sum(totaux.values())
    for ligne in top_pages:
        canaux = par_page.get(ligne["page"], {})
        ligne["canaux"] = [
            {"canal": c, "libelle": libelle_canal(c), "vues": canaux[c]}
            for c in sorted(canaux, key=rang_canal)
            if canaux[c]
        ]
    return [
        {
            "canal": canal,
            "libelle": libelle_canal(canal),
            "vues": totaux[canal],
            "part": _pourcent(totaux[canal], ensemble),
            "visiteurs": None if visiteurs is None else visiteurs.get(canal, 0),
        }
        for canal in sorted(totaux, key=rang_canal)
        if totaux[canal]
    ]
