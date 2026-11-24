"""Les résidents et le nettoyage des tests du public cible de la Communauté (#2950).

`test_communaute_public_cible.py` (#782) et `test_idee_edition.py` (#783)
portaient les mêmes aides — la fabrique de résident, la neutralisation du
périmètre, la purge, les fixtures `locataire` et `conseiller` —, recopiées à
l'identique. Elles vivent ici. `locataire` et `conseiller` sont des fixtures : un
fichier de tests les IMPORTE pour que pytest les trouve (même forme
qu'`aides_fil.cs`).
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import RoleUtilisateur, StatutUtilisateur, Utilisateur
from tests.aides_base import compte
from tests.aides_purge import purger_ligne


def utilisateur_du_public(
    role: RoleUtilisateur, statut: StatutUtilisateur | None, prenom: str
) -> Utilisateur:
    """⚠️ Le public cible se décide sur le STATUT, le périmètre sur le rôle.

    Les confondre est l'erreur naturelle : « locataire » est un statut et non un
    rôle, et `RoleUtilisateur` n'en a pas. C'est `public_cible_visible` qui lit
    `user.statut` — un test qui n'aurait posé que le rôle aurait vu passer tout
    le monde et conclu que le ciblage marchait.
    """
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        return compte(
            session,
            prefixe=prenom.lower(),
            prenom=prenom,
            nom="Aulnay",
            role=role,
            statut=statut,
        )


def sans_perimetre(modele: type, ident: int) -> None:
    """Neutralise l'axe GÉOGRAPHIQUE pour n'éprouver que le public cible.

    ⚠️ Ce n'est pas une commodité : `perimetre_visible` lit l'arbre des périmètres
    en base, et le refuse quand il est illisible — « un contrôle qui ne peut pas
    s'exécuter renvoie INCONNU, jamais OK » (`standards/04`). Sur une base de test
    dont la table `perimetre` n'est pas migrée, TOUT est donc invisible, et un
    test du public cible passerait au vert pour la mauvaise raison : il verrait
    l'objet caché sans que sa propre règle y soit pour quoi que ce soit.

    Un périmètre vide court-circuite cette lecture. Les deux axes restent testés
    séparément — celui-ci l'est déjà par `test_annonce_perimetre.py`.
    """
    with Session(engine) as session:
        objet = session.get(modele, ident)
        objet.perimetre_cible = "[]"
        session.add(objet)
        session.commit()


def supprimer(modele: type, ident: int) -> None:
    with Session(engine) as session:
        purger_ligne(session, modele, ident)
        session.commit()


@pytest.fixture()
def locataire() -> Utilisateur:
    u = utilisateur_du_public(RoleUtilisateur.résident, StatutUtilisateur.locataire, "Lou")
    yield u
    supprimer(Utilisateur, u.id)


@pytest.fixture()
def conseiller() -> Utilisateur:
    u = utilisateur_du_public(
        RoleUtilisateur.conseil_syndical, StatutUtilisateur.copropriétaire_résident, "Charlie"
    )
    yield u
    supprimer(Utilisateur, u.id)
