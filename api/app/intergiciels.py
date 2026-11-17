"""Les intergiciels de l'application, et les portes qui se posent sur toute écriture.

Extraits de `main.py` (R6 #1882) : le fichier était à 500 lignes, et le lot devait
y brancher une garde de plus. L'ordre est celui d'avant, la garde de suspension en
plus.

Starlette exécute en PREMIER le dernier intergiciel ajouté :

1. 🏢 `contexte.ResolutionCopropriete` — LE PLUS À L'EXTÉRIEUR : chaque requête
   s'exécute dans le contexte de SA copropriété — base, fichiers, secret, caches
   (#1746, spec §4.1). Résolue à l'entrée, une fois, par l'hôte : un hôte inconnu
   reçoit 421 avant toute autre couche, débit et CORS compris (#1751).
2. 🎭 `demo.GardeDemo` — le mode démo (spec `mode-demo.md` §4.3) : les gestes
   fermés reçoivent 403 avant toute route. Hors démo, la garde laisse tout passer.
3. ⏸️ `suspension.GardeSuspension` — une installation suspendue par la référence
   est en lecture seule (D20, R6 #1882). Hors suspension, la garde laisse tout passer.
4. CORS.

Et sur l'ÉCRITURE en base, hors de toute requête aussi : le plafond de comptes
actifs du mode limité (`inscription/plafond`, D18).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import contexte
from app.inscription import plafond, suspension
from app.utils import demo


def installer(app: FastAPI) -> None:
    """Branche les intergiciels sur `app`, dans l'ordre ci-dessus, et pose le plafond."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "https://localhost"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(suspension.GardeSuspension)
    app.add_middleware(demo.GardeDemo)
    app.add_middleware(contexte.ResolutionCopropriete)
    plafond.installer()
