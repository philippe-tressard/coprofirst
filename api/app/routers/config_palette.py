"""La palette de la copropriété : la liste offerte, et le choix (#2379).

La règle — les palettes, leurs couleurs, la palette par défaut — vit dans
`utils/palettes` ; ce routeur n'en est que les deux portes.

Une route à part et non `PUT /config` : la valeur se vérifie contre le registre.
Une palette inconnue écrite en base ne casserait rien (`code_palette` retombe sur
la charte), mais l'écran afficherait un choix que le site ne suit pas.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import require_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.utils.config_site import ecrire_cle
from app.utils.palettes import CLE_PALETTE, PALETTES

router = APIRouter(prefix="/config", tags=["config"])


class PaletteRead(BaseModel):
    code: str
    nom: str
    primaire: str
    accent: str
    fond: str


class ChoixPalette(BaseModel):
    palette: str


@router.get("/palettes", response_model=list[PaletteRead], summary="Les palettes offertes (admin)")
def lister_palettes(_: Utilisateur = Depends(require_admin)):
    """Les palettes du registre, dans l'ordre de l'écran, avec de quoi les montrer."""
    return [
        PaletteRead(code=code, nom=p.nom, primaire=p.primaire, accent=p.accent, fond=p.fond)
        for code, p in PALETTES.items()
    ]


@router.put("/palette", summary="Choisir la palette de la copropriété (admin)")
def choisir_palette(
    body: ChoixPalette,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Enregistre la palette ; une palette absente du registre est refusée."""
    if body.palette not in PALETTES:
        raise HTTPException(422, "Palette inconnue.")
    ecrire_cle(session, CLE_PALETTE, body.palette)
    session.commit()
    return {CLE_PALETTE: body.palette}
