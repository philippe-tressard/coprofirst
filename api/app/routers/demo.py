"""L'entrée de la démo publique par personnage (spec `mode-demo.md` §5, lot D3 #1903).

`GET /demo/entrer/{personnage}` — servie sous `/api` par Caddy — ouvre la session
du personnage et renvoie à l'accueil. Ce sont les adresses des boutons de la page
d'accueil de CoproFirst.

## Les règles

1. **Hors démo, 404** : la route n'existe pas pour une installation ordinaire — elle
   ne « refuse » pas, elle ne répond rien de plus qu'une adresse inconnue.
2. **Aucun mot de passe** : le personnage est un compte partagé (M5), dont le mot
   de passe aléatoire n'est jamais affiché. La session s'ouvre par la même fonction
   que la connexion (`auth/session_ouverte`), jamais par une copie.
3. **Un compte absent rend 503**, pas 500 : pendant la remise à zéro nocturne, la
   base se recharge, et le visiteur doit lire qu'il faut réessayer.
4. **Chaque entrée se journalise** (`entree_demo`) — l'identifiant du compte et le
   code du personnage, jamais une adresse.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.adresse_compte import compte_par_adresse
from app.auth.session_ouverte import ouvrir_session
from app.database import get_session
from app.demo.personnages import PERSONNAGES
from app.utils.demo import est_demo
from app.utils.journal_securite import journaliser_securite
from app.utils.limiter import LIMITE_ENTREE_DEMO, LIMITE_LECTURE_PUBLIQUE, limiter
from app.utils.recuperer import connu_ou_404

router = APIRouter(prefix="/demo", tags=["demo"])

#: Où arrive le visiteur : l'accueil de l'application, que la session ouvre.
ACCUEIL = "/tableau-de-bord"


class PersonnageRead(BaseModel):
    """Ce que la page de connexion de la démo montre d'un personnage (#1906)."""

    code: str
    libelle: str
    description: str


@router.get("/personnages", response_model=list[PersonnageRead])
@limiter.limit(LIMITE_LECTURE_PUBLIQUE)
def personnages(request: Request):
    """Les personnages, dans leur ordre — liste VIDE hors démo : rien à proposer.

    La page de connexion les lit ici plutôt que de recopier libellés et
    descriptions : la liste vit dans `app/demo/personnages.py`, et nulle part
    ailleurs.
    """
    if not est_demo():
        return []
    return [
        PersonnageRead(code=p.code, libelle=p.libelle, description=p.description)
        for p in PERSONNAGES.values()
    ]


@router.get("/entrer/{personnage}", include_in_schema=False)
@limiter.limit(LIMITE_ENTREE_DEMO)
def entrer(request: Request, personnage: str, session: Session = Depends(get_session)):
    """Ouvre la session du personnage et renvoie à l'accueil (303)."""
    #  Hors démo, le registre est VIDE : la route ne connaît aucun personnage (règle 1).
    choisi = connu_ou_404(PERSONNAGES if est_demo() else {}, personnage, "Not Found")
    user = compte_par_adresse(session, choisi.adresse)
    if user is None or not user.actif:
        raise HTTPException(503, "La démonstration se prépare : réessayez dans quelques minutes.")
    reponse = RedirectResponse(ACCUEIL, status_code=303)
    ouvrir_session(session, user, reponse)
    journaliser_securite("entree_demo", cible_id=user.id, detail=personnage)
    return reponse
