"""Le point CS / Syndic, ce que #2082 y ajoute côté affaires.

Ce qui est tenu :
- **l'état à la validation** : coché d'office « Chez le syndic » pour une affaire
  Ouverte, son état sinon — « À l'AG » reste à l'AG ; rien ne change avant la
  validation ; la validation le pose par une Suite d'état ; une affaire close
  ailleurs n'est pas rouverte ;
- **la liste figée à l'ouverture** : close ailleurs pendant le point, une affaire
  reste au tableau du point (`?point=true`) — pas à la relance — et au CR ;
- **un CR validé ne se modifie plus** ;
- **la vignette** : Privé quand seuls le conseil et le syndic lisent l'affaire,
  Public sinon (auteur résident compris) ;
- **« CS et présents »** se lit d'un compte du syndic dans la rubrique de l'affaire.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.models.core import RoleUtilisateur, StatutUtilisateur
from app.models.tickets import Ticket, TicketEvolution
from app.utils.points_conseil_etats import changement_a_poser, etat_par_defaut
from app.models.points_conseil import CompteRenduAffaire
from tests.aides_http import base_http, client_http
from tests.aides_points_conseil import intercepter_envois, point_termine
from tests.aides_suivi import affaire_ouverte


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


@pytest.fixture(name="envois")
def envois_fixture(monkeypatch):
    return intercepter_envois(monkeypatch)


def _statut(moteur, ticket_id: int) -> str:
    with Session(moteur) as s:
        return s.get(Ticket, ticket_id).statut


# ── L'état à la validation ──────────────────────────────────────────────────


def test_etat_par_defaut_chez_le_syndic_sauf_a_l_ag():
    assert etat_par_defaut("ouvert") == "en_cours"
    #  « Seule une correction manuelle est autorisée » (19/10/2026).
    assert etat_par_defaut("en_ag") == "en_ag"
    assert etat_par_defaut("chez_prestataire") == "chez_prestataire"


def test_une_affaire_close_ailleurs_n_est_pas_rouverte():
    t = Ticket(numero="X", titre="x", statut="résolu")
    assert (
        changement_a_poser(t, CompteRenduAffaire(point_id=1, ticket_id=1, etat_cible="en_cours"))
        is None
    )
    t.statut = "ouvert"
    assert (
        changement_a_poser(t, CompteRenduAffaire(point_id=1, ticket_id=1, etat_cible="résolu"))
        == "résolu"
    )
    assert (
        changement_a_poser(t, CompteRenduAffaire(point_id=1, ticket_id=1, etat_cible=None)) is None
    )


def test_le_suivi_dit_l_etat_coche_d_office(moteur):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    affaire_ouverte(moteur, "Ouverte")
    affaire_ouverte(moteur, "Au vote", statut="en_ag")
    etats = {a["titre"]: a["etat_par_defaut"] for a in cs.get("/suivi-affaires").json()["affaires"]}
    assert etats == {"Ouverte": "en_cours", "Au vote": "en_ag"}


def test_l_etat_ne_change_qu_a_la_validation(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, t, _ = point_termine(moteur, cs, etat_cible="résolu")
    assert _statut(moteur, t) == "ouvert", "rien avant la validation"
    assert cs.post(f"/points-conseil/{point}/valider").status_code == 204
    assert _statut(moteur, t) == "résolu"
    with Session(moteur) as s:
        (suite,) = s.exec(select(TicketEvolution).where(TicketEvolution.ticket_id == t)).all()
    assert (suite.type, suite.ancien_statut, suite.nouveau_statut) == ("etat", "ouvert", "résolu")
    assert "point CS / Syndic" in suite.contenu


def test_un_etat_hors_liste_est_refuse(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, t, _ = point_termine(moteur, cs)
    r = cs.put(
        f"/points-conseil/{point}/affaires/{t}",
        json={"contenu": "<p>x</p>", "etat_cible": "ouvert"},
    )
    assert r.status_code == 422


# ── La liste figée, et le CR validé ─────────────────────────────────────────


def test_close_ailleurs_pendant_le_point_elle_reste_au_tableau_du_point(moteur):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    t = affaire_ouverte(moteur, "Close pendant la réunion")
    point = cs.post(
        "/points-conseil", json={"mode": "affaires", "debut": "2026-10-19T17:00:00"}
    ).json()["point"]["id"]
    with Session(moteur) as s:
        ticket = s.get(Ticket, t)
        ticket.statut = "résolu"
        s.add(ticket)
        s.commit()
    du_point = cs.get("/suivi-affaires?point=true").json()["affaires"]
    assert [a["id"] for a in du_point] == [t]
    assert cs.get("/suivi-affaires").json()["affaires"] == [], "la relance ne la voit plus"
    r = cs.put(f"/points-conseil/{point}/affaires/{t}", json={"contenu": "<p>Close</p>"})
    assert r.status_code == 200, r.text


def test_un_cr_valide_ne_se_modifie_plus(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, t, _ = point_termine(moteur, cs)
    cs.post(f"/points-conseil/{point}/valider")
    r = cs.put(f"/points-conseil/{point}/affaires/{t}", json={"contenu": "<p>Après</p>"})
    assert r.status_code == 409


# ── La vignette ─────────────────────────────────────────────────────────────


def test_vignette_privee_quand_seuls_le_conseil_et_le_syndic_lisent(moteur):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    affaire_ouverte(moteur, "Confidentielle", confidentiel=True, auteur_id=None)
    #  L'auteur résident la lit : elle est publique (arbitré le 20/10/2026).
    affaire_ouverte(moteur, "De son auteur", confidentiel=True)
    vignettes = {a["titre"]: a["prive"] for a in cs.get("/suivi-affaires").json()["affaires"]}
    assert vignettes == {"Confidentielle": True, "De son auteur": False}


# ── « CS et présents » dans l'affaire ───────────────────────────────────────


def test_cs_et_presents_se_lit_d_un_compte_du_syndic_pas_d_un_resident(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, t, _ = point_termine(moteur, cs, conseil_seul=True)
    cs.post(f"/points-conseil/{point}/valider")
    syndic, _ = client_http(moteur, RoleUtilisateur.résident, statut=StatutUtilisateur.syndic)
    assert len(syndic.get(f"/points-conseil/affaires/{t}").json()) == 1
    resident, _ = client_http(moteur, RoleUtilisateur.résident)
    lu = resident.get(f"/points-conseil/affaires/{t}")
    assert lu.status_code in (200, 403) and (lu.status_code == 403 or lu.json() == [])
