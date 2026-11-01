"""Router prestataires & contrats d'entretien.

⚠️ Les RELEVÉS DE COMPTEURS et leur configuration vivent dans `compteurs.py`.
Ils partagent le préfixe d'URL `/prestataires` — l'écran est le même onglet, et
déplacer les routes aurait cassé les liens et le client TypeScript pour un gain
nul. Ce qui les sépare est le SUJET : un relevé d'eau ne parle ni d'un
prestataire ni d'un contrat, il parle d'un compteur. Coupé le 29/08/2026, la
modularité (rang 1) refusant que ce fichier grossisse encore.
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
import json

from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlmodel import Session, select

#  ⚠️ `get_current_user` n'est plus importé : il ne servait qu'à `list_devis`,
#  le SEUL endpoint de ce router ouvert à tous les comptes (les résidents y
#  voyaient les devis marqués `affichable`). Tous ceux qui restent exigent le
#  rôle CS ou admin — la page qu'ils servent leur est réservée (#603).
from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.utils.limiter import LIMITE_APPEL_FACTURE, limiter
from app.utils.perimetres.arbre import (
    batiments_cibles,
    parse_json_perimetres,
    perimetre_cible_json,
)
from app.models.core import (
    ContratEntretien,
    NotationPrestataire,
    Prestataire,
    Utilisateur,
)

from app.utils.echeance_contrat import poser_echeance
from app.utils.equipements import AUTRE, exiger_equipement
from app.utils.noms import nom_affiche, nom_auteur
from app.utils.recuperer import ou_rien
from app.utils.archivage import est_archivable
from app.utils.assiste_ia import marquer
from app.utils.recuperer import ou_404
from app.routers.prestataires_schemas import (
    PrestataireCreate,
    PrestataireRead,
    PrestataireUpdate,
)

router = APIRouter(prefix="/prestataires", tags=["prestataires"])


# ── Prestataires ─────────────────────────────────────────────────────────────


def _prest_to_read(p: Prestataire) -> PrestataireRead:
    """Construit un PrestataireRead en parsant contacts_json."""
    data = PrestataireRead.model_validate(p)
    #  Calculé par la règle déclarée, jamais relu de `actif` par l'écran (#1538).
    data.archivee = est_archivable("prestataire", p)
    if p.contacts_json:
        try:
            data.contacts = json.loads(p.contacts_json)
        except Exception:
            data.contacts = []
    return data


def lister_prestataires(session: Session, archivees: bool) -> list[PrestataireRead]:
    """Les fiches courantes, ou celles des Archives (`GET /prestataires/archives`).

    Par ordre ALPHABÉTIQUE (#1145) : on cherche une entreprise par son nom, et
    l'ordre d'insertion n'aidait personne. Sans tenir compte de la casse.
    📦 Le partage courants / Archives suit la règle déclarée (#1538), comme les
    affiches de hall : la décision vit dans `REGLES`, pas dans un `WHERE`.
    """
    prests = session.exec(select(Prestataire).order_by(func.lower(Prestataire.nom))).all()
    return [_prest_to_read(p) for p in prests if est_archivable("prestataire", p) == archivees]


@router.get("", response_model=list[PrestataireRead])
def list_prestataires(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return lister_prestataires(session, archivees=False)


@router.post("", response_model=PrestataireRead, status_code=201)
def create_prestataire(
    body: PrestataireCreate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    data = body.model_dump(exclude={"contacts"})
    if body.contacts is not None:
        data["contacts_json"] = json.dumps(
            [c.model_dump() for c in body.contacts], ensure_ascii=False
        )
    p = Prestataire(**data)
    session.add(p)
    session.commit()
    session.refresh(p)
    return _prest_to_read(p)


@router.patch("/{p_id}", response_model=PrestataireRead)
def update_prestataire(
    p_id: int,
    body: PrestataireUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    p = ou_404(session, Prestataire, p_id, "Prestataire")
    #  `assiste_ia` à part : `marquer` ne l'écrit que dans un sens (#1327).
    data = body.model_dump(exclude_unset=True, exclude={"contacts", "assiste_ia"})
    marquer(p, body)
    if "contacts" in body.model_fields_set:
        data["contacts_json"] = json.dumps(
            [c.model_dump() for c in (body.contacts or [])], ensure_ascii=False
        )
    for k, v in data.items():
        setattr(p, k, v)
    session.add(p)
    session.commit()
    session.refresh(p)
    return _prest_to_read(p)


#  📦 Archiver et ressortir : `prestataires_archivage.py` (#1538). C'était un
#  `DELETE` qui ne supprimait rien — trois mots pour un geste.


# ── Contrats d'entretien ──────────────────────────────────────────────────────


class ContratCreate(BaseModel):
    copropriete_id: int
    #: Le PÉRIMÈTRE couvert — des codes de l'arbre, `["bat:3"]`, `["parking"]`…
    #: C'est la seule chose que l'écran saisit depuis le 10/09/2026 ;
    #: `batiment_id` en est déduit par `_deriver_batiment` et n'est plus reçu.
    perimetre_cible: Optional[list[str]] = None
    prestataire_id: int
    #: Le code d'un équipement proposé à la saisie (`utils/equipements`, #2442).
    type_equipement: str = AUTRE
    libelle: str
    numero_contrat: Optional[str] = None
    date_debut: date
    duree_initiale_valeur: Optional[int] = None
    duree_initiale_unite: Optional[str] = None  # "mois" ou "ans"
    frequence_type: Optional[str] = None  # "semaines", "mois", "fois_par_an"
    frequence_valeur: Optional[int] = None
    prochaine_visite: Optional[date] = None
    notes: Optional[str] = None
    document_id: Optional[int] = None


class ContratRead(BaseModel):
    id: int
    copropriete_id: int
    #: Rendu tel quel — l'écran l'affiche par `perimetreLabel`, comme partout
    #: ailleurs. La chaîne JSON est parsée par le `field_validator` ci-dessous.
    perimetre_cible: Optional[list[str]] = None
    #: DÉRIVÉ, conservé pour les lectures qui s'y appuient encore.
    batiment_id: Optional[int] = None
    prestataire_id: int

    #  La colonne est du TEXTE, l'API rend une liste.
    #
    #  🔴 Elle DÉLÈGUE à `parse_json_perimetres` au lieu de refaire un
    #  `json.loads` avec son `try` : `schemas.py` en porte déjà deux, qui
    #  divergent **exprès** sur le cas illisible — un ticket retombe sur
    #  « résidence », un document ne rend plus de badge. Un contrat suit la règle
    #  canonique, celle de l'arbre : ce serait la QUATRIÈME écriture, et la
    #  première à oublier pourquoi les trois autres diffèrent.
    _perimetre = field_validator("perimetre_cible", mode="before")(
        classmethod(lambda cls, v: v if isinstance(v, list) else parse_json_perimetres(v))
    )
    type_equipement: str
    libelle: str
    numero_contrat: Optional[str] = None
    date_debut: date
    duree_initiale_valeur: Optional[int] = None
    duree_initiale_unite: Optional[str] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    prochaine_visite: Optional[date] = None
    actif: bool
    #: Calculé par `REGLES["contrat"]` (#1538) — ce que lit l'écran.
    archivee: bool = False
    notes: Optional[str] = None
    document_id: Optional[int] = None

    #: L'échéance DÉDUITE, et `reconduit` quand le terme initial est passé.
    #: Non stockées : elles se reportent avec le temps, et une colonne figerait
    #: la valeur au jour du calcul — c'est le défaut corrigé le 29/08/2026, où
    #: « échéance » désignait trois valeurs différentes selon l'écran.
    #: 📖 La règle, ses cas et son historique : `app/utils/echeance_contrat.py`.
    date_fin: Optional[date] = None
    reconduit: bool = False
    #: Terme passé sans reconduction — un mandat de syndic qui a CESSÉ.
    echu: bool = False
    #: 🔴 Le geste ✨ est-il proposable sur ce contrat ?
    #:
    #: C'est le SERVEUR qui répond, pas l'écran. La disponibilité dépend de la
    #: configuration de l'assistant — fournisseur actif, clé posée — et un membre
    #: du conseil syndical n'a aucun accès à cette configuration : lui faire lire
    #: `GET /config/admin` pour afficher une icône serait ouvrir l'administration
    #: pour un détail d'affichage (`standards/03` §1).
    synthese_disponible: bool = False

    class Config:
        from_attributes = True


@router.get("/contrats", response_model=list[ContratRead])
def list_contrats(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return lister_contrats(session, archivees=False)


def lister_contrats(session: Session, archivees: bool) -> list[ContratRead]:
    """Les contrats courants, ou ceux des Archives (`GET …/contrats/archives`)."""
    contrats = [
        c
        for c in session.exec(select(ContratEntretien)).all()
        if est_archivable("contrat", c) == archivees
    ]
    return lire_contrats(session, contrats)


def lire_contrats(session: Session, contrats: list[ContratEntretien]) -> list[ContratRead]:
    """La lecture d'un contrat, ce qui s'en DÉDUIT compris : échéance, archivage, ✨.

    La liste et la synthèse d'un prestataire passent par elle : la synthèse les
    relisait par `ContratRead.model_validate` seul, et `date_fin`, `reconduit`,
    `echu`… y gardaient leur valeur par défaut (#1687, classe de #1563).
    """
    #  ⚠️ La configuration de l'assistant se lit UNE fois, pas par contrat : elle
    #  est la même pour tous, et la relire à chaque ligne ferait autant d'allers
    #  en base que de contrats pour une réponse identique.
    from app.utils.llm import config_llm
    from app.utils.llm_usages import USAGE_SYNTHESE_CONTRAT
    from app.utils.synthese_contrat import documents_du_contrat

    cfg = config_llm(session, USAGE_SYNTHESE_CONTRAT)
    #  La MÊME règle que `synthese_disponible` — activation aux deux étages, clé,
    #  modèle de l'usage —, lue une fois ; seule la partie « ce contrat a-t-il
    #  un document » se rejoue par ligne.
    assistant_pret = cfg.pret

    lus = []
    for c in contrats:
        lu = poser_echeance(ContratRead.model_validate(c), c)
        lu.archivee = est_archivable("contrat", c)
        lu.synthese_disponible = assistant_pret and (
            not cfg.envoi_document or bool(documents_du_contrat(session, c))
        )
        lus.append(lu)
    return lus


@router.post("/contrats/{c_id}/synthese", summary="Proposer la synthèse d'un contrat (CS/Admin)")
@limiter.limit(LIMITE_APPEL_FACTURE)
async def proposer_synthese(
    request: Request,
    c_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Rend une synthèse PROPOSÉE. N'enregistre rien.

    🔴 Le geste est manuel et il le reste : rien n'appelle ce point d'entrée
    sinon l'icône ✨ d'une carte de contrat, cliquée par un membre du conseil
    syndical. Aucune tâche planifiée, aucun appel à la création d'un contrat —
    chaque synthèse est facturée, et chacune doit être voulue.

    ⚠️ Le texte rendu remplit le champ « Synthèse » du formulaire d'édition, que
    le CS relit et enregistre lui-même. Écrire directement en base ferait du
    modèle l'auteur d'un document réglementaire (décret n° 2001-477).
    """
    from app.utils.synthese_contrat import ErreurLLM, synthese_disponible, synthetiser

    contrat = ou_404(session, ContratEntretien, c_id, "Contrat")
    if not synthese_disponible(session, contrat):
        raise HTTPException(
            400,
            "L'assistant n'est pas configuré, ou ce contrat n'a pas de document joint.",
        )
    try:
        return {"synthese": await synthetiser(session, contrat, demandeur=user.id)}
    except ErreurLLM as exc:
        raise HTTPException(400, str(exc))


def _appliquer_perimetre(contrat: ContratEntretien, codes: Optional[list[str]]) -> None:
    """Pose le périmètre d'un contrat, et en DÉRIVE son bâtiment.

    🔴 Un seul point d'écriture pour `batiment_id`, et c'est ce qui empêche les
    deux colonnes de devenir deux vérités concurrentes. Le périmètre est la
    saisie ; le bâtiment est ce qu'on en déduit.

    ⚠️ **Un seul** bâtiment ciblé donne un identifiant ; zéro ou plusieurs
    donnent `NULL`. Un contrat qui couvre deux bâtiments n'en désigne aucun —
    choisir « le premier » produirait une réponse plausible et fausse, celle
    dont ce dépôt se méfie le plus.
    """
    if codes is None:
        return
    contrat.perimetre_cible = perimetre_cible_json(codes)
    vises = batiments_cibles(codes or [])
    contrat.batiment_id = next(iter(vises)) if len(vises) == 1 else None


@router.post("/contrats", response_model=ContratRead, status_code=201)
def create_contrat(
    body: ContratCreate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    exiger_equipement(session, body.type_equipement, "contrat")
    donnees = body.model_dump()
    codes = donnees.pop("perimetre_cible", None)
    c = ContratEntretien(**donnees)
    _appliquer_perimetre(c, codes or [])
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


@router.patch("/contrats/{c_id}", response_model=ContratRead)
def update_contrat(
    c_id: int,
    body: ContratCreate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    c = ou_404(session, ContratEntretien, c_id, "Contrat")
    modifications = body.model_dump(exclude_unset=True)
    codes = modifications.pop("perimetre_cible", None)
    #  Seul un équipement qui CHANGE se juge : un contrat dont l'équipement a été
    #  retiré depuis reste modifiable sans qu'on lui en choisisse un autre (#2442).
    if modifications.get("type_equipement", c.type_equipement) != c.type_equipement:
        exiger_equipement(session, modifications["type_equipement"], "contrat")
    for k, v in modifications.items():
        setattr(c, k, v)
    _appliquer_perimetre(c, codes)
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


# ── Notations prestataires ─────────────────────────────────────────────────


class NotationCreate(BaseModel):
    #  ⚠️ `devis_id` a disparu avec la prestation ponctuelle (#603). La COLONNE,
    #  elle, reste en base : les notations deja posees sur un devis gardent leur
    #  rattachement, et un retour arriere du code doit les retrouver. Le schema
    #  ne l'expose simplement plus — on ne peut plus en creer, on n'efface rien.
    prestataire_id: int
    note: int  # 1-5
    commentaire: Optional[str] = None
    contrat_id: Optional[int] = None

    @field_validator("note")
    @classmethod
    def validate_note(cls, v):
        if v < 1 or v > 5:
            raise ValueError("La note doit être entre 1 et 5")
        return v


class NotationRead(BaseModel):
    id: int
    prestataire_id: int
    note: int
    commentaire: Optional[str] = None
    contrat_id: Optional[int] = None
    auteur_id: Optional[int] = None  # compte supprimé (#1821)
    auteur_nom: Optional[str] = None
    cree_le: datetime

    class Config:
        from_attributes = True


@router.get("/notations", response_model=list[NotationRead])
def list_notations(
    prestataire_id: Optional[int] = None,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    q = select(NotationPrestataire)
    if prestataire_id is not None:
        q = q.where(NotationPrestataire.prestataire_id == prestataire_id)
    q = q.order_by(NotationPrestataire.cree_le.desc())
    notations = session.exec(q).all()
    result = []
    for n in notations:
        auteur = ou_rien(session, Utilisateur, n.auteur_id)
        nr = NotationRead.model_validate(n)
        nr.auteur_nom = nom_auteur(auteur)
        result.append(nr)
    return result


@router.post("/notations", response_model=NotationRead, status_code=201)
def create_notation(
    body: NotationCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    ou_404(session, Prestataire, body.prestataire_id, "Prestataire")
    n = NotationPrestataire(
        prestataire_id=body.prestataire_id,
        note=body.note,
        commentaire=body.commentaire,
        contrat_id=body.contrat_id,
        auteur_id=user.id,
    )
    session.add(n)
    session.commit()
    session.refresh(n)
    nr = NotationRead.model_validate(n)
    nr.auteur_nom = nom_affiche(user.prenom, user.nom)
    return nr


@router.delete("/notations/{n_id}", status_code=204)
def delete_notation(
    n_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    n = ou_404(session, NotationPrestataire, n_id, "Notation")
    session.delete(n)
    session.commit()


@router.get("/synthese/{p_id}")
def get_prestataire_synthese(
    p_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Synthèse complète d'un prestataire pour le reporting CS."""
    p = ou_404(session, Prestataire, p_id, "Prestataire")

    contrats = session.exec(
        select(ContratEntretien).where(
            ContratEntretien.prestataire_id == p_id,
            ContratEntretien.actif == True,  # noqa: E712
        )
    ).all()
    notations = session.exec(
        select(NotationPrestataire)
        .where(NotationPrestataire.prestataire_id == p_id)
        .order_by(NotationPrestataire.cree_le.desc())
    ).all()

    note_moy = round(sum(n.note for n in notations) / len(notations), 1) if notations else None
    notations_read = []
    for n in notations:
        auteur = ou_rien(session, Utilisateur, n.auteur_id)
        notations_read.append(
            {
                "id": n.id,
                "note": n.note,
                "commentaire": n.commentaire,
                "contrat_id": n.contrat_id,
                "auteur_nom": nom_auteur(auteur),
                "cree_le": n.cree_le.isoformat(),
            }
        )

    prest_data = _prest_to_read(p).model_dump()
    return {
        **prest_data,
        "contrats": [lu.model_dump() for lu in lire_contrats(session, contrats)],
        "notations": notations_read,
        "note_moyenne": note_moy,
        "nb_notations": len(notations),
        "nb_contrats": len(contrats),
        "prochaines_visites": [
            {"contrat": c.libelle, "date": c.prochaine_visite.isoformat()}
            for c in contrats
            if c.prochaine_visite
        ],
    }
