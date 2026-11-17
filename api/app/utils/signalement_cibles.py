"""Ce qu'un résident peut SIGNALER au conseil syndical — le registre unique (#2861).

## Pourquoi un registre

Les magasins d'applications exigent qu'un contenu publié par un utilisateur, et une
réponse de l'assistant IA, se signalent depuis l'app (Google Play, règlements sur le
contenu des utilisateurs et sur l'IA ; App Store, règle 1.2). `POST /signalements` ne
visait que la Communauté ; le 17/11/2026, Philippe a tranché d'y ajouter **une affaire
et ses suites** et **la réponse de l'assistant à une question au règlement**
(« 1a ; 2a ; 3 oui »).

Chaque cible déclare ici, une fois : son modèle, qui la VOIT, ce que le conseil lit
dans sa file (l'aperçu, l'auteur) et où le lien le dépose. Le routeur ne connaît plus
aucun type.

## 🔴 Ne signale que qui la voit

Le signalement ne vérifiait aucune visibilité : un identifiant tiré au hasard
répondait 404 ou 201 selon qu'il existait. Chaque cible nomme désormais le prédicat
qui REFUSE la lecture du même objet ailleurs (`ticket_visible`, `idee_visible`…),
jamais une copie ; un contenu invisible répond 404, comme un contenu absent.
🔒 `tests/test_signalements.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from sqlmodel import Session

from app.auth.deps import question_reglement_visible
from app.models.communaute import (
    CommentaireSondage,
    Idee,
    PetiteAnnonce,
    ReponseCommunaute,
    Sondage,
)
from app.models.core import Utilisateur
from app.models.reglement import QuestionReglement
from app.models.tickets import Ticket, TicketEvolution
from app.utils.liens import lien_element, lien_sondage, lien_ticket
from app.utils.synthese_affaire.lecture import evolutions_lisibles
from app.utils.visibility.objets import (
    annonce_visible,
    idee_visible,
    sondage_accessible,
    ticket_visible,
)

#: La longueur de l'aperçu qu'un texte long laisse dans la file du conseil.
LONGUEUR_APERCU = 140


def _auteur(objet: Any) -> Optional[int]:
    return objet.auteur_id


@dataclass(frozen=True)
class Cible:
    libelle: str  #: ce que la file du conseil affiche
    modele: type
    visible: Callable[[Session, Any, Utilisateur], bool]
    apercu: Callable[[Any], str]
    lien: Callable[[Any], str]
    #: Qui l'a écrite — `None` pour la réponse de l'assistant, que personne n'a écrite.
    auteur_id: Callable[[Any], Optional[int]] = _auteur
    #: Une cible de la Communauté exige aussi l'accès à la Communauté (`exiger_acces`).
    communaute: bool = False


def _court(texte: Optional[str]) -> str:
    return (texte or "")[:LONGUEUR_APERCU]


def _reponse_visible(session: Session, r: ReponseCommunaute, user: Utilisateur) -> bool:
    """Une réponse se lit sous son idée ou son annonce : elle en suit la visibilité."""
    if r.rubrique == "idee":
        idee = session.get(Idee, r.cible_id)
        return idee is not None and idee_visible(idee, user)
    annonce = session.get(PetiteAnnonce, r.cible_id)
    return annonce is not None and annonce_visible(annonce, user)


def _commentaire_visible(session: Session, c: CommentaireSondage, user: Utilisateur) -> bool:
    sondage = session.get(Sondage, c.sondage_id)
    return sondage is not None and sondage_accessible(sondage, user)


def _suite_visible(session: Session, e: TicketEvolution, user: Utilisateur) -> bool:
    """Une suite se lit par qui lit son affaire, sauf la synthèse en brouillon (#1643) ;
    une suite sans texte (un simple changement d'étape) n'a rien à signaler."""
    ticket = session.get(Ticket, e.ticket_id)
    if not e.contenu or ticket is None or not ticket_visible(ticket, user):
        return False
    return bool(evolutions_lisibles(session, ticket, [e], user))


#: Clé : le `cible_type` que le client envoie, et que la file garde.
CIBLES: dict[str, Cible] = {
    "idee": Cible(
        "Idée",
        Idee,
        lambda s, o, u: idee_visible(o, u),
        lambda o: o.titre,
        lambda o: lien_element("idee", o.id),
        communaute=True,
    ),
    "annonce": Cible(
        "Annonce",
        PetiteAnnonce,
        lambda s, o, u: annonce_visible(o, u),
        lambda o: o.titre,
        lambda o: lien_element("annonce", o.id),
        communaute=True,
    ),
    "sondage": Cible(
        "Sondage",
        Sondage,
        lambda s, o, u: sondage_accessible(o, u),
        lambda o: o.question,
        lambda o: lien_sondage(o.id),
        communaute=True,
    ),
    #  Les réponses et commentaires n'ont pas d'ancre propre : le lien mène à leur
    #  parent, où ils s'affichent.
    "reponse": Cible(
        "Réponse",
        ReponseCommunaute,
        _reponse_visible,
        lambda o: _court(o.contenu),
        lambda o: lien_element(o.rubrique, o.cible_id),
        communaute=True,
    ),
    "commentaire": Cible(
        "Commentaire",
        CommentaireSondage,
        _commentaire_visible,
        lambda o: _court(o.contenu),
        lambda o: lien_sondage(o.sondage_id),
        communaute=True,
    ),
    "affaire": Cible(
        "Affaire",
        Ticket,
        lambda s, o, u: ticket_visible(o, u),
        lambda o: o.titre,
        lambda o: lien_ticket(o.id),
    ),
    "suite": Cible(
        "Suite d'une affaire",
        TicketEvolution,
        _suite_visible,
        lambda o: _court(o.contenu),
        lambda o: lien_ticket(o.ticket_id),
    ),
    #  C'est la RÉPONSE de l'assistant qu'on signale : son auteur n'est personne,
    #  et l'aperçu montre la question qui l'a appelée.
    "question_reglement": Cible(
        "Réponse de l'assistant IA",
        QuestionReglement,
        lambda s, o, u: question_reglement_visible(o, u, s),
        lambda o: _court(o.question),
        lambda o: lien_element("question-reglement", o.id),
        auteur_id=lambda o: None,
    ),
}


def cible_lisible(session: Session, cible_type: str, cible_id: int, user: Utilisateur):
    """L'objet signalé, s'il existe ET que ce lecteur le voit — sinon `None`.

    L'accès à la Communauté (un compte banni) se juge AVANT, par le routeur, qui en
    rend le motif (`exiger_acces`) : c'était la seule porte du geste avant #2861.
    """
    cible = CIBLES[cible_type]
    objet = session.get(cible.modele, cible_id)
    if objet is None or not cible.visible(session, objet, user):
        return None
    return objet
