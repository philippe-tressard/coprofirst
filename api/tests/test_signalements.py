"""Signaler au conseil syndical : les cibles et la règle « ne signale que qui la voit » (#2861).

Les magasins exigent qu'un contenu publié et une réponse de l'assistant IA se
signalent depuis l'app. Le registre `utils/signalement_cibles.CIBLES` porte chaque
cible ; ces tests l'éprouvent par la vraie route, avec la vraie authentification.

🔴 Le cas que ce lot ferme : un contenu que le lecteur ne voit pas répondait 201 —
l'identifiant suffisait. Il répond désormais 404, comme un contenu absent.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.models.communaute import Idee
from app.models.core import RoleUtilisateur, Signalement
from app.models.reglement import QuestionReglement, TexteReglement
from app.models.tickets import TicketEvolution
from app.utils.signalement_cibles import CIBLES
from tests.aides_base import compte
from tests.aides_http import base_http, client_http
from tests.aides_suivi import affaire_ouverte


@pytest.fixture()
def moteur():
    with base_http() as m:
        yield m


def _signaler(http, cible_type: str, cible_id: int, motif: str = "Propos injurieux"):
    return http.post(
        "/signalements", json={"cible_type": cible_type, "cible_id": cible_id, "motif": motif}
    )


def _ajouter(moteur, objet) -> int:
    with Session(moteur) as s:
        s.add(objet)
        s.commit()
        s.refresh(objet)
        return objet.id


def _question(moteur, auteur_id: int) -> int:
    texte = _ajouter(
        moteur,
        TexteReglement(titre="RCP", nom_fichier="rcp.md", contenu="Article 1", empreinte="e"),
    )
    return _ajouter(
        moteur,
        QuestionReglement(
            question="Puis-je poser un store ?",
            verdict="oui",
            reponse="<p>Oui.</p>",
            texte_id=texte,
            auteur_id=auteur_id,
        ),
    )


def test_le_registre_porte_les_trois_cibles_tranchees():
    """« 1a ; 2a ; 3 oui » : l'affaire, sa suite et la réponse de l'assistant."""
    assert {"affaire", "suite", "question_reglement"} <= set(CIBLES)


def test_un_type_inconnu_est_refuse(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    assert _signaler(http, "publication", 1).status_code == 422


def test_une_affaire_lisible_se_signale_et_porte_son_lien(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    affaire = affaire_ouverte(moteur, "Insultes dans le hall")
    r = _signaler(http, "affaire", affaire)
    assert r.status_code == 201, r.text
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    (sig,) = cs.get("/signalements").json()
    assert sig["cible_type_label"] == "Affaire"
    assert sig["apercu"] == "Insultes dans le hall"
    assert sig["lien"] == f"/tickets/{affaire}"


def test_une_affaire_confidentielle_d_un_autre_ne_se_signale_pas(moteur):
    """Le cas du lot : l'identifiant ne suffit plus — 404, comme une affaire absente."""
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    affaire = affaire_ouverte(moteur, "Litige privé", confidentiel=True)
    assert _signaler(http, "affaire", affaire).status_code == 404
    assert _signaler(http, "affaire", 999_999).status_code == 404
    with Session(moteur) as s:
        assert s.exec(select(Signalement)).all() == []


def test_une_suite_se_signale_par_qui_lit_l_affaire(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    ouverte = affaire_ouverte(moteur)
    secrete = affaire_ouverte(moteur, confidentiel=True)
    with Session(moteur) as s:
        auteur = compte(s, prefixe="voisin").id
    lisible = _ajouter(
        moteur,
        TicketEvolution(ticket_id=ouverte, type="commentaire", contenu="Tais-toi", auteur_id=auteur),
    )
    cachee = _ajouter(
        moteur,
        TicketEvolution(ticket_id=secrete, type="commentaire", contenu="Secret", auteur_id=auteur),
    )
    sans_texte = _ajouter(
        moteur, TicketEvolution(ticket_id=ouverte, type="etat", nouveau_statut="en_cours")
    )
    assert _signaler(http, "suite", lisible).status_code == 201
    assert _signaler(http, "suite", cachee).status_code == 404
    assert _signaler(http, "suite", sans_texte).status_code == 404
    with Session(moteur) as s:
        (sig,) = s.exec(select(Signalement)).all()
        assert (sig.apercu, sig.auteur_cible_id) == ("Tais-toi", auteur)


def test_la_reponse_de_l_assistant_se_signale_par_son_auteur_seul(moteur):
    """Une question au règlement ne se lit que de son auteur et du conseil : un autre
    résident ne la signale pas. Son « auteur » signalé n'est personne."""
    cs, cs_id = client_http(moteur, RoleUtilisateur.conseil_syndical)
    question = _question(moteur, cs_id)
    assert _signaler(cs, "question_reglement", question).status_code == 201
    autre, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    assert _signaler(autre, "question_reglement", question).status_code == 404
    with Session(moteur) as s:
        (sig,) = s.exec(select(Signalement)).all()
        assert sig.auteur_cible_id is None
        assert sig.apercu == "Puis-je poser un store ?"


def test_une_cible_de_la_communaute_garde_sa_porte(moteur):
    """Un compte banni de la Communauté y est refusé avec son motif (403), comme avant ;
    une affaire, elle, ne dépend pas de la Communauté."""
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire, communaute_interdit=True)
    idee = _ajouter(moteur, Idee(titre="Un potager", description="…"))
    assert _signaler(http, "idee", idee).status_code == 403
    assert _signaler(http, "affaire", affaire_ouverte(moteur)).status_code == 201
