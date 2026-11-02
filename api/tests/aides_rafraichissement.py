"""Les sessions d'un compte, et l'horloge d'un échange de jeton de rafraîchissement.

Écrites dans `test_jeton_rejoue.py` (27/09/2026), qui appelle les routes en
fonctions ; un second fichier en a eu besoin pour le même parcours par HTTP, sans
navigateur (#2457) : elles s'écrivent ici une fois.
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.auth.empreinte_jeton import empreinte
from app.models.core import RefreshToken


def sessions_ouvertes(session: Session, user_id: int) -> set[str]:
    """Les EMPREINTES des jetons de rafraîchissement encore valables du compte."""
    session.expire_all()
    return {
        t.token
        for t in session.exec(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,  # noqa: E712
            )
        ).all()
    }


def vieillir_l_echange(session: Session, jeton: str, de: timedelta) -> None:
    """Recule l'échange de `jeton` : c'est l'horloge qu'on simule, pas la règle."""
    stocke = session.exec(select(RefreshToken).where(RefreshToken.token == empreinte(jeton))).one()
    assert stocke.remplace_le is not None, "l'échange n'a pas marqué le jeton remplacé"
    stocke.remplace_le -= de
    session.add(stocke)
    session.commit()
