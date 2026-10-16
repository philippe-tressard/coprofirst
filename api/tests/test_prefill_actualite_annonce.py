"""Une actualité se pré-remplit depuis une annonce de hall — et réciproquement (#832).

Le raccourci existait dans un seul sens : `FormulaireAnnonceHall` proposait
« Pré-remplir depuis une actualité » depuis le 01/09/2026. Le CS compose pourtant
souvent l'affiche du hall d'abord, puis veut la même information en ligne.

## Ce que ces tests verrouillent

1. les **quatre champs** repris — titre, description, périmètre, images ;
2. la **symétrie** : les deux sens rendent la même information sur le même
   couple, aux noms de champs près. Sans ce test, l'un des deux gagnerait un
   champ que l'autre ignore — c'est ainsi que les deux moitiés d'un même geste
   divergent, et personne ne les compare jamais ;
3. le **droit** : le pré-remplissage est réservé au CS, comme la création d'une
   actualité qu'il alimente.

Depuis le 23/09/2026, une actualité est une affaire de catégorie « Actualité »
(#1091) : le pré-remplissage vit dans `routers/tickets/depuis_annonce.py`, et
ses champs portent le vocabulaire de l'affaire (`description`, plus `contenu`).

⚠️ Aucun lien n'est conservé vers l'annonce d'origine, contrairement au sens
inverse qui garde `ticket_id`. Là-bas le lien SERT — il donne son URL au
message WhatsApp de l'affiche. Ici rien ne le lirait, et une colonne que personne
n'interroge devient une seconde vérité sur « d'où vient ce texte ».
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.annonce_hall import AnnonceHall
from app.models.core import Ticket
from app.routers.tickets.depuis_annonce import prefill_depuis_annonce_hall
from tests.aides_base import compte


@pytest.fixture()
def scene(batiments):
    """Une affiche de hall complète — les quatre champs renseignés.

    ⚠️ Le périmètre vient de l'ARBRE (fixture `batiments`), pas d'un code
    inventé : `parse_json_perimetres` rend ce qu'on lui donne, mais un code que
    l'arbre ignore ne prouverait rien du chemin réel.
    """
    from app.utils.perimetres import perimetre_du_batiment

    SQLModel.metadata.create_all(engine)
    noeud = perimetre_du_batiment(batiments[0])
    assert noeud is not None, "l'arbre ne connaît pas ce bâtiment — fixture cassée"

    with Session(engine) as session:
        #  ⚠️ `auteur_id` est NOT NULL et porte une clé étrangère : le `conftest`
        #  vérifie les clés (#546), donc un auteur inventé ferait échouer
        #  l'insertion — pas le test, ce qui est plus difficile à lire.
        auteur = compte(
            session, prefixe="cs", prenom="C", nom="CONSEIL", roles_json="conseil_syndical"
        )
        annonce = AnnonceHall(
            auteur_id=auteur.id,
            titre="Coupure d'eau mardi",
            message="<p>L'eau sera coupée de 9 h à 12 h.</p>",
            perimetre_cible=json.dumps([noeud.code], ensure_ascii=False),
            images_json=json.dumps(["/uploads/photos/a.jpg", "/uploads/photos/b.jpg"]),
        )
        session.add(annonce)
        session.commit()
        session.refresh(annonce)

        yield session, annonce, noeud.code

        session.delete(annonce)
        session.delete(auteur)
        session.commit()


def test_les_QUATRE_champs_sont_repris(scene):
    """🔴 Le geste lui-même : titre, description, périmètre, images."""
    session, annonce, code = scene

    prefill = prefill_depuis_annonce_hall(annonce.id, session=session, _=None)

    assert prefill["titre"] == annonce.titre
    assert prefill["description"] == annonce.message
    assert prefill["perimetre_cible"] == [code], (
        "le périmètre de l'affiche n'est pas repris : l'actualité viserait toute "
        "la résidence alors que l'affiche visait un bâtiment."
    )
    assert prefill["photos_urls"] == ["/uploads/photos/a.jpg", "/uploads/photos/b.jpg"], (
        "les images de l'affiche ne sont pas reprises — le CS devrait les "
        "re-téléverser une par une."
    )


def test_les_DEUX_SENS_reprennent_la_meme_information(scene):
    """🔴 Le garde-fou de la symétrie.

    Les deux moitiés d'un même geste vivent dans deux routeurs. Sans ce test,
    l'une gagnerait un champ que l'autre ignore — et personne ne les compare
    jamais, puisque chacune est cohérente avec elle-même.

    ⚠️ Les NOMS diffèrent volontairement : chaque sens emploie le vocabulaire de
    l'entité qu'il alimente (`message`/`images` pour l'affiche,
    `description`/`photos_urls` pour l'actualité). Renommer au point de collage se
    paierait à chaque lecture. C'est le CONTENU qui doit concorder.
    """
    #  ⚠️ Le sens « actualité → affiche » est passé par un endpoint GÉNÉRIQUE le
    #  10/09/2026 : le fil agrège trois familles, et l'affiche peut désormais
    #  reprendre un ticket ou un événement autant qu'une actualité. La symétrie
    #  qu'on vérifie ici reste celle des actualités — les deux seules qui se
    #  reprennent l'une l'autre.
    from app.utils.sources_affiche import prefill_source

    session, annonce, code = scene
    actu = Ticket(
        numero=f"TK-A{uuid.uuid4().hex[:6]}",
        titre=annonce.titre,
        description=annonce.message,
        categorie="actualite",
        statut="publie",
        perimetre_cible=annonce.perimetre_cible,
        photos_urls=annonce.images_json,
        auteur_id=annonce.auteur_id,
    )
    session.add(actu)
    session.commit()
    session.refresh(actu)
    try:
        vers_actualite = prefill_depuis_annonce_hall(annonce.id, session=session, _=None)
        vers_affiche = prefill_source(session, "ticket", actu.id)
        assert vers_affiche is not None, (
            "l'actualité d'essai n'est pas reprenable — archivée ou réservée ?"
        )

        assert vers_actualite["titre"] == vers_affiche["titre"]
        assert vers_actualite["description"] == vers_affiche["message"]
        assert vers_actualite["perimetre_cible"] == vers_affiche["perimetre_cible"]
        assert set(vers_actualite) == {"titre", "description", "perimetre_cible", "photos_urls"}, (
            "un champ a été ajouté d'un seul côté : "
            f"{sorted(vers_actualite)} contre {sorted(vers_affiche)}"
        )
    finally:
        session.delete(actu)
        session.commit()


def test_une_annonce_INTROUVABLE_leve_404(scene):
    """Un identifiant périmé ne doit pas rendre un formulaire vide en silence.

    Un pré-remplissage muet se lit comme « cette affiche n'avait rien à
    reprendre », ce qui est faux et impossible à distinguer d'un bogue.
    """
    from fastapi import HTTPException

    session, _, _ = scene
    with pytest.raises(HTTPException) as capture:
        prefill_depuis_annonce_hall(999_999, session=session, _=None)
    assert capture.value.status_code == 404


def test_l_endpoint_est_reserve_au_CS():
    """Le droit passe par la dépendance centrale, jamais par une garde locale.

    ⚠️ Vérifié sur la SIGNATURE et non par un appel : la dépendance est résolue
    par FastAPI, et un test qui appelle la fonction en Python la contourne. Ce
    qu'on peut constater ici est qu'elle est bien déclarée — et c'est le seul
    endroit où elle pourrait manquer.
    """
    import inspect

    from app.auth.deps import require_cs_or_admin

    defaut = inspect.signature(prefill_depuis_annonce_hall).parameters["_"].default
    assert getattr(defaut, "dependency", None) is require_cs_or_admin, (
        "le pré-remplissage n'est pas réservé au CS : un résident pourrait lire "
        "le contenu d'une affiche dont le périmètre ne le concerne pas."
    )
