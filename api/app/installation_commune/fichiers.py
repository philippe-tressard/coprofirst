"""Les fichiers `/uploads/*` d'une installation COMMUNE — servis par l'API (#2053).

Sur une installation propre à une copropriété (5Hostachy), Caddy sert `/uploads/*`
depuis le volume, après avoir demandé à l'API si la session est valide
(`forward_auth` → `/auth/verifier-acces`). Il ne sert qu'UNE racine : à plusieurs
copropriétés, il servirait les fichiers de toutes à chacune.

**Arbitrage de l'auteur, 17/10/2026 (option B)** : sur une installation commune,
l'API sert ces fichiers elle-même, et Caddy ne fait que relayer
(`deploiement/standard/commune/fichiers.caddy`). La racine est celle de la
copropriété que l'HÔTE a résolue à l'entrée (`contexte.ResolutionCopropriete`) —
la seule résolution qui existe. L'option A, Caddy servant une racine que l'API lui
rendrait en en-tête, a été écartée : l'étanchéité aurait reposé sur un contrat
d'en-tête entre deux processus, et sur une seconde description de « quelle
copropriété ».

Ce que la route garantit, à l'image du `Caddyfile` :

- une SESSION valide de la copropriété servie (`get_current_user`) — le jeton d'une
  autre est refusé, son secret diffère (§5.3) ;
- la clé ne sort jamais de la racine de la copropriété (`stockage.cle_valide`, puis
  `chemin`, borné même à travers un lien) ;
- les dossiers qui ne se servent JAMAIS en direct (`stockage.JAMAIS_SERVIS` : la
  bibliothèque privée, les affiches) rendent 404, comme chez Caddy ;
- le droit de lire l'objet qui CITE le fichier (`exiger_fichier_lisible`, #2154) —
  la règle que Caddy demande à `/auth/verifier-acces`, appelée ici à l'identique ;
- `Cache-Control: private, no-store` : un cache partagé ne garde pas un fichier
  dont l'accès dépend d'un cookie (incident du 03/08/2026, `Caddyfile`).

Sur une installation propre, la route répond 404 : Caddy y garde le service, et
`/api/uploads/…` ne devient pas une seconde porte.

🔒 `tests/test_installation_commune_fichiers.py`.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlmodel import Session

from app import contexte
from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Utilisateur
from app.utils.limiter import LIMITE_CONTROLE_FICHIER, limiter
from app.utils.recuperer import fichier_ou_404, present_ou_404
from app.utils.stockage import JAMAIS_SERVIS, CleInvalide, cle_valide, stockage
from app.utils.visibility.fichiers import exiger_fichier_lisible

router = APIRouter(tags=["installation-commune"])

#: Ce que chaque réponse porte — les mêmes en-têtes que le bloc `/uploads/*` du Caddyfile.
ENTETES = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}


@router.get("/uploads/{cle:path}", include_in_schema=False)
@limiter.limit(LIMITE_CONTROLE_FICHIER)
def servir_fichier(
    request: Request,
    cle: str,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
) -> FileResponse:
    """Le fichier `cle` de la copropriété servie, à une session de CETTE copropriété."""
    chemin = present_ou_404(_chemin_servi(cle), "Fichier introuvable sur le serveur")
    exiger_fichier_lisible(session, user, cle_valide(cle))
    return FileResponse(fichier_ou_404(chemin), headers=ENTETES)


def _chemin_servi(cle: str) -> Path | None:
    """Le chemin que la clé désigne sous la racine de la copropriété servie — ou None :
    installation propre, clé hors de la racine, dossier jamais servi."""
    if not contexte.est_commune():
        return None
    try:
        cle = cle_valide(cle)
        chemin = stockage().chemin(cle)
    except CleInvalide:
        return None
    return None if cle.split("/", 1)[0] in JAMAIS_SERVIS else chemin
