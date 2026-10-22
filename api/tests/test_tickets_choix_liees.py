"""Le routeur `tickets/liees` — le CHOIX des affaires à lier (#1569, #1342).

`GET /tickets/choix` alimente la section « Affaires liées » : numéro, titre et statut
des affaires que le lecteur PEUT LIRE, les plus récentes d'abord. La règle de fond
(un lien ne révèle rien) est tenue sans HTTP par `test_affaires_liees.py` ; ce
fichier tient la porte et le montage :

1. un anonyme est refusé (401) ;
2. la route est atteinte — son chemin est LITTÉRAL et `/{ticket_id}` la capterait
   si elle était montée après `crud` : elle répondrait 422 sans un mot ;
3. la réponse suit le lecteur : l'auteur lit ses affaires, jamais la confidentielle
   d'un autre ; le conseil les lit toutes ;
4. la forme se limite à ce qu'il faut pour reconnaître une affaire.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.models.core import RoleUtilisateur, StatutUtilisateur, Ticket
from tests.aides_base import compte
from tests.aides_http import base_http, client_http

_numero = [0]


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


def _affaire(moteur, auteur_id: int, titre: str, **champs) -> Ticket:
    _numero[0] += 1
    champs.setdefault("categorie", "nuisance")
    champs.setdefault("statut", "ouvert")
    with Session(moteur) as s:
        t = Ticket(
            numero=f"C-{_numero[0]:04d}",
            titre=titre,
            description="…",
            auteur_id=auteur_id,
            perimetre_cible='["résidence"]',
            **champs,
        )
        s.add(t)
        s.commit()
        s.refresh(t)
        return t


def _autre_auteur(moteur) -> int:
    with Session(moteur) as s:
        return compte(s, prefixe="voisin").id


def _resident(moteur):
    return client_http(moteur, RoleUtilisateur.résident, statut=StatutUtilisateur.locataire)


def test_un_anonyme_est_refuse(moteur):
    http, _ = client_http(moteur, None)
    assert http.get("/tickets/choix").status_code == 401


def test_la_route_litterale_n_est_pas_captee_par_la_route_a_parametre(moteur):
    """`/{ticket_id}` rendrait 422 si `/choix` était montée après elle."""
    http, _ = _resident(moteur)
    reponse = http.get("/tickets/choix")
    assert reponse.status_code == 200, reponse.text
    assert isinstance(reponse.json(), list)


def test_sans_affaire_le_choix_est_vide(moteur):
    http, _ = _resident(moteur)
    assert http.get("/tickets/choix").json() == []


def test_le_choix_ne_montre_que_numero_titre_statut_et_date(moteur):
    """La date de création s'y ajoute (#2173) : la section « Affaires liées »
    la montre avec le suivi — rien d'autre ne sort."""
    http, moi = _resident(moteur)
    t = _affaire(moteur, moi, "Porte du garage")

    assert http.get("/tickets/choix").json() == [
        {
            "id": t.id,
            "numero": t.numero,
            "titre": "Porte du garage",
            "statut": "ouvert",
            #  UTC naïf en base, rendu avec son `Z` comme toute date servie.
            "cree_le": f"{t.cree_le.isoformat()}Z",
        }
    ]


def test_les_plus_recentes_viennent_d_abord(moteur):
    http, moi = _resident(moteur)
    premiere = _affaire(moteur, moi, "Première")
    seconde = _affaire(moteur, moi, "Seconde")

    assert [e["id"] for e in http.get("/tickets/choix").json()] == [seconde.id, premiere.id]


def test_le_statut_est_rendu_comme_valeur_pas_comme_enumeration(moteur):
    http, moi = _resident(moteur)
    _affaire(moteur, moi, "En cours", statut="en_cours")

    assert http.get("/tickets/choix").json()[0]["statut"] == "en_cours"


def test_une_affaire_confidentielle_d_un_autre_n_est_pas_proposee(moteur):
    """Un lien ne révèle rien : ni son titre, ni son numéro."""
    http, moi = _resident(moteur)
    voisin = _autre_auteur(moteur)
    _affaire(moteur, voisin, "Impayé du 3B", confidentiel=True)
    sienne = _affaire(moteur, moi, "La mienne")

    choix = http.get("/tickets/choix").json()

    assert [e["id"] for e in choix] == [sienne.id]
    assert "Impayé" not in str(choix)


def test_sa_propre_affaire_confidentielle_reste_proposee(moteur):
    """L'auteur voit toujours ce qu'il a écrit."""
    http, moi = _resident(moteur)
    sienne = _affaire(moteur, moi, "Ma demande", confidentiel=True)

    assert [e["id"] for e in http.get("/tickets/choix").json()] == [sienne.id]


@pytest.mark.parametrize("role", [RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin])
def test_le_conseil_et_l_administration_peuvent_lier_toutes_les_affaires(moteur, role):
    voisin = _autre_auteur(moteur)
    ouverte = _affaire(moteur, voisin, "Ouverte")
    fermee = _affaire(moteur, voisin, "Confidentielle", confidentiel=True)
    http, _ = client_http(moteur, role)

    ids = [e["id"] for e in http.get("/tickets/choix").json()]

    assert ids == [fermee.id, ouverte.id]
