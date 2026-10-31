"""Les clés CALCULÉES que `GET /config` publie — jamais lues en base, jamais saisies.

Chacune dit à l'écran un fait que le serveur établit : le décor des jours de fête
s'affiche-t-il (#2312), quelle est l'adresse du site (#2058), sert-on la démo
(#1901), l'opérateur est-il désigné par l'exploitant (`auth/operateur`,
31/10/2026). Sorties de `routers/config.py` pour qu'il reste sous 500 lignes : une
clé calculée neuve s'ajoute ici, et `PUT /config` la refuse (`utils/reglages`).
"""

from __future__ import annotations

from app.auth import operateur
from app.utils import demo
from app.utils.liens import adresse_du_site
from app.utils.services import CLE_PUBLIQUE_DECOR_FETES, SERVICE_DECOR_FETES, service_actif


def _drapeau(vrai: bool) -> str:
    return "1" if vrai else "0"


def cles_calculees(reglages: dict[str, str]) -> dict[str, str]:
    """Les clés calculées, d'après les réglages lus en base (`ConfigSite`)."""
    return {
        #  La clé d'activation du décor ne sort pas : sa lecture unique, oui.
        CLE_PUBLIQUE_DECOR_FETES: _drapeau(service_actif(reglages, SERVICE_DECOR_FETES)),
        "site_url": adresse_du_site(),
        demo.CLE_PUBLIQUE: _drapeau(demo.est_demo()),
        operateur.CLE_PUBLIQUE: _drapeau(operateur.designe_par_l_exploitant()),
    }
