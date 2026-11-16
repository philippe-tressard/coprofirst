"""Corriger le nom mal orthographié d'une ligne d'import (#1152).

## Demandé à l'écran le 22/09/2026

> « En édition d'un locataire donner la possibilité d'éditer le copropriétaire,
>   car quand il y a une faute d'orthographe le rapprochement vigik et TC est
>   impossible. »

Arbitré le même jour : c'est le **texte importé** qu'on corrige — celui sur
lequel `auto_match` travaille —, pas la fiche du copropriétaire. Une faute dans
le fichier du syndic ne doit pas obliger à retoucher un compte d'utilisateur,
qui sert à l'annuaire, aux courriels et aux affiches.

## Ce que ces tests tiennent

1. le PATCH **applique** la correction, sur les deux types d'import ;
2. l'appariement **retrouve** alors le compte — le seul point qui prouve que la
   correction sert à quelque chose. Vérifier qu'un champ se copie ne dirait
   rien : ce serait vrai même si `auto_match` lisait ailleurs ;
3. il ne peut pas **effacer** le nom du propriétaire : la colonne est
   obligatoire, et une ligne sans nom n'est plus rattachable à personne.

⚠️ Chaque cas porte un nom UNIQUE et nettoie ce qu'il a créé : la base de test
est partagée, et ma première rédaction voyait le second paramétrage apparier le
compte du premier — même nom, même score. Un test qui fabrique son propre cas
limite ne mesure plus le produit.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.acces import StatutImport, TelecommandeImport, VigikImport
from app.models.core import Utilisateur
from app.routers.acces import socle_imports
from app.utils.types_acces import TELECOMMANDE, VIGIK

TYPES = [(TELECOMMANDE, TelecommandeImport), (VIGIK, VigikImport)]


@pytest.fixture()
def session():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def cas(session, request):
    """Un nom juste, sa faute, et le ménage à la fin.

    Le nom porte l'identifiant du test : deux cas qui partageraient le même
    apparieraient le compte l'un de l'autre.
    """
    marque = abs(hash(request.node.name)) % 100000
    juste = f"LEFEBVRE-MOREAU-{marque}"
    fautif = f"LEFEVRE-MOREAU-{marque}"
    cree: list = []
    yield juste, fautif, cree
    for objet in cree:
        session.delete(objet)
    session.commit()


def _proprietaire(session: Session, nom: str, cree: list) -> Utilisateur:
    u = Utilisateur(
        nom=nom, prenom="Claire", email=f"{nom.lower()}@exemple.test", hashed_password="x"
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    cree.append(u)
    return u


def _import(session: Session, modele, nom: str, cree: list):
    imp = modele(nom_proprietaire=nom, statut=StatutImport.en_attente)
    session.add(imp)
    session.commit()
    session.refresh(imp)
    cree.append(imp)
    return imp


@pytest.mark.parametrize("type_import,modele", TYPES)
def test_le_nom_importe_se_corrige(session, cas, type_import, modele):
    """Le geste demandé : réparer la faute venue du fichier du syndic."""
    juste, fautif, cree = cas
    imp = _import(session, modele, fautif, cree)

    socle_imports.patch(
        type_import, imp.id, socle_imports.PatchImportBody(nom_proprietaire=juste), session
    )
    session.refresh(imp)
    assert imp.nom_proprietaire == juste, (
        "le nom importé ne se corrige pas : la faute du fichier reste, et "
        "l'appariement continuera d'échouer (#1152)."
    )


@pytest.mark.parametrize("type_import,modele", TYPES)
def test_apres_correction_l_appariement_RETROUVE_le_compte(session, cas, type_import, modele):
    """🔴 Le seul test qui prouve que la correction sert à quelque chose."""
    juste, fautif, cree = cas
    proprietaire = _proprietaire(session, juste, cree)
    imp = _import(session, modele, fautif, cree)

    #  Avant : le nom fautif n'apparie rien. Sans ce constat, le test passerait
    #  même si l'appariement avait toujours fonctionné.
    socle_imports.auto_match(type_import, session)
    session.refresh(imp)
    assert imp.user_proprietaire_id is None, (
        "un nom fautif apparie déjà : le cas de ce test n'existe pas, et il ne "
        "mesure donc pas ce qu'il annonce."
    )

    socle_imports.patch(
        session=session,
        type_import=type_import,
        import_id=imp.id,
        body=socle_imports.PatchImportBody(nom_proprietaire=juste),
    )
    socle_imports.auto_match(type_import, session)
    session.refresh(imp)
    assert imp.user_proprietaire_id == proprietaire.id, (
        "après correction du nom, l'appariement ne retrouve toujours pas le "
        "compte — la correction ne débloque rien."
    )


@pytest.mark.parametrize("type_import,modele", TYPES)
def test_un_nom_de_proprietaire_VIDE_est_refuse(session, cas, type_import, modele):
    """⚠️ La colonne est obligatoire : une ligne sans nom n'est plus
    rattachable, et elle disparaîtrait des recherches sans rien dire."""
    juste, _, cree = cas
    imp = _import(session, modele, juste, cree)

    for vide in ("", "   "):
        socle_imports.patch(
            type_import, imp.id, socle_imports.PatchImportBody(nom_proprietaire=vide), session
        )
        session.refresh(imp)
        assert imp.nom_proprietaire == juste, (
            f"un nom vide (« {vide} ») a été accepté : la ligne n'est plus "
            "rattachable, et rien à l'écran ne le dira."
        )


@pytest.mark.parametrize("type_import,modele", TYPES)
def test_le_nom_du_LOCATAIRE_peut_se_vider(session, cas, type_import, modele):
    """Le pendant : une ligne sans locataire est un cas NORMAL — le
    propriétaire occupe son lot — et `None` le dit mieux que « »."""
    juste, _, cree = cas
    imp = _import(session, modele, juste, cree)
    imp.nom_locataire = "KERBRAT"
    session.add(imp)
    session.commit()

    socle_imports.patch(
        type_import, imp.id, socle_imports.PatchImportBody(nom_locataire="  "), session
    )
    session.refresh(imp)
    assert imp.nom_locataire is None, (
        "vider le locataire laisse une chaîne vide : deux façons de dire "
        "« personne », dont une qui s'affichera comme un nom sans lettres."
    )
