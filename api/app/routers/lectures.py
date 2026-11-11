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
from app.utils.lecture_pastille.modele import ApercuLecture
from app.utils.lecture_pastille.objets import perimetre_restreint_de
from app.utils.lecture_pastille.regle import apercu_de

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


@router.post("/apercu", response_model=ApercuLecture)
def apercu_lecture(
    corps: ApercuLectureEntree,
    _: Utilisateur = Depends(get_current_user),
) -> ApercuLecture:
    """Qui lirait cette saisie — la règle de l'objet enregistré, sur ce qu'elle dit."""
    return apercu_de(
        categorie=corps.categorie,
        statut=corps.statut,
        confidentiel=corps.confidentiel,
        public_cible=corps.public_cible,
        perimetre_restreint=perimetre_restreint_de(corps.perimetre_cible),
        reserve_perimetre=corps.reserve_perimetre,
    )
