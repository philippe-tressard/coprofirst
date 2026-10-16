"""Le relevé des affaires non closes — la règle d'entrée, écrite une fois.

## Qui entre au rapport

Les affaires que la **relance du syndic** retient (`utils/relance_syndic`) : ni
résolues, ni annulées, ni 📦 archivées, ni absorbées par une fusion, ni visites
d'entretien périodique — et que le conseil syndical voit (`ticket_visible`).

🔴 Jusqu'au 16/10/2026 (#2035), ce rapport prenait tous les états ACTIFS : il
comptait 29 affaires quand la relance en comptait 24, sur le même écran. Les deux
modes — Suivre et Relancer le syndic — lisent désormais la MÊME liste.

## L'ancienneté, et la relance

L'**âge** se compte de l'ouverture à aujourd'hui ; ses deux seuils — 30 et 90
jours — colorent la pastille, à l'écran comme au PDF : ils vivent ici, et
l'écran reçoit la tranche (`anciennete`), jamais les seuils.

Les **jours sans avancée** se comptent depuis `mis_a_jour_le` — le repère de la
relance (`envoyer_relance_syndic` le pose) ; au-delà du délai réglé, l'affaire
est `a_relancer`. En jours civils de Paris, l'un comme l'autre.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from sqlmodel import Session, select

from app.models.core import Utilisateur
from app.models.tickets import Ticket
from app.utils import horloge
from app.utils.annonce_hall import texte_brut
from app.utils.categories_ticket import libelle_categorie
from app.utils.perimetres import est_perimetre_par_defaut, parse_json_perimetres, perimetre_label
from app.utils.relance_syndic import conditions_relancable, delai_relance_jours, relances_envoyees
from app.utils.valeurs import valeur
from app.utils.visibility import ticket_visible

#: Au-delà, l'affaire « traîne » : pastille orange, puis rouge.
SEUIL_MOYENNE_JOURS = 30
SEUIL_ANCIENNE_JOURS = 90

#: Le descriptif transmis — l'écran et le PDF le coupent à cinq lignes ; au-delà
#: de ce plafond, le texte ne serait de toute façon pas lu.
MAX_CARACTERES_DESCRIPTIF = 2_000


def tranche(age_jours: int) -> str:
    """PURE. `ancienne` (> 90 j), `moyenne` (> 30 j) ou `recente`."""
    if age_jours > SEUIL_ANCIENNE_JOURS:
        return "ancienne"
    if age_jours > SEUIL_MOYENNE_JOURS:
        return "moyenne"
    return "recente"


@dataclass(frozen=True)
class AffaireOuverte:
    id: int
    numero: str
    titre: str
    descriptif: str
    categorie: str
    libelle_categorie: str
    statut: str
    libelle_statut: str
    ouverte_le: date
    age_jours: int
    anciennete: str
    jours_sans_avancee: int = 0
    a_relancer: bool = False
    #: Les jours des relances déjà envoyées au syndic, la plus ancienne en tête.
    relances: list[date] = field(default_factory=list)
    #: Le résumé de l'assistant (#2035), ou `None` s'il n'a jamais été rédigé.
    resume: Optional[str] = None
    #: Les codes du périmètre (le badge de l'écran les lit) et son libellé — vide
    #: pour le périmètre par défaut, qui ne s'affiche pas (règle 4, #2035).
    perimetre_cible: list[str] = field(default_factory=list)
    perimetre: str = ""

    @property
    def apercu(self) -> str:
        """Ce qui s'affiche sous le titre — le résumé, sinon le descriptif.

        Écrit ICI pour l'écran, le PDF et le courriel de relance : trois rendus,
        une seule règle.
        """
        return self.resume or self.descriptif

    @property
    def apercu_ia(self) -> bool:
        return bool(self.resume)


@dataclass(frozen=True)
class Categorie:
    categorie: str
    libelle: str
    nombre: int


@dataclass(frozen=True)
class Releve:
    jour: date
    affaires: list[AffaireOuverte] = field(default_factory=list)
    #: Le délai de relance réglé par l'administrateur, en jours.
    delai_jours: int = 30

    @property
    def total(self) -> int:
        return len(self.affaires)

    @property
    def anciennes(self) -> int:
        """Le nombre d'affaires ouvertes depuis plus de 90 jours."""
        return sum(1 for a in self.affaires if a.anciennete == "ancienne")

    @property
    def par_categorie(self) -> list[Categorie]:
        """La répartition, la catégorie la plus nombreuse en tête."""
        comptes: dict[str, Categorie] = {}
        for a in self.affaires:
            c = comptes.get(a.categorie)
            comptes[a.categorie] = Categorie(
                a.categorie, a.libelle_categorie, (c.nombre if c else 0) + 1
            )
        return sorted(comptes.values(), key=lambda c: (-c.nombre, c.libelle))


def lire_affaire(
    ticket: Ticket,
    jour: date,
    libelles_statut: dict[str, str],
    *,
    delai_jours: int = 30,
    relances: Optional[list] = None,
) -> AffaireOuverte:
    """PURE. Ce que le rapport montre d'une affaire."""
    ouverte_le = horloge.jour_civil(ticket.cree_le)
    age = max((jour - ouverte_le).days, 0)
    avancee = horloge.jour_civil(ticket.mis_a_jour_le or ticket.cree_le)
    sans_avancee = max((jour - avancee).days, 0)
    statut = valeur(ticket.statut)
    codes = parse_json_perimetres(ticket.perimetre_cible)
    return AffaireOuverte(
        id=ticket.id,
        numero=ticket.numero,
        titre=ticket.titre,
        descriptif=texte_brut(ticket.description or "")[:MAX_CARACTERES_DESCRIPTIF],
        categorie=valeur(ticket.categorie),
        libelle_categorie=libelle_categorie(ticket.categorie),
        statut=statut,
        libelle_statut=libelles_statut.get(statut, statut),
        ouverte_le=ouverte_le,
        age_jours=age,
        anciennete=tranche(age),
        jours_sans_avancee=sans_avancee,
        a_relancer=sans_avancee >= delai_jours,
        relances=[horloge.jour_civil(r) for r in (relances or [])],
        resume=(ticket.resume_ia or "").strip() or None,
        perimetre_cible=codes,
        perimetre="" if est_perimetre_par_defaut(codes) else perimetre_label(codes),
    )


def releve(session: Session, user: Utilisateur) -> Releve:
    """Les affaires non closes que `user` voit, la plus ancienne en tête."""
    #  Import différé, comme `synthese_affaire.production` : les libellés de
    #  l'écran vivent dans le paquet des routeurs de tickets.
    from app.routers.tickets.commun import STATUT_LABELS

    tickets = [
        t
        for t in session.exec(
            select(Ticket).where(*conditions_relancable()).order_by(Ticket.cree_le, Ticket.id)
        ).all()
        if ticket_visible(t, user)
    ]
    jour = horloge.aujourd_hui()
    delai = delai_relance_jours(session)
    relances = relances_envoyees(session, [t.id for t in tickets])
    return Releve(
        jour=jour,
        delai_jours=delai,
        affaires=[
            lire_affaire(t, jour, STATUT_LABELS, delai_jours=delai, relances=relances.get(t.id))
            for t in tickets
        ],
    )
