"""La provenance du texte du règlement, et ce que l'avis en dit (11/10/2026).

Ce qui est tenu ici :

- seule l'administration saisit la provenance, et seule elle la lit dans l'état
  de l'onglet ; une provenance vide ou trop longue est refusée ;
- chaque question garde la provenance du moment où elle a été posée ; une
  question plus ancienne que la saisie lit la provenance actuelle ;
- le coût d'un appel n'est rendu à personne : il ne figure plus dans l'avis.
"""

from __future__ import annotations

from sqlmodel import Session

from app.models.core import RoleUtilisateur
from app.models.reglement import QuestionReglement
from app.utils.question_reglement.provenance import MAX_CARACTERES
from tests.aides_http import client_http
from tests.aides_reglement import client_admin, client_cs, joindre
from tests.aides_reglement import assistant, moteur_fixture  # noqa: F401

PROVENANCE = "la numérisation du règlement fictif et de son modificatif de 1995"


def test_seule_l_administration_saisit_et_lit_la_provenance(moteur, assistant):
    admin, cs = client_admin(moteur), client_cs(moteur)
    assert admin.get("/reglement").json()["provenance"] is None
    corps = {"provenance": f"  {PROVENANCE}  "}
    assert cs.put("/reglement/provenance", json=corps).status_code == 403
    assistant.ouvert = True
    proprio, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    assert proprio.put("/reglement/provenance", json=corps).status_code == 403

    etat = admin.put("/reglement/provenance", json=corps)
    assert etat.status_code == 200 and etat.json()["provenance"] == PROVENANCE
    assert admin.get("/reglement").json()["provenance"] == PROVENANCE
    #  Les autres lisent la provenance sous chaque avis, pas dans l'état de l'onglet.
    assert cs.get("/reglement").json()["provenance"] is None


def test_une_provenance_vide_ou_trop_longue_est_refusee(moteur):
    admin = client_admin(moteur)
    for valeur in ("", "x" * (MAX_CARACTERES + 1)):
        assert admin.put("/reglement/provenance", json={"provenance": valeur}).status_code == 422


def test_chaque_question_garde_la_provenance_du_moment(moteur, assistant):
    admin = client_admin(moteur)
    joindre(admin, moteur)
    #  Posée avant toute saisie : elle lira la provenance actuelle.
    ancienne = admin.post("/reglement/questions", json={"question": "Avant ?"}).json()
    assert ancienne["provenance"] is None
    admin.put("/reglement/provenance", json={"provenance": PROVENANCE})
    posee = admin.post("/reglement/questions", json={"question": "Puis-je ?"}).json()
    assert posee["provenance"] == PROVENANCE
    with Session(moteur) as s:
        assert s.get(QuestionReglement, posee["id"]).provenance == PROVENANCE
        assert s.get(QuestionReglement, ancienne["id"]).provenance is None

    admin.put("/reglement/provenance", json={"provenance": "un autre texte"})
    lues = {q["id"]: q["provenance"] for q in admin.get("/reglement/questions").json()}
    assert lues == {posee["id"]: PROVENANCE, ancienne["id"]: "un autre texte"}


def test_le_cout_d_un_appel_n_est_rendu_a_personne(moteur, assistant):
    admin = client_admin(moteur)
    joindre(admin, moteur)
    q = admin.post("/reglement/questions", json={"question": "Puis-je ?"}).json()
    assert "cout_usd" not in q
    assert all("cout_usd" not in x for x in client_cs(moteur).get("/reglement/questions").json())
