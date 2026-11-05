"""Router délégations aidant — gestion des accès délégués pour les proches."""

from datetime import date, datetime
from app.utils.statuts_lus import invalider_cache as invalider_statuts_lus
from app.utils import horloge
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, or_

from app.auth.deps import est_moderateur, get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import Delegation, StatutDelegation, Utilisateur
from app.utils.noms import nom_affiche
from app.utils.lecture import lire_objet
from app.utils.recuperer import ou_404
from app.utils.valeurs import valeur
from app.utils.journal_securite import journaliser_securite
from app.auth.appartenance import (
    exiger_aidant_de_la_delegation,
    exiger_partie_de_la_delegation,
    peut_accepter_la_delegation,
    peut_revoquer_la_delegation,
)

router = APIRouter(prefix="/delegations", tags=["délégations-aidant"])


# ── Schemas ─────────────────────────────────────────────────────────────────


class DelegationCreate(BaseModel):
    mandant_id: int
    aidant_id: int
    motif: str = ""
    date_fin: Optional[str] = None  # ISO date, null = illimité


class DelegationRead(BaseModel):
    """Une délégation, et les deux gestes que CE lecteur peut y faire (#2525).

    Typée depuis #2525 : elle était déclarée ici sans servir, et les routes
    rendaient des `dict` que le contrat annonçait `{}`.
    """

    id: int
    mandant_id: int
    mandant_nom: str
    aidant_id: int
    aidant_nom: str
    statut: str
    motif: str
    date_debut: date
    date_fin: Optional[date] = None
    cree_le: datetime
    revoque_le: Optional[datetime] = None
    #: « Accepter » : l'aidant désigné, tant qu'elle attend (`POST …/accepter`).
    peut_accepter: bool = False
    #: « Révoquer » : ses deux parties ou le conseil, tant qu'elle n'est pas
    #: terminée (`POST …/revoquer`).
    peut_revoquer: bool = False


# ── Helpers ─────────────────────────────────────────────────────────────────

#: Les délégations qu'on ne révoque plus : la route répond 400, le geste se tait.
TERMINEES = (StatutDelegation.revoquee, StatutDelegation.expiree)


def _en_attente(d: Delegation) -> bool:
    """Seule une délégation en attente s'accepte : la route répond 400, le geste se tait."""
    return d.statut == StatutDelegation.en_attente


def _user_display(u: Utilisateur) -> str:
    return nom_affiche(u.prenom, u.nom)


def _lire(d: Delegation, session: Session, lecteur: Utilisateur) -> DelegationRead:
    """La délégation, et ses gestes pour `lecteur` — par les prédicats des refus.

    🔴 Le site décidait les deux gestes lui-même (`statut === 'en_attente' &&
    aidant_id === moi`) ; l'app iOS ne recopie pas cette règle. Les servir par les
    prédicats que les routes appellent garde le bouton et la route d'accord.
    """
    mandant = session.get(Utilisateur, d.mandant_id)
    aidant = session.get(Utilisateur, d.aidant_id)
    return lire_objet(
        DelegationRead,
        d,
        mandant_nom=_user_display(mandant) if mandant else "?",
        aidant_nom=_user_display(aidant) if aidant else "?",
        statut=valeur(d.statut),
        peut_accepter=_en_attente(d) and peut_accepter_la_delegation(d, lecteur),
        peut_revoquer=d.statut not in TERMINEES and peut_revoquer_la_delegation(d, lecteur),
    )


# ── Endpoints CS/Admin ──────────────────────────────────────────────────────


@router.get("", response_model=list[DelegationRead])
def list_delegations(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Liste les délégations visibles par l'utilisateur.
    - CS/Admin : toutes
    - Aidant : ses délégations
    - Mandant : les délégations le concernant
    """
    if est_moderateur(user):
        delegations = session.exec(select(Delegation).order_by(Delegation.cree_le.desc())).all()
    else:
        delegations = session.exec(
            select(Delegation)
            .where(or_(Delegation.aidant_id == user.id, Delegation.mandant_id == user.id))
            .order_by(Delegation.cree_le.desc())
        ).all()
    return [_lire(d, session, user) for d in delegations]


@router.post("", status_code=201, response_model=DelegationRead)
def create_delegation(
    body: DelegationCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Créer une délégation (CS/Admin uniquement)."""
    ou_404(session, Utilisateur, body.mandant_id, "Mandant")
    ou_404(session, Utilisateur, body.aidant_id, "Aidant")
    if body.mandant_id == body.aidant_id:
        raise HTTPException(400, "Le mandant et l'aidant doivent être différents")

    # Vérifier qu'il n'y a pas déjà une délégation active entre ces deux personnes
    existing = session.exec(
        select(Delegation).where(
            Delegation.mandant_id == body.mandant_id,
            Delegation.aidant_id == body.aidant_id,
            Delegation.statut == StatutDelegation.active,
        )
    ).first()
    if existing:
        raise HTTPException(400, "Une délégation active existe déjà entre ces deux personnes")

    delegation = Delegation(
        mandant_id=body.mandant_id,
        aidant_id=body.aidant_id,
        motif=body.motif,
        date_debut=horloge.aujourd_hui(),
        date_fin=date.fromisoformat(body.date_fin) if body.date_fin else None,
        cree_par_id=user.id,
        cree_le=horloge.maintenant(),
        statut=StatutDelegation.en_attente,
    )
    session.add(delegation)
    session.commit()
    session.refresh(delegation)
    journaliser_securite(
        "delegation_creee",
        acteur_id=user.id,
        cible_id=delegation.mandant_id,
        detail=f"aidant={delegation.aidant_id}",
    )
    return _lire(delegation, session, user)


#  🔴 `PATCH /delegations/{id}` A ÉTÉ RETIRÉ LE 13/09/2026, SUR ARBITRAGE (#934).
#
#  Il modifiait le `motif` et la `date_fin` d'une délégation existante, et
#  **aucun écran ne l'appelait** depuis l'origine. La question posée était :
#  *« corriger le motif ou la date de fin d'une délégation existante est-il un
#  besoin réel ? »* — la réponse a été **non**.
#
#  L'argument qui plaidait pour le garder reste vrai : révoquer puis recréer
#  impose à l'aidant de ré-accepter, et laisse deux entrées dans l'historique
#  pour une faute de frappe. Mais il décrit un inconfort dans un cas qui ne se
#  produit pas, et un endpoint d'écriture que personne n'éprouve est une surface,
#  pas une capacité.
#
#  🔒 Sa dépendance était `require_cs_or_admin` : un membre du conseil syndical
#  pouvait donc réécrire le motif d'une délégation liant deux tiers, sans que
#  ni le mandant ni l'aidant en soient informés. Le jour où le besoin se
#  manifestera, c'est CETTE question — qui a le droit de corriger — qu'il faudra
#  trancher d'abord ; la version retirée ne le faisait pas.
#
#  Le schéma `DelegationUpdate` part avec lui : un schéma d'entrée sans route
#  ne se maintient pas, il se recopie.


# ── Acceptation par l'aidant ────────────────────────────────────────────────


@router.post("/{delegation_id}/accepter", response_model=DelegationRead)
def accepter_delegation(
    delegation_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """L'aidant accepte la délégation."""
    d = ou_404(session, Delegation, delegation_id, "Délégation")
    exiger_aidant_de_la_delegation(d, user)
    if not _en_attente(d):
        #  Une phrase, pas la valeur de l'énumération (« StatutDelegation.active »), #1350.
        raise HTTPException(400, "Impossible d'accepter : cette délégation n'est plus en attente.")
    d.statut = StatutDelegation.active
    session.add(d)
    session.commit()
    invalider_statuts_lus(d.aidant_id)  # il lit désormais au titre de l'aidé (#1303)
    journaliser_securite(
        "delegation_acceptee",
        acteur_id=user.id,
        cible_id=d.mandant_id,
        detail=f"aidant={d.aidant_id}",
    )
    session.refresh(d)
    return _lire(d, session, user)


# ── Révocation ──────────────────────────────────────────────────────────────


@router.post("/{delegation_id}/revoquer", response_model=DelegationRead)
def revoquer_delegation(
    delegation_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Révoquer une délégation (par le mandant, l'aidant, ou un CS/Admin)."""
    d = ou_404(session, Delegation, delegation_id, "Délégation")

    exiger_partie_de_la_delegation(d, user)
    if d.statut in TERMINEES:
        raise HTTPException(400, "Délégation déjà terminée")

    d.statut = StatutDelegation.revoquee
    d.revoque_le = horloge.maintenant()
    d.revoque_par_id = user.id
    session.add(d)
    session.commit()
    invalider_statuts_lus(d.aidant_id)  # l'héritage cesse avec elle (#1303)
    journaliser_securite(
        "delegation_revoquee",
        acteur_id=user.id,
        cible_id=d.mandant_id,
        detail=f"aidant={d.aidant_id}",
    )
    session.refresh(d)
    return _lire(d, session, user)


# ── « Agir en tant que » — retiré (#1534) ───────────────────────────────────
#
#  Le commutateur « Agir pour… » du menu et la dépendance `get_acting_user`
#  sont partis le 02/10/2026 : aucune route ne prenait la dépendance, l'aidant
#  agissait donc sous sa propre identité. La délégation est en lecture seule.

#  🔴 `GET /delegations/mes-mandants` A ÉTÉ SUPPRIMÉ le 06/09/2026 (#801).
#
#  Sa docstring affirmait « utilisé par le switcher frontend ». C'était FAUX :
#  `Nav.svelte` lit `$currentUser.delegations_aidant`, servi par `auth.me()`.
#  L'endpoint était une seconde voie vers la même donnée, sans appelant.
#
#  ⚠️ Et les deux requêtes étaient IDENTIQUES — même filtre sur le statut, même
#  garde sur les dates (`auth.py`, construction de `delegations_aidant`). Deux
#  écritures d'une même règle d'autorisation : celle qui dit qui peut agir au
#  nom de qui. Elles avaient déjà commencé à diverger — celle-ci rendait un
#  `mandant_batiment_id` que l'autre n'a pas, et que personne ne lisait.
#
#  Une règle d'autorisation écrite deux fois se durcit une fois sur deux
#  (`CLAUDE.md`, la leçon de `_require_bailleur`). Ici la voie qui restait est
#  celle qui SERT.
