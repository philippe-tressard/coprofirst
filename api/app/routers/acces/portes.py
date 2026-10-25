"""Ce qu'un badge OUVRE : les choix permis, la proposition tirée des lots, le constat (#2217).

Sorti de `parc.py` le 25/10/2026 — le plafond de modularité l'imposait au premier
geste ajouté, et ces trois lectures répondent à une même question, que le parc
(les gestes d'écriture) n'a pas à porter.

🔴 La proposition **informe** le conseil ; elle ne pose rien. Ce qui écrit un accès,
ce sont les deux gestes du parc, validés par `valider_acces` et journalisés
(`acces_gestes.journaliser_acces`) — « proposer, jamais poser » (`utils/acces_portes`).
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.utils.acces_choix import codes_autorises
from app.utils.acces_constats import constater_badges
from app.utils.acces_portes import portes_proposees
from app.utils.constats import Constat
from app.utils.types_acces import TYPES_ACCES

router = APIRouter()


class ChoixAccesOut(BaseModel):
    """Ce qu'un type d'accès peut ouvrir, et comment son défaut se décide."""

    codes: list[str]
    #: 🔴 Dit à l'écran quelle aide afficher — « il est déduit du lot » ou « elle
    #: reçoit les portails ». Sans cela, le formulaire devrait écrire
    #: `type === 'vigik'`, c'est-à-dire reconnaître un type par son nom : la
    #: faute même que `TypeAcces` a supprimée côté serveur, réintroduite à
    #: l'écran.
    suit_le_lot: bool


@router.get("/admin/choix-acces", response_model=dict[str, ChoixAccesOut])
def choix_acces(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Ce que chaque type d'accès a le droit d'ouvrir — par clé de type.

    ⚠️ Des **codes**, pas des libellés : l'écran les met en forme lui-même à
    partir de l'arbre qu'il a déjà chargé, comme `BadgePerimetre` et
    `PerimetrePicker` le font partout ailleurs. Renvoyer des libellés obligerait
    le serveur à décider d'un rendu, et ferait de cette route un second endroit
    où le nom d'un périmètre s'écrit.

    ⚠️ Cette route **informe** l'écran ; elle ne le contraint pas. Ce qui
    contraint, c'est `valider_acces` sur les deux gestes d'écriture — un écran
    est une commodité, jamais un contrôle d'accès.
    """
    return {
        cle: ChoixAccesOut(
            codes=codes_autorises(session, type_acces),
            suit_le_lot=type_acces.acces_suit_le_lot,
        )
        for cle, type_acces in TYPES_ACCES.items()
    }


class PorteProposee(BaseModel):
    """Une porte que les lots justifient, et la raison qui se lit à l'écran."""

    code: str
    raison: str


@router.get("/admin/portes-proposees", response_model=list[PorteProposee])
def portes_proposees_route(
    porteur_id: Optional[int] = None,
    lot_id: Optional[int] = None,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Les portes qu'un badge Vigik DEVRAIT ouvrir, d'après son lot et ceux de son porteur.

    Une proposition, jamais une valeur posée : le conseil la reprend ou non dans
    le formulaire, et c'est l'enregistrement qui décide.
    """
    return [
        PorteProposee(code=p.code, raison=p.raison)
        for p in portes_proposees(session, porteur_id, lot_id)
    ]


@router.get("/admin/constats-badges", response_model=list[Constat])
def constats_badges(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Les badges dont l'accès diffère de ce que leurs lots justifient — jamais bloquant."""
    return constater_badges(session)
