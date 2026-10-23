"""Admin — Validation des comptes en attente et appariement des accès.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import (
    Delegation,
    StatutDelegation,
    StatutUtilisateur,
    UserLot,
    Utilisateur,
)
from app.schemas import UserRead
from app.utils.comptes import (
    REFUS,
    comptes_en_attente as lister_comptes_en_attente,
    est_en_attente,
    marquer_decide,
)
from typing import Any
from app.utils.noms import nom_affiche
from app.utils.recuperer import ou_404
from app.utils.cloche import sonner_systeme
from app.utils.journal_securite import journaliser_securite

router = APIRouter()


# ── Gestion des comptes ──────────────────────────────────────────────────────


class CompteEnAttenteItem(BaseModel):
    """User en attente enrichi du nombre de lots trouvés dans l'import."""

    user: UserRead
    lots_prevus: int  # 0 = pas dans l'import Lots


class CompteTraiteResult(BaseModel):
    """Résultat de la validation / refus d'un compte."""

    user: UserRead
    auto_match: dict[str, Any] = {}


@router.get("/comptes-en-attente", response_model=list[UserRead])
def comptes_en_attente(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    #  La définition de « en attente » vit dans `utils/comptes.py`, et nulle part
    #  ailleurs : elle était écrite ici, dans la variante enrichie et dans le
    #  compteur du tableau de bord — trois fois la même erreur (#399).
    return lister_comptes_en_attente(session)


@router.get("/comptes-en-attente/enrichis", response_model=list[CompteEnAttenteItem])
def comptes_en_attente_enrichis(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Comptes en attente enrichis du nombre de lots trouvés dans l'import.
    Permet à l'admin de vérifier si un copropriétaire est bien dans le fichier Lots."""
    from app.utils.auto_match_service import count_lots_for_user

    users = lister_comptes_en_attente(session)
    return [
        CompteEnAttenteItem(
            user=UserRead.model_validate(u),
            lots_prevus=count_lots_for_user(u.nom, u.prenom, session),
        )
        for u in users
    ]


class CompteAction(BaseModel):
    action: str  # valider | refuser
    motif: str | None = None


@router.post("/comptes/{user_id}/traiter", response_model=CompteTraiteResult)
def traiter_compte(
    user_id: int,
    body: CompteAction,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_cs_or_admin),
):
    user = ou_404(session, Utilisateur, user_id, "Utilisateur")
    #  🔴 On ne traite que ce que la file propose (#2152) : un compte déjà décidé
    #  — validé, refusé, ou désactivé par l'administration — ne se rouvre pas ici,
    #  où le conseil syndical passe. Réactiver est `PATCH /admin/utilisateurs/{id}`,
    #  réservé à l'administrateur.
    if not est_en_attente(user):
        raise HTTPException(409, "Ce compte n'attend plus de décision.")
    if body.action == "valider":
        user.actif = True
        notif_titre = "Votre compte a été activé"
        notif_corps = "Bienvenue sur l'application de la résidence."
    elif body.action == "refuser":
        notif_titre = "Votre compte n'a pas pu être activé"
        notif_corps = body.motif or "Contactez le conseil syndical pour plus d'informations."
    else:
        raise HTTPException(400, "Action invalide (valider | refuser)")

    #  Les DEUX issues sont une décision. Le refus n'écrivait rien du tout : il
    #  envoyait un e-mail, laissait `actif` à False, et le compte remontait dans
    #  la file au chargement suivant — indéfiniment, sans qu'aucun écran ne
    #  puisse distinguer « refusé » de « jamais traité » (#399).
    marquer_decide(user, None if body.action == "valider" else REFUS)

    sonner_systeme(
        session,
        "compte",
        destinataire_id=user.id,
        type="system",
        titre=notif_titre,
        corps=notif_corps,
    )
    session.add(user)

    # ── Email de confirmation au résident ─────────────────────────────────
    if user.email:
        from app.utils.email import send_email

        email_code = "compte_active" if body.action == "valider" else "compte_refuse"
        email_ctx: dict[str, Any] = {
            "destinataire": {"prenom": user.prenom, "nom": user.nom},
        }
        if body.action == "refuser" and body.motif:
            email_ctx["motif"] = body.motif
        background_tasks.add_task(
            send_email,
            code=email_code,
            to=user.email,
            context=email_ctx,
        )

    # Auto-match sur les 3 systèmes d'import dès qu'un compte est validé
    auto_match_result: dict[str, Any] = {}
    mandant_auto_id: int | None = None  # délégation posée d'office (aidant)
    if body.action == "valider":
        from app.utils.auto_match_service import (
            auto_match_pour_utilisateur,
            notifier_gestionnaire_appariement,
        )

        auto_match_result = auto_match_pour_utilisateur(user, session)
        # Des accès ont pu être créés sans validation préalable : le
        # gestionnaire du site doit pouvoir le vérifier sans aller le chercher.
        notifier_gestionnaire_appariement(user, auto_match_result, background_tasks, session)

        # ── Aidant / mandataire : copier lots, TC, vigik de l'aidé ───────
        if (
            user.statut in (StatutUtilisateur.aidant, StatutUtilisateur.mandataire)
            and user.nom_aide
            and user.prenom_aide
        ):
            from sqlalchemy import func

            aide = session.exec(
                select(Utilisateur).where(
                    func.lower(Utilisateur.nom) == user.nom_aide.strip().lower(),
                    func.lower(Utilisateur.prenom) == user.prenom_aide.strip().lower(),
                    Utilisateur.actif == True,  # noqa: E712
                )
            ).first()
            aide_result = {
                "aide_trouve": False,
                "lots": 0,
                "tc": 0,
                "vigik": 0,
                "delegation": False,
            }
            if aide:
                aide_result["aide_trouve"] = True
                aide_result["aide_nom"] = nom_affiche(aide.prenom, aide.nom)
                # Copier les lots
                aide_lots = session.exec(
                    select(UserLot).where(UserLot.user_id == aide.id, UserLot.actif == True)  # noqa: E712
                ).all()
                for ul in aide_lots:
                    exists = session.exec(
                        select(UserLot).where(
                            UserLot.user_id == user.id, UserLot.lot_id == ul.lot_id
                        )
                    ).first()
                    if not exists:
                        session.add(
                            UserLot(
                                user_id=user.id,
                                lot_id=ul.lot_id,
                                type_lien=ul.type_lien,
                                quote_part=ul.quote_part,
                            )
                        )
                        aide_result["lots"] += 1
                #  🔴 Les badges ne se COPIENT plus (#1194) : chaque copie créait
                #  un second objet pour le même badge physique, que l'unicité du
                #  code refuse désormais. Rattaché aux lots de l'aidé, l'aidant
                #  en porte les badges par la règle du lot — on les compte.
                session.flush()
                from app.utils.porteurs_acces import acces_de
                from app.utils.types_acces import TELECOMMANDE, VIGIK

                aide_result["tc"] = len(acces_de(session, TELECOMMANDE, user.id))
                aide_result["vigik"] = len(acces_de(session, VIGIK, user.id))
                # Créer la délégation automatiquement
                existing_del = session.exec(
                    select(Delegation).where(
                        Delegation.mandant_id == aide.id,
                        Delegation.aidant_id == user.id,
                        Delegation.statut.in_(
                            [StatutDelegation.en_attente, StatutDelegation.active]
                        ),
                    )
                ).first()
                if not existing_del:
                    session.add(
                        Delegation(
                            mandant_id=aide.id,
                            aidant_id=user.id,
                            motif="Affectation automatique à l'activation du compte",
                            cree_par_id=admin.id,
                            statut=StatutDelegation.active,
                        )
                    )
                    aide_result["delegation"] = True
                    mandant_auto_id = aide.id
            auto_match_result["aide_match"] = aide_result

    session.commit()
    #  Le geste qui OUVRE l'accès, et le conseil syndical le fait (#1548). Le
    #  motif d'un refus reste dehors : c'est un texte libre.
    journaliser_securite(
        "compte_valide" if body.action == "valider" else "compte_refuse",
        acteur_id=admin.id,
        cible_id=user.id,
    )
    if mandant_auto_id is not None:
        #  Posée d'office ET active : l'aidant lit dès maintenant au nom de l'aidé.
        journaliser_securite(
            "delegation_creee",
            acteur_id=admin.id,
            cible_id=mandant_auto_id,
            detail=f"aidant={user.id} automatique",
        )
    session.refresh(user)
    return CompteTraiteResult(user=UserRead.model_validate(user), auto_match=auto_match_result)


@router.post("/utilisateurs/{user_id}/auto-match", status_code=200)
def relancer_auto_match(
    user_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Rejoue le match automatique (lots, vigik, TC) pour un utilisateur déjà validé.
    Utile quand un import a été résolu après la validation du compte."""
    user = ou_404(session, Utilisateur, user_id, "Utilisateur")
    from app.utils.auto_match_service import auto_match_pour_utilisateur

    result = auto_match_pour_utilisateur(user, session)
    session.commit()
    return {"ok": True, "auto_match": result}
