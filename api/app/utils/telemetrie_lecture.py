"""Ce que toutes les lectures du tableau de télémétrie partagent (03/10/2026).

La `Lecture` — portée, filtre « gestionnaire », instant de Paris — et les
relevés que plusieurs portées emploient : top utilisateurs, fiches, uniques par
jour, heure de pointe, et les trois panneaux communs (erreurs, durées, « Qui
vient »). Les portées elles-mêmes et la réponse sont dans `telemetrie_tableau`,
qui dépassait 500 lignes avec ces relevés dedans (modularité, rang 1).

## Le filtre « avec / sans gestionnaire du site »

Le compte `site_manager_user_id` — qui administre, et consulte beaucoup — gonfle
les chiffres d'une petite résidence. En « sans », ses vues sortent de tout ce qui
porte un compte : les évènements (`user_id`), les agrégats (série `gestionnaire`),
« Qui vient ». Les erreurs et les durées d'affichage n'ont pas de compte et ne
bougent pas. Une ligne agrégée AVANT le drapeau (`None`) compte dans les deux
lectures, et la réponse dit jusqu'à quand (`non_distingue_jusqu_au`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app import dialecte
from app.models.core import (
    TelemetryDaily,
    TelemetryEvent,
    Utilisateur,
)
from app.utils import horloge
from app.utils.adoption import Fenetre, adoption
from app.utils.arrivees_notification import synthese_arrivees
from app.utils.echeance_contrat import ajouter_mois
from app.utils.erreurs_navigateur import CONSERVATION_JOURS, synthese_erreurs
from app.utils.gestes_formulaire import synthese_gestes
from app.utils.mesures_affichage import synthese_mesures
from app.utils.noms import nom_affiche
from app.utils.retour_comptes import retour_comptes

PAGE_TOTAL = "__total__"


@dataclass(frozen=True)
class Lecture:
    """Ce que toutes les requêtes d'une réponse partagent."""

    scope: str
    sans_gestionnaire: bool
    gestionnaire_id: Optional[int]
    now_paris: datetime
    paris_offset: int

    @property
    def paris_offset_str(self) -> str:
        return f"+{self.paris_offset} hours"

    @property
    def today_start_utc(self) -> datetime:
        return horloge.debut_du_jour_utc(self.now_paris)

    @property
    def mois_courant(self) -> str:
        return self.now_paris.strftime("%Y-%m")

    def evenements(self) -> list:
        """Les conditions du filtre sur les évènements — les anonymes restent."""
        if not self.sans_gestionnaire or self.gestionnaire_id is None:
            return []
        return [
            or_(TelemetryEvent.user_id.is_(None), TelemetryEvent.user_id != self.gestionnaire_id)
        ]

    def agregats(self, modele) -> list:
        """Les conditions du filtre sur un agrégat — les non distingués (`None`) restent."""
        return [modele.gestionnaire.isnot(True)] if self.sans_gestionnaire else []

    def exclus(self) -> set[int]:
        """Les comptes que « Qui vient » écarte."""
        return {self.gestionnaire_id} if self.sans_gestionnaire and self.gestionnaire_id else set()


# ── Fenêtres de chaque portée ────────────────────────────────────────────────


def mois_il_y_a(now_paris: date, n: int) -> str:
    """Le mois `n` mois avant celui de `now_paris`, « YYYY-MM » (la clé des tables mensuelles)."""
    mois = ajouter_mois(now_paris.replace(day=1), -n)
    return f"{mois.year}-{mois.month:02d}"


def _depuis_detail(scope: str):
    """Le premier jour des erreurs (#1631), des durées d'affichage (#1632) et des gestes (#1633) :
    celui du jour, sinon toute la conservation — ces tables ne vivent que
    `CONSERVATION_JOURS`, Année et Total n'en ont pas davantage. L'écran le dit."""
    jours = 0 if scope == "jour" else CONSERVATION_JOURS
    return horloge.aujourd_hui() - timedelta(days=jours)


def _fenetre_adoption(lecture: Lecture) -> Optional[Fenetre]:
    """Ce que « Qui vient » couvre pour cette portée ; `None` : la portée ne sait pas."""
    if lecture.scope == "jour":
        return Fenetre("aujourd’hui", lecture.today_start_utc, None)
    if lecture.scope == "mois":
        return Fenetre("30 derniers jours", horloge.maintenant() - timedelta(days=30), None)
    if lecture.scope == "annee":
        return Fenetre(
            "12 derniers mois",
            horloge.maintenant() - timedelta(days=30),
            mois_il_y_a(lecture.now_paris, 11),
        )
    return None  # total : au-delà de 12 mois, personne ne sait plus qui est venu


# ── Relevés partagés ─────────────────────────────────────────────────────────


def top_utilisateurs(session: Session, depuis, lecture: Optional[Lecture] = None):
    """Les trente utilisateurs les plus actifs depuis `depuis` : (id, vues, pages distinctes).

    Écrit trois fois (portées `jour` et `mois`, route `users-active`) jusqu'au
    02/10/2026, la borne basse étant la seule différence (#1564).
    """
    filtre = lecture.evenements() if lecture else []
    return session.exec(
        select(
            TelemetryEvent.user_id,
            func.count().label("total"),
            func.count(func.distinct(TelemetryEvent.page)).label("pages"),
        )
        .where(TelemetryEvent.cree_le >= depuis, TelemetryEvent.user_id.isnot(None), *filtre)
        .group_by(TelemetryEvent.user_id)
        .order_by(func.count().desc())
        .limit(30)
    ).all()


def fiches_utilisateurs(session: Session, lignes) -> dict[int, dict]:
    """Qui sont ces gens — nom, dernière visite, statut, bâtiment.

    🔴 Ce relevé était écrit TROIS fois (14/09/2026, #779), et les trois
    composaient le nom À LA MAIN — `f"{prenom} {nom}"` — alors que la règle
    d'affichage vit dans `utils/noms.nom_affiche`. Rend UN dictionnaire par
    personne, et non quatre dictionnaires parallèles.
    """
    ids = [ligne[0] for ligne in lignes if ligne[0]]
    if not ids:
        return {}
    rangs = session.exec(
        select(
            Utilisateur.id,
            Utilisateur.prenom,
            Utilisateur.nom,
            Utilisateur.derniere_connexion,
            Utilisateur.statut,
            Utilisateur.batiment_id,
        ).where(Utilisateur.id.in_(ids))
    ).all()
    return {
        u[0]: {
            "nom": nom_affiche(u[1], u[2]),
            "derniere_connexion": u[3].isoformat() if u[3] else None,
            "statut": u[4],
            "batiment_id": u[5],
        }
        for u in rangs
    }


def uniques_par_jour(
    session: Session, lecture: Lecture, depuis: Optional[date] = None
) -> dict[str, int]:
    """Les utilisateurs uniques de chaque jour — les évènements bruts d'abord, puis l'agrégat.

    Un jour dont les évènements bruts ont été purgés (30 jours) n'existe plus que
    dans `TelemetryDaily` : son total comble alors le trou, sans jamais écraser
    un jour que les évènements savent encore compter. Les deux séries d'un jour
    étant disjointes, leurs uniques s'additionnent.

    `depuis` est un JOUR : il borne l'horodatage des évènements à son minuit, et
    la colonne texte « AAAA-MM-JJ » des agrégats à sa forme écrite — une même
    chaîne ne vaut pas pour les deux sous PostgreSQL (#1747).
    """
    jour = dialecte.jour(TelemetryEvent.cree_le, lecture.paris_offset_str)
    evenements = (
        select(
            jour.label("jour"), func.count(func.distinct(TelemetryEvent.user_id)).label("uniques")
        )
        .where(TelemetryEvent.user_id.isnot(None), *lecture.evenements())
        .group_by(jour)
    )
    totaux = (
        select(TelemetryDaily.jour, func.sum(TelemetryDaily.utilisateurs_uniques))
        .where(TelemetryDaily.page == PAGE_TOTAL, *lecture.agregats(TelemetryDaily))
        .group_by(TelemetryDaily.jour)
    )
    if depuis is not None:
        evenements = evenements.where(TelemetryEvent.cree_le >= datetime.combine(depuis, time.min))
        totaux = totaux.where(TelemetryDaily.jour >= depuis.isoformat())
    uniques = {r[0]: r[1] for r in session.exec(evenements).all()}
    for r in session.exec(totaux).all():
        if r[0] not in uniques:
            uniques[r[0]] = r[1] or 0
    return uniques


def heure_de_pointe(session: Session, lecture: Lecture, depuis) -> Optional[str]:
    hour_stats = session.exec(
        select(
            sa.extract("hour", TelemetryEvent.cree_le).label("heure"),
            func.count().label("total"),
        )
        .where(TelemetryEvent.cree_le >= depuis, *lecture.evenements())
        .group_by("heure")
    ).all()
    if not hour_stats:
        return None
    best = max(hour_stats, key=lambda x: x[1])
    return f"{(best[0] + lecture.paris_offset) % 24}h"


def record(uniques: dict[str, int], cle: str) -> Optional[dict]:
    if not uniques:
        return None
    best = max(uniques, key=uniques.get)  # type: ignore[arg-type]
    return {cle: best, "uniques": uniques[best]}


def communs(session: Session, lecture: Lecture) -> dict:
    """Ce que toute portée rend : erreurs, durées, gestes aboutis (#1633), « Qui vient »,
    et le retour des comptes (#1629) — dormants et arrivants, à seuils fixes."""
    fenetre = _fenetre_adoption(lecture)
    return {
        "erreurs": synthese_erreurs(session, _depuis_detail(lecture.scope)),
        "performance": synthese_mesures(session, _depuis_detail(lecture.scope)),
        "gestes": synthese_gestes(session, _depuis_detail(lecture.scope)),
        "arrivees": synthese_arrivees(session, _depuis_detail(lecture.scope), lecture.evenements()),
        "adoption": adoption(session, fenetre, lecture.exclus()) if fenetre else None,
        "retour": retour_comptes(session),
    }
