"""Mot de passe : changement, oubli, réinitialisation.

Extrait de `routers/auth.py` le 14/08/2026, au fil de l'eau : ce fichier avait
atteint 736 lignes et le contrôle de modularité refuse qu'un fichier déjà
au-dessus de 500 grossisse (rang 1 §4). Il fallait y ajouter cinq lignes pour la
préférence d'affichage du profil (#339).

Ce bloc-ci est celui qui s'en détache le plus proprement : trois routes qui ne
partagent avec le reste ni état ni schéma, et dont le sujet — prouver qu'on est
soi quand on a perdu son mot de passe — a ses propres raisons de changer.

Le router porte le même préfixe `/auth` et est monté à part dans `main.py` :
FastAPI additionne les routers, les URL publiques sont donc rigoureusement
inchangées. `api/tests/test_endpoints_orphelins.py` le vérifie.
"""

from datetime import timedelta
from app.utils import horloge
import secrets

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from app.utils.config_site import config_site
from app.utils.journal_securite import journaliser_securite
from app.auth.adresse_compte import compte_par_adresse
from app.auth.deps import get_current_user
from app.auth.empreinte_jeton import empreinte
from app.auth.jwt import verify_password
from app.database import get_session
from app.models.core import PasswordResetToken, Utilisateur
from app.utils.limiter import LIMITE_COURRIEL_DECLENCHE, LIMITE_SECRET_EPROUVE, limiter
from app.utils.mots_de_passe import poser_mot_de_passe
from app.utils.mots_de_passe import verifier_robustesse as _check_password_strength
from app.utils.liens import adresse_du_site, nom_site

router = APIRouter(prefix="/auth", tags=["auth"])


class ChangePasswordBody(BaseModel):
    mot_de_passe_actuel: str
    nouveau_mot_de_passe: str


@router.post("/change-password", status_code=204)
@limiter.limit(LIMITE_SECRET_EPROUVE)
def change_password(
    request: Request,
    body: ChangePasswordBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
    refresh_token: str | None = Cookie(default=None),
):
    """Change son mot de passe, et ferme les autres sessions du compte.

    🔴 Cette route n'avait **ni** limitation de débit — alors qu'elle éprouve un
    mot de passe en `verify_password` — **ni** révocation de session : la porte
    jumelle (`reset_password`) révoquait, celle-ci non (#1027). La session de
    l'appelant survit ; toutes les autres tombent.
    """
    if not verify_password(body.mot_de_passe_actuel, user.hashed_password or ""):
        journaliser_securite("connexion_refusee", cible_id=user.id, detail="mot de passe actuel")
        raise HTTPException(400, "Mot de passe actuel incorrect.")
    poser_mot_de_passe(session, user, body.nouveau_mot_de_passe, jeton_courant=refresh_token)
    #  Acteur ET cible : on agit sur soi-même, et la ligne le dit sans cas
    #  particulier chez l'appelant.
    journaliser_securite("mot_de_passe_change", acteur_id=user.id, cible_id=user.id)
    session.commit()


class PasswordResetRequest(BaseModel):
    email: str


@router.post("/mot-de-passe-oublie", status_code=204)
@limiter.limit(LIMITE_COURRIEL_DECLENCHE)
def request_password_reset(
    request: Request,
    body: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    Génère un token de réinitialisation et envoie un e-mail si le compte existe.
    Retourne toujours 204 pour éviter l'enumération d'adresses e-mail.
    """
    cfg = config_site(session)
    site_url = adresse_du_site()
    site_nom = nom_site(cfg.get("site_nom"))

    user = compte_par_adresse(session, body.email)
    if user and user.actif:
        # Invalider les tokens de reset précédents non utilisés
        old_tokens = session.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used == False,  # noqa: E712
            )
        ).all()
        for t in old_tokens:
            t.used = True
            session.add(t)

        raw_token = secrets.token_urlsafe(32)
        prt = PasswordResetToken(
            user_id=user.id,
            token=empreinte(raw_token),
            expires_at=horloge.maintenant() + timedelta(hours=1),
        )
        session.add(prt)
        session.commit()

        from app.utils.email import send_email

        background_tasks.add_task(
            send_email,
            code="reinitialisation_mdp",
            to=user.email,
            context={
                "destinataire": {"prenom": user.prenom},
                "lien": f"{site_url}/auth/reinitialisation-mdp?token={raw_token}",
                "expire_heures": 1,
                "residence": {"nom": site_nom},
                "app": {"url": site_url},
            },
        )

    return None


class PasswordResetConfirm(BaseModel):
    token: str
    nouveau_mot_de_passe: str


@router.post("/reinitialiser-mot-de-passe", status_code=204)
@limiter.limit(LIMITE_SECRET_EPROUVE)
def reset_password(
    request: Request,
    body: PasswordResetConfirm,
    session: Session = Depends(get_session),
):
    """Utilise le token de réinitialisation pour définir un nouveau mot de passe."""
    #  La robustesse est vérifiée AVANT de chercher le jeton : un refus ne doit
    #  pas brûler le lien pour une faute de frappe. `poser_mot_de_passe` la
    #  revérifie — deux appels sur la même règle ne coûtent rien et gardent
    #  l'ordre intact.
    _check_password_strength(body.nouveau_mot_de_passe)

    prt = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.token == empreinte(body.token))
    ).first()

    if not prt or prt.used or prt.expires_at < horloge.maintenant():
        raise HTTPException(400, "Lien de réinitialisation invalide ou expiré.")

    user = session.get(Utilisateur, prt.user_id)
    if not user or not user.actif:
        raise HTTPException(400, "Lien de réinitialisation invalide ou expiré.")

    #  Aucun jeton courant n'est conservé : on réinitialise parce qu'on craint
    #  que quelqu'un d'autre soit entré, et l'appelant n'est pas authentifié.
    poser_mot_de_passe(session, user, body.nouveau_mot_de_passe)
    #  🔴 En WARNING, et pas au même niveau qu'un changement ordinaire : c'est le
    #  chemin qu'emprunterait quelqu'un qui a pris la boîte mail. `acteur_id`
    #  reste None — la route n'est pas authentifiée, et c'est l'information.
    journaliser_securite("mot_de_passe_reinitialise", cible_id=user.id)
    prt.used = True

    session.add(prt)
    session.commit()
    return None
