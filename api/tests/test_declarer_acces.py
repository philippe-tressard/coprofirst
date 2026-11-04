"""Déclarer un accès : les deux types se comportent PAREIL.

## 🔴 Le défaut que ces tests verrouillent (14/09/2026, #779)

`declarer_badge` portait deux branches jumelles — une par type d'accès — et
elles avaient divergé sans que personne le voie : à la résolution de la ligne
d'import, la branche **vigik** recopiait le `lot_id` sur l'objet créé, la
branche **télécommande** ne le faisait pas.

Conséquence : une télécommande déclarée par son porteur restait **sans lot** dans
la vue du conseil syndical (`lot_libelle: null`), alors que l'import connaissait
le lot. Rien ne levait, rien ne manquait dans les journaux — la colonne était
simplement vide, et on pouvait croire que l'information n'existait pas.

⚠️ **Aucun test ne pouvait l'attraper tant qu'il ne traitait qu'un type.** C'est
ce que ces cas corrigent : chaque comportement est éprouvé sur les DEUX types,
par paramétrage. Un troisième accès entrera dans les mêmes cas sans qu'on écrive
une ligne — et c'est ce qui empêchera la prochaine divergence.
"""

from datetime import datetime

import pytest
from sqlmodel import select

from app.models.core import (
    StatutAcces,
    StatutImport,
    VigikImport,
)
from app.utils.types_acces import TYPES_ACCES
from tests.aides_badges import TYPES, _lier, _lot
from tests.aides_base import compte


@pytest.fixture()
def porteur(session):
    return compte(session, prefixe="porteur", prenom="A", nom="B")


def _ligne_import(type_acces, code: str, lot_id):
    """Une ligne de staging du bon type, portant le code à l'endroit qu'il faut.

    ⚠️ C'est ici que se voit la seule divergence de vocabulaire : le classeur des
    vigiks nomme sa référence `code`, celui des télécommandes `reference`. Le
    descripteur la porte, le test n'a pas à la répéter.
    """
    ligne = type_acces.modele_import()
    setattr(ligne, type_acces.colonne_code_import, code)
    ligne.lot_id = lot_id
    ligne.statut = StatutImport.en_attente
    #  Le nom du propriétaire est requis dans les DEUX tables : c'est la colonne
    #  que les deux classeurs portent, et le seul champ obligatoire commun.
    ligne.nom_proprietaire = "B A"
    if isinstance(ligne, VigikImport):
        ligne.batiment_raw, ligne.appartement_raw = "1", "10"
    return ligne


def test_les_deux_types_sont_declares():
    """Cas zéro : si la table des types se vidait, tout ce fichier passerait."""
    assert set(TYPES_ACCES) == {"vigik", "telecommande"}


def _lot_du_porteur(session, porteur, type_acces) -> int:
    """Un lot de la nature du badge, auquel le porteur est rattaché."""
    lot = _lot(session, type_acces, numero="7")
    _lier(session, porteur, lot)
    return lot.id


@pytest.mark.parametrize("type_acces", TYPES)
def test_le_lot_de_l_import_est_repris_sur_l_objet(session, porteur, type_acces):
    """🔴 LE CAS QUI ÉTAIT FAUX POUR LA TÉLÉCOMMANDE."""
    from app.routers.acces.resident import _declarer_acces

    lot_id = _lot_du_porteur(session, porteur, type_acces)
    session.add(_ligne_import(type_acces, "A-42", lot_id=lot_id))
    session.commit()

    resultat = _declarer_acces(session, type_acces, "A-42", porteur)

    assert resultat.import_resolu is True
    objet = session.get(type_acces.modele, resultat.id)
    assert objet.lot_id == lot_id, (
        f"{type_acces.libelle} : le lot connu de l'import n'a pas été repris — "
        "c'est exactement la divergence de #779"
    )
    assert objet.statut == StatutAcces.actif
    ligne = session.exec(select(type_acces.modele_import)).one()
    assert ligne.statut == StatutImport.resolu
    assert getattr(ligne, type_acces.colonne_import) == resultat.id
    assert isinstance(ligne.resolu_le, datetime)


@pytest.mark.parametrize("type_acces", TYPES)
def test_la_ligne_d_un_AUTRE_lot_n_est_pas_capturee(session, porteur, type_acces):
    """🔴 #1194 : taper le code d'un voisin ne rattache plus sa ligne à soi.

    La déclaration résolvait la ligne du fichier par son SEUL code, au nom du
    déclarant, quel que soit le lot qu'elle désigne.
    """
    from fastapi import HTTPException

    from app.routers.acces.resident import _declarer_acces

    voisin = _lot(session, type_acces, numero="8")
    session.add(_ligne_import(type_acces, "B-7", lot_id=voisin.id))
    session.commit()

    with pytest.raises(HTTPException) as refus:
        _declarer_acces(session, type_acces, "B-7", porteur)
    assert refus.value.status_code == 400
    assert session.exec(select(type_acces.modele)).first() is None


@pytest.mark.parametrize("type_acces", TYPES)
def test_sans_lot_connu_le_badge_prend_le_lot_unique_du_porteur(session, porteur, type_acces):
    from app.routers.acces.resident import _declarer_acces

    lot_id = _lot_du_porteur(session, porteur, type_acces)
    resultat = _declarer_acces(session, type_acces, "C-9", porteur)

    assert session.get(type_acces.modele, resultat.id).lot_id == lot_id


@pytest.mark.parametrize("type_acces", TYPES)
def test_sans_ligne_d_import_l_objet_existe_quand_meme(session, porteur, type_acces):
    """Déclarer un accès que l'import ne connaît pas reste un geste valide."""
    from app.routers.acces.resident import _declarer_acces

    resultat = _declarer_acces(session, type_acces, "INCONNU-1", porteur)

    assert resultat.import_resolu is False
    objet = session.get(type_acces.modele, resultat.id)
    assert objet.code == "INCONNU-1"
    assert objet.lot_id is None


@pytest.mark.parametrize("type_acces", TYPES)
def test_le_meme_code_deux_fois_est_refuse(session, porteur, type_acces):
    from fastapi import HTTPException

    from app.routers.acces.resident import _declarer_acces

    _declarer_acces(session, type_acces, "C-1", porteur)
    with pytest.raises(HTTPException) as erreur:
        _declarer_acces(session, type_acces, "C-1", porteur)
    assert erreur.value.status_code == 400


@pytest.mark.parametrize("type_acces", TYPES)
def test_un_acces_qui_n_est_pas_le_sien_est_introuvable(session, porteur, type_acces):
    """🔒 404 et non 403 : « interdit » confirmerait que le badge existe."""
    from fastapi import HTTPException

    #  La règle d'appartenance a quitté le routeur pour `auth/appartenance`
    #  (#1028) : elle ne s'écrit pas chez celui qui l'applique.
    from app.auth.appartenance import exiger_acces_du_porteur
    from app.routers.acces.resident import _declarer_acces

    resultat = _declarer_acces(session, type_acces, "D-1", porteur)

    autre = compte(session, prefixe="autre", prenom="C", nom="D")

    with pytest.raises(HTTPException) as erreur:
        exiger_acces_du_porteur(session, type_acces, resultat.id, autre)
    assert erreur.value.status_code == 404
