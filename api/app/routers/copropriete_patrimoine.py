"""Le PATRIMOINE physique de la copropriété — ses bâtiments et ses lots.

Extrait de `routers/copropriete.py` le 22/09/2026, au fil de l'eau : le fichier
faisait 513 lignes et le garde-fou de modularité (rang 1) a refusé qu'il
grossisse en recevant le nom du propriétaire dans la liste des lots (#1154).

🔴 Ce bloc, et pas un autre : les deux routes qui restent là-bas décrivent la
FICHE de la copropriété — son assurance, son syndic, les contrats qui les
portent — et partagent pour cela six fonctions de lecture de contrat. Ces
deux-ci ne partagent rien avec elles : elles listent des objets physiques.

⚠️ Le préfixe reste `/copropriete` : les URL publiques ne bougent pas. FastAPI
additionne les routeurs, et `main.py` inclut les deux — c'est la même forme que
`auth_profil` ou `calendrier_historique`, sortis pour la même raison.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Batiment, Utilisateur

from .copropriete import BatimentRead

router = APIRouter(prefix="/copropriete", tags=["copropriété"])


@router.get("/batiments", response_model=list[BatimentRead])
def get_batiments(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    return session.exec(select(Batiment)).all()


#  🔴 `GET /copropriete/lots` a été RETIRÉE le 23/09/2026 (#1194). Son seul
#  appelant était l'écran d'import des badges, qui choisit désormais le lot
#  d'une ligne par `GET /acces/admin/imports-lots` — réservée au conseil
#  syndical, et qui nomme le copropriétaire tel que le FICHIER des lots l'écrit.
#  Celle-ci était ouverte à tout résident connecté, et donnait le nom du
#  propriétaire de chaque lot de la copropriété.
