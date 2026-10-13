"""Ouvrir une session : les deux jetons, leur trace en base et les deux cookies.

## Pourquoi une seule fonction (#1903)

La pose des jetons et des cookies était écrite dans `login`, puis recopiée en
partie dans `refresh` (`routers/auth.py`). L'entrée de la démo publique (spec
`mode-demo.md` §5.2) en aurait été la troisième copie — c'est-à-dire la troisième
occasion d'oublier un drapeau de cookie, ou de stocker le jeton de
rafraîchissement en clair (#1389).

Ce qui reste chez les appelants est ce qui les distingue : `login` éprouve un mot
de passe, `refresh` fait tourner le jeton qu'on lui présente, l'entrée de démo
choisit un personnage.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Response
from sqlmodel import Session

from app.auth.empreinte_jeton import empreinte
from app.auth.jwt import creer_jeton_acces, create_refresh_token
from app.config import get_settings
from app.models.core import RefreshToken, Utilisateur
from app.utils import horloge
from app.utils.purge_comptes.regles import marquer_activite

settings = get_settings()

#: Les drapeaux des deux cookies de session — la seule écriture.
COOKIE_OPTS = dict(httponly=True, secure=settings.cookie_secure, samesite="strict", path="/")


def ouvrir_session(
    session: Session,
    user: Utilisateur,
    response: Response,
    maintenant: Optional[datetime] = None,
) -> None:
    """Émet les jetons de `user`, garde l'EMPREINTE du rafraîchissement, pose les cookies.

    Marque aussi l'activité du compte : une session ouverte ou renouvelée dit que
    le résident est là, et remet à zéro un avertissement de purge (#1580).
    Committe la session.
    """
    maintenant = maintenant or horloge.maintenant()
    marquer_activite(user, maintenant)
    session.add(user)

    refresh = create_refresh_token({"sub": str(user.id)})
    session.add(
        RefreshToken(
            user_id=user.id,
            token=empreinte(refresh),
            expires_at=maintenant + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    session.commit()

    response.set_cookie(
        "access_token",
        creer_jeton_acces(user.id, user.hashed_password),
        max_age=settings.access_token_expire_minutes * 60,
        **COOKIE_OPTS,
    )
    response.set_cookie(
        "refresh_token",
        refresh,
        max_age=settings.refresh_token_expire_days * 86400,
        **COOKIE_OPTS,
    )
