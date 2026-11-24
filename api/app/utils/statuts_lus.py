"""Les statuts au titre desquels un compte LIT — le sien, et ceux qu'il hérite (#1303).

## Pourquoi

Arbitré le 25/09/2026 : **un aidant n'est pas un bailleur ; il hérite du droit
du copropriétaire qu'il aide**, occupant ou bailleur. `public_cible_visible`
décidait sur le seul `user.statut` : une actualité adressée aux
« Copropriétaires occupants » était invisible à l'aidant d'un occupant, alors
que l'aidé la lisait.

L'héritage passe par la délégation ACTIVE (`utils/delegations_actives`), et
par elle seule : un aidant sans délégation active ne lit qu'à son propre titre.
Il ne s'étend qu'au STATUT, jamais au rôle — aider un membre du conseil ne fait
pas lire ce que lit le conseil.

## Le cache

Même montage que `mes_batiments` : la règle d'accès est appelée pour chaque
objet d'une liste, et la délégation change rarement. 30 secondes de TTL ;
`invalider_cache` pour qui modifie une délégation.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from app import contexte
from app.utils.valeurs import valeur

logger = logging.getLogger(__name__)

_TTL_SECONDES = 30.0


def _cache() -> dict[int, tuple[float, frozenset[str]]]:
    """Le cache de LA copropriété servie, indexé par `user_id` (#1744, spec §4.5)."""
    return contexte.etat("statuts_lus")


def invalider_cache(user_id: Optional[int] = None) -> None:
    if user_id is None:
        _cache().clear()
    else:
        _cache().pop(user_id, None)


def statuts_lus(user) -> frozenset[str]:
    """Son statut, plus — pour un aidant — ceux des personnes qu'il aide."""
    propre = str(valeur(getattr(user, "statut", None)) or "")
    statuts = frozenset({propre}) if propre else frozenset()
    user_id = getattr(user, "id", None)
    if propre != "aidant" or user_id is None:
        return statuts

    entree = _cache().get(user_id)
    if entree is not None and (time.monotonic() - entree[0]) < _TTL_SECONDES:
        return statuts | entree[1]
    try:
        from app.models.core import Utilisateur
        from app.utils.delegations_actives import delegations_de_l_aidant

        with contexte.nouvelle_session() as session:
            herites = frozenset(
                str(valeur(m.statut))
                for d in delegations_de_l_aidant(session, user_id)
                if (m := session.get(Utilisateur, d.mandant_id)) is not None
                and m.actif
                and m.statut is not None
            )
    except Exception as exc:  # noqa: BLE001 — base indisponible : l'aidant lit à son seul titre
        #  Pas de cache : la base reviendra. Sans héritage, l'aidant lit à son
        #  seul titre — le sens fermé, jamais l'ouvert.
        logger.error("Délégations de l'aidant %s illisibles (%s)", user_id, exc)
        return statuts
    _cache()[user_id] = (time.monotonic(), herites)
    return statuts | herites
