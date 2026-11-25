"""Quelle part de la résidence se sert du site — le taux d'adoption (#1628).

## Pourquoi (03/10/2026)

Le tableau de bord donnait des volumes : 40 utilisateurs actifs, c'est beaucoup
sur 50 comptes et peu sur 200. Le taux rapporte les comptes VENUS sur la
période aux comptes qui POUVAIENT venir.

## La règle

- **dénominateur** : les comptes ouverts (`actif`), MOINS ceux qui ont refusé la
  mesure d'audience — leurs visites ne sont pas enregistrées, les compter
  ferait baisser le taux par construction. Leur nombre est rendu à côté, pour
  que l'écran le dise ;
- **numérateur** : ceux de ces comptes qui sont VENUS sur la fenêtre de la
  portée consultée (Jour, Mois, Année — 03/10/2026) : un événement de
  télémétrie depuis `depuis_utc` — les événements vivent 30 jours — ou, pour la
  vue Année, une `PresenceMensuelle` depuis `mois_depuis` : le seul fait « venu
  ce mois-là », gardé 12 mois par l'agrégation. Au-delà, personne ne sait plus
  qui est venu : la vue Total n'a pas de « Qui vient » ;
- les comptes `exclus` — le gestionnaire du site, en lecture « sans » — sortent
  des deux termes du rapport ;
- ventilé par **profil** — les rôles, CUMULÉS : un copropriétaire membre du
  conseil compte sous « Propriétaire » et sous « Conseil syndical », donc les
  lignes ne s'additionnent pas —, par **type de résident** (le statut :
  copropriétaire résident, bailleur, locataire…) et par **bâtiment**
  (`libelle_batiment`). Libellés de `roles_libelles`, jamais réécrits ici.
  Présentation arbitrée sur maquette le 03/10/2026 (« Qui vient »).

Chaque ligne porte ses deux nombres avec le taux : sur un bâtiment de trois
comptes, « 33 % » ne veut rien dire seul.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from app.models.copropriete import Batiment
from app.models.core import PresenceMensuelle, TelemetryEvent, Utilisateur
from app.utils.batiments import libelle_batiment_ou
from app.utils.pourcentages import part_en_pourcent
from app.utils.roles_libelles import libelle_role, libelle_statut


@dataclass(frozen=True)
class Fenetre:
    """Ce que « Qui vient » couvre : son libellé pour l'écran, et ses deux bornes."""

    libelle: str
    #: Les événements à partir de cet instant (UTC naïf, comme la base).
    depuis_utc: datetime
    #: Les présences mensuelles à partir de ce mois (« YYYY-MM ») ; `None` : aucune.
    mois_depuis: Optional[str] = None


#: Le libellé d'un compte sans bâtiment — syndic, compte technique, arrivant
#: pas encore rattaché.
SANS_BATIMENT = "Sans bâtiment"


def _ligne(libelle: str, comptes: list[Utilisateur], actifs: set[int]) -> dict:
    venus = sum(1 for c in comptes if c.id in actifs)
    return {
        "libelle": libelle,
        "actifs": venus,
        "comptes": len(comptes),
        "taux": part_en_pourcent(venus, len(comptes), vide=None),
    }


def _par(comptes: list[Utilisateur], libelles, actifs: set[int]) -> list[dict]:
    """Une ligne par libellé ; `libelles(compte)` en rend un ou plusieurs."""
    groupes: dict[str, list[Utilisateur]] = {}
    for c in comptes:
        for libelle in libelles(c):
            groupes.setdefault(libelle, []).append(c)
    lignes = [_ligne(libelle, groupe, actifs) for libelle, groupe in groupes.items()]
    return sorted(lignes, key=lambda ligne: (-ligne["comptes"], ligne["libelle"]))


def _venus(session: Session, fenetre: Fenetre) -> set[int]:
    """Les comptes venus sur la fenêtre : les événements, puis la présence mensuelle."""
    actifs = set(
        session.exec(
            select(TelemetryEvent.user_id)
            .where(TelemetryEvent.cree_le >= fenetre.depuis_utc, TelemetryEvent.user_id.isnot(None))
            .distinct()
        ).all()
    )
    if fenetre.mois_depuis:
        actifs |= set(
            session.exec(
                select(PresenceMensuelle.user_id)
                .where(PresenceMensuelle.mois >= fenetre.mois_depuis)
                .distinct()
            ).all()
        )
    return actifs


def adoption(session: Session, fenetre: Fenetre, exclus: set[int] = frozenset()) -> dict:
    """Le taux d'adoption sur la fenêtre, et sa ventilation — sans les comptes `exclus`."""
    ouverts = [
        c
        for c in session.exec(select(Utilisateur).where(Utilisateur.actif == True)).all()  # noqa: E712
        if c.id not in exclus
    ]
    mesures = [c for c in ouverts if not c.opt_out_telemetrie]
    actifs = _venus(session, fenetre)
    batiments = {b.id: b for b in session.exec(select(Batiment)).all()}
    return {
        "periode": fenetre.libelle,
        "global": _ligne("Tous les comptes", mesures, actifs),
        "refus": len(ouverts) - len(mesures),
        "par_profil": _par(mesures, lambda c: [libelle_role(r) for r in c.roles], actifs),
        "par_type": _par(mesures, lambda c: [libelle_statut(c.statut)], actifs),
        "par_batiment": _par(
            mesures,
            lambda c: [libelle_batiment_ou(batiments.get(c.batiment_id), SANS_BATIMENT)],
            actifs,
        ),
    }
