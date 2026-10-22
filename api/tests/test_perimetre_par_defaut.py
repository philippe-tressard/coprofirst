"""Le périmètre par défaut : ce qu'on écrit et la question qu'on pose (#1567).

`perimetre_cible_json` (ce qu'un contenu reçoit quand on ne lui donne rien) et
`est_perimetre_par_defaut` (« toute la copropriété ? ») lisent la racine dans
l'ARBRE, comme `perimetreDefautListe` et `estPerimetreParDefaut` côté front.
Le garde-fou statique (`test_perimetre_racine_source_unique.py`) refuse le code
écrit en dur ; ces tests-ci vérifient le COMPORTEMENT — en particulier sur une
copropriété dont la racine n'est pas « résidence », seul cas où l'ancien code
en dur se trompait.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.database import engine
from app.models.perimetre import Perimetre
from app.models.tickets import Ticket
from app.utils import perimetres as P
from app.utils.whatsapp_message import _libelle_perimetre


def test_arbre_seme_la_racine_est_le_defaut(batiments):
    assert P.perimetre_defaut_liste() == ["résidence"]
    assert P.perimetre_cible_json() == '["résidence"]'
    assert P.perimetre_cible_json([]) == '["résidence"]'
    assert P.perimetre_cible_json(["bat:1"]) == '["bat:1"]'
    assert P.perimetre_defaut_texte() == "résidence"


def test_la_question_suit_l_arbre(batiments):
    assert P.est_perimetre_par_defaut([]) is True
    assert P.est_perimetre_par_defaut(None) is True
    assert P.est_perimetre_par_defaut(["résidence"]) is True
    assert P.est_perimetre_par_defaut([" Résidence "]) is True
    assert P.est_perimetre_par_defaut(["bat:1"]) is False
    assert P.est_perimetre_par_defaut(["résidence", "bat:1"]) is False


def test_le_message_du_groupe_tait_le_defaut(batiments):
    assert _libelle_perimetre('["résidence"]') == "Copropriété"
    assert _libelle_perimetre("[]") == "Copropriété"
    assert _libelle_perimetre(None) == "Copropriété"
    #  Le libellé de l'arbre, jamais le code brut : le groupe lisait « bat:4/ascenseur »
    #  (22/10/2026) — le rendu commun du site, `perimetre_label`.
    assert _libelle_perimetre('["bat:1"]') == "Bâtiment 1"
    assert _libelle_perimetre('["bat:4/ascenseur"]') == "Bât. 4 › Ascenseur"
    assert _libelle_perimetre('["bat:1", "bat:2"]') == "Bâtiment 1 · Bâtiment 2"


def test_une_autre_racine_devient_le_defaut(batiments):
    """Le cas que le code en dur ratait : la racine n'est plus « résidence »."""
    with Session(engine) as session:
        ancienne = session.exec(select(Perimetre).where(Perimetre.code == "résidence")).one()
        ancienne.actif = False
        session.add(ancienne)
        session.add(
            Perimetre(code="copro", libelle="Toute la copropriété", portee_globale=True, ordre=-1)
        )
        session.commit()
    P.invalider_cache()

    assert P.perimetre_cible_json() == '["copro"]'
    assert P.est_perimetre_par_defaut(["copro"]) is True
    assert P.est_perimetre_par_defaut(["résidence"]) is False
    #  Le défaut de colonne suit aussi : il se lit à la création de l'objet.
    assert Ticket(titre="t", description="d", auteur_id=1).perimetre_cible == '["copro"]'
    assert _libelle_perimetre('["copro"]') == "Copropriété"


def test_arbre_vide_aucun_code_invente(arbre_vide):
    """Sans arbre, aucun code n'est fabriqué : liste vide, « concerne tout le monde »."""
    assert P.perimetre_defaut_liste() == []
    assert P.perimetre_cible_json() == "[]"
    assert P.perimetre_defaut_texte() == ""
    assert P.est_perimetre_par_defaut([]) is True
    assert P.est_perimetre_par_defaut(["résidence"]) is False
