"""Les deux gestionnaires d'erreurs de l'application entière.

Extraits de `main.py` le 13/10/2026 (#1901) : le fichier atteignait le plafond de
500 lignes (`scripts/poste/scripts-ci-modularite.sh`), et le lot du mode démo devait
y brancher une garde. Le comportement est inchangé.
"""

from __future__ import annotations

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app import contexte

_logger = logging.getLogger("hostachy.api")


async def erreur_de_base(request: Request, exc: OperationalError):
    """Serveur de base injoignable, connexion coupée → 503 avec log structuré.
    Le pool est purgé ici pour que la prochaine requête reparte sur une connexion saine.
    """

    contexte.moteur().dispose()
    _logger.error(
        "DB OperationalError sur %s %s — pool purgé : %s",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Base de données temporairement indisponible. Veuillez réessayer."},
    )


async def erreur_non_geree(request: Request, exc: Exception):
    """Filet de sécurité : toute exception non gérée → 500 loggué, jamais de crash silencieux."""
    _logger.error(
        "Exception non gérée sur %s %s :\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Erreur interne du serveur."},
    )


def installer(app: FastAPI) -> None:
    """Branche les deux gestionnaires sur `app`."""
    app.add_exception_handler(OperationalError, erreur_de_base)
    app.add_exception_handler(Exception, erreur_non_geree)
