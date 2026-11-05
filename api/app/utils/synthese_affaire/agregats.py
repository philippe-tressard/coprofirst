"""Les métriques d'un ENSEMBLE d'affaires closes — le bilan du carnet et la fiche prestataire.

Deux lecteurs, un calcul : la vue annuelle du carnet d'entretien (#1645 — par
exercice comptable et par catégorie) et les affaires d'un prestataire (#1646 —
celles où il était l'intervenant désigné, par exercice).

## Rien n'est mesuré ici

Chaque affaire passe par `metriques.calculer` — la mesure de sa synthèse, à
l'identique : mêmes faits (`rassemblement.faits_de`), mêmes jours ouvrés, mêmes
étapes. Ce module ne fait que **moyenner** ce qu'elle rend. Une seconde façon de
découper la vie d'une affaire en étapes donnerait, pour la même affaire, un
chiffre au carnet et un autre dans sa synthèse.

## Arbitré par l'utilisateur (04/10/2026)

- **Source : toutes les affaires closes** (résolues ou annulées), recalculées —
  pas les métriques figées des synthèses : l'usage de l'assistant est livré
  désactivé, elles sont presque toutes vides.
- **Lecture : le conseil syndical seul** — les deux routes exigent
  `require_cs_or_admin`. Un délai moyen par prestataire est un argument de
  négociation, pas une information de copropriétaire.
- « Affaire du carnet » = `carnet_entretien.contribue_au_carnet`, jamais une
  liste de catégories recopiée (🔒 `test_synthese_eligibilite.py`).

## Ce qu'une moyenne ne dit pas

Une valeur absente n'est jamais 0 (`metriques.moyenne_de`) : une affaire sans
relance ne fait pas baisser le délai de réaction, elle n'en a pas. Chaque
moyenne porte donc le nombre d'affaires qui la composent.

⚠️ Le seuil de trois affaires de la comparaison (`MINIMUM_COMPARABLES`) ne
s'applique pas ici : il masque une moyenne opposée à UNE affaire ; un bilan
affiche la sienne avec son effectif, et le lecteur juge.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from sqlmodel import Session, col, select

from app.models.core import Ticket
from app.models.prestataires import Prestataire
from app.models.tickets import STATUTS_TICKET_CLOS, StatutTicket
from app.utils import horloge
from app.utils.affaire_absorbee import ouverture_effective, pas_absorbee
from app.utils.carnet_entretien import contribue_au_carnet
from app.utils.categories_ticket import libelle_categorie
from app.utils.jours_ouvres import au_demi_jour
from app.utils.synthese_affaire import metriques as m
from app.utils.synthese_affaire.rassemblement import (
    faits_de,
    mois_debut_exercice,
    reconnaisseur_syndic,
)
from app.utils.valeurs import valeur

#: L'étape qui mesure un intervenant — celle de la fiche prestataire.
ETAPE_PRESTATAIRE = StatutTicket.chez_prestataire.value
#: Les prestataires « les plus lents » d'une catégorie : les premiers, pas un palmarès.
NOMBRE_PLUS_LENTS = 5


@dataclass(frozen=True)
class Exercice:
    """Un exercice comptable : l'année où il commence, son nom (« 2025-2026 ») et ses bornes."""

    annee: int
    libelle: str
    debut: date
    #: Le lendemain de son dernier jour — la borne EXCLUE, celle des requêtes.
    fin: date

    def contient(self, ferme_le) -> bool:
        """Une clôture (UTC naïf, comme en base) tombe-t-elle dans l'exercice ?"""
        return m.debut_utc(self.debut) <= ferme_le < m.debut_utc(self.fin)


@dataclass(frozen=True)
class Mesure:
    """Une affaire close, mesurée par `metriques.calculer`."""

    categorie: str
    prestataire_id: Optional[int]
    exercice: Exercice
    issue: str
    metriques: dict


def exercice_de(jour: date, mois_debut: Optional[int]) -> Exercice:
    """L'exercice qui contient ce jour — la règle de `metriques.bornes_exercice`."""
    debut, fin, libelle = m.bornes_exercice(jour, mois_debut)
    return Exercice(debut.year, libelle, debut, fin)


def exercice_commence_en(annee: int, mois_debut: Optional[int]) -> Exercice:
    """L'exercice qui commence en `annee` — celui qui contient son 31 décembre.

    Quel que soit le mois de début, le 31 décembre tombe dans l'exercice ouvert
    cette année-là : aucune règle de mois à réécrire ici.
    """
    return exercice_de(date(annee, 12, 31), mois_debut)


def affaires_closes(session: Session, *conditions) -> list[Ticket]:
    """Les affaires closes et datées — résolues ou annulées, de la plus ancienne clôture."""
    return list(
        session.exec(
            select(Ticket)
            .where(
                col(Ticket.statut).in_(STATUTS_TICKET_CLOS),
                col(Ticket.ferme_le).isnot(None),
                pas_absorbee(),  # comptée dans sa principale (#1704)
                *conditions,
            )
            .order_by(col(Ticket.ferme_le))
        ).all()
    )


def mesurer(session: Session, tickets: list[Ticket]) -> list[Mesure]:
    """Chaque affaire, mesurée comme sa synthèse la mesurerait."""
    est_syndic = reconnaisseur_syndic(session)
    mois_debut = mois_debut_exercice(session)
    mesures = []
    for t in tickets:
        met = m.calculer(
            cree_le=ouverture_effective(session, t),
            cloture_le=t.ferme_le,
            issue=valeur(t.statut),
            faits=faits_de(session, t.id, est_syndic),
        )
        mesures.append(
            Mesure(
                categorie=valeur(t.categorie),
                prestataire_id=t.prestataire_id,
                exercice=exercice_de(horloge.jour_civil(t.ferme_le), mois_debut),
                issue=met["issue"],
                metriques=met,
            )
        )
    return mesures


def _jours_moyens(valeurs: list[float]) -> Optional[float]:
    moy = m.moyenne_de(valeurs)
    return au_demi_jour(moy) if moy is not None else None


def jours_d_etape(mesure: Mesure, statut: str) -> Optional[float]:
    """Les jours ouvrés passés dans une étape — `None` si l'affaire n'y est pas passée."""
    return next((e["jours"] for e in mesure.metriques["etapes"] if e["statut"] == statut), None)


def resumer(mesures: list[Mesure]) -> dict:
    """Les moyennes d'un ensemble d'affaires — chacune avec son effectif.

    Vide, il rend `nombre: 0` et des moyennes `None` : l'écran dit « aucune
    affaire », jamais « 0 j ».
    """
    met = [x.metriques for x in mesures]
    etapes = []
    for statut in m.ETAPES_KANBAN:
        jours = [j for x in mesures if (j := jours_d_etape(x, statut)) is not None]
        if jours:
            etapes.append({"statut": statut, "jours": _jours_moyens(jours), "nombre": len(jours)})
    reactions = [x["reaction_relance"] for x in met if x["reaction_relance"] is not None]
    relances = sum(x["relances"] for x in met)
    suites = m.moyenne_de(x["suites"] for x in met)
    return {
        "nombre": len(mesures),
        "annulees": sum(1 for x in mesures if x.issue == StatutTicket.annulé.value),
        "duree_totale": _jours_moyens([x["duree_totale"] for x in met]),
        "etapes": etapes,
        "relances": relances,
        "relances_par_affaire": round(relances / len(met), 1) if met else None,
        "reaction_relance": _jours_moyens(reactions),
        "reactions": len(reactions),
        "premiere_reponse_syndic": _jours_moyens([x["premiere_reponse_syndic"] for x in met]),
        "suites": round(suites, 1) if suites is not None else None,
    }


def plus_lents(session: Session, mesures: list[Mesure]) -> list[dict]:
    """Les prestataires dont l'étape « Chez le prestataire » a duré le plus, en moyenne.

    Seules comptent les affaires où un intervenant était désigné ET qui sont
    passées par cette étape : une affaire réglée sans lui ne le mesure pas.
    """
    par: dict[int, list[float]] = {}
    for x in mesures:
        jours = jours_d_etape(x, ETAPE_PRESTATAIRE)
        if x.prestataire_id is not None and jours is not None:
            par.setdefault(x.prestataire_id, []).append(jours)
    lignes = []
    for prestataire_id, jours in par.items():
        p = session.get(Prestataire, prestataire_id)
        lignes.append(
            {
                "prestataire_id": prestataire_id,
                "nom": p.nom if p else "Prestataire supprimé",
                "jours": _jours_moyens(jours),
                "nombre": len(jours),
            }
        )
    lignes.sort(key=lambda ligne: (-ligne["jours"], ligne["nom"].lower()))
    return lignes[:NOMBRE_PLUS_LENTS]


def par_exercice(mesures: list[Mesure]) -> list[tuple[Exercice, list[Mesure]]]:
    """Les mesures rangées par exercice, du plus récent au plus ancien."""
    groupes: dict[Exercice, list[Mesure]] = {}
    for x in mesures:
        groupes.setdefault(x.exercice, []).append(x)
    return sorted(groupes.items(), key=lambda g: g[0].annee, reverse=True)


def bilan_carnet(session: Session, annee: Optional[int] = None) -> dict:
    """La vue annuelle du carnet (#1645) : un exercice, ses moyennes par catégorie.

    `annee` est l'année où commence l'exercice ; absente, l'exercice EN COURS.
    Les exercices proposés sont ceux où une affaire du carnet s'est close, plus
    l'exercice en cours — même vide : c'est celui qu'on vient regarder.
    """
    mois_debut = mois_debut_exercice(session)
    courant = exercice_de(horloge.aujourd_hui(), mois_debut)
    choisi = courant if annee is None else exercice_commence_en(annee, mois_debut)
    closes = [t for t in affaires_closes(session) if contribue_au_carnet(t)]
    exercices = {exercice_de(horloge.jour_civil(t.ferme_le), mois_debut) for t in closes}
    dans = [t for t in closes if choisi.contient(t.ferme_le)]
    categories: dict[str, list[Mesure]] = {}
    for x in mesurer(session, dans):
        categories.setdefault(x.categorie, []).append(x)
    lignes = [
        {
            "categorie": c,
            "categorie_libelle": libelle_categorie(c),
            **resumer(ms),
            "prestataires": plus_lents(session, ms),
        }
        for c, ms in categories.items()
    ]
    lignes.sort(key=lambda ligne: (-ligne["nombre"], ligne["categorie"]))
    return {
        #  `fin` est le DERNIER jour, inclus : c'est ce que l'écran écrit.
        "exercice": {
            **_exercice_lu(choisi),
            "debut": choisi.debut,
            "fin": choisi.fin - timedelta(days=1),
        },
        "exercices": [
            _exercice_lu(e) for e in sorted(exercices | {courant}, key=lambda e: -e.annee)
        ],
        "categories": lignes,
        "nombre": len(dans),
    }


def bilan_prestataire(session: Session, prestataire_id: int) -> dict:
    """Les affaires closes d'un prestataire (#1646) : l'ensemble, puis chaque exercice.

    Toutes les affaires où il était l'intervenant désigné (`Ticket.prestataire_id`),
    celles du carnet comme les autres — arbitré le 04/10/2026.
    """
    mesures = mesurer(session, affaires_closes(session, Ticket.prestataire_id == prestataire_id))
    return {
        "prestataire_id": prestataire_id,
        "ensemble": resumer(mesures),
        "exercices": [{**_exercice_lu(e), **resumer(ms)} for e, ms in par_exercice(mesures)],
    }


def _exercice_lu(exercice: Exercice) -> dict:
    return {"annee": exercice.annee, "libelle": exercice.libelle}


__all__ = [
    "ETAPE_PRESTATAIRE",
    "Exercice",
    "Mesure",
    "affaires_closes",
    "bilan_carnet",
    "bilan_prestataire",
    "exercice_commence_en",
    "exercice_de",
    "mesurer",
    "par_exercice",
    "plus_lents",
    "resumer",
]
