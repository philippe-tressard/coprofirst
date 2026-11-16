"""Le badge 📍 d'une carte de ticket dit-il bien le bâtiment du DEMANDEUR ?

`auteur_batiment_nom` porte son sens dans son nom, la carte le rend sous 📍 —
l'icône réservée au **lieu physique** — et son commentaire dit « LE BÂTIMENT DU
DEMANDEUR ». Trois affirmations, et le calcul en faisait une quatrième :

    auteur_batiment_id = ticket.batiment_id or (auteur.batiment_id if auteur else None)

Le bâtiment **du ticket** d'abord, celui de l'auteur seulement à défaut. Dès
qu'un ticket portait un `batiment_id`, le badge affichait le périmètre visé sous
une étiquette qui annonce une personne : un membre du CS lisait
« Paul DELMAS 📍 Bât. 4 » et en déduisait où habite Paul.

Signalé à l'écran le 30/08/2026 (#653) sur une carte où « Bât. 4 » apparaissait
**deux fois** — une fois en périmètre (🔹), une fois en badge (📍). La question
posée était « n'est-ce pas inutile ? » ; la réponse est que ce n'était pas
seulement redondant, c'était **faux**.

## Ce que ce fichier verrouille, et pourquoi chaque cas est là

Aucun test ne couvrait ce champ. Les trois cas ci-dessous sont exactement les
trois façons de le casser à nouveau :

  1. le repli revient  → le bâtiment du ticket réapparaît sous l'étiquette ;
  2. le repli revient  → un auteur SANS bâtiment se voit attribuer celui du
     ticket, ce qui est la forme la plus discrète du même défaut ;
  3. le cas nominal    → sans lui, un champ constamment `None` passerait les
     deux premiers (`standards/04` §2 : un contrôle dont le vert peut être
     obtenu sans rien mesurer ne mesure rien).

⚠️ Le cas 3 n'est pas une politesse : les cas 1 et 2 attendent tous deux une
ABSENCE. Une implémentation qui renverrait toujours `None` les satisferait.
"""

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models.core import Batiment, Ticket, Utilisateur
from app.routers.tickets.commun import ticket_read
from tests.aides_base import compte

EMAIL = "demandeur-653@test.test"


def _purger(session: Session) -> None:
    """Retirer l'auteur de test et ses tickets, s'ils ont survécu.

    ⚠️ Appelé à l'ENTRÉE comme à la sortie. Une fixture qui ne nettoie qu'en
    sortie laisse ses lignes derrière elle dès qu'un test échoue — et le
    suivant tombe alors sur `UNIQUE constraint failed: utilisateur.email`,
    c'est-à-dire une erreur de montage qui masque le vrai verdict. Vécu en
    écrivant ce fichier, et c'est le motif que `conftest.py` documente déjà
    pour le patrimoine (15/08/2026).
    """
    for u in session.exec(select(Utilisateur).where(Utilisateur.email == EMAIL)).all():
        for t in session.exec(select(Ticket).where(Ticket.auteur_id == u.id)).all():
            session.delete(t)
        session.delete(u)
    session.commit()


@pytest.fixture()
def contexte(batiments: list[int]):
    """Un auteur, et deux bâtiments distincts : le sien et celui que le ticket vise.

    Les deux doivent différer — c'est la seule configuration où l'ancien calcul
    et le nouveau ne rendent pas la même chose. Un test monté sur un bâtiment
    unique aurait passé avant comme après le correctif.
    """
    with Session(engine) as session:
        _purger(session)
        bat_auteur, bat_ticket = batiments[0], batiments[1]
        assert bat_auteur != bat_ticket
        auteur = compte(
            session, email=EMAIL, prenom="Alex", nom="Demandeur", batiment_id=bat_auteur
        )
        yield session, auteur, bat_auteur, bat_ticket
        _purger(session)


def _numero(session: Session, batiment_id: int) -> str:
    return f"Bât. {session.get(Batiment, batiment_id).numero}"


_compteur = 0


def _lire(session: Session, **champs) -> str | None:
    """Crée un ticket, lit son `auteur_batiment_nom`, puis le retire.

    `numero` est NOT NULL et normalement posé par l'endpoint de création ; on le
    fournit donc ici, unique par appel — le rôle de ce fichier est d'éprouver
    `ticket_read`, pas la fabrique de numéros.
    """
    global _compteur
    _compteur += 1
    ticket = Ticket(
        numero=f"TK-653-{_compteur:03d}",
        titre="T",
        description="d",
        categorie="panne",
        **champs,
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    try:
        return ticket_read(ticket, session).auteur_batiment_nom
    finally:
        session.delete(ticket)
        session.commit()


def test_le_batiment_du_ticket_ne_prend_jamais_la_place_de_celui_de_l_auteur(contexte):
    """🔴 LE CAS DE #653 : les deux existent et diffèrent — c'est l'auteur qui gagne."""
    session, auteur, bat_auteur, bat_ticket = contexte
    lu = _lire(session, auteur_id=auteur.id, batiment_id=bat_ticket)
    assert lu == _numero(session, bat_auteur), (
        "Le badge doit dire le bâtiment du DEMANDEUR. Obtenu le bâtiment du "
        "ticket : le repli `ticket.batiment_id or …` est revenu."
    )
    assert lu != _numero(session, bat_ticket)


def test_un_auteur_sans_batiment_n_herite_pas_de_celui_du_ticket(contexte):
    """La forme discrète du même défaut : une valeur juste, sous une étiquette fausse.

    Ne rien afficher est le bon comportement — le périmètre visé est déjà rendu
    à côté par le badge 🔹, donc taire ce champ ne perd aucune information.
    """
    session, auteur, _bat_auteur, bat_ticket = contexte
    auteur.batiment_id = None
    session.add(auteur)
    session.commit()
    assert _lire(session, auteur_id=auteur.id, batiment_id=bat_ticket) is None


def test_le_batiment_de_l_auteur_est_bien_rendu_quand_il_existe(contexte):
    """Le cas zéro de ce fichier : sans lui, un champ toujours `None` passerait."""
    session, auteur, bat_auteur, _bat_ticket = contexte
    assert _lire(session, auteur_id=auteur.id) == _numero(session, bat_auteur)
