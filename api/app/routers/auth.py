"""Router auth — inscription, connexion, déconnexion, refresh.

Le bloc « profil » — `GET /me`, `PATCH /me` et les demandes de modification — est
parti dans `auth_profil.py` le 09/09/2026, au fil de l'eau : ce fichier était à
561 lignes et le contrôle de modularité refuse qu'un fichier déjà au-dessus de
500 grossisse (rang 1 §4). Il fallait y ajouter l'alerte de divergence d'étage.

C'est la TROISIÈME extraction de ce fichier — après le mot de passe (14/08/2026)
et la télémétrie —, et la césure est la même à chaque fois : *prouver qu'on est
soi* reste ici, *décrire qui l'on est* s'en va. Le router garde le préfixe
`/auth` et est monté à part dans `main.py` : FastAPI additionne les routers, les
URL publiques sont donc rigoureusement inchangées.
"""

from app.utils import horloge

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, Cookie, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from app.utils.config_site import config_site
from app.utils.journal_securite import journaliser_securite
from app.auth.jwt import (
    decode_token,
    hash_password,
    verify_and_rehash,
)
from app.auth.adresse_compte import compte_par_adresse
from app.auth.session_ouverte import ouvrir_session
from app.auth.deps import get_current_user
from app.auth.empreinte_jeton import empreinte
from app.auth.jetons_rafraichissement import est_rejoue, remplacer, revoquer_sessions
from app.config import get_settings
from app.database import get_session
from app.models.core import (
    Utilisateur,
    RefreshToken,
    StatutUtilisateur,
    RoleUtilisateur,
    Batiment,
)
from app.routers.auth_schemas import LoginRequest, UserCreate
from app.schemas import UserRead
from app.utils.lecture_utilisateur import construire_user_read
from app.utils.limiter import (
    LIMITE_CONTROLE_FICHIER,
    LIMITE_COURRIEL_DECLENCHE,
    LIMITE_LECTURE_PUBLIQUE,
    LIMITE_SECRET_EPROUVE,
    LIMITE_SESSION,
    limiter,
)
from app.utils.mots_de_passe import verifier_robustesse as _check_password_strength
from app.utils.liens import adresse_du_site, nom_site

from app.utils.noms import contexte_personne
from app.utils.roles_du_statut import poser_roles_du_statut
from app.utils.verification_adresse import (
    emettre_verification_email,
    invalider_liens_en_attente,
    servir_lien,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.get("/batiments")
@limiter.limit(LIMITE_LECTURE_PUBLIQUE)
def list_batiments(request: Request, session: Session = Depends(get_session)):
    """Liste publique des bâtiments pour le formulaire d'inscription."""
    return session.exec(select(Batiment).order_by(Batiment.numero)).all()


#  La vérification d'une adresse — sa durée, l'émission du lien, ce que le servir
#  fait — vit dans `utils/verification_adresse.py` depuis le 02/10/2026 (#1549) :
#  le changement d'adresse emploie le même mécanisme, depuis deux routeurs (le
#  profil et l'administration), et un routeur n'en importe pas un autre.


@router.post("/register", response_model=UserRead, status_code=201)
@limiter.limit(LIMITE_SECRET_EPROUVE)
def register(
    request: Request,
    body: UserCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Créer un compte. Pour les profils syndic et mandataire, société et fonction sont obligatoires."""
    if body.statut in (StatutUtilisateur.syndic, StatutUtilisateur.mandataire):
        if not body.societe or not body.fonction:
            raise HTTPException(
                400,
                "Pour un profil syndic ou mandataire, la société et la fonction sont obligatoires.",
            )
    if body.statut == StatutUtilisateur.locataire:
        if not body.nom_proprietaire or not body.nom_proprietaire.strip():
            raise HTTPException(400, "Le nom du propriétaire est obligatoire pour un locataire.")
    if body.statut in (StatutUtilisateur.aidant, StatutUtilisateur.mandataire):
        if (
            not body.nom_aide
            or not body.nom_aide.strip()
            or not body.prenom_aide
            or not body.prenom_aide.strip()
        ):
            raise HTTPException(400, "Le nom et prénom du copropriétaire aidé sont obligatoires.")
    if not body.consentement_rgpd:
        raise HTTPException(400, "Le consentement RGPD est obligatoire.")
    _check_password_strength(body.password)

    if compte_par_adresse(session, body.email):
        raise HTTPException(400, "Email déjà utilisé.")

    user = Utilisateur(
        nom=body.nom,
        prenom=body.prenom,
        email=body.email,
        telephone=body.telephone,
        societe=body.societe,
        fonction=body.fonction,
        hashed_password=hash_password(body.password),
        statut=body.statut,
        role=RoleUtilisateur.résident,
        actif=False,  # en attente de validation
        consentement_rgpd=body.consentement_rgpd,
        batiment_id=body.batiment_id,
        etage=body.etage,
        nom_proprietaire=body.nom_proprietaire or None,
        nom_aide=body.nom_aide or None,
        prenom_aide=body.prenom_aide or None,
    )
    #  Les rôles que le statut confère : `utils/roles_du_statut`, la même règle
    #  qu'au changement de statut (#2161). Le syndic, le mandataire et l'aidant
    #  sont externes — consulter seulement (#1911) ; le statut reste porté par
    #  `statut`, que `profil_admet` lit (le syndic garde ses PV d'AG).
    poser_roles_du_statut(user, body.statut)
    session.add(user)
    session.commit()
    session.refresh(user)

    # ── Vérification de l'adresse : jeton + courriel, en un seul geste ──
    emettre_verification_email(session, user, background_tasks)

    #  Les autres clés servent à la notification du gestionnaire, plus bas —
    #  qui a besoin du même envoyeur.
    from app.utils.email import send_email as _send_email

    cfg = config_site(
        session,
        "notify_new_user_created_email",
        "site_manager_user_id",
        "site_email",
    )

    # Notification au gestionnaire du site
    if cfg.get("notify_new_user_created_email") == "1":
        from app.utils.email import get_site_manager_notification_email

        target_email, site_cfg = get_site_manager_notification_email(session)
        if target_email:
            background_tasks.add_task(
                _send_email,
                code="compte_en_attente",
                to=target_email,
                context={
                    "utilisateur": contexte_personne(user, email=user.email),
                    "residence": {
                        "nom": nom_site(site_cfg.get("site_nom"), cfg.get("site_nom")),
                    },
                    "app": {
                        "url": adresse_du_site(),
                    },
                },
            )

    # Si le compte est actif dès la création (cas admin ou futur flow),
    # lancer l'auto-match immédiatement
    if user.actif:
        from app.utils.auto_match_service import (
            auto_match_pour_utilisateur,
            notifier_gestionnaire_appariement,
        )

        resultat = auto_match_pour_utilisateur(user, session)
        session.commit()
        # Le résultat était jusqu'ici jeté : des accès pouvaient être créés
        # sans que personne n'en soit informé.
        notifier_gestionnaire_appariement(user, resultat, background_tasks, session)

    return user


@router.post("/login")
@limiter.limit(LIMITE_SECRET_EPROUVE)
def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
):
    user = compte_par_adresse(session, body.email)
    if not user or not user.hashed_password:
        #  🔴 L'adresse essayée ne s'écrit PAS dans le journal (#777) : la ligne dit
        #  qu'une tentative a échoué sur un compte inconnu, et cela suffit.
        journaliser_securite("connexion_refusee", detail="compte inconnu")
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect.")
    valid, new_hash = verify_and_rehash(body.password, user.hashed_password)
    if not valid:
        journaliser_securite("connexion_refusee", cible_id=user.id, detail="mot de passe")
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect.")
    if not user.actif:
        raise HTTPException(status_code=403, detail="Compte en attente de validation.")
    if not user.email_verifie:
        raise HTTPException(
            status_code=403,
            detail="Veuillez vérifier votre adresse e-mail. Consultez votre boîte de réception.",
        )
    if new_hash:
        user.hashed_password = new_hash  # rehash silencieux 12→10 rounds

    #  Jetons, empreinte, cookies — et l'activité, qui remet à zéro un
    #  avertissement de purge (#1580) : `auth/session_ouverte` (#1903).
    ouvrir_session(session, user, response)
    return construire_user_read(user, session)


@router.post("/refresh")
@limiter.limit(LIMITE_SESSION)
def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
):
    if not refresh_token:
        raise HTTPException(401, "Refresh token manquant.")
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(401, "Refresh token invalide.")

    stored = session.exec(
        select(RefreshToken).where(RefreshToken.token == empreinte(refresh_token))
    ).first()
    maintenant = horloge.maintenant()
    if stored and est_rejoue(stored, maintenant):
        #  Un jeton déjà échangé qui revient : le porteur légitime ou un voleur,
        #  on ne sait pas lequel — toutes les sessions ferment. Même réponse
        #  qu'une session expirée : le voleur n'apprend pas qu'il est repéré.
        revoquees = revoquer_sessions(session, stored.user_id)
        session.commit()
        journaliser_securite(
            "jeton_rejoue", cible_id=stored.user_id, detail=f"sessions_fermees={revoquees}"
        )
        raise HTTPException(401, "Session expirée. Reconnectez-vous.")
    if not stored or stored.revoked or stored.expires_at < maintenant:
        raise HTTPException(401, "Session expirée. Reconnectez-vous.")

    user = session.get(Utilisateur, stored.user_id)
    if not user or not user.actif:
        raise HTTPException(401, "Utilisateur invalide.")

    # Rotation : révoquer l'ancien token, émettre un nouveau
    remplacer(session, stored, maintenant)
    #  🔴 Un résident resté connecté ne repasse JAMAIS par `login` : c'est cet
    #  échange — au plus un toutes les deux heures, jamais à chaque requête — qui
    #  dit qu'il est là (`ouvrir_session` marque l'activité). Sans lui, la purge des
    #  comptes inactifs (#1580) l'aurait cru parti depuis sa dernière saisie de mot
    #  de passe.
    ouvrir_session(session, user, response, maintenant)
    return {"message": "Token rafraîchi"}


@router.post("/logout")
@limiter.limit(LIMITE_SESSION)
def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
):
    if refresh_token:
        stored = session.exec(
            select(RefreshToken).where(RefreshToken.token == empreinte(refresh_token))
        ).first()
        if stored:
            stored.revoked = True
            session.add(stored)
            session.commit()
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Déconnecté"}


@router.get("/verifier-acces", status_code=204)
@limiter.limit(LIMITE_CONTROLE_FICHIER)
def verifier_acces(request: Request, _: Utilisateur = Depends(get_current_user)) -> Response:
    """Réservé au `forward_auth` de Caddy : 204 si la session est valide, 401 sinon.

    Caddy interroge cet endpoint avant de servir un fichier de `/uploads/*`, qui
    était jusqu'ici public. Il ne renvoie **aucun contenu** : seul le code compte,
    et un corps vide évite d'exposer quoi que ce soit sur le porteur du cookie.

    Il s'appuie volontairement sur `get_current_user`, la dépendance d'authentification
    commune, et non sur une vérification allégée maison. Une seconde façon de valider
    une session serait une seconde sémantique à maintenir — et à faire diverger. Le
    coût dominant est le trajet HTTP interne, pas la lecture en base qu'elle effectue :
    l'économiser ne rapporterait presque rien et laisserait un compte désactivé
    conserver l'accès jusqu'à l'expiration de son jeton (120 min).
    """
    return Response(status_code=204)


class RenvoiVerificationRequest(BaseModel):
    email: str


@router.get("/verifier-email", status_code=200)
@limiter.limit(LIMITE_SECRET_EPROUVE)
def verify_email(request: Request, token: str, session: Session = Depends(get_session)):
    """Vérifie l'adresse email via le token reçu par mail.

    🔴 Cette route **éprouve un secret** — un jeton passé en clair dans l'URL —
    et n'avait aucune limitation de débit jusqu'au 19/09/2026 (#1027) : les
    jetons étaient énumérables au rythme que le réseau permettait.

    🔴 Un lien DÉJÀ SERVI, pour une adresse vérifiée, répond « déjà vérifiée »
    — et non « invalide » (29/09/2026). Les messageries analysent les liens
    reçus dans un vrai navigateur, qui exécute la page : le 29/09, le scanner
    de Microsoft avait consommé le jeton une minute avant que le destinataire
    clique, et celui-ci lisait en rouge l'échec d'une vérification réussie.
    Répondre ainsi ne livre rien : seul le porteur du lien connaît le jeton.

    Depuis le 02/10/2026 (#1549), le même lien confirme aussi une NOUVELLE
    adresse : la réponse porte alors `changement_adresse`, et l'écran le dit.
    """
    return servir_lien(session, token)


@router.post("/renvoyer-verification", status_code=204)
@limiter.limit(LIMITE_COURRIEL_DECLENCHE)
def resend_verification(
    request: Request,
    body: RenvoiVerificationRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Renvoie un email de vérification (si le compte existe et n'est pas encore vérifié)."""
    user = compte_par_adresse(session, body.email)

    if user and not user.email_verifie:
        #  Les liens de l'inscription seulement : un changement d'adresse en cours
        #  garde le sien.
        invalider_liens_en_attente(session, user.id, changement=False)
        emettre_verification_email(session, user, background_tasks)

    # Toujours 204 (pas d'énumération de comptes)
    return None
