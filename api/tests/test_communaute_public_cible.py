# SPDX-FileCopyrightText: 2026 Philippe Tressard
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Le public cible d'une annonce et d'une idée protège **tous** les chemins (#782).

## Ce que ce test verrouille, et pourquoi ce n'est pas la liste

Ouvrir le ciblage à une entité, c'est ouvrir autant de portes qu'elle a
d'endpoints. Filtrer la liste est la partie visible — et la moins utile seule :
une carte absente de l'écran reste atteignable en appelant l'API directement.

Les chemins qui comptent ici :

| Chemin | Ce qu'un exclu pourrait faire sans contrôle |
|---|---|
| liste | voir l'objet |
| lire les réponses | lire ce que les voisins en disent |
| écrire une réponse | s'inviter dans la conversation |
| **voter** (idée) | **peser sur un résultat qui ne le regarde pas** |

Les trois routes de réponses vérifiaient l'**existence** de la cible, jamais sa
visibilité : inoffensif tant qu'annonces et idées s'adressaient à tous, exploitable
dès l'ouverture du public cible. Corrigé dans la fabrique, donc pour les deux
rubriques à la fois.

## 🔒 404 et non 403

Répondre « interdit » confirmerait l'existence de l'objet à qui n'a pas le droit
de le voir : sur une petite annonce, cela révélerait qu'un voisin vend quelque
chose sans dire quoi.

## ⚠️ Le cas zéro est le plus important de ce fichier

**Absence de public cible = visible de tous**, jamais « visible de personne ».
C'est ce que portent toutes les annonces et idées déposées avant la migration
0176. L'inverse les aurait fait disparaître d'un coup, sans message ni ligne de
journal — la panne la plus difficile à diagnostiquer, parce que rien ne casse.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from app.database import engine
from app.models.core import (
    Idee,
    PetiteAnnonce,
    RoleUtilisateur,
    StatutUtilisateur,
    Utilisateur,
)
from app.routers.annonces import AnnonceCreate, create_annonce, list_annonces
from app.routers.idees import IdeeCreate, create_idee, list_idees, voter
from app.utils.visibility import annonce_visible, idee_visible
from tests.aides_communaute_cible import (  # noqa: F401 — fixtures importées par leur nom
    conseiller,
    locataire,
    sans_perimetre,
    supprimer,
    utilisateur_du_public,
)


@pytest.fixture()
def coproprietaire() -> Utilisateur:
    u = utilisateur_du_public(
        RoleUtilisateur.propriétaire, StatutUtilisateur.copropriétaire_résident, "Camille"
    )
    yield u
    supprimer(Utilisateur, u.id)


# ── Petite annonce ────────────────────────────────────────────────────────────


def test_annonce_ciblee_invisible_hors_public(locataire, coproprietaire):
    """Une annonce réservée aux copropriétaires n'apparaît pas au locataire."""
    with Session(engine) as session:
        cree = create_annonce(
            AnnonceCreate(
                titre="Cave à vendre",
                description="<p>10 m².</p>",
                public_cible=["copropriétaires"],
            ),
            session=session,
            user=coproprietaire,
        )
    sans_perimetre(PetiteAnnonce, cree["id"])
    try:
        with Session(engine) as session:
            annonce = session.get(PetiteAnnonce, cree["id"])
            assert annonce_visible(annonce, coproprietaire) is True
            assert annonce_visible(annonce, locataire) is False
            titres = [a["titre"] for a in list_annonces(session=session, user=locataire)]
            assert "Cave à vendre" not in titres
    finally:
        supprimer(PetiteAnnonce, cree["id"])


def test_annonce_sans_public_cible_reste_visible_de_tous(locataire, coproprietaire):
    """🔴 LE CAS ZÉRO : rien de précisé = tout le monde, jamais personne."""
    with Session(engine) as session:
        cree = create_annonce(
            AnnonceCreate(titre="Table basse", description="<p>Chêne.</p>"),
            session=session,
            user=coproprietaire,
        )
    sans_perimetre(PetiteAnnonce, cree["id"])
    try:
        with Session(engine) as session:
            annonce = session.get(PetiteAnnonce, cree["id"])
            #  `None` en base, et non `"[]"` : c'est ce que portent les annonces
            #  déposées avant la migration 0176.
            assert annonce.public_cible is None
            assert annonce_visible(annonce, locataire) is True
    finally:
        supprimer(PetiteAnnonce, cree["id"])


def test_annonce_ciblee_reste_visible_du_conseil(locataire, coproprietaire, conseiller):
    """Le CS voit tout — c'est ce qui lui laisse de quoi corriger un ciblage fautif."""
    with Session(engine) as session:
        cree = create_annonce(
            AnnonceCreate(
                titre="Poussette",
                description="<p>Bon état.</p>",
                public_cible=["copropriétaires"],
            ),
            session=session,
            user=coproprietaire,
        )
    sans_perimetre(PetiteAnnonce, cree["id"])
    try:
        with Session(engine) as session:
            annonce = session.get(PetiteAnnonce, cree["id"])
            assert annonce_visible(annonce, conseiller) is True
            assert annonce_visible(annonce, locataire) is False
    finally:
        supprimer(PetiteAnnonce, cree["id"])


# ── Idée ──────────────────────────────────────────────────────────────────────


def test_idee_ciblee_invisible_hors_public(locataire, coproprietaire):
    with Session(engine) as session:
        idee = create_idee(
            IdeeCreate(
                titre="Refaire le local vélos",
                description="<p>Il pleut dedans.</p>",
                public_cible=["copropriétaires"],
            ),
            session=session,
            user=coproprietaire,
        )
        idee_id = idee.id
    sans_perimetre(Idee, idee_id)
    try:
        with Session(engine) as session:
            objet = session.get(Idee, idee_id)
            assert idee_visible(objet, coproprietaire) is True
            assert idee_visible(objet, locataire) is False
            titres = [i["titre"] for i in list_idees(session=session, user=locataire)]
            assert "Refaire le local vélos" not in titres
    finally:
        supprimer(Idee, idee_id)


def test_voter_sur_une_idee_non_visible_est_refuse(locataire, coproprietaire):
    """🔒 Le chemin qui compte : voter pèse sur un résultat.

    La liste ne montrait déjà plus l'idée ; sans ce contrôle, l'endpoint restait
    appelable directement — et un exclu votait.
    """
    with Session(engine) as session:
        idee = create_idee(
            IdeeCreate(
                titre="Composteur collectif",
                description="<p>Dans les espaces verts.</p>",
                public_cible=["copropriétaires"],
            ),
            session=session,
            user=coproprietaire,
        )
        idee_id = idee.id
    sans_perimetre(Idee, idee_id)
    try:
        with Session(engine) as session:
            with pytest.raises(HTTPException) as refus:
                voter(idee_id, session=session, user=locataire)
            #  404 et non 403 : ne pas confirmer l'existence de l'idée.
            assert refus.value.status_code == 404
    finally:
        supprimer(Idee, idee_id)


def test_idee_sans_public_cible_reste_votable(locataire, coproprietaire):
    """Le cas zéro, sur le chemin d'écriture : une idée non ciblée se vote."""
    with Session(engine) as session:
        idee = create_idee(
            IdeeCreate(titre="Boîte à livres", description="<p>Dans le hall.</p>"),
            session=session,
            user=coproprietaire,
        )
        idee_id = idee.id
    sans_perimetre(Idee, idee_id)
    try:
        with Session(engine) as session:
            resultat = voter(idee_id, session=session, user=locataire)
            assert resultat is not None
    finally:
        supprimer(Idee, idee_id)
