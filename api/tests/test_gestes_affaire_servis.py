"""Un geste servi avec l'affaire n'est jamais plus large que sa route (#2508).

`TicketRead` porte les gestes que CE lecteur peut faire de CETTE affaire
(`peut_archiver`, `peut_changer_etat`, `peut_repondre`, `peut_modifier`,
`peut_deplacer_au_kanban`) : le site et l'app iOS les LISENT au lieu de recomposer
« conseil ou admin » depuis les rôles. Un champ plus large que la route tendrait un
bouton qui finit en 403 ; plus étroit, il tairait un geste permis.

Ces tests ne comparent pas deux fonctions : ils lisent l'affaire par sa route
(`GET /tickets/{id}`), puis JOUENT le geste par la sienne, pour chaque rôle et
chaque sorte d'affaire, et confrontent la réponse au champ. Le cas fautif d'abord :
un résident à qui l'on offrirait l'archivage — la règle recopiée de l'app.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.core import RoleUtilisateur, Ticket
from app.routers.tickets import crud
from tests.aides_affaire import _compte, _corriger, _creer, _prestataire, _suite, session  # noqa: F401

CS = RoleUtilisateur.conseil_syndical
ADMIN = RoleUtilisateur.admin

#: Les sortes d'affaire, et qui la dépose — l'auteur résident pour une demande,
#: le conseil pour ce qui lui est réservé.
SORTES = ("panne_ouverte", "panne_chez_le_syndic", "panne_absorbee", "etude", "actu", "actu_suivie")
ROLES = ("auteur", "voisin", "conseil", "admin")


def _monde(session, sorte: str):
    """Les quatre comptes, et une affaire NEUVE de cette sorte."""
    comptes = {
        "auteur": _compte(session),
        "voisin": _compte(session),
        "conseil": _compte(session, role=CS),
        "admin": _compte(session, role=ADMIN),
    }
    if sorte.startswith("panne"):
        affaire = _creer(session, comptes["auteur"], categorie="panne")
        if sorte == "panne_chez_le_syndic":
            _corriger(session, comptes["conseil"], affaire.id, statut="en_cours")
        if sorte == "panne_absorbee":
            principale = _creer(session, comptes["auteur"], categorie="panne")
            ligne = session.get(Ticket, affaire.id)
            ligne.fusionnee_dans_id = principale.id
            session.add(ligne)
            session.commit()
    elif sorte == "etude":
        affaire = _creer(session, comptes["conseil"], categorie="etude_travaux")
    else:
        suivie = sorte == "actu_suivie"
        affaire = _creer(
            session, comptes["conseil"], categorie="actualite", suivre_actualite=suivie
        )
    return comptes, affaire.id


def _lu(session, user, ticket_id):
    """L'affaire telle que CE lecteur la reçoit, ou `None` s'il ne la lit pas."""
    try:
        return crud.get_ticket(ticket_id, session=session, user=user)
    except HTTPException:
        return None


def _permis(geste) -> bool:
    try:
        geste()
    except HTTPException as e:
        assert e.status_code in (403, 422), e
        return False
    return True


def _etat_cible(session, ticket_id) -> str:
    """Un état que la Suite peut porter, s'il est permis : l'actualité a les siens."""
    return "résolu" if session.get(Ticket, ticket_id).categorie == "actualite" else "en_ag"


GESTES = {
    "peut_archiver": lambda s, u, i: _corriger(s, u, i, archive_manuel=True),
    "peut_modifier": lambda s, u, i: _corriger(s, u, i, titre="Titre corrigé"),
    "peut_repondre": lambda s, u, i: _suite(s, u, i),
    "peut_changer_etat": lambda s, u, i: _suite(
        s, u, i, type="etat", nouveau_statut=_etat_cible(s, i)
    ),
}


def test_le_cas_fautif_un_resident_ne_se_voit_jamais_offrir_l_archivage(session):
    """La règle que l'app recomposait : « modérer » se lit, il ne se devine pas."""
    comptes, ticket_id = _monde(session, "panne_ouverte")
    lu = _lu(session, comptes["auteur"], ticket_id)
    assert lu.peut_archiver is False
    assert not _permis(
        lambda: _corriger(session, comptes["auteur"], ticket_id, archive_manuel=True)
    )
    assert _lu(session, comptes["conseil"], ticket_id).peut_archiver is True


@pytest.mark.parametrize("sorte", SORTES)
@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("geste", sorted(GESTES))
def test_le_champ_servi_dit_ce_que_la_route_accepte(session, sorte, role, geste):
    comptes, ticket_id = _monde(session, sorte)
    user = comptes[role]
    lu = _lu(session, user, ticket_id)
    permis = _permis(lambda: GESTES[geste](session, user, ticket_id))
    if lu is None:
        #  Qui ne lit pas l'affaire n'a rien à se voir offrir — et la route le refuse.
        assert not permis, f"{role} ne lit pas « {sorte} » mais la route accepte {geste}"
        return
    assert getattr(lu, geste) is permis, (
        f"{sorte}, {role} : servi {geste}={getattr(lu, geste)}, la route "
        f"{'accepte' if permis else 'refuse'}"
    )


@pytest.mark.parametrize("sorte", SORTES)
@pytest.mark.parametrize("role", ROLES)
def test_glisser_au_kanban_est_plus_etroit_que_la_suite_jamais_plus_large(session, sorte, role):
    """Arbitré le 23/09/2026 : le conseil seul glisse une carte suivie au tableau."""
    comptes, ticket_id = _monde(session, sorte)
    user = comptes[role]
    lu = _lu(session, user, ticket_id)
    if lu is None:
        return
    if lu.peut_deplacer_au_kanban:
        assert lu.peut_changer_etat and lu.suivi_kanban and role in ("conseil", "admin")
    else:
        assert not (role in ("conseil", "admin") and lu.suivi_kanban and lu.peut_changer_etat)


def test_sans_lecteur_tous_les_gestes_sont_fermes(session):
    """Un défaut FERMÉ : un geste qu'on n'a pas calculé n'est pas offert."""
    from app.routers.tickets.commun import ticket_read

    comptes, ticket_id = _monde(session, "panne_ouverte")
    lu = ticket_read(session.get(Ticket, ticket_id), session, None)
    assert not any(
        getattr(lu, g)
        for g in (
            "peut_archiver",
            "peut_changer_etat",
            "peut_deplacer_au_kanban",
            "peut_repondre",
            "peut_modifier",
            "peut_corriger",
            "peut_changer_prestataires",
        )
    )


#  ── ✏️ Le crayon : `peut_corriger` (#2633) ──────────────────────────────────


def _crayon_du_front(lu, user) -> bool:
    """La règle que la carte calculait (`peutEditer`, `#lib/droits`, retirée) :
    l'administrateur, l'auteur ou le « saisi pour »."""
    return user.has_role(ADMIN) or user.id in (lu.auteur_id, lu.saisi_pour_user_id)


@pytest.mark.parametrize("sorte", SORTES)
@pytest.mark.parametrize("role", ROLES)
def test_le_crayon_servi_est_celui_que_la_carte_montrait(session, sorte, role):
    """Sans régression : sur chaque sorte et chaque rôle, le crayon servi est celui
    que l'ancien calcul du front montrait — l'écart arbitré se teste à part."""
    comptes, ticket_id = _monde(session, sorte)
    user = comptes[role]
    lu = _lu(session, user, ticket_id)
    if lu is None:
        return
    assert lu.peut_corriger is _crayon_du_front(lu, user), (sorte, role)


def test_l_ecart_arbitre_le_conseil_corrige_l_actualite_d_un_autre(session):
    """Arbitré le 11/11/2026 (#2633) : la route l'accepte depuis #1091, la carte le
    taisait. Un second membre du conseil reçoit désormais le crayon."""
    comptes, ticket_id = _monde(session, "actu")
    autre_membre = _compte(session, role=CS)
    lu = _lu(session, autre_membre, ticket_id)
    assert _crayon_du_front(lu, autre_membre) is False
    assert lu.peut_corriger is True
    assert _permis(lambda: _corriger(session, autre_membre, ticket_id, titre="Corrigée"))


@pytest.mark.parametrize("sorte", SORTES)
@pytest.mark.parametrize("role", ROLES)
def test_le_crayon_n_est_jamais_plus_etroit_que_corriger_le_contenu(session, sorte, role):
    """Le crayon ouvre la correction ; sans lui, la route refuse le contenu."""
    comptes, ticket_id = _monde(session, sorte)
    user = comptes[role]
    lu = _lu(session, user, ticket_id)
    if lu is None:
        return
    if lu.peut_modifier:
        assert lu.peut_corriger
    if not lu.peut_corriger:
        assert not _permis(lambda: _corriger(session, user, ticket_id, titre="Corrigée"))


#  ── 🛠️ Les prestataires : `peut_changer_prestataires` (#2704) ─────────────────


@pytest.mark.parametrize("sorte", SORTES)
@pytest.mark.parametrize("role", ROLES)
def test_les_prestataires_servis_ne_sont_jamais_plus_larges_que_la_route(session, sorte, role):
    """Servi, le geste CHANGE la liste par la route ; la route l'ignore pour un
    non-modérateur (200 sans effet), d'où une mesure sur l'effet, pas sur le code.
    Plus étroit que la route sur une affaire close : arbitré le 12/11/2026 (Q1)."""
    comptes, ticket_id = _monde(session, sorte)
    user = comptes[role]
    lu = _lu(session, user, ticket_id)
    if lu is None or not lu.peut_changer_prestataires:
        return
    assert role in ("conseil", "admin"), f"{sorte} : offert à {role}"
    p = _prestataire(session)
    corrige = _corriger(session, user, ticket_id, prestataire_ids=[p.id])
    assert [x.id for x in corrige.prestataires] == [p.id], (sorte, role)
