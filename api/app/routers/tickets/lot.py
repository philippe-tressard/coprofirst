"""Poser les visites de l'exercice en UNE fois — « ⚙️ Init. prestataires » (#1193).

## D'où ça vient

Le bouton vivait dans le kanban du Calendrier (`POST /calendrier/lot`, #605),
parti avec les événements au lot 5b2 (v2.23.0, #1092). Il sert une fois par
exercice, en début d'année : sans lui, les visites des contrats se saisiraient
une à une. Il pose désormais des affaires **Entretien**, « Chez le
prestataire », suivies au kanban.

## Les trois règles reprises de l'ancien lot

1. **Une transaction** : soit toutes les visites existent, soit aucune — le
   geste reste rejouable, la clé anti-doublon (`#lib/init-prestataires`) écarte
   ce qui existe déjà.
2. **Aucune diffusion, jamais** : un lot est un pré-remplissage silencieux ; en
   faire un canal offrirait l'envoi de cent courriels en une requête. Le corps
   n'ACCEPTE aucun champ de canal (`extra="forbid"`) : un appelant qui en
   enverrait un reçoit un 422 au lieu de croire avoir diffusé.
3. **Le conseil seul** — comme la catégorie Entretien elle-même.
"""

from __future__ import annotations

from datetime import datetime
from app.utils import horloge
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Ticket, Utilisateur
from app.models.prestataires import Prestataire
from app.models.tickets import CategorieTicket, StatutTicket
from app.utils.courriel_entrant import nouveau_jeton
from app.utils.intervenant import FREQUENCES, contrat_valide
from app.utils.perimetres import perimetre_cible_json

from .commun import generer_numero

router = APIRouter()

#: Au-delà, ce n'est plus un exercice, c'est une erreur d'appel.
LOT_MAX = 200


class VisiteDuLot(BaseModel):
    """Une visite planifiée — et RIEN d'autre : aucun champ de diffusion."""

    model_config = ConfigDict(extra="forbid")

    titre: str
    description: Optional[str] = None
    debut: datetime
    perimetre_cible: list[str] = []
    prestataire_id: Optional[int] = None
    #: La visite d'un CONTRAT (#1445) : sa fréquence se lit sur lui.
    contrat_id: Optional[int] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None


class LotDeVisites(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affaires: list[VisiteDuLot]


@router.post("/lot", status_code=201)
def creer_visites_en_lot(
    body: LotDeVisites,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
) -> dict:
    """Crée les visites de l'exercice, toutes ou aucune."""
    if not body.affaires:
        raise HTTPException(422, "Aucune visite à créer.")
    if len(body.affaires) > LOT_MAX:
        raise HTTPException(422, f"Lot trop grand : {len(body.affaires)} > {LOT_MAX}.")
    maintenant = horloge.maintenant()
    for i, v in enumerate(body.affaires, start=1):
        if not v.titre.strip():
            raise HTTPException(422, f"Visite {i} : titre vide.")
        if v.frequence_type and v.frequence_type not in FREQUENCES:
            raise HTTPException(422, f"Visite {i} : fréquence inconnue.")
        if v.prestataire_id is not None and session.get(Prestataire, v.prestataire_id) is None:
            raise HTTPException(422, f"Visite {i} : prestataire introuvable.")
        if v.contrat_id is not None:
            try:
                contrat_valide(session, v.contrat_id, v.prestataire_id)
            except HTTPException as refus:
                raise HTTPException(422, f"Visite {i} : {refus.detail}.") from refus
        #  Sous contrat, le rythme est celui du contrat — la règle d'`appliquer_intervenant`.
        rythme = (None, None) if v.contrat_id else (v.frequence_type, v.frequence_valeur)
        session.add(
            Ticket(
                numero=generer_numero(session),
                jeton_courriel=nouveau_jeton(),
                titre=v.titre.strip(),
                #  La description est obligatoire pour une affaire : le titre la porte
                #  à défaut — c'est ce que faisait la migration des événements (0212).
                description=v.description or f"<p>{escape(v.titre.strip())}</p>",
                categorie=CategorieTicket.entretien,
                statut=StatutTicket.chez_prestataire,
                priorite="normale",
                suivi_kanban=True,
                auteur_id=user.id,
                perimetre_cible=perimetre_cible_json(v.perimetre_cible),
                debut=v.debut,
                prestataire_id=v.prestataire_id,
                contrat_id=v.contrat_id,
                frequence_type=rythme[0],
                frequence_valeur=rythme[1] if rythme[0] else None,
                cree_le=maintenant,
                mis_a_jour_le=maintenant,
            )
        )
    session.commit()
    return {"crees": len(body.affaires)}


__all__ = ["LOT_MAX", "creer_visites_en_lot", "router"]
