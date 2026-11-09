"""Le logo de la résidence : le téléverser, le retirer, le servir (#1728).

La règle — formats, repli neutre, tailles — vit dans `utils/logo` ; ce routeur
n'en est que les trois portes — chacune pour le logo, ou pour sa variante du thème
sombre (`variante=sombre`, 09/11/2026) : la même règle, le même contrôle.

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
    CLES,
    DOSSIER,
    TAILLE_MAX,
    TAILLE_MIN,
    Variante,
    fichier_logo,
    logo_png,
)

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/logo.png", summary="Le logo de la résidence (public)")
def servir_logo(
    taille: int = Query(192, ge=TAILLE_MIN, le=TAILLE_MAX, description="Côté en pixels"),
    variante: Variante = Query("clair", description="Le logo, ou son dessin du thème sombre"),
    session: Session = Depends(get_session),
):
    """Le logo en PNG carré — celui de la résidence, sinon le logo neutre."""
    return Response(content=logo_png(session, taille, variante), media_type="image/png")


@router.post("/logo", summary="Téléverser le logo de la résidence (admin)")
def televerser_logo(
    file: UploadFile = File(...),
    variante: Variante = Query("clair"),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_admin),
):
    """Remplace le logo. PNG ou JPEG (famille « logo »), lisible par Pillow."""
    if variante == "sombre" and fichier_logo(session) is None:
        #  La variante ACCOMPAGNE le logo : seule, aucun écran ne la montrerait.
        raise HTTPException(409, "Téléversez d'abord le logo de la résidence.")
    cle = CLES[variante]
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
    ancien = fichier_logo(session, variante)
    ecrire_cle(session, cle, nom)
    session.commit()
    if ancien is not None:
        ancien.unlink(missing_ok=True)
    return {cle: nom}


@router.delete("/logo", summary="Retirer le logo de la résidence (admin)")
def retirer_logo(
    variante: Variante = Query("clair"),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Revient au logo neutre : la clé disparaît, puis le fichier.

    Retirer le logo retire AUSSI sa variante sombre : elle ne vit pas sans lui.
    """
    cles = [CLES[variante]] if variante == "sombre" else list(CLES.values())
    anciens = [fichier_logo(session, v) for v, c in CLES.items() if c in cles]
    lignes = [ligne for c in cles if (ligne := session.get(ConfigSite, c)) is not None]
    for ligne in lignes:
        session.delete(ligne)
    if lignes:
        session.commit()
    for ancien in anciens:
        if ancien is not None:
            ancien.unlink(missing_ok=True)
    return {c: None for c in cles}
