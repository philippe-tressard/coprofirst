"""La RÉPARTITION des vues par canal d'accès — écrite par l'agrégation, lue par le tableau.

Demandé le 14/11/2026 (`utils/canaux_audience`). Trois sources, celles des vues
du tableau, pour que la répartition tombe sur le même total que l'indicateur
« Pages vues » :

| Portée | Vues | Visiteurs par canal |
|---|---|---|
| `jour` | les évènements d'aujourd'hui | les évènements d'aujourd'hui |
| `mois` | `audience_canal_jour` sur 30 jours | les évènements (30 jours) |
| `annee`, `total` | `audience_canal_mois` + le journalier du mois en cours | — |

Chaque vue garde aussi sa classe d'appareil (#2774) : la répartition se lit par
canal, puis, sous chaque canal, par appareil (`appareils`, « non précisé » compris).

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
from app.utils.canaux_audience import (
    APPAREIL_NON_PRECISE,
    libelle_appareil,
    libelle_canal,
    rang_appareil,
    rang_canal,
)
from app.utils.pourcentages import part_en_pourcent

#: (canal, appareil) — l'appareil `None` quand il n'est pas précisé (#2774).
Acces = tuple[str, Optional[str]]
#: page → (canal, appareil) → vues
ParPage = dict[str, dict[Acces, int]]


# ── L'écriture, appelée par `telemetry_aggregation` ──────────────────────────


def agreger_jour(session: Session, jour: str, fenetre: tuple, serie) -> None:
    """(Ré)écrit la répartition d'UN jour depuis ses évènements — idempotent.

    `fenetre` et `serie` sont ceux de l'agrégat journalier : mêmes bornes, même
    drapeau du gestionnaire.
    """
    session.exec(delete(AudienceCanalJour).where(AudienceCanalJour.jour == jour))
    lignes = session.exec(
        select(
            TelemetryEvent.page, TelemetryEvent.canal, TelemetryEvent.appareil, serie, func.count()
        )
        .where(*fenetre)
        .group_by(TelemetryEvent.page, TelemetryEvent.canal, TelemetryEvent.appareil, serie)
    ).all()
    for page, canal, appareil, gestionnaire, vues in lignes:
        session.add(
            AudienceCanalJour(
                jour=jour,
                page=page,
                canal=canal,
                appareil=appareil,
                gestionnaire=bool(gestionnaire),
                vues=vues,
            )
        )


def agreger_mois(session: Session, mois: str) -> None:
    """(Ré)écrit la répartition d'UN mois depuis le journalier — idempotent."""
    session.exec(delete(AudienceCanalMois).where(AudienceCanalMois.mois == mois))
    lignes = session.exec(
        select(
            AudienceCanalJour.page,
            AudienceCanalJour.canal,
            AudienceCanalJour.appareil,
            AudienceCanalJour.gestionnaire,
            func.sum(AudienceCanalJour.vues),
        )
        .where(AudienceCanalJour.jour.startswith(mois))
        .group_by(
            AudienceCanalJour.page,
            AudienceCanalJour.canal,
            AudienceCanalJour.appareil,
            AudienceCanalJour.gestionnaire,
        )
    ).all()
    for page, canal, appareil, gestionnaire, vues in lignes:
        if vues:
            session.add(
                AudienceCanalMois(
                    mois=mois,
                    page=page,
                    canal=canal,
                    appareil=appareil,
                    gestionnaire=gestionnaire,
                    vues=vues,
                )
            )


# ── La lecture, appelée par `telemetrie_tableau` ─────────────────────────────


def _par_page(lignes) -> ParPage:
    par_page: ParPage = defaultdict(lambda: defaultdict(int))
    for page, canal, appareil, vues in lignes:
        par_page[page][(canal, appareil)] += vues or 0
    return par_page


def vues_evenements(session: Session, conditions: list) -> ParPage:
    """Les vues par page, canal et appareil, lues sur les évènements (portée Jour)."""
    e = TelemetryEvent
    return _par_page(
        session.exec(
            select(e.page, e.canal, e.appareil, func.count())
            .where(*conditions)
            .group_by(e.page, e.canal, e.appareil)
        ).all()
    )


def vues_agregees(session: Session, modele, conditions: list) -> ParPage:
    """Les vues par page, canal et appareil, sur `AudienceCanalJour` ou `AudienceCanalMois`."""
    return _par_page(
        session.exec(
            select(modele.page, modele.canal, modele.appareil, func.sum(modele.vues))
            .where(*conditions)
            .group_by(modele.page, modele.canal, modele.appareil)
        ).all()
    )


def fusionner(*parts: ParPage) -> ParPage:
    """Additionne des répartitions — le mensuel et le journalier du mois en cours."""
    total: ParPage = defaultdict(lambda: defaultdict(int))
    for part in parts:
        for page, acces in part.items():
            for cle, vues in acces.items():
                total[page][cle] += vues
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


def servir(
    par_page: ParPage, top_pages: list[dict], visiteurs: Optional[dict[str, int]]
) -> list[dict]:
    """La répartition du tableau ; pose aussi, sur chaque ligne de `top_pages`, ses `canaux`.

    La part (`part`, en pour cent des vues) se calcule ICI : le site et l'app
    l'affichent, elle ne se recalcule pas dans chacun (`standards/09` §8). Seuls
    les canaux qui ont des vues sont listés.
    """
    totaux: dict[str, int] = defaultdict(int)
    par_appareil: dict[str, dict[Optional[str], int]] = defaultdict(lambda: defaultdict(int))
    for acces in par_page.values():
        for (canal, appareil), vues in acces.items():
            totaux[canal] += vues
            par_appareil[canal][appareil] += vues
    ensemble = sum(totaux.values())
    for ligne in top_pages:
        canaux: dict[str, int] = defaultdict(int)
        for (canal, _appareil), vues in par_page.get(ligne["page"], {}).items():
            canaux[canal] += vues
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
            "part": part_en_pourcent(totaux[canal], ensemble),
            "visiteurs": None if visiteurs is None else visiteurs.get(canal, 0),
            "appareils": _appareils(canal, par_appareil[canal], totaux[canal]),
        }
        for canal in sorted(totaux, key=rang_canal)
        if totaux[canal]
    ]


def _appareils(canal: str, vues: dict[Optional[str], int], total: int) -> list[dict]:
    """Les classes d'appareil d'un canal, dans l'ordre déclaré, « non précisé » en dernier."""
    return [
        {
            "appareil": appareil or APPAREIL_NON_PRECISE,
            "libelle": libelle_appareil(appareil),
            "vues": vues[appareil],
            "part": part_en_pourcent(vues[appareil], total),
        }
        for appareil in sorted(vues, key=lambda a: rang_appareil(canal, a))
        if vues[appareil]
    ]
