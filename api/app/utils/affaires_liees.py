"""Les AFFAIRES LIÉES : lire, poser, ajouter — la règle, écrite une fois (#1342).

## 🔴 Un lien ne révèle rien

Une affaire liée que le lecteur ne peut pas lire — confidentielle, hors de son
périmètre — n'apparaît PAS pour lui : ni son titre, ni son numéro. La lecture
passe par `ticket_visible`, la règle de la fiche elle-même : un lien n'est pas
une seconde porte d'entrée.

Et ce qu'on ne voit pas, on ne le défait pas : poser les liens d'une affaire
(création, correction) ne remplace que ceux que le lecteur VOIT. Un lien vers
une affaire confidentielle, posé par le conseil, survit à la correction d'un
résident qui ignore son existence.

## 🔒 Le conseil relie, et lui seul (arbitré le 30/09/2026)

Poser, retirer ou ajouter un lien est un geste du conseil syndical ou de
l'administration (`est_moderateur`) — à la création, en correction comme
depuis une Suite. L'auteur les lisait et les posait depuis #1342 ; il les
LIT encore, sur la fiche. La règle s'écrit ICI, dans les deux fonctions qui
écrivent un lien, et non chez les trois routeurs qui les appellent : un
quatrième chemin l'hériterait sans y penser.

⚠️ Elle refuse un CHANGEMENT, pas l'envoi : une correction qui renvoie les
liens tels qu'ils sont — un client en cache, un formulaire qui les recopie —
passe, et ne fait rien.

## Réciproque par construction

Une ligne par paire, rangée (`models/affaires_liees`) : lire les liens d'une
affaire, c'est lire les deux colonnes.
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import NaiveDatetime
from sqlmodel import Session, or_, select

from app.auth.deps import est_moderateur
from app.models.affaires_liees import AffaireLiee
from app.models.core import Ticket, Utilisateur
from app.utils.valeurs import valeur
from app.utils.visibility import ticket_visible


def _paire(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def liens_de(session: Session, ticket_id: int) -> dict[int, NaiveDatetime]:
    """Les affaires liées à celle-ci, dans les deux sens, avec la DATE du lien."""
    lignes = session.exec(
        select(AffaireLiee).where(
            or_(AffaireLiee.affaire_id == ticket_id, AffaireLiee.liee_id == ticket_id)
        )
    ).all()
    return {
        (lg.liee_id if lg.affaire_id == ticket_id else lg.affaire_id): lg.cree_le for lg in lignes
    }


def ids_lies(session: Session, ticket_id: int) -> set[int]:
    """Les affaires liées à celle-ci, dans les deux sens."""
    return set(liens_de(session, ticket_id))


def index_des_liens(session: Session) -> dict[int, set[int]]:
    """Tous les liens, en UNE requête — pour une liste d'affaires."""
    index: dict[int, set[int]] = {}
    for lg in session.exec(select(AffaireLiee)).all():
        index.setdefault(lg.affaire_id, set()).add(lg.liee_id)
        index.setdefault(lg.liee_id, set()).add(lg.affaire_id)
    return index


def liees_lisibles(
    session: Session,
    ticket_id: int,
    lecteur: Utilisateur | None,
    *,
    index: dict[int, set[int]] | None = None,
    tickets: dict[int, Ticket] | None = None,
) -> list[dict]:
    """Les affaires liées que CE lecteur peut lire : numéro, titre, statut.

    Sans lecteur, rien : c'est le défaut sûr d'une réponse qui ne sait pas à
    qui elle parle.
    """
    if lecteur is None:
        return []
    ids = index.get(ticket_id, set()) if index is not None else ids_lies(session, ticket_id)
    if not ids:
        return []
    if tickets is None:
        tickets = {t.id: t for t in session.exec(select(Ticket).where(Ticket.id.in_(ids))).all()}
    lues = [tickets[i] for i in ids if i in tickets and ticket_visible(tickets[i], lecteur)]
    return [_lue(t) for t in sorted(lues, key=lambda t: t.numero)]


def _lue(t: Ticket) -> dict:
    """Ce qu'on montre d'une affaire liée — et d'une affaire proposée au choix,
    ou à la fusion (`fusion_affaires.candidates`)."""
    return {
        "id": t.id,
        "numero": t.numero,
        "titre": t.titre,
        "statut": valeur(t.statut),
        "cree_le": t.cree_le,
        #  L'état d'une absorbée est celui de sa principale (#2186) : sans ce
        #  drapeau, l'écran la prenait pour une affaire ouverte à fusionner.
        "fusionnee": t.fusionnee_dans_id is not None,
    }


def choix_lisibles(session: Session, lecteur: Utilisateur) -> list[dict]:
    """Les affaires que ce lecteur peut lier : celles qu'il peut LIRE, les plus
    récentes d'abord. Le choix se filtre à l'écran — une copropriété en compte
    quelques centaines, et la règle de lecture n'a pas d'écriture SQL."""
    tickets = session.exec(select(Ticket).order_by(Ticket.id.desc())).all()
    return [_lue(t) for t in tickets if ticket_visible(t, lecteur)]


def _cibles_lisibles(session: Session, ticket: Ticket, ids, lecteur: Utilisateur) -> set[int]:
    """Les affaires demandées, chacune existante et LISIBLE par le lecteur — sinon 422.

    Absente ou illisible, la réponse est la MÊME : dire « elle existe mais pas
    pour vous » révélerait ce que la règle cache. Un 422 et non un 404 : c'est
    le corps de la requête qui désigne l'inconnu, pas l'URL.
    """
    cibles = {int(i) for i in ids or [] if int(i) != ticket.id}
    for i in cibles:
        t = session.get(Ticket, i)
        if t is None or not ticket_visible(t, lecteur):
            raise HTTPException(422, f"Affaire liée introuvable (#{i})")
    return cibles


def _exiger_conseil(lecteur: Utilisateur) -> None:
    """Relier des affaires est un geste du conseil ou de l'admin (lève 403 sinon)."""
    if not est_moderateur(lecteur):
        raise HTTPException(403, "Seul le conseil syndical relie des affaires entre elles")


def poser_liens(session: Session, ticket: Ticket, ids, lecteur: Utilisateur) -> None:
    """Création, correction : les liens VISIBLES du lecteur deviennent `ids`. Sans `commit`."""
    cibles = _cibles_lisibles(session, ticket, ids, lecteur)
    actuels = ids_lies(session, ticket.id)
    visibles = {
        i
        for i in actuels
        if (t := session.get(Ticket, i)) is not None and ticket_visible(t, lecteur)
    }
    if cibles - actuels or visibles - cibles:
        _exiger_conseil(lecteur)
    for i in cibles - actuels:
        a, b = _paire(ticket.id, i)
        session.add(AffaireLiee(affaire_id=a, liee_id=b, cree_par_id=lecteur.id))
    for i in visibles - cibles:
        a, b = _paire(ticket.id, i)
        ligne = session.exec(
            select(AffaireLiee).where(AffaireLiee.affaire_id == a, AffaireLiee.liee_id == b)
        ).first()
        if ligne:
            session.delete(ligne)


def ajouter_liens(session: Session, ticket: Ticket, ids, lecteur: Utilisateur) -> None:
    """Une Suite : elle AJOUTE des liens, elle n'en retire aucun. Sans `commit`."""
    actuels = ids_lies(session, ticket.id)
    nouveaux = _cibles_lisibles(session, ticket, ids, lecteur) - actuels
    if nouveaux:
        _exiger_conseil(lecteur)
    for i in nouveaux:
        a, b = _paire(ticket.id, i)
        session.add(AffaireLiee(affaire_id=a, liee_id=b, cree_par_id=lecteur.id))


def supprimer_liens_de(session: Session, ticket_id: int) -> None:
    """Une affaire supprimée ne laisse aucun lien derrière elle. Sans `commit`."""
    for lg in session.exec(
        select(AffaireLiee).where(
            or_(AffaireLiee.affaire_id == ticket_id, AffaireLiee.liee_id == ticket_id)
        )
    ).all():
        session.delete(lg)
