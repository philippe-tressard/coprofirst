"""La purge d'une ligne et de tout ce qui la référence — clés étrangères ACTIVES.

## Pourquoi ce test existe (#546, 28/08/2026)

`supprimer_utilisateur` nettoyait **onze** familles de dépendances, énumérées à la
main. Le modèle en compte **cinquante-six**, dont trente-sept obligatoires : les
publications, tickets, messages, idées, sondages et signalements d'un compte
supprimé restaient en base, à pointer vers un identifiant disparu.

## Ce que ce test fait

Il monte un moteur **dédié**, avec les clés étrangères **vérifiées**, sur la vraie
déclaration des modèles. Il n'exerce donc pas l'application — mais il n'exerce pas
non plus une maquette : c'est le schéma réel qui refuse ou accepte.

Ce qu'il verrouille : **une purge qui laisserait un orphelin échouerait ici**, au
`commit`, sans qu'on ait à énumérer les tables.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.communaute import PetiteAnnonce
from app.models.core import Utilisateur
from app.utils.purge_referentielle import purger, references_entrantes
from tests.aides_base import moteur_de_test


@pytest.fixture()
def base_stricte():
    """Un moteur à part, clés étrangères VÉRIFIÉES, sur le schéma réel."""
    with Session(moteur_de_test(cles_etrangeres=True)) as session:
        yield session


def test_les_cles_sont_bien_verifiees_sur_cette_base(base_stricte):
    """Cas zéro du test lui-même : sans cela, tout ce qui suit passerait à vide."""
    base_stricte.add(PetiteAnnonce(titre="Orpheline", description="…", auteur_id=99999))
    with pytest.raises(IntegrityError):
        base_stricte.commit()


def test_les_references_sont_lues_dans_les_metadonnees_pas_recitees():
    """C'est la propriété qui distingue ce module d'une liste tenue à la main.

    Le compte exact n'est pas figé — il augmentera. Ce qui est vérifié, c'est
    qu'il est du bon ORDRE DE GRANDEUR : une liste de onze, c'était le défaut.
    """
    refs = references_entrantes("utilisateur")
    assert len(refs) > 40, (
        f"seulement {len(refs)} références lues — la lecture des métadonnées est cassée"
    )
    obligatoires = [r for r in refs if r[2]]
    #  31 avant #1688/#1821, qui ont rendu facultatifs les auteurs des contenus
    #  gardés : leur liste se lit dans `suppression_compte`, et
    #  `test_references_au_compte_declarees` la tient. Ici, l'ordre de grandeur.
    assert len(obligatoires) >= 10
    #  Une table à auteur OBLIGATOIRE doit en faire partie. C'était `publication`,
    #  qui a révélé le défaut ; elle est supprimée depuis le 30/09/2026 (#1177).
    assert any(t.name == "idee" and c.name == "auteur_id" for t, c, _ in refs)


def test_supprimer_un_compte_emporte_son_contenu_et_ne_laisse_aucun_orphelin(base_stricte):
    """Le cas qui échouait : un compte avec un contenu à auteur OBLIGATOIRE.

    Sans purge, `DELETE FROM utilisateur` faisait tenter à l'ORM un
    `UPDATE publication SET auteur_id = NULL` — refusé, la colonne est NOT NULL.
    La table `publication` n'existe plus (#1177) et l'idée est gardée depuis
    #1821 ; la petite annonce, PERSONNELLE, porte la même contrainte et tient le cas.
    """
    auteur = Utilisateur(email="auteur@test", hashed_password="x", prenom="A", nom="B")
    base_stricte.add(auteur)
    base_stricte.commit()
    base_stricte.refresh(auteur)
    base_stricte.add(PetiteAnnonce(titre="Vélo", description="…", auteur_id=auteur.id))
    base_stricte.commit()

    comptes = purger(base_stricte, "utilisateur", auteur.id)
    base_stricte.commit()

    assert base_stricte.exec(select(PetiteAnnonce)).all() == []
    assert base_stricte.exec(select(Utilisateur)).all() == []
    assert comptes.get("petite_annonce") == 1


def test_une_reference_NULLABLE_est_deliee_et_sa_ligne_reste(base_stricte):
    """La règle a deux moitiés, et celle-ci est la moins évidente.

    Une publication n'existe pas sans son auteur — elle part. Un objet dont
    l'utilisateur n'est qu'un détail (« traité par », « déclenché par ») garde son
    existence : c'est la référence qui s'efface, pas la ligne.
    """
    from app.models.core import DemandeModificationProfil

    demandeur = Utilisateur(email="d@test", hashed_password="x", prenom="D", nom="E")
    traiteur = Utilisateur(email="t@test", hashed_password="x", prenom="T", nom="F")
    base_stricte.add(demandeur)
    base_stricte.add(traiteur)
    base_stricte.commit()
    base_stricte.refresh(demandeur)
    base_stricte.refresh(traiteur)
    base_stricte.add(
        DemandeModificationProfil(
            utilisateur_id=demandeur.id, traite_par_id=traiteur.id, champs_json="{}"
        )
    )
    base_stricte.commit()

    purger(base_stricte, "utilisateur", traiteur.id)
    base_stricte.commit()

    restantes = base_stricte.exec(select(DemandeModificationProfil)).all()
    assert len(restantes) == 1, "la demande devait SURVIVRE à la suppression de son traiteur"
    assert restantes[0].traite_par_id is None


def test_la_purge_descend_sur_plusieurs_etages(base_stricte):
    """Un bail porte ses objets remis : les deux partent avec le bailleur.

    Les affaires (#1688) puis les sondages (#1821) ne servent plus d'exemple :
    leur auteur est facultatif, ils restent. Le bail est PERSONNEL — et l'objet
    remis n'a pas d'existence hors du bail qui le porte.
    """
    from datetime import date

    from app.models.bailleur import LocationBail, RemiseObjet
    from app.models.copropriete import Lot

    bailleur = Utilisateur(email="a@test", hashed_password="x", prenom="A", nom="B")
    autre = Utilisateur(email="b@test", hashed_password="x", prenom="C", nom="D")
    lot = Lot(numero="12")
    for ligne in (bailleur, autre, lot):
        base_stricte.add(ligne)
    base_stricte.commit()
    bail = LocationBail(lot_id=lot.id, bailleur_id=bailleur.id, date_entree=date(2026, 1, 1))
    base_stricte.add(bail)
    base_stricte.commit()
    base_stricte.add(RemiseObjet(bail_id=bail.id, libelle="Clé porte palière"))
    base_stricte.commit()

    purger(base_stricte, "utilisateur", bailleur.id)
    base_stricte.commit()

    assert base_stricte.exec(select(LocationBail)).all() == []
    assert base_stricte.exec(select(RemiseObjet)).all() == [], (
        "l'objet remis part avec le bail : il n'existe pas sans lui"
    )
    assert base_stricte.exec(select(Utilisateur)).all() != [], "l'autre compte devait rester"


def test_purger_une_ligne_inexistante_ne_fait_rien_et_ne_leve_pas(base_stricte):
    """Cas zéro : la purge est appelée après un `get` qui a pu rendre `None`."""
    comptes = purger(base_stricte, "utilisateur", 99999)
    base_stricte.commit()
    assert comptes.get("utilisateur") == 1  # le DELETE porte sur zéro ligne, sans erreur
