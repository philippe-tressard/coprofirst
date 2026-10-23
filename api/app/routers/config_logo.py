"""Le logo de la résidence : le téléverser, le retirer, le servir (#1728).

La règle — formats, repli neutre, tailles — vit dans `utils/logo` ; ce routeur
n'en est que les trois portes.

🔴 `GET /config/logo.png` est PUBLIC, et c'est une décision (déclarée dans
`tests/test_autorisation.py`) : le logo s'affiche sur l'écran de connexion, dans
l'onglet du navigateur, sur l'écran d'accueil du téléphone et dans les
courriels — partout où personne n'est encore connecté. Il ne porte aucune
donnée de résident, et ses tailles sont bornées : la route ne redimensionne
pas n'importe quoi à la demande de n'importe qui.
"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlmodel import Session

from app.auth.deps import require_admin
from app.database import get_session
from app.models.core import ConfigSite, Utilisateur
from app.utils.config_site import ecrire_cle
from app.utils.fichiers import enregistrer_fichier_recu, lire_fichier_recu
from app.utils.images import carre_png
from app.utils.stockage import stockage
from app.utils.logo import (
    CLE_LOGO,
    DOSSIER,
    TAILLE_MAX,
    TAILLE_MIN,
    fichier_logo,
    logo_png,
)

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/logo.png", summary="Le logo de la résidence (public)")
def servir_logo(
    taille: int = Query(192, ge=TAILLE_MIN, le=TAILLE_MAX, description="Côté en pixels"),
    session: Session = Depends(get_session),
):
    """Le logo en PNG carré — celui de la résidence, sinon le logo neutre."""
    return Response(content=logo_png(session, taille), media_type="image/png")


@router.post("/logo", summary="Téléverser le logo de la résidence (admin)")
def televerser_logo(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_admin),
):
    """Remplace le logo. PNG ou JPEG (famille « logo »), lisible par Pillow."""
    octets = lire_fichier_recu(file, "logo")
    nom = enregistrer_fichier_recu(
        octets, file.filename, file.content_type, "logo", DOSSIER, user=user, session=session
    )
    try:
        #  La signature dit « PNG » : encore faut-il que l'image se lise. Un
        #  fichier tronqué passerait le contrôle des premiers octets.
        carre_png(octets, 32)
    except ValueError:
        stockage().supprimer(f"{DOSSIER}/{nom}")
        raise HTTPException(400, "Impossible de lire l'image.")
    ancien = fichier_logo(session)
    ecrire_cle(session, CLE_LOGO, nom)
    session.commit()
    if ancien is not None:
        ancien.unlink(missing_ok=True)
    return {CLE_LOGO: nom}


@router.delete("/logo", summary="Retirer le logo de la résidence (admin)")
def retirer_logo(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Revient au logo neutre : la clé disparaît, puis le fichier."""
    ancien = fichier_logo(session)
    ligne = session.get(ConfigSite, CLE_LOGO)
    if ligne is not None:
        session.delete(ligne)
        session.commit()
    if ancien is not None:
        ancien.unlink(missing_ok=True)
    return {CLE_LOGO: None}
