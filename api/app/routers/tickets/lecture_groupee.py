"""Tickets — ce que `ticket_read` lit autour d'une affaire, lu d'un coup pour une liste.

## 🔴 Pourquoi ce module (#1838, 11/10/2026)

`GET /tickets` répondait en 300 à 470 ms en production, et s'alourdissait
d'une semaine à l'autre : `ticket_read` relisait, POUR CHAQUE affaire, son
auteur, le bâtiment de celui-ci, la personne « saisi pour », son prestataire,
son contrat, l'affaire qui l'a absorbée, le compte de ses relances, le délai
d'archivage du site et — faute de pièce propre — tout son fil. Mesuré : 40
requêtes pour 5 affaires, 298 pour 40. Sous PostgreSQL, chaque requête coûte
quelques dizaines de millisecondes : la boucle se payait affaire par affaire.

Ici, chaque notion est lue UNE fois pour toute la liste. Une affaire seule
passe par le même chemin, avec une liste d'un élément : il n'y a donc qu'une
écriture de chaque lecture, et la fiche ne peut pas diverger de la liste.

🔒 `tests/test_requetes_listes_affaires.py` : le compte de requêtes de la liste
est le même pour 5 et pour 40 affaires. Un champ dérivé qui relirait sa table
affaire par affaire le fait échouer.

⚠️ La règle de LECTURE reste en Python (`ticket_visible`, #710) : on groupe ce
qui se lit, jamais ce qui se décide.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sqlmodel import Session, func, select

from app.models.core import Batiment, Ticket, TicketEvolution, Utilisateur
from app.models.prestataires import ContratEntretien, Prestataire
from app.utils.affaires_liees import index_des_liens
from app.utils.archivage import seuil_archivage_jours
from app.utils.photos import parse_photos
from app.utils.recuperer import precharger


@dataclass(frozen=True)
class LectureGroupee:
    """Ce que les affaires d'une liste partagent, lu une fois."""

    #: Les liens entre affaires, dans les deux sens (#1342).
    liens: dict[int, set[int]]
    #: Toutes les affaires que la lecture peut nommer : la liste, ses affaires
    #: liées, et celles qui en ont absorbé une.
    tickets: dict[int, Ticket]
    #: Le nombre de relances syndic de chaque affaire.
    relances: Counter
    #: Les pièces de l'entrée de fil la plus RÉCENTE qui en porte (#464).
    pieces_du_fil: dict[int, list[str]]
    seuil_jours: int
    #: Lignes préchargées pour `session.get` : la carte d'identité de la
    #: session ne les retient que faiblement (`recuperer.precharger`).
    retenues: tuple


def relances_par_affaire(session: Session, ids) -> Counter:
    """Le nombre de relances syndic déjà envoyées, par affaire — 0 si aucune."""
    return Counter(
        dict(
            session.exec(
                select(TicketEvolution.ticket_id, func.count())
                .where(TicketEvolution.ticket_id.in_(ids), TicketEvolution.type == "relance")
                .group_by(TicketEvolution.ticket_id)
            ).all()
        )
    )


def pieces_du_fil(session: Session, ids) -> dict[int, list[str]]:
    """Par affaire, les pièces de l'entrée de fil la plus RÉCENTE qui en porte.

    C'est le repli de la vignette d'une carte repliée quand l'affaire n'a pas
    de pièce propre (`commun.ticket_read`, #464). ⚠️ La plus récente, jamais la
    première : un dossier qui a avancé montrerait sinon indéfiniment la photo
    du jour de son ouverture.
    """
    pieces: dict[int, list[str]] = {}
    for ticket_id, fichiers in session.exec(
        select(TicketEvolution.ticket_id, TicketEvolution.fichiers_urls)
        .where(
            TicketEvolution.ticket_id.in_(ids),
            TicketEvolution.fichiers_urls.is_not(None),
            TicketEvolution.fichiers_urls != "[]",  # le défaut de la colonne : rien à montrer
        )
        .order_by(TicketEvolution.cree_le.desc(), TicketEvolution.id.desc())
    ).all():
        if ticket_id not in pieces and (trouvees := parse_photos(fichiers)):
            pieces[ticket_id] = trouvees
    return pieces


def lecture_groupee(session: Session, tickets: list[Ticket]) -> LectureGroupee:
    """Tout ce que `ticket_read` lit autour de ces affaires, en un nombre fixe de requêtes."""
    ids = [t.id for t in tickets]
    connus = {t.id: t for t in tickets}
    liens = index_des_liens(session)
    voisins = {i for t in tickets for i in liens.get(t.id, ())}
    voisins |= {t.fusionnee_dans_id for t in tickets if t.fusionnee_dans_id}
    connus |= {t.id: t for t in precharger(session, Ticket, voisins - connus.keys())}
    personnes = precharger(
        session, Utilisateur, {i for t in tickets for i in (t.auteur_id, t.saisi_pour_user_id)}
    )
    retenues = (
        *personnes,
        *precharger(session, Batiment, {p.batiment_id for p in personnes}),
        *precharger(session, Prestataire, {t.prestataire_id for t in tickets}),
        *precharger(session, ContratEntretien, {t.contrat_id for t in tickets}),
    )
    return LectureGroupee(
        liens=liens,
        tickets=connus,
        relances=relances_par_affaire(session, ids),
        pieces_du_fil=pieces_du_fil(session, ids),
        seuil_jours=seuil_archivage_jours(session),
        retenues=retenues,
    )
