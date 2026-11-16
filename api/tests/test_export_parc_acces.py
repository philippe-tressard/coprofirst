"""L'export du parc d'accès : **deux fichiers**, un par type (15/09/2026).

## La décision, et son retournement

Le 14/09, un fichier unique avait été arbitré, avec une colonne « Type » :

> « un fichier se trie et se filtre dans un tableur ; deux obligent à les
>   rapprocher à la main »

L'usage a tranché l'inverse le lendemain :

> « ne fais pas qu'un seul export en format CSV, mais 2 : l'un pour les vigik et
>   l'autre pour les télécommandes »

⚠️ **Ce fichier verrouille le retournement, pas seulement le format.** Une
décision renversée sans trace se re-renverse au prochain audit — c'est ce qui
était arrivé à l'écriture sur cet écran même (#805 fermait ce que #953 a rouvert).

## Ce qu'il éprouve

1. il y a une route **par type**, et plus de route globale ;
2. un export ne contient **que** son type ;
3. il ne porte plus de colonne « Type » — une colonne constante n'apprend rien ;
4. le format reste lisible par un tableur français : BOM, `;`, CRLF ;
5. un type inconnu est refusé (422), et pas silencieusement vide.
"""

from __future__ import annotations

import inspect

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import Telecommande, Utilisateur, Vigik
from app.routers.acces import parc
from app.utils.types_acces import TELECOMMANDE, TYPES_ACCES, VIGIK


@pytest.fixture()
def parc_dessai():
    """Un porteur, un vigik, une télécommande — le minimum qui distingue."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        porteur = Utilisateur(
            email="parc@essai.test",
            hashed_password="x",
            prenom="Anne",
            nom="Durand",
        )
        session.add(porteur)
        session.commit()
        session.refresh(porteur)

        session.add(Vigik(code="V-001", user_id=porteur.id))
        session.add(Telecommande(code="T-001", user_id=porteur.id))
        session.commit()

        yield session

        for modele in (Vigik, Telecommande):
            for o in session.exec(select(modele)).all():
                session.delete(o)
        session.delete(porteur)
        session.commit()


def test_il_y_a_une_route_par_type_et_plus_de_route_globale():
    """🔴 La route est paramétrée — pas deux fonctions jumelles, pas une globale.

    Deux `exporter_vigiks` / `exporter_telecommandes` auraient divergé à la
    première colonne ajoutée : c'est le défaut que `TYPES_ACCES` corrige partout
    ailleurs dans ce module.
    """
    chemins = [r.path for r in parc.router.routes]
    assert "/admin/{type_cle}/export.csv" in chemins
    assert "/admin/export.csv" not in chemins, (
        "La route globale subsiste : un export unique et un export par type "
        "rendraient deux vérités sur le même parc."
    )


def test_le_type_est_resolu_par_la_dependance_partagee():
    """La garde d'entrée est dans la SIGNATURE, donc impossible à oublier.

    Elle était recopiée dans les trois routes paramétrées, et l'export allait en
    faire une quatrième.
    """
    params = inspect.signature(parc.exporter_parc).parameters
    assert "type_acces" in params, "l'export doit recevoir un TypeAcces résolu"
    assert "type_cle" not in params, (
        "l'export valide encore la clé lui-même : c'est la quatrième copie de la "
        "garde que `type_acces_demande` existe pour supprimer."
    )


@pytest.mark.parametrize(
    "type_acces,present,absent",
    [(VIGIK, "V-001", "T-001"), (TELECOMMANDE, "T-001", "V-001")],
)
def test_un_export_ne_porte_que_son_type(parc_dessai, type_acces, present, absent):
    """Chacun son fichier — c'est tout l'objet de la demande."""
    csv_rendu = parc._csv_du_parc(parc_dessai, type_acces)
    assert present in csv_rendu
    assert absent not in csv_rendu, (
        f"L'export {type_acces.cle} contient {absent}, qui n'est pas de son type."
    )


def test_plus_de_colonne_type(parc_dessai):
    """Une colonne dont toutes les lignes ont la même valeur n'apprend rien.

    Le nom du fichier porte le type ; la colonne ne servait qu'au fichier unique.
    """
    assert "Type" not in parc.COLONNES_EXPORT
    entete = parc._csv_du_parc(parc_dessai, VIGIK).splitlines()[0]
    assert entete.lstrip("﻿") == ";".join(parc.COLONNES_EXPORT)


def test_le_format_reste_lisible_par_un_tableur_francais(parc_dessai):
    """BOM, `;` et CRLF — les trois, et chacun pour une raison précise.

    ⚠️ Sans BOM, « Bâtiment » s'affiche « BÃ¢timent » dans Excel. Avec une
    virgule, Excel en configuration française met tout dans une seule colonne.
    Ce fichier est fait pour être ouvert dans un tableur, pas relu par une
    machine — et c'est ce qui justifie des choix qu'on ne ferait pas autrement.
    """
    rendu = parc._csv_du_parc(parc_dessai, VIGIK)
    assert rendu.startswith("﻿"), "BOM absent : les accents casseront dans Excel"
    assert "\r\n" in rendu, "fins de ligne CRLF attendues"
    assert ";" in rendu.splitlines()[0], "séparateur point-virgule attendu"


def test_un_type_inconnu_est_refuse():
    """🔴 422, jamais un fichier vide.

    Un export vide se lit « il n'y a rien à exporter », ce qui est faux et
    indétectable. C'est le cas zéro de `standards/04` §2, appliqué à un
    téléchargement.
    """
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as erreur:
        parc.type_acces_demande("badge-magique")
    assert erreur.value.status_code == 422
    #  Le message NOMME les types valides — il est composé depuis `TYPES_ACCES`,
    #  donc un troisième type y apparaîtra sans qu'on touche à ce test.
    for cle in TYPES_ACCES:
        assert cle in erreur.value.detail


def test_chaque_ligne_porte_SON_PROPRE_perimetre(parc_dessai):
    """🔴 Le défaut du 15/09/2026 : l'export portait le périmètre d'un AUTRE badge.

    `_acces_admin_out` **trie par code** ; la liste lue en base ne l'est pas. La
    boucle les appariait par `zip`, si bien que chaque ligne recevait le
    périmètre de son voisin de rang. Constaté en comparant l'export à l'écran :
    le même code y affichait deux bâtiments différents.

    ⚠️ **Un accès dit quelle porte s'ouvre.** Ce n'est pas une gêne de lecture :
    l'export désignait la mauvaise serrure, et rien dans le fichier ne permettait
    de s'en apercevoir.

    ## Pourquoi les tests voisins ne pouvaient pas le voir

    Ils créent UN vigik et UNE télécommande. Avec un seul élément par type, tout
    appariement est correct — y compris un appariement faux. Il faut au moins
    deux éléments, et surtout un ordre d'insertion qui DIFFÈRE de l'ordre de
    tri : sans cela le `zip` fautif aurait encore donné le bon résultat.

    C'est la leçon de ce fichier : **un jeu d'essai à un seul élément ne prouve
    rien sur le rang.**
    """
    porteur = parc_dessai.exec(select(Utilisateur)).first()
    #  Codes à REBOURS de l'ordre alphabétique : le tri rend Z09 → A01, l'ordre
    #  d'insertion est A01 → Z09. Un `zip` des deux séquences inverse donc les
    #  périmètres, et ce test le voit.
    pose = {"Z09": '["zone-z"]', "M05": '["zone-m"]', "A01": '["zone-a"]'}
    for code, perimetre in pose.items():
        parc_dessai.add(Vigik(code=code, user_id=porteur.id, perimetre_cible=perimetre))
    parc_dessai.commit()

    lignes = parc._csv_du_parc(parc_dessai, VIGIK).splitlines()[1:]
    vus = {}
    for ligne in lignes:
        cellules = ligne.split(";")
        vus[cellules[0].lstrip("\ufeff")] = cellules[3]

    for code, brut in pose.items():
        attendu = brut.strip('[]"')
        assert code in vus, f"{code} absent de l'export"
        assert attendu in vus[code], (
            f"La ligne « {code} » porte « {vus[code]} » au lieu de « {attendu} ».\n"
            "Les deux séquences ne sont pas appariées : l'export attribue à ce "
            "badge le périmètre d'un autre, c'est-à-dire une autre serrure."
        )

    #  …et l'ordre du fichier est bien celui du tri par code : c'est ce qui rend
    #  un export relisible d'un mois sur l'autre.
    codes = [c for c in vus if c in pose]
    assert codes == sorted(codes), f"ordre inattendu : {codes}"
