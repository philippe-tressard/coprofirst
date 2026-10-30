"""Questions au règlement de copropriété — Ma résidence › Règlement (03/10/2026).

L'administration y joint les fichiers du règlement que l'assistant lit (Markdown),
par l'objet Pièces jointes standard ; on y pose une question, le conseil syndical
relit l'historique et publie une réponse relue dans la FAQ.

## Qui fait quoi (arbitré le 11/10/2026 — l'onglet quitte l'Espace CS)

| Geste | Qui |
|---|---|
| lire l'onglet, poser une question | copropriétaires (si l'usage leur est ouvert), conseil, admin — `require_questions_reglement` |
| lire une question | son AUTEUR, le conseil et l'admin — `question_reglement_visible`, ici et au fil d'activité |
| publier dans la FAQ | le conseil et l'admin |
| supprimer une question | son AUTEUR et l'admin (11/10/2026) — `peut_editer` |
| joindre ou retirer les fichiers du règlement, saisir leur provenance | l'admin |

Les fichiers se déposent par les routes des DOCUMENTS (catégorie
`texte_reglement`, réservée à l'admin par `visibility.CATEGORIES_ADMIN_SEUL`) :
ce routeur ne fait que dire à l'admin où les déposer (`categorie_id`). Les
autres lisent un lien vers le règlement publié dans la Fiche. Le copropriétaire
ne reçoit pas le modèle : il lit l'avis, pas son exploitation. Le coût d'un
appel ne sort plus d'ici (11/10/2026) — il se lit dans la consommation de
l'assistant (Admin › Assistant IA). L'écran masque, le serveur refuse (`standards/03` §1).

La logique vit dans `utils/question_reglement/` ; ce routeur ne fait que la servir.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from app.auth.appartenance import exiger_objet_autorise
from app.auth.deps import (
    est_moderateur,
    peut_editer,
    peut_poser_questions_reglement,
    question_reglement_visible,
    require_admin,
    require_cs_or_admin,
    require_proprietaire,
    require_questions_reglement,
)
from app.database import get_session
from app.models.core import Utilisateur
from app.models.reglement import QuestionReglement
from app.models.roles import RoleUtilisateur
from app.routers.faq import FaqItemCreate, creer_entree
from app.utils.limiter import LIMITE_APPEL_FACTURE, limiter
from app.utils.lecture import lire_objet
from app.utils.noms import nom_affiche
from app.utils.question_reglement.documents import lien_reglement
from app.utils.question_reglement.format import MAX_CARACTERES_QUESTION, VERDICTS
from app.utils.question_reglement.production import disponible, repondre
from app.utils.question_reglement.provenance import (
    MAX_CARACTERES as MAX_CARACTERES_PROVENANCE,
)
from app.utils.question_reglement.provenance import enregistrer_provenance, lire_provenance
from app.utils.question_reglement.texte import (
    CODE_CATEGORIE_AG,
    categorie,
    texte_disponible,
    texte_en_vigueur,
)
from app.utils.recuperer import ou_404

router = APIRouter(prefix="/reglement", tags=["reglement"])


# ── Schémas propres à cet écran ────────────────────────────────────────────


class EtatReglement(BaseModel):
    """Ce que l'onglet lit en arrivant."""

    #: L'assistant peut-il répondre ? — décidé par le serveur.
    disponible: bool
    #: Un fichier Markdown lisible est-il joint ? — sans lui, pas de question.
    texte_disponible: bool
    #: Le règlement publié dans la Fiche, pour qui n'est pas l'administration.
    lien_reglement: Optional[str] = None
    #: Pour l'administration seule : la catégorie où joindre les fichiers.
    categorie_id: Optional[int] = None
    #: Pour l'administration seule : celle des décisions d'AG transcrites.
    categorie_ag_id: Optional[int] = None
    #: Pour l'administration seule : d'où vient le texte (« la numérisation du RCP… »).
    provenance: Optional[str] = None


class ProvenanceUpdate(BaseModel):
    provenance: str = Field(min_length=1, max_length=MAX_CARACTERES_PROVENANCE)


class AccesReglement(BaseModel):
    """L'onglet doit-il se montrer à ce copropriétaire ?"""

    acces: bool


class ExtraitRead(BaseModel):
    citation: str
    reference: str = ""
    apport: str = ""
    verifie: bool
    page: Optional[str] = None
    acte: Optional[str] = None
    #: `reglement` ou `ag` — déduit par le code (`extraits.source_de`).
    source: Optional[str] = None


class QuestionCreate(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_CARACTERES_QUESTION)


class QuestionReglementRead(BaseModel):
    id: int
    question: str
    verdict: str
    verdict_libelle: str
    reponse: str
    #: Les sections (29/10/2026) — vides dans un avis plus ancien.
    selon_reglement: Optional[str] = None
    selon_ag: Optional[str] = None
    synthese: Optional[str] = None
    reserves: Optional[str] = None
    extraits: list[ExtraitRead]
    texte_id: int
    #: La réponse a-t-elle lu le texte EN VIGUEUR ? — sinon l'écran le signale.
    texte_en_vigueur: bool
    #: D'où vient le texte lu — celle de la question, sinon l'actuelle.
    provenance: Optional[str] = None
    auteur_nom: Optional[str] = None
    #: Le modèle — rendu au conseil et à l'admin seulement.
    modele: Optional[str] = None
    faq_item_id: Optional[int] = None
    #: Ce lecteur peut-il la supprimer ? — son auteur et l'admin ; l'écran
    #: montre la corbeille d'après le serveur, il ne recalcule rien.
    peut_supprimer: bool = False
    cree_le: datetime

    class Config:
        from_attributes = True


# ── Lectures ───────────────────────────────────────────────────────────────


def _noms(session: Session, ids: set[Optional[int]]) -> dict[int, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    gens = session.exec(select(Utilisateur).where(col(Utilisateur.id).in_(ids))).all()
    return {u.id: nom_affiche(u.prenom, u.nom) for u in gens}


def _lire_questions(
    session: Session, lignes: list[QuestionReglement], user: Utilisateur
) -> list[QuestionReglementRead]:
    en_vigueur = texte_en_vigueur(session)
    actuelle = lire_provenance(session)
    noms = _noms(session, {q.auteur_id for q in lignes})
    #  Le modèle regarde qui paie l'appel, pas qui lit l'avis.
    exploitation = est_moderateur(user)
    return [
        lire_objet(
            QuestionReglementRead,
            q,
            verdict_libelle=VERDICTS.get(q.verdict, q.verdict),
            extraits=[ExtraitRead(**e) for e in json.loads(q.extraits_json or "[]")],
            texte_en_vigueur=bool(en_vigueur and en_vigueur.id == q.texte_id),
            provenance=q.provenance or actuelle,
            auteur_nom=noms.get(q.auteur_id),
            modele=q.modele if exploitation else None,
            peut_supprimer=peut_editer(q, user),
        )
        for q in lignes
    ]


@router.get("/acces", response_model=AccesReglement)
def acces(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_proprietaire),
):
    """L'onglet se montre-t-il ? — Ma résidence le demande pour le masquer au
    copropriétaire quand l'usage ne lui est pas ouvert. Le même prédicat refuse
    les autres routes : l'onglet et le serveur ne peuvent pas diverger."""
    return AccesReglement(acces=peut_poser_questions_reglement(user, session))


@router.get("", response_model=EtatReglement)
def etat(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_questions_reglement),
):
    """L'assistant est-il prêt, un texte est-il joint, où lire le règlement ?
    — rien de la configuration, et les fichiers à l'administration seule."""
    admin = user.has_role(RoleUtilisateur.admin)
    cat = categorie(session) if admin else None
    cat_ag = categorie(session, CODE_CATEGORIE_AG) if admin else None
    return EtatReglement(
        disponible=disponible(session),
        texte_disponible=texte_disponible(session),
        lien_reglement=None if admin else lien_reglement(session, user),
        categorie_id=cat.id if cat else None,
        categorie_ag_id=cat_ag.id if cat_ag else None,
        provenance=lire_provenance(session) if admin else None,
    )


@router.put("/provenance", response_model=EtatReglement)
def modifier_provenance(
    body: ProvenanceUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_admin),
):
    """La provenance du texte, que chaque avis cite (« d'après … ») — l'administration
    la saisit avec les fichiers qu'elle joint. Rend l'état de l'onglet relu."""
    enregistrer_provenance(session, body.provenance)
    return etat(session, user)


@router.get("/questions", response_model=list[QuestionReglementRead])
def lister_questions(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_questions_reglement),
):
    """L'historique, la plus récente d'abord — une question déjà posée ne se repaie pas.

    Le conseil et l'administration lisent toutes les questions ; un copropriétaire,
    les SIENNES seulement : une question dit souvent ce qu'on envisage chez soi.
    Le fil d'activité les filtre par le même prédicat (`flux/reglement.py`)."""
    lignes = session.exec(
        select(QuestionReglement).order_by(
            col(QuestionReglement.cree_le).desc(), col(QuestionReglement.id).desc()
        )
    ).all()
    #  La liste FILTRE par le prédicat du lecteur, jamais par sa copie en SQL
    #  (`test_regles_acces_centralisees.py`) : la table est courte.
    lignes = [q for q in lignes if question_reglement_visible(q, user, session)]
    return _lire_questions(session, list(lignes), user)


# ── Gestes ─────────────────────────────────────────────────────────────────


@router.post(
    "/questions",
    response_model=QuestionReglementRead,
    status_code=201,
    summary="Poser une question au règlement (copropriétaires, CS, admin)",
)
@limiter.limit(LIMITE_APPEL_FACTURE)
async def poser_question(
    request: Request,
    body: QuestionCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_questions_reglement),
):
    """🔴 Le geste est manuel et facturé : rien d'autre n'appelle cette route
    que le bouton « Poser la question ». Les limites d'appels de l'usage
    (par heure et par personne, par mois) valent pour tous, conseil compris."""
    ligne = await repondre(session, body.question, user.id)
    return _lire_questions(session, [ligne], user)[0]


@router.post("/questions/{question_id}/faq", response_model=QuestionReglementRead)
def publier_dans_la_faq(
    question_id: int,
    body: FaqItemCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Publie dans la FAQ la réponse RELUE — le texte envoyé est celui que le
    conseil a corrigé, jamais la réponse brute de l'assistant. Une entrée de FAQ
    ne porte aucun auteur ; c'est au conseil de retirer de la question ce qui
    désignerait qui l'a posée."""
    q = ou_404(session, QuestionReglement, question_id, "Question")
    if q.faq_item_id:
        raise HTTPException(409, "Cette réponse est déjà publiée dans la FAQ.")
    item = creer_entree(session, body)
    q.faq_item_id = item.id
    session.add(q)
    session.commit()
    session.refresh(q)
    return _lire_questions(session, [q], user)[0]


@router.delete("/questions/{question_id}", status_code=204)
def supprimer_question(
    question_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_questions_reglement),
):
    """Efface une question et sa réponse — son AUTEUR, ou l'administration.

    Ouvert à l'auteur le 11/10/2026 : *« un auteur peut supprimer sa réponse dans
    la rubrique règlement »*. La règle est celle de `peut_editer` — l'auteur, et
    l'admin pour arbitrer ; pas le conseil syndical, qui relit et publie, mais
    n'efface pas la question d'un autre. Supprimée, elle quitte aussi le fil
    d'activité, qui lit la table. L'entrée de FAQ née de la réponse, elle, reste :
    c'est un contenu publié, qui se retire depuis la FAQ."""
    question = exiger_objet_autorise(
        session,
        QuestionReglement,
        question_id,
        "Question",
        user,
        peut_editer,
        refus="Seuls son auteur et l'administration suppriment une question.",
    )
    session.delete(question)
    session.commit()


#  Les transcriptions des PV d'AG, à l'administration (29/10/2026) — routes à segment
#  FIXE (`/transcriptions/…`), sans conflit avec `/questions/{id}`.
from app.routers.reglement_transcriptions import router as _transcriptions  # noqa: E402

router.include_router(_transcriptions)
