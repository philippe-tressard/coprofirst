"""Une question au règlement au fil d'activité, et sa suppression par l'auteur (11/10/2026).

Ce qui est tenu ici :

- le fil montre une question à qui la lit dans l'onglet — son auteur, le conseil,
  l'administration —, jamais à un autre copropriétaire, et plus à son auteur quand
  l'usage est refermé aux copropriétaires ;
- supprimée, elle quitte le fil ;
- son auteur la supprime, comme l'administration ; le conseil et les autres
  copropriétaires non, et l'écran le sait (`peut_supprimer`).
"""

from __future__ import annotations

from app.models.core import RoleUtilisateur
from tests.aides_http import client_http
from tests.aides_reglement import client_admin, client_cs, joindre
from tests.aides_reglement import assistant, moteur_fixture  # noqa: F401


def _au_fil(http) -> list[dict]:
    return [i for i in http.get("/flux").json()["items"] if i["type"] == "question_reglement"]


def _poser_par_un_coproprietaire(moteur, assistant):
    assistant.ouvert = True
    joindre(client_admin(moteur), moteur)
    auteur, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    voisin, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    q = auteur.post("/reglement/questions", json={"question": "Puis-je exercer ?"}).json()
    return auteur, voisin, q


def test_le_fil_suit_la_visibilite_de_l_onglet(moteur, assistant):
    auteur, voisin, q = _poser_par_un_coproprietaire(moteur, assistant)
    (carte,) = _au_fil(auteur)
    assert carte["titre"] == "Puis-je exercer ?"
    assert carte["lien"] == f"/residence/reglement#question-reglement-{q['id']}"
    assert carte["badges"] == ["Oui, sous conditions"]
    assert carte["meta"]["verdict"] == "sous_conditions"
    assert carte["detail"].startswith("Question au règlement — Oui")
    assert _au_fil(voisin) == []
    assert len(_au_fil(client_cs(moteur))) == 1
    assert len(_au_fil(client_admin(moteur))) == 1
    #  Usage refermé : l'auteur ne lit plus l'onglet, ni la carte au fil.
    assistant.ouvert = False
    assert _au_fil(auteur) == []
    assert len(_au_fil(client_cs(moteur))) == 1


def test_l_auteur_supprime_sa_question_et_elle_quitte_le_fil(moteur, assistant):
    auteur, voisin, q = _poser_par_un_coproprietaire(moteur, assistant)
    cs = client_cs(moteur)
    assert auteur.get("/reglement/questions").json()[0]["peut_supprimer"] is True
    assert cs.get("/reglement/questions").json()[0]["peut_supprimer"] is False
    assert voisin.delete(f"/reglement/questions/{q['id']}").status_code == 403
    assert cs.delete(f"/reglement/questions/{q['id']}").status_code == 403

    assert auteur.delete(f"/reglement/questions/{q['id']}").status_code == 204
    assert _au_fil(auteur) == [] and _au_fil(cs) == []
    assert cs.get("/reglement/questions").json() == []


def test_l_administration_supprime_la_question_d_un_autre(moteur, assistant):
    _, _, q = _poser_par_un_coproprietaire(moteur, assistant)
    admin = client_admin(moteur)
    assert admin.get("/reglement/questions").json()[0]["peut_supprimer"] is True
    assert admin.delete(f"/reglement/questions/{q['id']}").status_code == 204
    assert _au_fil(admin) == []
