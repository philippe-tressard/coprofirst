"""La recherche d'un locataire n'est pas l'annuaire de la résidence (#2153).

## 🔴 Pourquoi

`GET /bailleur/search-locataire` (`require_proprietaire`) cherchait par
sous-chaîne parmi TOUS les comptes — conseil, administration, syndic, autres
copropriétaires — et rendait leur adresse entière. Un copropriétaire balayait
`q=aa`, `q=ab`… et repartait avec le nom et l'adresse de chacun.
`GET /bailleur/locataires-suggeres` rendait l'adresse de tout locataire dont le
propriétaire déclaré partageait un mot quelconque avec le prénom ou le nom du
bailleur.

## Ce que ces tests tiennent

1. Seuls les comptes LOCATAIRES se cherchent, par nom comme par adresse exacte.
2. Aucune réponse ne porte une adresse entière (`standards/03` §2 : le masquage
   se fait dans le schéma de sortie, et le test lit la réponse).
3. Les suggestions se font sur le NOM du bailleur, mot pour mot.
4. La recherche est bornée en débit.
"""

from __future__ import annotations

import pytest

from app.models.core import RoleUtilisateur, StatutUtilisateur
from app.routers.bailleur.baux import locataires_suggeres, search_locataire
from tests.aides_base import compte
from tests.aides_http import base_http, client_http
from tests.conftest import requete_de_test


def _chercher(session, bailleur, q: str):
    requete = requete_de_test("/bailleur/search-locataire", "GET")
    return search_locataire(requete, q=q, user=bailleur, session=session)


def _aucune_adresse_entiere(reponses, comptes) -> None:
    adresses = {c.email for c in comptes}
    for r in reponses:
        valeurs = set(map(str, r.model_dump().values()))
        assert not valeurs & adresses, f"adresse entière servie : {r}"
        assert "***@" in r.email_masque, r.email_masque


@pytest.fixture()
def residence(session):
    bailleur = compte(session, prefixe="bailleur", prenom="Jean", nom="MARTIN")
    conseil = compte(
        session,
        prefixe="conseil",
        prenom="Claire",
        nom="MOREL",
        roles_json="conseil_syndical",
        statut=StatutUtilisateur.copropriétaire_résident,
    )
    locataire = compte(
        session,
        prefixe="locataire",
        prenom="Alice",
        nom="DURAND",
        statut=StatutUtilisateur.locataire,
        nom_proprietaire="M. MARTIN",
    )
    homonyme = compte(
        session,
        prefixe="homonyme",
        prenom="Odile",
        nom="PERRIN",
        statut=StatutUtilisateur.locataire,
        nom_proprietaire="Jean DUPONT",
    )
    return bailleur, conseil, locataire, homonyme


def test_un_membre_du_conseil_ne_se_trouve_ni_par_nom_ni_par_adresse(session, residence):
    bailleur, conseil, *_ = residence
    assert _chercher(session, bailleur, "Morel") == []
    assert _chercher(session, bailleur, conseil.email) == []


def test_un_locataire_se_trouve_et_son_adresse_arrive_masquee(session, residence):
    bailleur, _conseil, locataire, homonyme = residence
    par_nom = _chercher(session, bailleur, "Durand")
    assert [r.id for r in par_nom] == [locataire.id]
    par_adresse = _chercher(session, bailleur, locataire.email)
    assert [r.id for r in par_adresse] == [locataire.id]
    _aucune_adresse_entiere(par_nom + par_adresse, residence)


def test_un_balayage_ne_rend_que_des_locataires(session, residence):
    bailleur, _conseil, locataire, homonyme = residence
    vus = {r.id for lettre in "aeiou" for r in _chercher(session, bailleur, lettre)}
    assert vus == {locataire.id, homonyme.id}


def test_les_suggestions_se_font_sur_le_nom_du_bailleur(session, residence):
    bailleur, _conseil, locataire, _homonyme = residence
    suggeres = locataires_suggeres(user=bailleur, session=session)
    #  « Jean DUPONT » partage le PRÉNOM du bailleur : ce n'est pas son locataire.
    assert [r.id for r in suggeres] == [locataire.id]
    _aucune_adresse_entiere(suggeres, residence)


def test_la_recherche_est_bornee_en_debit():
    """Par la porte réelle : le plafond ne s'applique qu'à travers l'application."""
    with base_http() as moteur:
        http, _ = client_http(
            moteur, RoleUtilisateur.propriétaire, statut=StatutUtilisateur.copropriétaire_bailleur
        )
        codes = [
            http.get("/bailleur/search-locataire", params={"q": "x"}).status_code for _ in range(21)
        ]
    assert codes[:20] == [200] * 20 and codes[20] == 429, codes
