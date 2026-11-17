"""Les écrans de hall — appairer, lister, retirer, et ce qu'un écran lit (#2770).

Trois publics, trois portes :

- **l'écran, avant d'être appairé** — `POST /ecrans/appairage` puis
  `POST /ecrans/appairage/jeton` : publics, plafonnés, ils ne révèlent rien de
  l'installation (`auth/appairage_ecran`) ;
- **le conseil syndical** — `GET`, `POST`, `DELETE /ecrans` (`require_cs_or_admin`) :
  la liste avec la dernière lecture, la confirmation d'un code court, le retrait ;
- **l'écran appairé** — `GET /ecrans/moi/affiches` et leurs images (`ecran_appaire`) :
  ce que sa portée ouvre (`auth/jetons_appareil.PORTEES["ecran"]`), et rien d'autre.
  Ce qui sort se décide dans `utils/ecran_affiches`, la porte de sortie vers le hall.

Le client TypeScript (`#lib/api/ecrans.ts`) ne connaît que les routes du conseil ;
l'app Apple TV génère le sien du contrat publié (#2456).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, delete, select

from app.auth import appairage_ecran
from app.auth.deps import ecran_appaire, require_cs_or_admin
from app.contrat import REPONSE_FICHIER
from app.database import get_session
from app.models.core import Utilisateur
from app.models.ecrans import Ecran
from app.utils import horloge
from app.utils.ecran_affiches import (
    AfficheEcran,
    affiches_de_l_ecran,
    ce_que_montre_l_ecran,
    image_de_l_ecran,
)
from app.utils.journal_securite import journaliser_securite
from app.utils.lecture import lire_objet
from app.utils.limiter import (
    LIMITE_APPAIRAGE,
    LIMITE_CONTROLE_FICHIER,
    LIMITE_INTERROGATION_APPAIRAGE,
    LIMITE_LECTURE_AUTHENTIFIEE,
    LIMITE_SECRET_EPROUVE,
    LIMITE_SESSION,
    limiter,
)
from app.utils.perimetres import arbre, perimetre_badge
from app.utils.recuperer import ou_404, present_ou_404

router = APIRouter(prefix="/ecrans", tags=["ecrans"])


class DemandeAppairage(BaseModel):
    """Ce que l'écran affiche et garde — rendu une fois, rien sur l'installation."""

    code_appareil: str
    code_court: str
    expire_dans: int
    intervalle: int


class Interrogation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_appareil: str = Field(max_length=128)


class JetonEcran(BaseModel):
    """Le jeton de l'écran, rendu UNE fois ; à présenter en `Authorization: Bearer`."""

    jeton: str
    expire_le: datetime


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_court: str = Field(max_length=32)
    nom: str = Field(min_length=1, max_length=80)
    #  UN code de l'arbre des périmètres.
    perimetre: str = Field(min_length=1, max_length=120)


class AppairageConfirme(BaseModel):
    """Ce que deviendra l'écran — `perimetre_libelle` vide pour le périmètre par défaut."""

    nom: str
    perimetre: str
    perimetre_libelle: str


class EcranLu(BaseModel):
    """Un écran, tel que le conseil le voit — jamais son jeton."""

    id: int
    nom: str
    perimetre: str
    #  Le badge 🔹 (`perimetres.perimetre_badge`) — vide pour le périmètre par défaut.
    perimetre_libelle: str
    cree_le: datetime
    vu_le: Optional[datetime]
    expire_le: datetime
    #  Échu : l'écran ne lit plus rien jusqu'à un nouvel appairage.
    echu: bool


def _lu(ecran: Ecran, maintenant: datetime) -> EcranLu:
    return lire_objet(
        EcranLu,
        ecran,
        perimetre_libelle=perimetre_badge([ecran.perimetre]),
        echu=ecran.expire_le <= maintenant,
    )


# ── L'écran, avant d'être appairé (public) ──────────────────────────────────


@router.post("/appairage", response_model=DemandeAppairage)
@limiter.limit(LIMITE_APPAIRAGE)
def demander_appairage(request: Request, session: Session = Depends(get_session)):
    """L'écran demande un code d'appareil et un code court à afficher (RFC 8628)."""
    demande = appairage_ecran.nouvelle_demande(session, horloge.maintenant())
    if demande is None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop d'appairages en attente — réessayez dans quelques minutes.",
        )
    return DemandeAppairage(**demande.__dict__)


@router.post("/appairage/jeton", response_model=JetonEcran)
@limiter.limit(LIMITE_INTERROGATION_APPAIRAGE)
def interroger_appairage(
    request: Request, body: Interrogation, session: Session = Depends(get_session)
):
    """L'écran échange son code d'appareil contre son jeton, une fois le code confirmé.

    Sinon 400, et `detail` dit quoi faire : `en_attente` (réinterroger après
    l'intervalle), `ralentir` (l'intervalle a grandi de 5 s), `inconnu` (recommencer).
    """
    ecran, brut, raison = appairage_ecran.echanger(
        session, body.code_appareil, horloge.maintenant()
    )
    if ecran is None or brut is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=raison)
    journaliser_securite("ecran_relie", cible_id=ecran.id, detail=f"écran {ecran.id}")
    return JetonEcran(jeton=brut, expire_le=ecran.expire_le)


# ── Le conseil syndical ─────────────────────────────────────────────────────


@router.get("", response_model=list[EcranLu])
@limiter.limit(LIMITE_LECTURE_AUTHENTIFIEE)
def lister_ecrans(
    request: Request,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Les écrans appairés, avec leur dernière lecture."""
    maintenant = horloge.maintenant()
    ecrans = session.exec(select(Ecran).order_by(Ecran.nom, Ecran.id)).all()
    return [_lu(e, maintenant) for e in ecrans]


@router.post("", response_model=AppairageConfirme, status_code=201)
@limiter.limit(LIMITE_SECRET_EPROUVE)
def confirmer_appairage(
    request: Request,
    body: Confirmation,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Le conseil saisit le code court affiché par l'écran, et choisit son nom et son périmètre."""
    noeud = arbre().get(body.perimetre.strip().lower())
    if noeud is None:
        raise HTTPException(status_code=422, detail="Périmètre inconnu")
    demande = present_ou_404(
        appairage_ecran.confirmer(
            session, body.code_court, body.nom.strip(), noeud.code, horloge.maintenant()
        ),
        "Code inconnu ou expiré — affichez un nouveau code sur l'écran.",
    )
    journaliser_securite(
        "ecran_appaire", acteur_id=user.id, cible_id=demande.id, detail=f"demande {demande.id}"
    )
    return AppairageConfirme(
        nom=demande.nom or "",
        perimetre=noeud.code,
        perimetre_libelle=perimetre_badge([noeud.code]),
    )


@router.delete("/{ecran_id}", status_code=204, response_class=Response)
@limiter.limit(LIMITE_SESSION)
def retirer_ecran(
    request: Request,
    ecran_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Retire un écran : son jeton cesse aussitôt de servir."""
    ou_404(session, Ecran, ecran_id, "Écran")
    session.exec(delete(Ecran).where(Ecran.id == ecran_id))
    session.commit()
    journaliser_securite(
        "ecran_retire", acteur_id=user.id, cible_id=ecran_id, detail=f"écran {ecran_id}"
    )
    return Response(status_code=204)


# ── L'écran appairé : sa portée, et rien d'autre ────────────────────────────


@router.get("/moi/affiches", response_model=list[AfficheEcran])
@limiter.limit(LIMITE_LECTURE_AUTHENTIFIEE)
def affiches_de_mon_ecran(
    request: Request,
    session: Session = Depends(get_session),
    ecran: Ecran = Depends(ecran_appaire),
):
    """Les affiches de son périmètre, non archivées — sans auteur, destinataires ni gestes."""
    return [ce_que_montre_l_ecran(a) for a in affiches_de_l_ecran(session, ecran)]


@router.get(
    "/moi/affiches/{affiche_id}/images/{rang}",
    response_class=FileResponse,
    responses=REPONSE_FICHIER,
)
@limiter.limit(LIMITE_CONTROLE_FICHIER)
def image_d_une_affiche(
    request: Request,
    affiche_id: int,
    rang: int,
    session: Session = Depends(get_session),
    ecran: Ecran = Depends(ecran_appaire),
):
    """Une image d'une affiche que l'écran montre — 404 pour toute autre."""
    fichier, type_mime = present_ou_404(
        image_de_l_ecran(session, ecran, affiche_id, rang), "Image introuvable"
    )
    return FileResponse(fichier, media_type=type_mime)
