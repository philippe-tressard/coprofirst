"""Qui lit un fichier servi en direct (`/uploads/*`) — le droit de l'objet PORTEUR (#2154).

## Le défaut corrigé (audit OWASP du 22/10/2026)

Caddy servait `/uploads/*` à toute session valide (`forward_auth` →
`/auth/verifier-acces`, qui ne lisait pas l'adresse demandée). La pièce jointe
d'une affaire réservée à un bâtiment, d'un message interne du conseil, se lisait
donc par tout compte qui en connaissait l'URL — et l'URL circule (courriels,
transferts, historique), et reste valable après la perte du droit. Le fichier
d'une affaire réservée était plus ouvert que l'affaire.

## La règle — arbitrée par Philippe le 23/10/2026

1. Un dossier qui ne se sert jamais (`stockage.JAMAIS_SERVIS`) : refusé.
2. Un dossier sans objet porteur à juger (`TOUTE_SESSION` : avatars, photo de la
   résidence, logo) : toute session — l'annuaire montre déjà les avatars à tout
   compte.
3. Sinon, les objets qui CITENT le fichier (`PORTEURS`) : il se lit si l'UN d'eux
   se lit, par le prédicat de visibilité de cet objet — jamais une copie.
4. Aucun porteur : son auteur seul (`FichierRecu`, la photo d'un formulaire pas
   encore enregistré) ; sans auteur connu (fichier reçu avant #2154, compte
   supprimé), le conseil et l'administration.

Un fichier cité seulement dans un HTML riche n'a pas de porteur ici : l'éditeur
n'insère aucune image (`RichEditor`, sans extension Image), et une citation forgée
par l'API retombe sur la règle 4 — le sens fermé.

## Deux portes, une règle

Caddy (`/auth/verifier-acces`) et le service d'une installation commune
(`installation_commune/fichiers`) appellent `exiger_fichier_lisible`.
🔒 `tests/test_acces_fichiers_porteur.py` : la règle par cas, les deux portes, et
toute colonne qui cite un fichier (`photos.COLONNES_DE_FICHIERS`) a son porteur ici.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlmodel import Session, select

from app.auth.deps import est_moderateur, lit_les_notes_internes
from app.models.annonce_hall import AnnonceHall
from app.models.communaute import PetiteAnnonce
from app.models.core import Utilisateur
from app.models.evenement import Evenement, EvenementEvolution
from app.models.fichiers_recus import FichierRecu
from app.models.tickets import MessageTicket, Ticket, TicketEvolution
from app.utils.photos import parse_photos
from app.utils.recuperer import present_ou_404
from app.utils.stockage import JAMAIS_SERVIS, PREFIXE_URL
from app.utils.visibility.objets import annonce_visible, evenement_visible, ticket_visible

#: Les dossiers sans objet porteur à juger — et pourquoi (arbitrage du 23/10/2026).
TOUTE_SESSION = {
    "avatars": "la photo d'un compte : l'annuaire la montre déjà à tout compte",
    "residence": "la photo de la résidence, celle de l'accueil de chacun",
    "logo": "le logo, servi sans session par /config/logo.png",
}


def _ticket(session: Session, user: Utilisateur, ticket: Ticket) -> bool:
    return ticket_visible(ticket, user)


def _suite(session: Session, user: Utilisateur, evol: TicketEvolution) -> bool:
    from app.utils.synthese_affaire.lecture import evolutions_lisibles

    ticket = session.get(Ticket, evol.ticket_id)
    return (
        ticket is not None
        and ticket_visible(ticket, user)
        and bool(evolutions_lisibles(session, ticket, [evol], user))
    )


def _message(session: Session, user: Utilisateur, message: MessageTicket) -> bool:
    if message.interne and not lit_les_notes_internes(user):
        return False
    ticket = session.get(Ticket, message.ticket_id)
    return ticket is not None and ticket_visible(ticket, user)


def _affiche(session: Session, user: Utilisateur, _affiche: AnnonceHall) -> bool:
    #  Les affiches se préparent et se lisent au conseil (`require_cs_or_admin`).
    return est_moderateur(user)


def _petite_annonce(session: Session, user: Utilisateur, annonce: PetiteAnnonce) -> bool:
    from app.utils.communaute import acces_ouvert

    return acces_ouvert(user) and annonce_visible(annonce, user)


def _evenement(session: Session, user: Utilisateur, ev: Evenement) -> bool:
    return evenement_visible(ev, user)


def _suite_evenement(session: Session, user: Utilisateur, evol: EvenementEvolution) -> bool:
    ev = session.get(Evenement, evol.evenement_id)
    return ev is not None and evenement_visible(ev, user)


@dataclass(frozen=True)
class Porteur:
    """Une colonne qui cite des fichiers, et le prédicat de lecture de sa ligne."""

    modele: type
    colonne: str
    lisible: Callable[[Session, Utilisateur, object], bool]


#: Toute colonne de `photos.COLONNES_DE_FICHIERS` d'une table déclarée est ici —
#: le test le vérifie, une table neuve qui joint des fichiers n'y échappe pas.
PORTEURS = (
    Porteur(Ticket, "photos_urls", _ticket),
    Porteur(Ticket, "fichiers_urls", _ticket),
    Porteur(TicketEvolution, "fichiers_urls", _suite),
    Porteur(MessageTicket, "fichiers_urls", _message),
    Porteur(AnnonceHall, "images_json", _affiche),
    Porteur(PetiteAnnonce, "photos_json", _petite_annonce),
    Porteur(Evenement, "photos_urls", _evenement),
    Porteur(Evenement, "fichiers_urls", _evenement),
    Porteur(EvenementEvolution, "fichiers_urls", _suite_evenement),
)


def porteurs_du_fichier(session: Session, cle: str) -> list[tuple[Porteur, object]]:
    """Les lignes qui citent ce fichier — l'adresse exacte, pas un préfixe."""
    url = PREFIXE_URL + cle
    trouves = []
    for porteur in PORTEURS:
        colonne = getattr(porteur.modele, porteur.colonne)
        candidats = session.exec(
            select(porteur.modele).where(colonne.contains(url, autoescape=True))
        ).all()
        trouves += [
            (porteur, ligne)
            for ligne in candidats
            if url in parse_photos(getattr(ligne, porteur.colonne))
        ]
    return trouves


def fichier_lisible(session: Session, user: Utilisateur, cle: str) -> bool:
    """Cet utilisateur peut-il lire le fichier `cle` (`fichiers/<nom>.jpg`) ?"""
    dossier = cle.split("/", 1)[0]
    if dossier in JAMAIS_SERVIS:
        return False
    if dossier in TOUTE_SESSION:
        return True
    porteurs = porteurs_du_fichier(session, cle)
    if porteurs:
        return any(p.lisible(session, user, ligne) for p, ligne in porteurs)
    recu = session.exec(select(FichierRecu).where(FichierRecu.cle == cle)).first()
    if recu is not None and recu.auteur_id is not None:
        return recu.auteur_id == user.id
    return est_moderateur(user)


def exiger_fichier_lisible(session: Session, user: Utilisateur, cle: str | None) -> None:
    """404 si la clé est absente ou illisible pour lui — sans dire lequel des deux."""
    present_ou_404(
        cle if cle and fichier_lisible(session, user, cle) else None, "Fichier introuvable"
    )
