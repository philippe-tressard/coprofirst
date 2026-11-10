"""Un geste servi avec une entrée du fil n'est jamais plus large que sa route (#2646).

`TicketEvolutionRead` porte `peut_modifier` et `peut_supprimer` : le site et l'app iOS
les LISENT au lieu de recomposer « conseil ou admin, auteur ou saisi pour, type
saisi » depuis les rôles. Un champ plus large que la route tendrait un crayon qui
finit en 403 ; plus étroit, il tairait un geste permis.

Ces tests ne comparent pas deux fonctions : ils lisent le fil par sa route
(`GET /tickets/{id}/evolutions`), puis JOUENT le geste par la sienne, pour chaque
rôle, chaque auteur d'entrée et chaque type — et confrontent la réponse au champ.
La dépendance que la route déclare est lue sur sa signature : une dépendance
relâchée côté route, mais pas ici, ne passe pas inaperçue.
"""

from __future__ import annotations

import inspect

import pytest
from fastapi import HTTPException

from app.models.core import RoleUtilisateur, Ticket, TicketEvolution
from app.routers.tickets import evolutions
from app.schemas import TicketEvolutionUpdate
from tests.aides_affaire import _compte, _creer, session  # noqa: F401

CS = RoleUtilisateur.conseil_syndical
ADMIN = RoleUtilisateur.admin

#: Ce qu'un humain écrit, ce qu'un humain répond, et ce que le serveur trace lui-même.
TYPES = ("commentaire", "etat", "reponse", "correction")
ROLES = ("auteur", "voisin", "conseil", "admin")
#: Qui a écrit l'entrée : le résident de l'affaire, ou le conseil.
ECRIVAINS = ("auteur", "conseil")
SORTES = ("ouverte", "absorbee")


def _monde(session, sorte: str, type_: str, ecrivain: str):
    comptes = {
        "auteur": _compte(session),
        "voisin": _compte(session),
        "conseil": _compte(session, role=CS),
        "admin": _compte(session, role=ADMIN),
    }
    affaire = _creer(session, comptes["auteur"], categorie="panne")
    if sorte == "absorbee":
        principale = _creer(session, comptes["auteur"], categorie="panne")
        ligne = session.get(Ticket, affaire.id)
        ligne.fusionnee_dans_id = principale.id
        session.add(ligne)
        session.commit()
    entree = TicketEvolution(
        ticket_id=affaire.id,
        type=type_,
        contenu="<p>Point d'étape.</p>",
        auteur_id=comptes[ecrivain].id,
    )
    session.add(entree)
    session.commit()
    return comptes, affaire.id, entree.id


def _dependance(route):
    """La dépendance d'autorisation que la route déclare sur `user`, jouée telle quelle."""
    return inspect.signature(route).parameters["user"].default.dependency


def _permis(session, geste) -> bool:
    try:
        geste()
    except HTTPException as e:
        assert e.status_code in (403, 404, 422), e
        session.rollback()
        return False
    return True


def _corriger(session, user, ticket_id, evol_id):
    _dependance(evolutions.update_evolution)(user)
    return evolutions.update_evolution(
        ticket_id,
        evol_id,
        TicketEvolutionUpdate(contenu="<p>Point corrigé.</p>"),
        session=session,
        user=user,
    )


def _supprimer(session, user, ticket_id, evol_id):
    _dependance(evolutions.delete_evolution)(user)
    return evolutions.delete_evolution(ticket_id, evol_id, session=session, user=user)


GESTES = {"peut_modifier": _corriger, "peut_supprimer": _supprimer}


def _servi(session, user, ticket_id, evol_id):
    """L'entrée telle que CE lecteur la reçoit, ou `None` s'il ne lit pas le fil."""
    try:
        fil = evolutions.get_evolutions(ticket_id, session=session, user=user)
    except HTTPException:
        return None
    return next(e for e in fil if e.id == evol_id)


def test_le_cas_fautif_un_voisin_ne_se_voit_jamais_offrir_le_crayon(session):
    """La règle que l'app recomposait : le crayon se lit, il ne se devine pas."""
    comptes, ticket_id, evol_id = _monde(session, "ouverte", "commentaire", "auteur")
    for lecteur in ("voisin", "auteur"):
        lue = _servi(session, comptes[lecteur], ticket_id, evol_id)
        if lue is not None:
            assert lue.peut_modifier is False, lecteur
    assert not _permis(session, lambda: _corriger(session, comptes["voisin"], ticket_id, evol_id))
    assert _servi(session, comptes["admin"], ticket_id, evol_id).peut_modifier is True


@pytest.mark.parametrize("sorte", SORTES)
@pytest.mark.parametrize("type_", TYPES)
@pytest.mark.parametrize("ecrivain", ECRIVAINS)
@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("geste", sorted(GESTES))
def test_le_champ_servi_dit_ce_que_la_route_accepte(session, sorte, type_, ecrivain, role, geste):
    comptes, ticket_id, evol_id = _monde(session, sorte, type_, ecrivain)
    user = comptes[role]
    lue = _servi(session, user, ticket_id, evol_id)
    permis = _permis(session, lambda: GESTES[geste](session, user, ticket_id, evol_id))
    if lue is None:
        #  Qui ne lit pas le fil n'a rien à se voir offrir — et la route le refuse.
        assert not permis, f"{role} ne lit pas le fil mais la route accepte {geste}"
        return
    assert getattr(lue, geste) is permis, (
        f"{sorte}/{type_}/{ecrivain}, {role} : servi {geste}={getattr(lue, geste)}, "
        f"la route {'accepte' if permis else 'refuse'}"
    )


def test_cas_zero_au_moins_un_geste_est_servi_ouvert(session):
    """Sans lui, un `False` partout ferait passer la confrontation ci-dessus."""
    comptes, ticket_id, evol_id = _monde(session, "ouverte", "commentaire", "conseil")
    lue = _servi(session, comptes["admin"], ticket_id, evol_id)
    assert lue.peut_modifier is True and lue.peut_supprimer is True


def test_sans_lecteur_tous_les_gestes_sont_fermes(session):
    """Un défaut FERMÉ : un geste qu'on n'a pas calculé n'est pas offert."""
    from app.auth.gestes_evolution import gestes_evolution_servis

    comptes, ticket_id, evol_id = _monde(session, "ouverte", "commentaire", "auteur")
    entree = session.get(TicketEvolution, evol_id)
    affaire = session.get(Ticket, ticket_id)
    assert gestes_evolution_servis(entree, affaire, None) == {
        "peut_modifier": False,
        "peut_supprimer": False,
    }
    assert gestes_evolution_servis(entree, None, comptes["admin"]) == {
        "peut_modifier": False,
        "peut_supprimer": False,
    }
