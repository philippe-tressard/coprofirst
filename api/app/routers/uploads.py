"""
Router uploads — gestion des photos (avatar, résidence, publications).
Les fichiers sont enregistrés dans /app/uploads/{type}/{uuid}.ext
et servis en statique via /uploads/*.
"""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
import logging

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import Copropriete, Utilisateur
from app.utils.stockage import stockage
from app.utils.fichiers import (
    FAMILLES,
    enregistrer_fichier_recu,
    lire_fichier_recu,
    verifier_fichier_recu,
)
from app.utils.images import reencoder_jpeg
from app.utils.limiter import LIMITE_TELEVERSEMENT, limiter
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["uploads"])

#  🔴 LES LISTES DE TYPES ET LES PLAFONDS ONT QUITTÉ CE FICHIER (#1026,
#  19/09/2026). Ils vivent dans `utils/fichiers.FAMILLES`, avec ceux des
#  documents privés et des imports de tableurs.
#
#  Ce n'était pas une question de rangement : les trois chemins de téléversement
#  du projet appliquaient des règles DIFFÉRENTES, et celui des documents privés
#  n'avait ni liste de types ni plafond. Il n'existait aucune table où le voir.
#
#  Un routeur nomme désormais une **famille** — « image », « document » —, il ne
#  décide plus de ce qu'il accepte. `test_televersement_source_unique.py` refuse
#  qu'une liste MIME ou un plafond en mégaoctets réapparaisse ici.
# ── helpers ────────────────────────────────────────────────────────────────


def _save_image(file: UploadFile, subfolder: str, max_dim: int = 1600) -> str:
    """Valide, redimensionne si besoin et sauvegarde le fichier. Retourne l'URL relative."""
    data = lire_fichier_recu(file, "image")

    #  Les trois règles — type, plafond, cohérence du contenu — sont appliquées
    #  par la famille « image ». Elles étaient écrites ici, et deux autres
    #  chemins les écrivaient à leur façon (#1026).
    #
    #  ⚠️ Le contrôle porte sur ce qui ARRIVE, avant réencodage : c'est l'octet
    #  reçu qui peut mentir, pas celui que nous produisons.
    verifier_fichier_recu(data, file.filename, file.content_type, "image")

    #  Le réencodage vit dans `app/utils/images.py` — il est partagé avec la
    #  diffusion WhatsApp, qui doit faire tenir la même photo sous un budget
    #  d'octets. Deux routines de redimensionnement divergeraient sur
    #  l'orientation ou la qualité (`standards/02-factorisation.md` §2).
    try:
        data = reencoder_jpeg(data, max_dim=max_dim)
    except ValueError:
        raise HTTPException(400, "Impossible de lire l'image.")

    #  Le nom passe par `nom_stocke`, comme toute autre pièce jointe. Il était
    #  fabriqué ici à la main — `f"{uuid4().hex}.jpg"`, sans radical — alors que
    #  `app/utils/fichiers.py` annonce en tête « écrit une seule fois ». Il l'était
    #  deux fois, et la seconde perdait le nom d'origine : une photo arrivait dans
    #  l'e-mail sous « fb6cb1df94734926bfcd9b7f07e99ded.jpg », là où un PDF joint au
    #  même message s'affichait « Devis-toiture.pdf ». Signalé sur un e-mail réel le
    #  07/08/2026. L'image est réencodée en JPEG, d'où l'extension forcée — mais le
    #  radical du fichier d'origine, lui, n'a aucune raison d'être jeté.
    #  🔴 L'écriture passe par la source unique, seule autorisée à poser sur le
    #  disque des octets venus du réseau. `extension_forcee=".jpg"` parce que
    #  l'image vient d'être réencodée : le contrôle porte sur le type reçu,
    #  l'extension sur ce qui est écrit.
    #
    #  Le nom passe par `nom_stocke`, comme toute autre pièce jointe. Il était
    #  fabriqué à la main — `f"{uuid4().hex}.jpg"`, sans radical — alors que
    #  `app/utils/fichiers.py` annonce en tête « écrit une seule fois ». Il l'était
    #  deux fois, et la seconde perdait le nom d'origine : une photo arrivait dans
    #  l'e-mail sous « fb6cb1df94734926bfcd9b7f07e99ded.jpg », là où un PDF joint au
    #  même message s'affichait « Devis-toiture.pdf ». Signalé sur un e-mail réel le
    #  07/08/2026.
    filename = enregistrer_fichier_recu(
        data,
        file.filename,
        file.content_type,
        "image",
        subfolder,
        extension_forcee=".jpg",
    )
    return stockage().url(f"{subfolder}/{filename}")


# ── endpoints ──────────────────────────────────────────────────────────────


@router.post("/avatar", summary="Mettre à jour la photo de profil")
@limiter.limit(LIMITE_TELEVERSEMENT)
def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Upload et sauvegarde la photo de profil de l'utilisateur connecté."""
    url = _save_image(file, "avatars", max_dim=400)
    user.photo_url = url
    session.add(user)
    session.commit()
    return {"url": url}


@router.post("/residence", summary="Ajouter une photo de la résidence (CS/Admin)")
@limiter.limit(LIMITE_TELEVERSEMENT)
def upload_residence(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Upload une photo de la résidence. Retourne l'URL publique."""
    url = _save_image(file, "residence", max_dim=1600)
    # Enregistre la dernière photo dans la table copropriete
    copro = session.exec(select(Copropriete)).first()
    if copro:
        copro.photo_url = url  # type: ignore[attr-defined]
        session.add(copro)
        session.commit()
    return {"url": url}


# Les endpoints `/ticket/{id}`, `/evenement/{id}` et `/publication/{id}` ont été
# supprimés — les deux premiers le 03/08/2026 avec les pièces jointes
# documentaires, le dernier le 10/08/2026 : les formulaires de création
# téléversent désormais photos ET documents par `/fichier`, avant que l'élément
# existe, et passent les URLs dans le payload de création. C'est ce qui permet à
# l'e-mail syndic/CS de partir avec ses pièces jointes — l'ancien flux
# « créer puis téléverser » construisait l'e-mail avant les photos.


@router.post("/fichier", summary="Upload une pièce jointe (photo ou document)")
@limiter.limit(LIMITE_TELEVERSEMENT)
def upload_fichier(
    request: Request,
    file: UploadFile = File(...),
    user: Utilisateur = Depends(get_current_user),
):
    """
    Upload une photo ou un document (PDF, Word, Excel) destiné à être joint
    à un commentaire d'actualité ou de ticket.
    - Images : redimensionnées à 1200px max, converties en JPEG
    - Documents : stockés tels quels, max 15 Mo
    Retourne { url, nom, type }
    """
    #  La FAMILLE décide, et elle est nommée ici plutôt que déduite d'une liste
    #  locale : `FAMILLES` (`utils/fichiers`) porte les types acceptés, le
    #  plafond et les extensions de chacune (#1026). Les deux listes qui
    #  vivaient dans ce fichier décidaient seules de ce que le routeur
    #  acceptait — et les documents privés, eux, n'avaient aucune liste.
    is_image = file.content_type in FAMILLES["image"].types
    is_doc = file.content_type in FAMILLES["document"].types

    if not is_image and not is_doc:
        attendus = ", ".join(
            sorted(set(FAMILLES["image"].extensions) | set(FAMILLES["document"].extensions))
        )
        raise HTTPException(
            400, f"Format non supporté : {file.content_type}. Attendu : {attendus}."
        )

    original_name = file.filename or "fichier"

    if is_image:
        url = _save_image(file, "fichiers", max_dim=1200)
        ftype = "image"
    else:
        data = lire_fichier_recu(file, "document")
        #  🔴 Les trois règles — type, plafond, cohérence du contenu — et
        #  l'écriture, en un seul appel. Elles étaient recopiées ici depuis
        #  `utils/fichiers`, au caractère près pour le message de journal, et
        #  c'est cette copie qui rendait possible que les documents PRIVÉS,
        #  eux, n'aient ni type ni plafond vérifiés (#1026).
        #
        #  L'extension écrite vient du TYPE, jamais du nom fourni :
        #  `/app/uploads` est servi en statique et Caddy pose le `Content-Type`
        #  d'après l'extension du fichier sur disque. Un `.html` téléversé sous
        #  un type MIME autorisé s'exécuterait sur notre origine. Et le contenu
        #  doit correspondre à ce type (#773) : un exécutable annoncé
        #  `application/pdf` était stocké en `.pdf`, puis servi aux résidents.
        filename = enregistrer_fichier_recu(
            data,
            original_name,
            file.content_type,
            "document",
            "fichiers",
            user=user,
        )
        url = stockage().url(f"fichiers/{filename}")
        ftype = "document"

    return {"url": url, "nom": original_name, "type": ftype}
