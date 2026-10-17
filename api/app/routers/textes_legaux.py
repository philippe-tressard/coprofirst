"""Les textes légaux de la copropriété servie : leur rendu public, leur source, leur relecture (#2065).

À part de `config.py`, à 500 lignes ; même préfixe `/config`, comme `config_services`.

| Route | Qui | Ce qu'elle rend |
|---|---|---|
| `GET /config/legal` | tout visiteur | les deux textes, **champs remplis** de l'identité de la copropriété |
| `GET /config/textes-legaux` | l'administrateur | les textes **source**, les champs et leur valeur, le constat |
| `POST /config/textes-legaux/relecture` | l'administrateur | le geste « J'ai relu ces textes » |

🔴 L'écran d'édition lit la SOURCE, jamais le rendu : un texte rendu, enregistré,
figerait les noms d'aujourd'hui à la place de ses champs.
"""

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.auth.deps import require_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.utils.config_site import config_site
from app.utils.textes_legaux import relecture
from app.utils.textes_legaux.champs import CHAMPS, rendre, valeur
from app.utils.textes_legaux.identite import CLE_CONTACT, identite_legale

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/legal", response_model=Dict[str, str])
def textes_publics(session: Session = Depends(get_session)):
    """Les deux pages légales, telles que le public les lit. Un texte absent de la base
    est le gabarit du produit : ses champs se remplissent tout autant."""
    identite = identite_legale(session)
    return {
        cle: rendre(texte, identite) for cle, texte in relecture.textes_sources(session).items()
    }


@router.get("/textes-legaux")
def textes_sources(
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Ce que l'onglet « Pages légales » édite et ce qu'il signale."""
    identite = identite_legale(session)
    return {
        "textes": relecture.textes_sources(session),
        "champs": [
            {"nom": c.nom, "libelle": c.libelle, "ou": c.ou, "valeur": valeur(identite, c.nom)}
            for c in CHAMPS
        ],
        "contact": config_site(session, CLE_CONTACT).get(CLE_CONTACT) or "",
        "etat": relecture.en_dict(relecture.etat(session)),
    }


@router.post("/textes-legaux/relecture")
def declarer_relus(
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """L'administrateur déclare avoir relu les deux textes tels qu'ils sont enregistrés."""
    try:
        return relecture.en_dict(relecture.declarer_relus(session, user))
    except relecture.TexteIncomplet as e:
        raise HTTPException(409, str(e)) from e
