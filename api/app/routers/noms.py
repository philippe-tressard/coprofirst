"""Le nom d'une personne en cours de SAISIE, rendu par le serveur (#2633).

Un formulaire qui nomme quelqu'un avant de l'enregistrer — un membre de
l'annuaire qu'on corrige, un invité ajouté au point du conseil — montre son
« Prénom NOM ». Le site le composait dans son front (`nomAffiche`) ; arbitré le
11/11/2026 (option a) : le SERVEUR le rend, par la règle de l'objet enregistré
(`utils/noms.nom_affiche`), et l'app iOS l'appelle aussi. L'écran attend ~150 ms
après la frappe, ignore une réponse périmée et garde le dernier nom pendant
l'attente (`#lib/apercu-serveur`).

Rien n'est lu ni écrit en base : la route ne rend que ce qu'on lui envoie.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.deps import get_current_user
from app.models.core import Utilisateur
from app.utils.noms import nom_affiche

router = APIRouter(prefix="/noms", tags=["noms"])

#: Plus long qu'aucun prénom ni nom saisissable ; au-delà, la requête est refusée.
_LONGUEUR_MAX = 120


class NomSaisi(BaseModel):
    """Ce que la saisie dit de la personne."""

    prenom: Optional[str] = Field(default=None, max_length=_LONGUEUR_MAX)
    nom: Optional[str] = Field(default=None, max_length=_LONGUEUR_MAX)


class NomRendu(BaseModel):
    #: « Prénom NOM » (`utils/noms.nom_affiche`) — vide si l'un et l'autre manquent.
    nom_affiche: str


@router.post("/affiche", response_model=NomRendu)
def nom_d_une_saisie(corps: NomSaisi, _: Utilisateur = Depends(get_current_user)) -> NomRendu:
    """« Jean-Baptiste », « ForT » → « Jean-Baptiste FORT » — l'aperçu d'une saisie."""
    return NomRendu(nom_affiche=nom_affiche(corps.prenom, corps.nom))
