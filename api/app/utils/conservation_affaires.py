"""La CONSERVATION des affaires — quand une affaire close arrive à son échéance (#2014).

Spécification : `specs/architecture/conservation-affaires.md`. Ce module porte la
RÈGLE (la durée par catégorie, l'échéance par exercice) et le CONSTAT : ce qui
partira, et quand. Il ne retire rien — le lot L1 est un constat seul ; le geste
viendra en L2, derrière une case de l'administrateur coupée à la livraison.

## La règle

- Une affaire **close** pendant l'exercice N échoit au lendemain du dernier jour de
  l'exercice N + durée — en exercices COMPLETS, quelle que soit la date de clôture
  dans l'exercice.
- La durée dépend de la CATÉGORIE (`DUREES`) : 10 exercices pour ce que la garantie
  décennale peut encore mettre en cause, 5 pour ce que la prescription de droit
  commun couvre, 2 pour ce qui n'a rien à prouver.
- Une affaire **ouverte** n'échoit jamais. Une affaire **absorbée** par une autre
  (fusion à la clôture) suit celle qui l'absorbe et ne se compte pas seule.
- L'exercice est celui de la fiche copropriété (`Copropriete.mois_debut_exercice`,
  l'année civile par défaut), borné par `synthese_affaire.metriques.bornes_exercice` :
  une seule notion d'exercice dans le code, pas deux.

Ce qu'une affaire porte comme fichiers est lu par `fichiers_de` : ses photos et ses
pièces jointes, celles de son fil et de ses évolutions, et les documents qui lui
sont rattachés. Le constat les compte et les pèse — c'est ce que L2 archivera.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from sqlmodel import Session, col, select

from app.models.core import MessageTicket, Ticket, TicketEvolution
from app.models.documents import Document
from app.models.tickets import STATUTS_TICKET_CLOS, CategorieTicket
from app.utils import horloge
from app.utils.affaire_absorbee import pas_absorbee
from app.utils.photos import parse_photos
from app.utils.stockage import stockage
from app.utils.synthese_affaire.metriques import bornes_exercice
from app.utils.synthese_affaire.rassemblement import mois_debut_exercice
from app.utils.valeurs import valeur


@dataclass(frozen=True)
class TypeConservation:
    """Une durée de conservation et les catégories qui la suivent."""

    code: str
    libelle: str
    #: en exercices complets après celui de la clôture
    exercices: int
    #: pourquoi cette durée — dit à l'écran, à valider avec le syndic
    fondement: str


TRAVAUX = TypeConservation(
    "travaux", "Travaux et sinistres", 10, "garantie décennale (C. civ. art. 1792-4-1)"
)
ENTRETIEN = TypeConservation(
    "entretien",
    "Pannes et entretien",
    5,
    "prescription de droit commun (C. civ. art. 2224 ; loi 65-557 art. 42)",
)
BREVES = TypeConservation(
    "breves", "Actualités et questions", 2, "rien à prouver : minimisation des données"
)

#: LA table des durées — une catégorie absente ferait conserver ses affaires sans
#: limite, sans un mot : `test_conservation_affaires.py` exige chacune.
DUREES: dict[CategorieTicket, TypeConservation] = {
    CategorieTicket.etude_travaux: TRAVAUX,
    CategorieTicket.sinistre: TRAVAUX,
    CategorieTicket.panne: ENTRETIEN,
    CategorieTicket.entretien: ENTRETIEN,
    CategorieTicket.espaces_verts: ENTRETIEN,
    CategorieTicket.acces_accueil: ENTRETIEN,
    CategorieTicket.nuisance: ENTRETIEN,
    CategorieTicket.actualite: BREVES,
    CategorieTicket.question: BREVES,
    CategorieTicket.bug: BREVES,
}

TYPES: tuple[TypeConservation, ...] = (TRAVAUX, ENTRETIEN, BREVES)


def type_de(categorie) -> TypeConservation:
    """Le type de conservation d'une catégorie (valeur ou énumération)."""
    return DUREES[CategorieTicket(valeur(categorie))]


def jour_de_cloture(ticket: Ticket) -> Optional[date]:
    """Le jour où l'affaire s'est close — `None` tant qu'elle est ouverte.

    Une actualité n'a pas de cycle : sa date est celle de sa clôture si elle en a
    une, sinon celle de sa publication.
    """
    if valeur(ticket.categorie) == CategorieTicket.actualite.value:
        return horloge.jour_civil(ticket.ferme_le or ticket.cree_le)
    if valeur(ticket.statut) not in STATUTS_TICKET_CLOS:
        return None
    return horloge.jour_civil(ticket.ferme_le or ticket.mis_a_jour_le)


def _plus_annees(jour: date, annees: int) -> date:
    """Le même jour `annees` plus tard — les bornes d'exercice tombent le 1er du mois."""
    return jour.replace(year=jour.year + annees)


def echeance(cloture: date, exercices: int, mois_debut: Optional[int]) -> tuple[date, str, str]:
    """(jour où elle échoit, exercice de clôture, dernier exercice gardé).

    L'affaire close pendant l'exercice N est gardée jusqu'au dernier jour de
    l'exercice N + `exercices` ; elle échoit le lendemain.
    """
    _, fin, exercice_cloture = bornes_exercice(cloture, mois_debut)
    echoit_le = _plus_annees(fin, exercices)
    _, _, dernier_garde = bornes_exercice(echoit_le - timedelta(days=1), mois_debut)
    return echoit_le, exercice_cloture, dernier_garde


def fichiers_de(
    ticket: Ticket,
    messages: list[MessageTicket],
    evolutions: list[TicketEvolution],
    documents: list[Document],
) -> list[Optional[Path]]:
    """Les fichiers d'une affaire sur le disque — `None` pour une référence sans fichier."""
    st = stockage()
    urls = parse_photos(ticket.photos_urls) + parse_photos(ticket.fichiers_urls)
    for porteur in (*messages, *evolutions):
        urls += parse_photos(porteur.fichiers_urls)
    chemins: list[Optional[Path]] = [st.fichier_de_url(u) for u in dict.fromkeys(urls)]
    return chemins + [st.fichier_de(d) for d in documents]


@dataclass
class Echeance:
    """Un exercice et un type : ce qui partira ensemble, et quand."""

    type: TypeConservation
    exercice_cloture: str
    dernier_exercice_garde: str
    echoit_le: date
    affaires: int = 0
    fichiers: int = 0
    octets: int = 0
    #: une référence en base sans fichier sur le disque — rien à archiver
    absents: int = 0


def _par_ticket(session: Session, modele, ids: list[int]) -> dict[int, list]:
    """Les lignes de `modele` des affaires `ids`, rangées par affaire — une requête."""
    rangees: dict[int, list] = defaultdict(list)
    if ids:
        for ligne in session.exec(select(modele).where(col(modele.ticket_id).in_(ids))).all():
            rangees[ligne.ticket_id].append(ligne)
    return rangees


def constat(session: Session) -> list[Echeance]:
    """Les échéances à venir (et passées), par exercice et par type, de la plus proche
    à la plus lointaine. Ne modifie rien."""
    mois_debut = mois_debut_exercice(session)
    tickets = session.exec(select(Ticket).where(pas_absorbee())).all()
    closes = [(t, j) for t in tickets if (j := jour_de_cloture(t)) is not None]
    ids = [t.id for t, _ in closes]
    messages = _par_ticket(session, MessageTicket, ids)
    evolutions = _par_ticket(session, TicketEvolution, ids)
    documents = _par_ticket(session, Document, ids)

    groupes: dict[tuple[str, str], Echeance] = {}
    for ticket, cloture in closes:
        genre = type_de(ticket.categorie)
        echoit_le, exercice, dernier = echeance(cloture, genre.exercices, mois_debut)
        groupe = groupes.setdefault(
            (genre.code, exercice), Echeance(genre, exercice, dernier, echoit_le)
        )
        groupe.affaires += 1
        for chemin in fichiers_de(
            ticket, messages[ticket.id], evolutions[ticket.id], documents[ticket.id]
        ):
            if chemin is None or not chemin.is_file():
                groupe.absents += 1
            else:
                groupe.fichiers += 1
                groupe.octets += chemin.stat().st_size
    return sorted(groupes.values(), key=lambda e: (e.echoit_le, e.type.exercices))
