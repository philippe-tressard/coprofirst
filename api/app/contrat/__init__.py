"""Le CONTRAT de l'API : ce qu'un client hors du navigateur tient pour acquis (#2456).

L'application iOS (`philippe-tressard/coprofirst-ios`, #2460) génère son client
Swift depuis le schéma OpenAPI — jamais une copie des routes à la main. Le schéma
part donc avec chaque version taguée (`scripts/ci/lib-contrat-version.sh`, joint à
la release), et l'installation dit quel contrat elle sert : `version_contrat` dans
`GET /config` (`utils/config_publique`), pour que l'app adapte ses gestes à une
installation plus ancienne (vague Fixe, `registre/versions`).

⚠️ `/api/openapi.json` reste FERMÉ en production (`ENABLE_API_DOCS=false`,
`main.py`, décision du 08/08/2026) : le schéma se publie comme fichier de la
release, jamais sur le site.

## La version du contrat — une seule source, calculée

Elle ne s'écrit pas : elle se lit dans `reference.json`, à côté de ce module, que
SEUL `python scripts/ci/exporter_openapi.py --ecrire-reference` écrit. Le
générateur compare l'inventaire du code (`inventaire.py` : opérations, champs de
réponse, entrées requises) à la référence, et calcule :

| Écart avec la référence | Version |
|---|---|
| aucun | inchangée |
| un ajout, une dépréciation, une entrée relâchée, un champ resserré | mineure + 1 |
| un retrait ANNONCÉ (`retraits.RETRAITS`) | majeure + 1 |
| un retrait non annoncé, une entrée requise neuve | refusé |

🔒 `test_contrat_api.py` échoue si la référence ne décrit plus le code, avec la
commande qui la régénère. Deux lots qui la touchent en parallèle se rencontrent
sur sa ligne `empreinte` : prendre la version de `dev`, puis régénérer.

Elle reste distincte de la version de l'application (`front/package.json`) : le
contrat ne bouge que quand ce qu'un client lit bouge. `GET /config` et `/health`
sont publics, et elle n'y apprend rien de neuf — le code et les releases sont
publics, et la version de l'application se lit déjà dans le client servi.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.routing import APIRoute

#: La référence du contrat — générée, jamais éditée à la main.
FICHIER_REFERENCE = Path(__file__).with_name("reference.json")

#: La clé de `GET /config` qui la publie (`utils/config_publique`) ; `PUT /config`
#: la refuse (`utils/reglages`).
CLE_PUBLIQUE = "version_contrat"

#: Le chemin sous lequel le proxy sert l'API (`Caddyfile`, `handle /api/*` puis
#: `uri strip_prefix /api`) : le schéma publié le déclare dans `servers`.
PREFIXE_SERVI = "/api"


#: La réponse d'une route qui rend un FICHIER (`FileResponse`) : sans elle, le
#: contrat la déclarait en JSON et le client généré tentait de la décoder (#2505).
#: `@router.get(…, response_class=FileResponse, responses=REPONSE_FICHIER)`.
REPONSE_FICHIER: dict = {
    200: {
        "description": "Le fichier, avec son type",
        "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
    }
}


def lire_reference() -> dict:
    """La référence du contrat : `version`, `empreinte`, `operations`."""
    return json.loads(FICHIER_REFERENCE.read_text(encoding="utf-8"))


VERSION_CONTRAT: str = lire_reference()["version"]


def identifiant_operation(route: APIRoute) -> str:
    """L'`operationId` d'une route : sa méthode et son chemin, rien d'autre.

    Celui de FastAPI dérive du NOM de la fonction Python : la renommer renommait la
    méthode du client Swift, sans que rien ne le signale ici. Dérivé du chemin, il
    ne change qu'avec la route elle-même — ce que l'inventaire voit déjà.
    `GET /tickets/{ticket_id}` → `get_tickets_ticket_id`.
    """
    methode = sorted(route.methods)[0].lower()
    return re.sub(r"_+", "_", re.sub(r"\W", "_", f"{methode}{route.path_format}")).strip("_")


def contrat_publie(schema: dict) -> dict:
    """Le schéma tel qu'il part dans la release : celui de l'application, servi sous `/api`."""
    return {**schema, "servers": [{"url": PREFIXE_SERVI, "description": "l'installation"}]}
