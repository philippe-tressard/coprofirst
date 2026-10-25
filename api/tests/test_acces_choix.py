"""Ce qu'un badge a le DROIT d'ouvrir — la liste fermée, et ce qu'elle refuse.

## Pourquoi ce fichier (15/09/2026, #953)

> « Est-ce possible de restreindre pour badges & télécommandes que le périmètre
>   soit parmi : pour les vigik copropriété entière ou bâtiment x **et Extérieurs
>   / portillons** ; pour les télécommandes Parking résidence / portail d'accès +
>   AFUL / portail public »

La restriction ne vaut que si elle est opposée **à la requête**, pas seulement
proposée par l'écran. Ce fichier exerce donc les deux faces :

* ce que la liste CONTIENT — et qu'elle le tire de l'arbre, jamais d'un code
  écrit dans le produit ;
* ce qu'elle REFUSE — un code hors liste, sur les deux types.

⚠️ L'arbre d'essai n'emploie **aucun** code du seed réel : `parc:portail`,
`tiers:portail` et `dehors:portillon` sont inventés ici exprès. Un test qui
reprendrait `parking` ou `aful` passerait aussi bien avec un produit qui les
aurait écrits en dur — c'est ce qu'il doit interdire.
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, select

from app import contexte
from app.database import engine
from app.models.copropriete import Batiment, Copropriete, Lot
from app.models.core import ConfigSite, UserLot, Utilisateur
from app.models.perimetre import Perimetre
from app.utils.acces_choix import (
    acces_par_defaut,
    cle_config,
    codes_autorises,
    valider_acces,
)
from app.utils.acces_gestes import _acces_json
from app.utils.perimetres import invalider_cache
from app.utils.types_acces import TELECOMMANDE, VIGIK
from tests.aides_purge import vider_patrimoine

#: Les portails de l'arbre d'essai — deux nœuds de second niveau, sous deux
#: parents différents : c'est la forme exacte de la demande (« parking » ET
#: « AFUL »), et elle interdit de s'en tirer avec un seul parent.
PORTAILS = ["parc:portail", "tiers:portail"]

#: Ce qu'un vigik ouvre **en plus** de son bâtiment — ajouté le 15/09/2026 sur
#: correction. Un portillon ne dépend d'aucun lot : il s'ouvre pareil pour tout le
#: monde, et c'est ce que « accès fixe » veut dire.
PORTILLONS = ["dehors:portillon"]


@pytest.fixture()
def arbre_dessai():
    """Une copropriété complète en base : deux bâtiments, deux portails.

    ⚠️ Les lignes sont **retirées** à la fin, et le cache de l'arbre invalidé des
    deux côtés : `arbre()` est un état de module, et un test qui le laisserait
    chargé ferait passer — ou échouer — le suivant pour une raison qui ne le
    concerne pas.
    """
    SQLModel.metadata.create_all(engine)
    invalider_cache()
    with contexte.nouvelle_session() as s:
        copro = Copropriete(nom="Essai", adresse="1 rue de l'Essai")
        s.add(copro)
        s.commit()
        s.refresh(copro)

        batiments = []
        for numero in (1, 2):
            b = Batiment(copropriete_id=copro.id, numero=numero, nb_etages=4)
            s.add(b)
            s.commit()
            s.refresh(b)
            batiments.append(b)

        def noeud(code, libelle, **kw):
            n = Perimetre(code=code, libelle=libelle, **kw)
            s.add(n)
            s.commit()
            s.refresh(n)
            return n

        noeud("copro:tout", "Copropriété entière", portee_globale=True, ordre=0)
        groupe = noeud("copro:bats", "Bâtiments", selectionnable=False, ordre=1)
        for rang, b in enumerate(batiments):
            noeud(
                f"copro:b{b.numero}",
                f"Bâtiment {b.numero}",
                parent_id=groupe.id,
                batiment_id=b.id,
                ordre=10 + rang,
            )
        parc = noeud("parc", "Parking résidence", ordre=20)
        noeud("parc:portail", "Portail d'accès", parent_id=parc.id, ordre=21)
        tiers = noeud("tiers", "AFUL", hors_copropriete=True, ordre=30)
        noeud("tiers:portail", "Portail public", parent_id=tiers.id, ordre=31)
        dehors = noeud("dehors", "Extérieurs", ordre=40)
        noeud("dehors:portillon", "Portillons", parent_id=dehors.id, ordre=41)

        for type_acces, codes in ((TELECOMMANDE, PORTAILS), (VIGIK, PORTILLONS)):
            s.add(
                ConfigSite(
                    cle=cle_config(type_acces),
                    valeur=json.dumps(codes, ensure_ascii=False),
                )
            )
        s.commit()
        invalider_cache()
        yield s, batiments

        for ligne in s.exec(select(ConfigSite)).all():
            s.delete(ligne)
        #  Le patrimoine ENTIER — arbre, bâtiments, copropriété : la fixture ne
        #  retirait que l'arbre, et la copropriété et ses deux bâtiments restaient
        #  dans la base du processus pour le test suivant (#2223). L'arbre part
        #  par vagues, des enfants vers les parents (`vider_perimetres`).
        vider_patrimoine(s)
    invalider_cache()


def test_un_vigik_ouvre_la_copropriete_un_batiment_ou_un_portillon(arbre_dessai):
    """La copropriété entière, les bâtiments, les portillons — et RIEN d'autre.

    🔴 Les PORTAILS n'y sont pas, les portillons si : c'est tout l'objet de la
    restriction. Le sélecteur ouvrait l'arbre entier, si bien qu'un badge pouvait
    se voir attribuer « Bât. 2 › Local poubelles », qu'aucun vigik ne commande.

    Le groupe « Bâtiments » (`copro:bats`) n'y figure pas : il regroupe, il ne
    s'ouvre pas — il ne porte pas de `batiment_id`.

    🔢 **L'ordre de cette liste est un CONTRAT, pas une commodité** — et c'est
    pour lui que la comparaison est un `==` et non une égalité d'ensembles : ce
    qui englobe, puis les bâtiments dans l'ordre de l'arbre, puis les accès
    fixes. L'écran affiche la rangée dans cet ordre-là, sans le recalculer.
    Le 15/09/2026, le sélecteur le jetait et retriait par le rang `ordre` de
    chaque nœud ; or ce rang est **relatif à la fratrie** (« Bâtiment 1 » et
    « Portillons » valaient tous deux 1), et la rangée sortait entrelacée.
    Ne pas réordonner `codes_autorises` en croyant la séquence indifférente.
    """
    session, batiments = arbre_dessai
    assert (
        codes_autorises(session, VIGIK)
        == [
            "copro:tout",
            "copro:b1",
            "copro:b2",
        ]
        + PORTILLONS
    ), (
        "attendu, dans CET ordre : ce qui englobe, les bâtiments, puis les accès "
        "fixes — sans le groupe « Bâtiments », qui ne s'ouvre pas"
    )


def test_une_telecommande_nouvre_que_les_portails(arbre_dessai):
    """Ni bâtiment, ni copropriété entière, ni portillon : QUE ses accès fixes."""
    session, _ = arbre_dessai
    assert codes_autorises(session, TELECOMMANDE) == PORTAILS


def test_un_portillon_est_bien_permis_a_un_vigik(arbre_dessai):
    """Le pendant du refus : ce qui est autorisé passe, et c'est la correction du 15/09."""
    session, _ = arbre_dessai
    valider_acces(session, VIGIK, PORTILLONS)


def test_les_portails_sont_aussi_la_valeur_par_defaut(arbre_dessai):
    """Une télécommande ouvre LES portails : ses accès fixes sont son défaut."""
    session, _ = arbre_dessai
    assert acces_par_defaut(session, TELECOMMANDE) == PORTAILS


def test_un_portillon_nest_pas_un_defaut_de_vigik(arbre_dessai):
    """🔴 Autorisé n'est pas attribué.

    Poser les portillons d'office sur tout le parc élargirait un droit d'accès
    physique que personne n'a décidé — et un accès élargi par erreur ne se voit
    pas : la porte s'ouvre quand même.
    """
    session, batiments = arbre_dessai
    porteur = Utilisateur(
        email="defaut@essai.fr",
        hashed_password="x",
        prenom="C",
        nom="D",
    )
    session.add(porteur)
    session.commit()
    session.refresh(porteur)
    lot = Lot(batiment_id=batiments[0].id, numero="102")
    session.add(lot)
    session.commit()
    session.refresh(lot)

    assert json.loads(_acces_json(session, VIGIK, None, lot.id, porteur.id)) == ["copro:b1"]

    session.delete(lot)
    session.delete(porteur)
    session.commit()


@pytest.mark.parametrize(
    "type_acces,intrus",
    [
        (VIGIK, "parc:portail"),
        (VIGIK, "copro:bats"),
        (TELECOMMANDE, "dehors:portillon"),
        (TELECOMMANDE, "copro:b1"),
        (TELECOMMANDE, "copro:tout"),
    ],
)
def test_un_code_hors_liste_est_refuse(arbre_dessai, type_acces, intrus):
    """🔒 Le refus vient de la ROUTE, pas de l'écran — c'est le sujet du lot."""
    session, _ = arbre_dessai
    with pytest.raises(HTTPException) as erreur:
        valider_acces(session, type_acces, [intrus])
    assert erreur.value.status_code == 422
    assert intrus in erreur.value.detail


@pytest.mark.parametrize("valeur", [None, []])
def test_ni_transmis_ni_choisi_passent(arbre_dessai, valeur):
    """`None` = « ne change rien », `[]` = « on ne sait pas ». Deux décisions, pas des erreurs."""
    session, _ = arbre_dessai
    valider_acces(session, VIGIK, valeur)


def test_cas_zero_un_arbre_vide_ninterdit_rien():
    """⚠️ Sans arbre ni configuration, la liste est vide et **rien n'est refusé**.

    Le sens de l'échec est une décision : une restriction qui se retourne en
    blocage total sur une donnée absente ferait d'une copropriété non configurée
    une copropriété paralysée (`standards/04` §2).
    """
    invalider_cache()
    with contexte.nouvelle_session() as s:
        assert codes_autorises(s, VIGIK) == []
        valider_acces(s, VIGIK, ["n'importe quoi"])


def test_une_telecommande_ignore_le_batiment_du_lot(arbre_dessai):
    """🔴 Le défaut d'une télécommande ne se déduit PAS du lot (signalé à l'écran).

    Le porteur n'a qu'un lot, dans le bâtiment 1 : la déduction d'un vigik
    rendrait ce bâtiment. Une télécommande rend les portails — deux objets qui se
    ressemblent n'ouvrent pas les mêmes portes.
    """
    session, batiments = arbre_dessai
    porteur = Utilisateur(
        email="porteur@essai.fr",
        hashed_password="x",
        prenom="A",
        nom="B",
    )
    session.add(porteur)
    session.commit()
    session.refresh(porteur)
    lot = Lot(batiment_id=batiments[0].id, numero="101")
    session.add(lot)
    session.commit()
    session.refresh(lot)
    session.add(UserLot(user_id=porteur.id, lot_id=lot.id))
    session.commit()

    vu_par_un_vigik = _acces_json(session, VIGIK, None, lot.id, porteur.id)
    vu_par_une_telecommande = _acces_json(session, TELECOMMANDE, None, lot.id, porteur.id)

    assert json.loads(vu_par_un_vigik) == ["copro:b1"]
    assert json.loads(vu_par_une_telecommande) == PORTAILS

    session.delete(session.exec(select(UserLot).where(UserLot.user_id == porteur.id)).first())
    session.commit()
    session.delete(lot)
    session.delete(porteur)
    session.commit()


def test_le_code_dun_batiment_vient_de_larbre(arbre_dessai):
    """🔴 La déduction rend le code du NŒUD, pas `bat:<id>` fabriqué.

    C'est ce qui rend la déduction et la restriction compatibles : un code
    fabriqué qui ne serait pas celui de l'arbre se ferait refuser par la
    validation, et le produit se contredirait sur le même badge.
    """
    from app.utils.acces_perimetre import code_batiment

    _, batiments = arbre_dessai
    assert code_batiment(batiments[1].id) == "copro:b2"
