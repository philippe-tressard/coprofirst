"""Qui voit un contenu, selon le PUBLIC visé — publications ET sondages.

L'autre moitié du ciblage d'une actualité : le périmètre dit *où*, le public dit
*à qui*. `test_perimetres_arbre.py` couvre le premier ; celui-ci couvre le second,
qui n'avait aucun test alors qu'il décide d'un accès.

Écrit en ajoutant le destinataire « bailleurs » (13/08/2026). « Copropriétaires »
couvre les DEUX statuts `copropriétaire_*` : rien ne permettait de s'adresser aux
bailleurs sans toucher les copropriétaires occupants, alors que tout un pan du
produit leur est propre (baux, remise d'objets, accès confiés aux locataires).

Étendu le 16/08/2026 sur deux points, à l'occasion de l'unification du ciblage
des sondages :

  • « copropriétaires occupants » complète la symétrie. Sans ce code, la
    conversion d'un sondage réservé aux occupants l'aurait rendu accessible aux
    bailleurs — une migration de données qui ÉLARGIT un accès ;
  • la règle est désormais UNE fonction (`public_cible_visible`) appelée par les
    publications ET les sondages. Ces derniers avaient la leur, écrite sur des
    statuts bruts, qui ne connaissait ni les bailleurs ni le conseil syndical.
    Les cas ci-dessous sont donc rejoués sur les deux porteurs — c'est le seul
    moyen de vérifier que la règle est bien UNE règle, et pas deux qui se
    ressemblent aujourd'hui.
"""

import pytest

from app.models.core import Sondage, StatutUtilisateur, Ticket, Utilisateur
from app.utils.visibility import actualite_visible, sondage_accessible


def _publication(public: str | None) -> Ticket:
    #  `perimetre_cible` absent : ce fichier ne teste QUE le public. Une actualité
    #  est une affaire de catégorie « Actualité » depuis le 23/09/2026 (#1091).
    return Ticket(
        numero="TK-A1",
        titre="T",
        description="C",
        categorie="actualite",
        statut="publie",
        perimetre_cible=None,
        public_cible=public,
    )


def _lecteur(statut: StatutUtilisateur, roles: str = "résident") -> Utilisateur:
    return Utilisateur(
        nom="X",
        prenom="Y",
        email=f"{statut.value}@test.test",
        statut=statut,
        roles_json=roles,
        actif=True,
    )


TOUS = [
    StatutUtilisateur.copropriétaire_résident,
    StatutUtilisateur.copropriétaire_bailleur,
    StatutUtilisateur.locataire,
]


def _sondage(public: str | None) -> Sondage:
    #  `perimetre_cible` absent : ce fichier ne teste QUE le public.
    return Sondage(question="Q", auteur_id=1, perimetre_cible=None, public_cible=public)


#: Les deux porteurs du même ciblage.
PORTEURS = [
    pytest.param((_publication, actualite_visible), id="actualite"),
    pytest.param((_sondage, sondage_accessible), id="sondage"),
]


def _voit(porteur, public: str | None, user: Utilisateur) -> bool:
    construire, regle = porteur
    return regle(construire(public), user)


@pytest.mark.parametrize("porteur", PORTEURS)
@pytest.mark.parametrize("statut", TOUS)
def test_residents_vise_tout_le_monde(porteur, statut):
    assert _voit(porteur, '["résidents"]', _lecteur(statut)) is True


@pytest.mark.parametrize("porteur", PORTEURS)
@pytest.mark.parametrize("statut", TOUS)
def test_public_absent_ne_restreint_rien(porteur, statut):
    assert _voit(porteur, None, _lecteur(statut)) is True


@pytest.mark.parametrize("porteur", PORTEURS)
def test_coproprietaires_englobe_resident_ET_bailleur(porteur):
    """Comportement existant, épinglé : « Copropriétaires » ne distingue pas.

    C'est précisément ce qui rendait « Bailleurs » nécessaire — et ce qui ne doit
    pas changer, sous peine de retirer un public à des publications déjà parues.
    """
    cible = '["copropriétaires"]'
    assert _voit(porteur, cible, _lecteur(StatutUtilisateur.copropriétaire_résident)) is True
    assert _voit(porteur, cible, _lecteur(StatutUtilisateur.copropriétaire_bailleur)) is True
    assert _voit(porteur, cible, _lecteur(StatutUtilisateur.locataire)) is False


@pytest.mark.parametrize("porteur", PORTEURS)
def test_bailleurs_ne_vise_QUE_les_bailleurs(porteur):
    """Les copropriétaires occupants ne le reçoivent pas."""
    cible = '["bailleurs"]'
    assert _voit(porteur, cible, _lecteur(StatutUtilisateur.copropriétaire_bailleur)) is True
    assert _voit(porteur, cible, _lecteur(StatutUtilisateur.copropriétaire_résident)) is False
    assert _voit(porteur, cible, _lecteur(StatutUtilisateur.locataire)) is False


@pytest.mark.parametrize("porteur", PORTEURS)
def test_occupants_ne_visent_QUE_les_occupants(porteur):
    """Le symétrique exact de « bailleurs », ajouté le 16/08/2026.

    Sans lui, la migration 0147 aurait dû convertir un sondage réservé aux
    copropriétaires occupants en `["copropriétaires"]` — c'est-à-dire
    l'ouvrir aux bailleurs. Un `upgrade` ne doit jamais élargir un accès.
    """
    cible = '["copropriétaires_occupants"]'
    assert _voit(porteur, cible, _lecteur(StatutUtilisateur.copropriétaire_résident)) is True
    assert _voit(porteur, cible, _lecteur(StatutUtilisateur.copropriétaire_bailleur)) is False
    assert _voit(porteur, cible, _lecteur(StatutUtilisateur.locataire)) is False


@pytest.mark.parametrize("porteur", PORTEURS)
def test_locataires_ne_vise_que_les_locataires(porteur):
    cible = '["locataires"]'
    assert _voit(porteur, cible, _lecteur(StatutUtilisateur.locataire)) is True
    assert _voit(porteur, cible, _lecteur(StatutUtilisateur.copropriétaire_résident)) is False


@pytest.mark.parametrize("porteur", PORTEURS)
def test_conseil_syndical_n_est_visible_que_du_conseil(porteur):
    cible = '["conseil_syndical"]'
    for statut in TOUS:
        assert _voit(porteur, cible, _lecteur(statut)) is False
    #  Le CS et l'admin sortent avant tout filtrage : ils voient tout.
    assert (
        _voit(
            porteur,
            cible,
            _lecteur(StatutUtilisateur.copropriétaire_résident, "conseil_syndical"),
        )
        is True
    )


@pytest.mark.parametrize("porteur", PORTEURS)
def test_public_inconnu_n_accorde_rien(porteur):
    """Une valeur non reconnue refuse — et c'est ce qui rend les ajouts sûrs.

    C'est aussi ce qui autorise la migration 0147 à recopier telle quelle une
    valeur qu'elle ne sait pas convertir : un résidu ne peut que RESTREINDRE.
    """
    for statut in TOUS:
        assert _voit(porteur, '["martiens"]', _lecteur(statut)) is False


@pytest.mark.parametrize("porteur", PORTEURS)
def test_plusieurs_publics_s_additionnent(porteur):
    cible = '["bailleurs", "locataires"]'
    assert _voit(porteur, cible, _lecteur(StatutUtilisateur.copropriétaire_bailleur)) is True
    assert _voit(porteur, cible, _lecteur(StatutUtilisateur.locataire)) is True
    assert _voit(porteur, cible, _lecteur(StatutUtilisateur.copropriétaire_résident)) is False
