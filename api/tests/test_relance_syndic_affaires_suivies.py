"""Espace CS → Reporting → Suivi des affaires, mode « Relancer le syndic » :
seules les affaires encore suivies.

Arbitré par l'utilisateur les 09 et 10/10/2026 : « relance toutes les affaires
sauf celles résolues, annulées, supprimées ou archivées, sans exceptions » — puis,
le 10 au soir, une seule exception : l'entretien périodique (sous contrat ou à
récurrence), qui a sa propre vue. La
liste gardait une affaire 📦 archivée et une affaire absorbée par une fusion,
mais écartait la catégorie « bug » et les affaires marquées « non relançable » ;
le compteur du tableau de bord ne comptait que les affaires adressées au syndic ;
les réponses du syndic citaient les affaires closes ; l'envoi acceptait une
affaire close depuis un écran resté ouvert.

Chaque test passe par la sortie que l'écran reçoit, jamais par la règle
(`utils/relance_syndic`) : la rappeler ici comparerait la fonction à elle-même.
"""

import json
from datetime import timedelta

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.models.core import Ticket
from app.models.courriel import RelanceCourriel, ReponseRelance
from app.routers.flux.commun import ContexteFlux
from app.routers.flux.sante import calculer
from app.routers.suivi_affaires import lire_suivi
from app.routers.tickets.relance import (
    RelanceSyndicRequest,
    envoyer_relance_syndic,
    list_reponses_relance,
)
from app.utils.horloge import maintenant
from tests.aides_base import compte

#: Les affaires que la relance doit proposer.
SUIVIES = {
    "ouvert": {"statut": "ouvert"},
    "en_cours": {"statut": "en_cours"},
    "en_ag": {"statut": "en_ag"},
    "chez_prestataire": {"statut": "chez_prestataire"},
    #  Sans exception : ni la catégorie, ni l'adresse.
    "bug": {"statut": "ouvert", "categorie": "bug"},
    "pas_au_syndic": {"statut": "ouvert", "destinataire_syndic": False},
    #  Un Entretien ouvert à la main — ni contrat, ni récurrence (10/10/2026).
    "entretien_ponctuel": {"statut": "en_cours", "categorie": "entretien"},
}

#: Celles qu'elle ne doit jamais proposer, avec ce qui les en écarte.
ECARTEES = {
    "résolue": {"statut": "résolu"},
    "annulée": {"statut": "annulé"},
    "actualité": {"statut": "publie"},
    "archivée": {"statut": "ouvert", "archive_manuel": True},
    "absorbée": {"statut": "ouvert", "fusionnee_dans_id": -1},
    #  L'entretien PÉRIODIQUE se suit dans sa propre vue (`test_entretien_periodique`).
    "entretien_sous_contrat": {
        "statut": "chez_prestataire",
        "categorie": "entretien",
        "contrat_id": 1,
    },
    "entretien_recurrent": {
        "statut": "chez_prestataire",
        "categorie": "entretien",
        "frequence_type": "mois",
        "frequence_valeur": 6,
    },
}


@pytest.fixture()
def affaires(session):
    """Une affaire par cas, sans avancée depuis 60 jours."""
    auteur = compte(session, roles_json="conseil_syndical")
    vieux = maintenant() - timedelta(days=60)
    par_nom = {}
    for nom, champs in {**SUIVIES, **ECARTEES}.items():
        valeurs = {"categorie": "panne", "destinataire_syndic": True, **champs}
        t = Ticket(
            numero=f"TK-{nom}",
            titre=nom,
            description="d",
            auteur_id=auteur.id,
            mis_a_jour_le=vieux,
            **valeurs,
        )
        session.add(t)
        session.commit()
        session.refresh(t)
        par_nom[nom] = t
    return auteur, par_nom


def _liste(session, auteur):
    """La liste que l'écran reçoit — le Suivi des affaires porte la relance (#2035)."""
    return lire_suivi(session=session, user=auteur).affaires


def test_la_liste_ne_propose_que_les_affaires_suivies(session, affaires):
    auteur, _ = affaires
    assert {a.titre for a in _liste(session, auteur)} == set(SUIVIES)


def test_les_affaires_sans_avancee_depuis_le_delai_sont_a_relancer(session, affaires):
    auteur, par_nom = affaires
    recente = par_nom["ouvert"]
    recente.mis_a_jour_le = maintenant() - timedelta(days=3)
    session.add(recente)
    session.commit()
    a_relancer = {a.titre: a.a_relancer for a in _liste(session, auteur)}
    assert a_relancer.pop("ouvert") is False
    assert all(a_relancer.values())


def test_le_compteur_du_tableau_de_bord_annonce_la_liste(session, affaires):
    auteur, _ = affaires
    maintenant_ = maintenant()
    ctx = ContexteFlux(session=session, user=auteur, now=maintenant_, since=maintenant_)
    assert calculer(ctx).tickets_relance_syndic == len(_liste(session, auteur))


@pytest.mark.parametrize("nom", sorted(ECARTEES))
def test_l_envoi_refuse_une_affaire_qui_n_est_plus_a_relancer(session, affaires, nom):
    auteur, par_nom = affaires
    corps = RelanceSyndicRequest(ticket_ids=[par_nom["ouvert"].id, par_nom[nom].id])
    with pytest.raises(HTTPException) as refus:
        envoyer_relance_syndic(
            body=corps, background_tasks=BackgroundTasks(), session=session, user=auteur
        )
    assert refus.value.status_code == 422
    assert f"TK-{nom}" in refus.value.detail
    assert "TK-ouvert" not in refus.value.detail


def _reponse(session, ids: list[int]) -> None:
    relance = RelanceCourriel(jeton=f"j-{ids}", tickets_json=json.dumps(ids))
    session.add(relance)
    session.commit()
    session.refresh(relance)
    session.add(ReponseRelance(relance_id=relance.id, expediteur="syndic", contenu="ok"))
    session.commit()


def test_les_reponses_ne_citent_que_les_affaires_suivies(session, affaires):
    auteur, par_nom = affaires
    #  9999 : une affaire supprimée depuis la relance.
    _reponse(session, [par_nom["ouvert"].id, par_nom["résolue"].id, 9999])
    reponses = list_reponses_relance(session=session, _user=auteur)["reponses"]
    assert [r["tickets"] for r in reponses] == [["TK-ouvert"]]


def test_une_reponse_dont_toutes_les_affaires_sont_closes_quitte_la_liste(session, affaires):
    auteur, par_nom = affaires
    _reponse(session, [par_nom["résolue"].id, par_nom["annulée"].id, 9999])
    assert list_reponses_relance(session=session, _user=auteur)["reponses"] == []
