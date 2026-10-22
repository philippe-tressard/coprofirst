"""
Configuration du site — paramètres admin persistants en base de données.
Remplace le localStorage pour permettre la synchronisation multi-appareils.
"""

from html import escape
from typing import Dict
from app.utils import horloge

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from app.auth.deps import require_admin
from app.utils.services import (
    CLES_ACTIVATION,
    SERVICE_REPONSES_COURRIEL,
    normaliser_activation,
    refus_d_activation,
    service_actif,
)
from app.database import get_session
from app.models.core import ConfigSite, Utilisateur
from app.utils.destinataires import peut_gerer_le_site
from app.utils import demo, pied_de_page, reglages
from app.utils.config_site import config_site
from app.utils.conservation_politique import apres_ecriture
from app.utils.liens import adresse_du_site, nom_site
from app.utils.recuperer import ou_404
from app.utils.textes_legaux.relecture import CLE_RELECTURE, TEXTES

router = APIRouter(prefix="/config", tags=["config"])

#  Les textes légaux ont leurs routes (`routers/textes_legaux.py`), et leur relecture
#  son geste : aucun ne passe par `/config/admin`.
_LEGAL_KEYS = {*TEXTES, CLE_RELECTURE}

# ─────────────────────────────────────────────────────────────────────────────
#  LISTE BLANCHE des clés exposables SANS authentification.
#
#  ⚠️ Ne rien ajouter ici sans se demander : « accepterais-je de le lire dans un
#  résultat de moteur de recherche ? » Cet endpoint est public : tout ce qui y
#  figure est lisible par n'importe qui, et indexable.
#
#  POURQUOI une liste blanche (audit du 26/07/2026) — ce filtre était une liste
#  NOIRE (`_PRIVATE_KEYS = {'whatsapp_api_key', 'smtp_password'}`) : toute clé non
#  explicitement interdite était publiée. Correct avec cinq clés de configuration,
#  devenu une fuite à mesure qu'elles s'accumulaient — 31 clés étaient exposées, dont
#  toute la configuration SMTP sauf le mot de passe (serveur, identifiant, port),
#  l'URL interne du bridge WhatsApp, l'identifiant du groupe privé, la référence de
#  copropriété du syndic, et un LIEN D'INVITATION FONCTIONNEL au groupe WhatsApp des
#  résidents. Une liste noire échoue en s'ouvrant ; une liste blanche échoue en se
#  fermant. La donnée manquante casse un écran — visible, corrigible ; la donnée en
#  trop fuit en silence.
#
#  Clés retenues = strictement celles lues hors session (écran de connexion, pages
#  légales) et par la coquille de l'interface (navigation, titres de pages).
#  Tout le reste passe par `GET /config/admin`, protégé par `require_admin`.
# ─────────────────────────────────────────────────────────────────────────────
_PUBLIC_KEYS = {
    "site_nom",  # titre de l'onglet et en-tête, écran de connexion inclus
    "site_url",  # liens des pages légales
    "site_logo",  # nom du logo téléversé (#1728) : sa présence, et l'invalidation du cache
    "login_sous_titre",  # sous-titre de l'écran de connexion
    "pages_order",  # ordre des entrées de navigation
} | pied_de_page.CLES_PUBLIQUES  # le pied de page : tout ce qu'il affiche est déjà public
# Titres et descriptifs des pages, consommés par `getPageConfig()` côté front.
_PUBLIC_PREFIXES = ("page_config_",)


def _est_public(cle: str) -> bool:
    return cle in _PUBLIC_KEYS or cle.startswith(_PUBLIC_PREFIXES)


#: 🔴 Les clés dont la VALEUR ne sort jamais, même pour un administrateur.
#:
#: `GET /config/admin` renvoyait `smtp_password` en clair (03/09/2026). L'écran ne
#: l'affichait pas — il s'en servait pour savoir si un mot de passe était posé —
#: mais il était bien dans la réponse HTTP : lisible dans l'onglet réseau du
#: navigateur, dans un cache, dans une capture d'écran de débogage.
#:
#: Un secret qu'un écran n'affiche pas mais que l'API transmet est un secret
#: exposé : la protection est alors dans le rendu, c'est-à-dire nulle part.
#:
#: ⚠️ Le marqueur conserve ce dont l'écran a besoin — savoir si la valeur EXISTE —
#: sans transmettre laquelle. C'est pourquoi il n'est pas une chaîne vide.
_SECRETS = {"smtp_password", "imap_password", "llm_api_key"}

#: Ce que l'API renvoie à la place. L'écran teste sa présence, jamais sa valeur.
MARQUEUR_SECRET = "••••••••"


def _valeur_pour_admin(cle: str, valeur: str) -> str:
    """La valeur telle qu'un administrateur a le droit de la LIRE."""
    if cle in _SECRETS and valeur:
        return MARQUEUR_SECRET
    return valeur


#: Les clés dont la VALEUR se normalise à l'enregistrement. `site_url` en était la
#: première (11/09/2026, un lien en `//tickets/34`) ; il ne s'enregistre plus (#2058).
_NORMALISEURS = {
    **pied_de_page.NORMALISEURS,
    #  L'activation d'un service ne s'écrit que `"1"` ou `"0"` (#1718) : la
    #  lecture unique (`service_actif`) n'en accepte pas d'autre.
    **{cle: normaliser_activation for cle in CLES_ACTIVATION},
}


@router.get("", response_model=Dict[str, str])
def get_config(session: Session = Depends(get_session)):
    """Clés de configuration de l'interface exposables **sans authentification**.

    Filtrage par liste blanche (`_PUBLIC_KEYS` / `_PUBLIC_PREFIXES`) : une clé
    inconnue n'est pas publiée. Les contenus légaux ont leur propre endpoint
    (`/config/legal`), la configuration complète est réservée à l'admin
    (`/config/admin`).
    """
    rows = session.exec(select(ConfigSite)).all()
    publiques = {r.cle: r.valeur for r in rows if _est_public(r.cle)}
    publiques |= {"site_url": adresse_du_site()}  # dérivée, jamais lue en base (#2058)
    #  Calculée, jamais lue en base : le front apprend ainsi qu'il sert la démo (#1901).
    publiques[demo.CLE_PUBLIQUE] = "1" if demo.est_demo() else "0"
    return publiques


@router.get("/admin", response_model=Dict[str, str])
def get_config_admin(
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Retourne toutes les clés de configuration, y compris les clés privées (admin uniquement)."""
    rows = session.exec(select(ConfigSite)).all()
    lues = {r.cle: _valeur_pour_admin(r.cle, r.valeur) for r in rows if r.cle not in _LEGAL_KEYS}
    return lues | {"site_url": adresse_du_site()}  # dérivée (#2058)


@router.put("")
def save_config(
    data: Dict[str, str],
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Sauvegarde ou met à jour des clés de configuration (admin uniquement)."""
    gestionnaire = (data.get("site_manager_user_id") or "").strip()
    if gestionnaire and not (
        gestionnaire.isdigit() and peut_gerer_le_site(session.get(Utilisateur, int(gestionnaire)))
    ):
        raise HTTPException(422, "Le gestionnaire du site doit être un administrateur.")
    #  🔴 Liste blanche (#2055) : une clé non déclarée n'est pas écrite — et rien
    #  ne l'est, la requête entière est refusée avant la première écriture.
    for cle in data:
        refus = reglages.refus_d_ecriture(cle)
        if refus:
            raise HTTPException(422, refus)
    for cle, valeur in data.items():
        if cle in _NORMALISEURS:
            valeur = _NORMALISEURS[cle](valeur)
        existing = session.get(ConfigSite, cle)
        refus = refus_d_activation(cle, valeur, existing.valeur if existing else None)
        if refus:
            raise HTTPException(409, refus)
        if existing:
            existing.valeur = str(valeur)
            session.add(existing)
        else:
            session.add(ConfigSite(cle=cle, valeur=str(valeur)))
        apres_ecriture(session, cle, str(valeur))
    session.commit()
    return {"ok": True}


# ── WhatsApp scheduled messages ──────────────────────────────────────


class WhatsAppScheduledUpdate(BaseModel):
    label: str | None = None
    message: str | None = None
    cron_rule: str | None = None
    enabled: bool | None = None


@router.get("/whatsapp-scheduled")
def list_whatsapp_scheduled(
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Liste les messages WhatsApp planifiés."""
    from app.models.core import WhatsAppScheduled

    rows = session.exec(select(WhatsAppScheduled).order_by(WhatsAppScheduled.id)).all()
    return [
        {
            "id": r.id,
            "label": r.label,
            "message": r.message,
            "cron_rule": r.cron_rule,
            "enabled": r.enabled,
            "mis_a_jour_le": r.mis_a_jour_le.isoformat() if r.mis_a_jour_le else None,
        }
        for r in rows
    ]


@router.put("/whatsapp-scheduled/{item_id}")
def update_whatsapp_scheduled(
    item_id: int,
    data: WhatsAppScheduledUpdate,
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Met à jour un message WhatsApp planifié."""
    from app.models.core import WhatsAppScheduled

    item = ou_404(session, WhatsAppScheduled, item_id, "Message planifié")
    if data.label is not None:
        item.label = data.label
    if data.message is not None:
        item.message = data.message
    if data.cron_rule is not None:
        item.cron_rule = data.cron_rule
    if data.enabled is not None:
        item.enabled = data.enabled
    item.mis_a_jour_le = horloge.maintenant()
    session.add(item)
    session.commit()
    return {"ok": True}


@router.get("/whatsapp-logs")
def list_whatsapp_logs(
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Retourne les 6 derniers messages WhatsApp envoyés, avec le canal qui les reçoit.

    Le « Nom du canal » (`whatsapp_group_name`, Admin › WhatsApp) est lu ICI (#2059) : il
    était écrit par l'onglet et lu par personne. Il nomme le groupe de la résidence dans
    le journal — le nom courant, un seul canal étant configuré.
    """
    from app.models.core import WhatsAppLog

    canal = (config_site(session, "whatsapp_group_name").get("whatsapp_group_name") or "").strip()
    rows = session.exec(select(WhatsAppLog).order_by(WhatsAppLog.envoye_le.desc()).limit(6)).all()
    return [
        {
            "id": r.id,
            "canal": canal,
            "label": r.label,
            "message": r.message,
            "statut": r.statut,
            "erreur": r.erreur,
            "envoye_le": r.envoye_le.isoformat() if r.envoye_le else None,
        }
        for r in rows
    ]


class WhatsAppTestPayload(BaseModel):
    message: str


@router.post("/whatsapp-test")
def whatsapp_test(
    payload: WhatsAppTestPayload,
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Envoie un message de test sur le groupe WhatsApp (admin uniquement)."""
    from app.utils.whatsapp import (
        STATUT_ENVOYE,
        STATUT_INCERTAIN,
        envoyer_whatsapp_raw,
        verdict_envoi,
    )
    from app.models.core import WhatsAppLog
    from app.utils.whatsapp_scheduler import _prune_logs

    rows = session.exec(select(ConfigSite)).all()
    config = {r.cle: r.valeur for r in rows}

    text = (payload.message or "").strip()
    if not text:
        raise HTTPException(400, "Le message ne peut pas être vide.")

    log = WhatsAppLog(label="Test manuel", message=text)
    resultat: dict = {}

    def _envoyer() -> None:
        resultat.update(envoyer_whatsapp_raw(text, config) or {})

    log.statut, log.erreur = verdict_envoi(_envoyer)
    session.add(log)
    session.commit()
    # Garder seulement les 6 derniers
    _prune_logs(session)

    if log.statut == STATUT_ENVOYE:
        return {"ok": True, "message": "Message envoyé sur le groupe WhatsApp.", "detail": resultat}
    if log.statut == STATUT_INCERTAIN:
        #  Ne pas présenter un doute comme un échec : renvoyer sur ce bouton
        #  après un délai dépassé est précisément ce qui crée les doublons.
        raise HTTPException(
            502,
            "Le bridge n'a pas répondu à temps : le message est peut-être arrivé. "
            "Vérifiez le groupe WhatsApp avant de renvoyer.",
        )
    raise HTTPException(500, f"Échec de l'envoi : {log.erreur}")


@router.get("/whatsapp-status")
def whatsapp_status(
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Retourne l'état de la connexion WhatsApp (admin uniquement)."""
    from app.utils.whatsapp import get_whatsapp_status

    rows = session.exec(select(ConfigSite)).all()
    config = {r.cle: r.valeur for r in rows}

    try:
        return get_whatsapp_status(config)
    except Exception as e:
        raise HTTPException(500, f"Impossible de joindre le bridge : {e}")


@router.get("/whatsapp-qr")
def whatsapp_qr(
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Retourne l'image QR code du bridge WhatsApp (admin uniquement)."""
    import httpx

    rows = session.exec(select(ConfigSite)).all()
    config = {r.cle: r.valeur for r in rows}

    from app.utils.whatsapp import entetes_bridge

    api_url = config.get("whatsapp_api_url", "").strip()
    if not api_url:
        raise HTTPException(400, "whatsapp_api_url non configuré.")

    demo.exiger_hors_demo("WhatsApp")  # doublé par la garde du lot D1 (#1902)
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{api_url.rstrip('/')}/qr", headers=entetes_bridge())
            resp.raise_for_status()
            return Response(content=resp.content, media_type="image/png")
    except Exception as e:
        raise HTTPException(500, f"Impossible d'obtenir le QR code : {e}")


class SmtpTestPayload(BaseModel):
    email: EmailStr


@router.post("/smtp-test")
async def smtp_test(
    payload: SmtpTestPayload,
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Envoie un e-mail de test à l'adresse fournie en utilisant la config SMTP actuelle (admin uniquement)."""
    from app.utils.email import _get_smtp_config, connexion_smtp, envoi_actif
    from app.utils.smtp import adresses_a_tester

    smtp_cfg = _get_smtp_config(session)

    #  La règle de l'ENVOI, pas une recopie (#1718) : elle disait « actif » quand
    #  la base désactivait l'envoi et que l'environnement l'activait.
    if not envoi_actif(session):
        raise HTTPException(400, "L'envoi d'e-mails est désactivé. Activez-le avant de tester.")

    #  UN envoi PAR ADRESSE d'expédition configurée (#756). Le test n'en exerçait
    #  qu'une, alors que deux servent désormais selon l'intention du message : un
    #  serveur qui refuse la seconde — cas courant quand elle est un ALIAS et non
    #  un compte — passait le test et échouait sur un vrai ticket.
    adresses = adresses_a_tester(smtp_cfg)
    #  Le nom de CETTE résidence, lu dans sa configuration (#1725) : il était
    #  écrit « 5Hostachy » trois fois dans ce message.
    nom = nom_site(config_site(session).get("site_nom"))
    site = escape(nom)
    envoyees: list[str] = []
    try:
        from fastapi_mail import FastMail, MessageSchema

        for adresse in adresses:
            cfg = connexion_smtp(smtp_cfg, expediteur=adresse)
            fm = FastMail(cfg)
            msg = MessageSchema(
                subject=f"[{nom}] Test de configuration SMTP — depuis {adresse}",
                recipients=[payload.email],
                body=(
                    "<p>Bonjour,</p>"
                    "<p>Ceci est un e-mail de test envoyé depuis l'interface "
                    f"d'administration de <strong>{site}</strong>.</p>"
                    f"<p>Il part de <strong>{adresse}</strong>. Si vous recevez un message "
                    "pour chacune des adresses configurées, l'envoi fonctionne pour les "
                    "deux ✅</p>"
                    f"<p style='color:#64748b;font-size:.85em'>— {site}</p>"
                ),
                subtype="html",
            )
            await fm.send_message(msg)
            envoyees.append(adresse)
    except Exception as e:
        #  Dire ce qui est DÉJÀ parti : sans cela, un échec sur la seconde adresse
        #  se lirait comme un échec total, et on chercherait la panne du côté du
        #  serveur alors que seule l'adresse ajoutée est en cause.
        deja = f" ({len(envoyees)} déjà envoyé depuis {', '.join(envoyees)})" if envoyees else ""
        raise HTTPException(500, f"Échec de l'envoi depuis {adresses[len(envoyees)]}{deja} : {e}")
    return {
        "ok": True,
        "message": (
            f"{len(envoyees)} e-mail(s) de test envoyé(s) à {payload.email}, "
            f"depuis {', '.join(envoyees)}"
        ),
    }


@router.post("/imap-test")
def imap_test(
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Ouvre la boîte des réponses et rend ce qu'elle contient (admin uniquement).

    🔴 Ce test existe parce qu'un réglage qu'on ne peut pas éprouver est un
    réglage qu'on croit bon. Il ne se contente pas de se connecter : il compte les
    messages **non lus**, c'est-à-dire exactement ce que la relève traitera.

    ⚠️ Il ne TRAITE rien et ne marque rien comme lu — le lancer dix fois ne change
    rien à l'état de la boîte. C'est ce qui le rend utilisable pour tâtonner sur
    les paramètres OVH sans conséquence.
    """
    import imaplib

    from app.utils.courriel_boite import config_imap

    cfg = config_imap(session)
    manquants = [c for c in ("imap_server", "imap_username", "imap_password") if not cfg.get(c)]
    if manquants:
        raise HTTPException(400, "Paramètre(s) manquant(s) : " + ", ".join(manquants))

    dossier = cfg.get("imap_dossier") or "INBOX"
    demo.exiger_hors_demo("Boîte de réception")  # doublé par la garde du lot D1 (#1902)
    try:
        boite = imaplib.IMAP4_SSL(cfg["imap_server"], int(cfg.get("imap_port") or 993))
    except Exception as e:
        raise HTTPException(502, f"Connexion au serveur impossible : {e}")
    try:
        try:
            boite.login(cfg["imap_username"], cfg["imap_password"])
        except Exception as e:
            raise HTTPException(401, f"Identifiants refusés par le serveur : {e}")
        statut, _ = boite.select(dossier, readonly=True)
        if statut != "OK":
            raise HTTPException(404, f"Dossier « {dossier} » introuvable sur ce compte.")
        _st, donnees = boite.search(None, "UNSEEN")
        non_lus = len(donnees[0].split()) if donnees and donnees[0] else 0
    finally:
        try:
            boite.logout()
        except Exception:
            pass

    actif = service_actif(cfg, SERVICE_REPONSES_COURRIEL)
    return {
        "ok": True,
        "non_lus": non_lus,
        "dossier": dossier,
        "actif": actif,
        "message": (
            f"Connexion réussie — {non_lus} message(s) non lu(s) dans « {dossier} ». "
            + (
                "La relève est active."
                if actif
                else "⚠️ La relève est INACTIVE : cochez « Relever les réponses » et enregistrez."
            )
        ),
    }
