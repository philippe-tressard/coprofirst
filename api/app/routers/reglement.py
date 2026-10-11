"""Questions au règlement de copropriété — Ma résidence › Règlement (03/10/2026).

L'administration y charge le texte de travail du règlement (Markdown) et choisit
les actes de la bibliothèque montrés à côté ; on y pose une question, le conseil
syndical relit l'historique et publie une réponse relue dans la FAQ.

## Qui fait quoi (arbitré le 11/10/2026 — l'onglet quitte l'Espace CS)

| Geste | Qui |
|---|---|
| lire l'onglet, poser une question | copropriétaires (si l'usage leur est ouvert), conseil, admin — `require_questions_reglement` |
| lire une question | son AUTEUR, le conseil et l'admin — filtré ici, jamais par l'écran |
| publier dans la FAQ | le conseil et l'admin |
| charger le texte, choisir les documents, supprimer une question | l'admin |

Le copropriétaire ne reçoit ni le modèle ni le coût d'un appel, ni la fiche
technique du texte (fichier, taille, qui l'a chargé) : il lit l'avis, pas son
exploitation. L'écran masque, le serveur refuse (`standards/03` §1).

La logique vit dans `utils/question_reglement/` ; ce routeur ne fait que la servir.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, col, func, select

from app.auth.deps import (
    est_moderateur,
    peut_poser_questions_reglement,
    require_admin,
    require_cs_or_admin,
    require_proprietaire,
    require_questions_reglement,
)
from app.database import get_session
from app.models.core import Utilisateur
from app.models.reglement import QuestionReglement, TexteReglement
from app.models.roles import RoleUtilisateur
from app.routers.faq import FaqItemCreate, creer_entree
from app.utils.limiter import LIMITE_APPEL_FACTURE, limiter
from app.utils.lecture import lire_objet
from app.utils.noms import nom_affiche
from app.utils.question_reglement.documents import (
    MAX_DOCUMENTS,
    candidats,
    documents_lies,
    ids_lies,
    lier,
)
from app.utils.question_reglement.format import MAX_CARACTERES_QUESTION, VERDICTS
from app.utils.question_reglement.production import disponible, repondre
from app.utils.question_reglement.texte import MAX_CARACTERES_TEXTE, charger, texte_en_vigueur
from app.utils.recuperer import ou_404

router = APIRouter(prefix="/reglement", tags=["reglement"])


# ── Schémas propres à cet écran ────────────────────────────────────────────


class TexteReglementRead(BaseModel):
    id: int
    titre: str
    #: La fiche technique — rendue au conseil et à l'admin seulement.
    nom_fichier: Optional[str] = None
    nb_caracteres: Optional[int] = None
    charge_par: Optional[str] = None
    cree_le: datetime

    class Config:
        from_attributes = True


class DocumentLie(BaseModel):
    """Un acte de la bibliothèque, et l'endroit où CE lecteur l'ouvre."""

    id: int
    titre: str
    lien: str


class DocumentCandidat(BaseModel):
    id: int
    titre: str
    categorie: str


class EtatReglement(BaseModel):
    """Ce que l'onglet lit en arrivant."""

    #: L'assistant peut-il répondre ? — décidé par le serveur.
    disponible: bool
    texte: Optional[TexteReglementRead] = None
    nb_versions: int
    #: Les actes choisis par l'administration, filtrés pour le lecteur.
    documents: list[DocumentLie] = []
    #: Pour l'administration seule : ce qu'elle peut lier, et ce qu'elle a lié.
    documents_candidats: Optional[list[DocumentCandidat]] = None
    documents_ids: Optional[list[int]] = None


class AccesReglement(BaseModel):
    """L'onglet doit-il se montrer à ce copropriétaire ?"""

    acces: bool


class DocumentsChoisis(BaseModel):
    ids: list[int] = Field(max_length=MAX_DOCUMENTS)


class TexteCharge(BaseModel):
    """Le fichier lu par le navigateur, envoyé comme texte."""

    nom_fichier: str = Field(min_length=1, max_length=255)
    contenu: str = Field(max_length=MAX_CARACTERES_TEXTE + 10_000)


class ExtraitRead(BaseModel):
    citation: str
    reference: str = ""
    apport: str = ""
    verifie: bool
    page: Optional[str] = None
    acte: Optional[str] = None


class QuestionCreate(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_CARACTERES_QUESTION)


class QuestionReglementRead(BaseModel):
    id: int
    question: str
    verdict: str
    verdict_libelle: str
    reponse: str
    reserves: Optional[str] = None
    extraits: list[ExtraitRead]
    texte_id: int
    #: La réponse a-t-elle lu le texte EN VIGUEUR ? — sinon l'écran le signale.
    texte_en_vigueur: bool
    texte_charge_le: Optional[datetime] = None
    auteur_nom: Optional[str] = None
    #: Le modèle et le coût — rendus au conseil et à l'admin seulement.
    modele: Optional[str] = None
    cout_usd: Optional[str] = None
    faq_item_id: Optional[int] = None
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


def _lire_texte(session: Session, texte: TexteReglement, user: Utilisateur) -> TexteReglementRead:
    if not est_moderateur(user):
        return TexteReglementRead(id=texte.id, titre=texte.titre, cree_le=texte.cree_le)
    noms = _noms(session, {texte.charge_par_id})
    return lire_objet(
        TexteReglementRead,
        texte,
        nb_caracteres=len(texte.contenu),
        charge_par=noms.get(texte.charge_par_id),
    )


def _lire_questions(
    session: Session, lignes: list[QuestionReglement], user: Utilisateur
) -> list[QuestionReglementRead]:
    en_vigueur = texte_en_vigueur(session)
    textes = {
        t.id: t.cree_le
        for t in session.exec(
            select(TexteReglement).where(col(TexteReglement.id).in_({q.texte_id for q in lignes}))
        ).all()
    }
    noms = _noms(session, {q.auteur_id for q in lignes})
    #  Le modèle et le coût regardent qui paie l'appel, pas qui lit l'avis.
    exploitation = est_moderateur(user)
    return [
        lire_objet(
            QuestionReglementRead,
            q,
            verdict_libelle=VERDICTS.get(q.verdict, q.verdict),
            extraits=[ExtraitRead(**e) for e in json.loads(q.extraits_json or "[]")],
            texte_en_vigueur=bool(en_vigueur and en_vigueur.id == q.texte_id),
            texte_charge_le=textes.get(q.texte_id),
            auteur_nom=noms.get(q.auteur_id),
            modele=q.modele if exploitation else None,
            cout_usd=q.cout_usd if exploitation else None,
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
    """L'assistant est-il prêt, quel texte est en vigueur, quels actes montrer ?
    — rien de la configuration."""
    texte = texte_en_vigueur(session)
    admin = user.has_role(RoleUtilisateur.admin)
    return EtatReglement(
        disponible=disponible(session),
        texte=_lire_texte(session, texte, user) if texte else None,
        nb_versions=session.exec(select(func.count()).select_from(TexteReglement)).one(),
        documents=[
            DocumentLie(id=d.id, titre=d.titre, lien=lien)
            for d, lien in documents_lies(session, user)
        ],
        documents_candidats=(
            [
                DocumentCandidat(
                    id=d.id, titre=d.titre, categorie=d.categorie.libelle if d.categorie else ""
                )
                for d in candidats(session)
            ]
            if admin
            else None
        ),
        documents_ids=ids_lies(session) if admin else None,
    )


@router.get("/questions", response_model=list[QuestionReglementRead])
def lister_questions(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_questions_reglement),
):
    """L'historique, la plus récente d'abord — une question déjà posée ne se repaie pas.

    Le conseil et l'administration lisent toutes les questions ; un copropriétaire,
    les SIENNES seulement : une question dit souvent ce qu'on envisage chez soi."""
    requete = select(QuestionReglement)
    if not est_moderateur(user):
        requete = requete.where(QuestionReglement.auteur_id == user.id)
    lignes = session.exec(
        requete.order_by(col(QuestionReglement.cree_le).desc(), col(QuestionReglement.id).desc())
    ).all()
    return _lire_questions(session, list(lignes), user)


# ── Gestes ─────────────────────────────────────────────────────────────────


@router.post("/textes", response_model=TexteReglementRead)
def charger_texte(
    body: TexteCharge,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_admin),
):
    """Charge une version du texte — geste de l'administration seule : le texte
    est ce que l'assistant lit pour TOUTES les questions, et chaque version en
    plus est une base à relire. Le même contenu que la version en vigueur ne
    crée rien : elle est rendue telle quelle."""
    version, _ = charger(session, body.contenu, body.nom_fichier, user.id)
    return _lire_texte(session, version, user)


@router.put("/documents", response_model=list[int])
def choisir_documents(
    body: DocumentsChoisis,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Les actes montrés à côté du texte — geste de l'administration seule, comme
    le texte lui-même. L'ordre envoyé est l'ordre d'affichage."""
    return lier(session, body.ids)


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
    _: Utilisateur = Depends(require_admin),
):
    """Efface une question et sa réponse — geste de l'administration seule.

    L'historique évite de repayer une question déjà posée : on n'y touche que
    pour retirer une réponse fausse ou une question qui n'aurait pas dû être
    posée. L'entrée de FAQ née de la réponse, elle, reste : c'est un contenu
    publié, qui se retire depuis la FAQ."""
    session.delete(ou_404(session, QuestionReglement, question_id, "Question"))
    session.commit()
