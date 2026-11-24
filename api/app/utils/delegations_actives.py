"""Les délégations ACTIVES d'un aidant — la règle, écrite une fois (#1303).

Active = acceptée (`statut == active`), commencée, et pas terminée. Cette
condition s'écrivait deux fois — `auth/deps.get_acting_user` (agir au nom de
quelqu'un) et `utils/lecture_utilisateur` (le profil qui liste les personnes
aidées) —, et #1303 en demandait une troisième : l'aidant qui LIT ce que lit
la personne qu'il aide. Trois copies d'une condition de droit divergent sur la
borne de date au premier ajustement.

Depuis le 02/10/2026 (#1534), la délégation est en LECTURE SEULE : le premier
appelant, `get_acting_user`, a été retiré — aucune route ne l'avait jamais
pris. Restent le profil et l'héritage de lecture (`utils/statuts_lus`).

## Désigné, pas seulement actif : la question du MENU (#3001)

L'aidant désigné par une délégation EN ATTENTE la lit (`GET /delegations`) et
l'accepte (`POST …/accepter`) : l'entrée « Délégations » doit donc s'y montrer.
`est_aidant_designe` pose cette question, et elle seule : 🔴 elle n'ouvre AUCUNE
lecture au titre du mandant — l'héritage (`statuts_lus`) et `UserRead.delegations_aidant`
lisent `delegations_de_l_aidant`, les actives seules.
"""

from __future__ import annotations

from app.utils import horloge
from typing import Optional

from sqlmodel import Session, and_, or_, select

from app.models.core import Delegation, StatutDelegation


def _active_aujourd_hui():
    """La condition « active », écrite une fois : acceptée, commencée, pas terminée."""
    today = horloge.aujourd_hui()
    return and_(
        Delegation.statut == StatutDelegation.active,
        Delegation.date_debut <= today,
        or_(Delegation.date_fin.is_(None), Delegation.date_fin >= today),  # type: ignore[arg-type]
    )


def delegations_de_l_aidant(
    session: Session, aidant_id: int, *, mandant_id: Optional[int] = None
) -> list[Delegation]:
    """Les délégations actives aujourd'hui où `aidant_id` aide — d'un mandant
    précis si `mandant_id` est donné."""
    requete = select(Delegation).where(Delegation.aidant_id == aidant_id, _active_aujourd_hui())
    if mandant_id is not None:
        requete = requete.where(Delegation.mandant_id == mandant_id)
    return list(session.exec(requete).all())


def est_aidant_designe(session: Session, aidant_id: int) -> bool:
    """Une délégation active aujourd'hui, ou EN ATTENTE de son accord, désigne-t-elle
    ce compte comme aidant ? La question du menu (`utils/acces_menu`, #3001).

    En attente : la condition des deux routes que l'aidant désigné peut appeler —
    `routers/delegations._en_attente` et `appartenance.peut_accepter_la_delegation`
    (`aidant_id`). N'ouvre aucune lecture : voir l'en-tête du module.
    """
    requete = select(Delegation.id).where(
        Delegation.aidant_id == aidant_id,
        or_(Delegation.statut == StatutDelegation.en_attente, _active_aujourd_hui()),
    )
    return session.exec(requete).first() is not None
