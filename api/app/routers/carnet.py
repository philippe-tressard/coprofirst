"""Router carnet d'entretien — la lecture de l'histoire du bâti.

Un routeur à lui seul, et non trois routes de plus dans `copropriete.py` : ce
fichier était à 478 lignes, et le plafond de modularité (rang 1) refuse qu'un
fichier déjà proche des 500 les franchisse pour une fonctionnalité neuve.

## Le droit : copropriétaires, conseil syndical, admin

Arbitré par Philippe le 10/09/2026. Le décret n° 2001-477 destine le carnet aux
**copropriétaires** — un acquéreur peut le réclamer via son vendeur —, et il porte
des références de contrats qui ne regardent pas un locataire.

🔴 **Aucune règle n'est écrite ici** : `require_proprietaire` disait déjà
exactement cela (propriétaire **ou** conseil syndical **ou** admin). Réécrire la
condition dans ce fichier en aurait fait une seconde version, libre de diverger au
premier durcissement — c'est `standards/03` §1, et c'est la dérive que
`_require_bailleur` avait produite sur dix-sept endpoints.

## Le bilan de l'exercice : le conseil syndical seul (#1645)

`GET /carnet-entretien/metriques` — les moyennes des affaires du carnet closes
sur un exercice comptable. Arbitré le 04/10/2026 : un argument chiffré pour
l'assemblée générale, que le conseil prépare — `require_cs_or_admin`, et non le
droit du carnet. Le calcul vit dans `utils/synthese_affaire/agregats`.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin, require_proprietaire
from app.database import get_session
from app.models.core import Utilisateur
from app.schemas_synthese import ExerciceLu, ResumeAffaires, SyntheseLue
from app.utils.carnet_affichage import (
    annees_du_carnet,
    entrees_de_l_annee,
    groupes_par_equipement,
)
from app.utils.carnet_entretien import construire_carnet
from app.utils.equipements import libelles
from app.utils.synthese_affaire.agregats import bilan_carnet

router = APIRouter(prefix="/carnet-entretien", tags=["carnet-entretien"])


class ExerciceBorne(ExerciceLu):
    """L'exercice affiché, avec son premier et son DERNIER jour (inclus)."""

    debut: date
    fin: date


class PrestataireLent(BaseModel):
    """Un intervenant et la durée moyenne de l'étape « Chez le prestataire »."""

    prestataire_id: int
    nom: str
    jours: float
    nombre: int


class CategorieBilan(ResumeAffaires):
    """Les moyennes d'une catégorie d'affaire du carnet sur l'exercice."""

    categorie: str
    #: …et son libellé (« Panne ») — `categories_ticket.libelle_categorie` (#2511).
    categorie_libelle: str
    prestataires: list[PrestataireLent] = []


class BilanCarnet(BaseModel):
    """Le bilan d'un exercice : ses catégories, et les exercices qu'on peut choisir."""

    exercice: ExerciceBorne
    exercices: list[ExerciceLu]
    categories: list[CategorieBilan]
    nombre: int


@router.get("/metriques", response_model=BilanCarnet)
def lire_bilan(
    exercice: Optional[int] = Query(default=None, ge=2000, le=2100),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Le bilan d'un exercice — `exercice` est l'année où il commence ; absent, l'en-cours.

    Toutes les affaires du carnet closes sur l'exercice (résolues ou annulées),
    mesurées comme leur synthèse : durées en jours ouvrés, moyennes par étape du
    kanban, relances au syndic, intervenants les plus lents. Le conseil voit
    toutes les affaires (`ticket_visible` lui ouvre tout) : aucun filtre de
    lecture à rejouer ici.
    """
    return bilan_carnet(session, exercice)


class EntreeCarnetLue(BaseModel):
    """Un fait daté du carnet — `utils/carnet_entretien.EntreeCarnet.en_dict`."""

    #: ISO : une clé de tri ; chaque client la rend avec son formateur.
    date: str
    libelle: str
    origine: Literal["contrat", "intervention", "affaire"]
    detail: str = ""
    #: Le n° de l'affaire (`TK-109008`).
    numero: Optional[str] = None
    #: La VALEUR de la catégorie d'une affaire (`etude_travaux`)…
    categorie: Optional[str] = None
    #: …et son libellé (« Étude / travaux ») — `categories_ticket.libelle_categorie`.
    categorie_libelle: str
    #: Le CODE de l'équipement ; son libellé est celui du groupe (`GroupeCarnet`).
    equipement: Optional[str] = None
    #: Les codes de périmètre de la ligne…
    perimetre: list[str] = []
    #: …et la portée en clair, toujours dite (`perimetres.perimetre_label`).
    perimetre_libelle: str
    lien: str = ""
    #: « visite attendue depuis 12 jours » — une visite dont l'échéance est passée.
    alerte: Optional[str] = None
    #: La synthèse VALIDÉE de l'affaire (#1643), s'il y en a une.
    synthese: Optional[SyntheseLue] = None
    #: Les trois lignes d'aperçu de la carte.
    extrait: str = ""


class GroupeCarnet(BaseModel):
    """Les entrées d'un équipement, dans l'ordre où l'écran les montre."""

    equipement: Optional[str] = None
    #: Le libellé administré de l'équipement, « Sans équipement rattaché » sinon.
    equipement_libelle: str
    entrees: list[EntreeCarnetLue]


class CarnetLu(BaseModel):
    """Le carnet de ce lecteur (#2505 : typé, il était déclaré `{}` au contrat)."""

    #: Du fait le plus récent au plus ancien, filtrées par `annee`.
    entrees: list[EntreeCarnetLue]
    total: int
    #: Les mêmes, rangées par équipement : le groupe le plus récent d'abord.
    groupes: list[GroupeCarnet]
    #: Les années qu'on peut choisir, la plus récente d'abord — calculées sur
    #: tout le carnet du périmètre, quelle que soit l'année demandée.
    annees: list[str]


@router.get("", response_model=CarnetLu)
def lire_carnet(
    perimetre: Optional[str] = Query(default=None),
    #: Une année civile (`2025`) ; absente, tout le carnet. Les contrats restent.
    annee: Optional[str] = Query(default=None, pattern=r"^\d{4}$"),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_proprietaire),
):
    """Le carnet, éventuellement restreint à un PÉRIMÈTRE.

    ⚠️ `perimetre` est un **code de l'arborescence** (`"bat:3"`, `"parking"`),
    pas un identifiant de bâtiment. C'est ce qui permet de filtrer sur des
    espaces qui n'ont pas de bâtiment — et de suivre un périmètre créé demain en
    administration, sans migration ni déploiement.

    Le filtre lui-même n'est pas écrit ici : `couvre()` (arbre des périmètres)
    répond à « cette ligne entre-t-elle dans ce que l'utilisateur regarde ? », et
    c'est la même question sur toutes les pages qui filtrent.
    """
    #  Le carnet de CE lecteur : une affaire qu'il ne lit pas n'y paraît pas
    #  (Carnet = Affaires = Kanban, standard du 30/09/2026).
    tout = construire_carnet(session, lecteur=user, perimetre=perimetre)
    #  Les règles d'affichage du carnet — année, regroupement — vivent dans
    #  `utils/carnet_affichage` : l'app iOS les lit au lieu de les recopier (#2505).
    entrees = entrees_de_l_annee(tout, annee)
    return {
        "entrees": entrees,
        "groupes": groupes_par_equipement(entrees, libelles(session)),
        "annees": annees_du_carnet(tout),
        #  Le compte est rendu par le SERVEUR plutôt que déduit de la longueur du
        #  tableau : l'écran affiche « n interventions » à côté d'un filtre, et
        #  recompter côté client donnerait un chiffre juste tant que la pagination
        #  n'existe pas — c'est-à-dire jusqu'au jour où elle existera.
        "total": len(entrees),
    }
