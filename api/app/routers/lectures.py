"""Ce qu'une SAISIE donnerait à lire — l'aperçu de la pastille de lecture (#2633).

Le formulaire d'une affaire dit « qui la lira » pendant qu'on coche ses
Destinataires, et la correction annonce le changement de lecteurs avant
d'enregistrer. Le site le calculait dans son front (`lectureDe`) ; arbitré le
11/11/2026 : le SERVEUR le dit, par la même règle que l'objet enregistré
(`lecture_pastille.objets.lecture_de_saisie`), et l'app iOS l'appelle aussi pour
ses formulaires. L'écran attend ~150 ms après un choix, ignore une réponse
périmée et garde la dernière phrase pendant l'attente.

Rien n'est lu ni écrit en base, hors l'arbre des périmètres : la route ne dit
que ce que la règle déduit de ce qu'on lui envoie.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.deps import get_current_user
from app.models.core import Utilisateur
from app.utils.lecture_pastille.modele import Lecture
from app.utils.lecture_pastille.objets import lecture_de_saisie
from app.utils.nature_affaire import ACTUALITE
from app.utils.valeurs import valeur
from app.utils.visibility.defauts_affaire import defauts_de_nature

router = APIRouter(prefix="/lectures", tags=["lectures"])

#: Une saisie n'a jamais plus de codes que cela ; au-delà, la requête est refusée.
_CODES_MAX = 64


class ApercuLectureEntree(BaseModel):
    """Ce que la saisie dit de ses lecteurs."""

    #: La catégorie (`actualite` pour une actualité) ; absente, une Suite sans nature.
    categorie: Optional[str] = Field(default=None, max_length=64)
    #: L'état — une Étude & travaux s'ouvre aux copropriétaires en AG.
    statut: Optional[str] = Field(default=None, max_length=64)
    confidentiel: bool = False
    public_cible: list[str] = Field(default_factory=list, max_length=_CODES_MAX)
    perimetre_cible: list[str] = Field(default_factory=list, max_length=_CODES_MAX)
    reserve_perimetre: bool = False


class ApercuLecture(BaseModel):
    """La pastille de la saisie, et ce que sa nature décide sans choix du conseil."""

    lecture: Lecture
    #: Les Destinataires d'une affaire SANS choix du conseil — vide pour une actualité.
    destinataires_par_defaut: list[str]
    #: Personne d'autre que le conseil (et l'auteur) ne la lit, périmètre mis à part :
    #: rien ne sort, ni sur le groupe ni au hall.
    lue_du_seul_conseil: bool


@router.post("/apercu", response_model=ApercuLecture)
def apercu_lecture(
    corps: ApercuLectureEntree,
    _: Utilisateur = Depends(get_current_user),
) -> ApercuLecture:
    """Qui lirait cette saisie — la règle de l'objet enregistré, sur ce qu'elle dit."""
    actualite = valeur(corps.categorie) == ACTUALITE
    sans_perimetre = lecture_de_saisie(
        categorie=corps.categorie,
        statut=corps.statut,
        confidentiel=corps.confidentiel,
        public_cible=corps.public_cible,
        perimetre_cible=[],
        reserve_perimetre=False,
    )
    return ApercuLecture(
        lecture=lecture_de_saisie(
            categorie=corps.categorie,
            statut=corps.statut,
            confidentiel=corps.confidentiel,
            public_cible=corps.public_cible,
            perimetre_cible=corps.perimetre_cible,
            reserve_perimetre=corps.reserve_perimetre,
        ),
        destinataires_par_defaut=(
            [] if actualite else defauts_de_nature(False, corps.categorie, corps.statut)
        ),
        lue_du_seul_conseil=not sans_perimetre.profils,
    )
