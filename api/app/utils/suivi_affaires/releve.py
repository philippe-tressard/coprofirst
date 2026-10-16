"""Le relevé des affaires non closes — la règle d'entrée, écrite une fois.

## Qui entre au rapport

Toute affaire dont l'état est ACTIF (`STATUTS_TICKET_ACTIFS` : ni résolue, ni
annulée, ni actualité sans cycle), que le conseil syndical voit
(`ticket_visible`). Plus seulement celles « suivies au kanban » : l'ancienne vue
« Suivi des dossiers » ne montrait que celles-là, et le conseil voulait le compte
de TOUTES les affaires ouvertes (demande du 16/10/2026).

## L'ancienneté

Comptée en jours civils de Paris, de l'ouverture à aujourd'hui. Ses deux seuils
— 30 et 90 jours — colorent la pastille d'âge à l'écran comme au PDF : ils
vivent ici, et l'écran reçoit la tranche (`anciennete`), jamais les seuils.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlmodel import Session, select

from app.models.core import Utilisateur
from app.models.tickets import STATUTS_TICKET_ACTIFS, Ticket
from app.utils import horloge
from app.utils.annonce_hall import texte_brut
from app.utils.categories_ticket import libelle_categorie
from app.utils.valeurs import valeur
from app.utils.visibility import ticket_visible

#: Au-delà, l'affaire « traîne » : pastille orange, puis rouge.
SEUIL_MOYENNE_JOURS = 30
SEUIL_ANCIENNE_JOURS = 90

#: Le descriptif transmis — l'écran et le PDF le coupent à dix lignes ; au-delà
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


@dataclass(frozen=True)
class Categorie:
    categorie: str
    libelle: str
    nombre: int


@dataclass(frozen=True)
class Releve:
    jour: date
    affaires: list[AffaireOuverte] = field(default_factory=list)

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


def lire_affaire(ticket: Ticket, jour: date, libelles_statut: dict[str, str]) -> AffaireOuverte:
    """PURE. Ce que le rapport montre d'une affaire."""
    ouverte_le = horloge.jour_civil(ticket.cree_le)
    age = max((jour - ouverte_le).days, 0)
    statut = valeur(ticket.statut)
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
    )


def releve(session: Session, user: Utilisateur) -> Releve:
    """Les affaires non closes que `user` voit, la plus ancienne en tête."""
    #  Import différé, comme `synthese_affaire.production` : les libellés de
    #  l'écran vivent dans le paquet des routeurs de tickets.
    from app.routers.tickets.commun import STATUT_LABELS

    tickets = session.exec(
        select(Ticket)
        .where(Ticket.statut.in_(STATUTS_TICKET_ACTIFS))  # type: ignore[union-attr]
        .order_by(Ticket.cree_le, Ticket.id)
    ).all()
    jour = horloge.aujourd_hui()
    return Releve(
        jour=jour,
        affaires=[lire_affaire(t, jour, STATUT_LABELS) for t in tickets if ticket_visible(t, user)],
    )
