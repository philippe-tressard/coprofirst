"""Utilitaire envoi WhatsApp via whatsapp-bridge."""

import logging
from typing import Any, Callable
from urllib.parse import urlsplit

import httpx

from app.utils.demo import exiger_hors_demo
from app.utils.services import SERVICE_DIFFUSION, cle_actif, service_actif
from app.utils.whatsapp_media import image_pour_bridge, renvoi_photos

logger = logging.getLogger(__name__)


class EnvoiIncertain(Exception):
    """L'envoi n'a pas été acquitté — et rien ne dit qu'il n'a pas eu lieu.

    À distinguer d'un échec : un **échec** est établi (la requête n'a jamais
    atteint le bridge, donc rien n'a pu être remis au groupe), un envoi
    **incertain** a peut-être été remis. Les deux ne se traitent pas pareil : on
    rejoue le premier, jamais le second.
    """


#: Verdicts d'un envoi, tels qu'ils sont stockés dans `WhatsAppLog.statut`.
STATUT_ENVOYE = "envoyé"
STATUT_ECHEC = "échec"
STATUT_INCERTAIN = "incertain"
STATUT_EN_COURS = "en cours"

#: Verdicts qui interdisent de rejouer l'envoi.
#:
#: `en cours` en fait partie : une tentative engagée dont on n'a jamais vu la fin
#: (redémarrage du conteneur en plein envoi) est, du point de vue du groupe,
#: exactement un envoi incertain.
STATUTS_NON_REJOUABLES = frozenset({STATUT_ENVOYE, STATUT_INCERTAIN, STATUT_EN_COURS})

#: Délai d'attente d'une réponse du bridge.
#:
#: Le bridge chiffre le message pour chaque appareil du groupe et resynchronise
#: au besoin les sessions Signal : sur un Raspberry Pi, la réponse peut demander
#: bien plus que les 15 s d'origine. Ce délai ne garantit rien — il ne fait que
#: rendre le verdict « incertain » rare. C'est `EnvoiIncertain`, et non ce
#: nombre, qui protège du doublon.
TIMEOUT_ENVOI = 60


def _motif_du_bridge(resp) -> str | None:
    """Le champ `error` du corps JSON d'une réponse du bridge, s'il y en a un."""
    try:
        motif = resp.json().get("error")
    except (ValueError, AttributeError):
        return None
    return str(motif) if motif else None


def _poster_au_bridge(url: str, payload: dict, headers: dict, timeout: float = TIMEOUT_ENVOI):
    """POST vers le bridge, en distinguant l'échec établi du résultat inconnu.

    Un client HTTP qui n'obtient pas de réponse ne sait **rien** de ce que le
    serveur a fait. Traiter ce silence comme « rien n'est parti » puis rejouer,
    c'est fabriquer des doublons dès que le bridge est lent : le 14/08/2026,
    trois exemplaires du message « Encombrants » sont partis dans le groupe pour
    cette seule raison — le bridge dépassait le délai d'attente mais délivrait.
    Un doublon dans un groupe de copropriétaires ne se retire pas.

    Les cas où l'on **sait** que rien n'est sorti sont énumérés ici ; tout le
    reste est incertain par défaut (`standards/04-fiabilite-des-controles.md` :
    un résultat qu'on ne peut pas constater se rapporte INCONNU, jamais autre
    chose — ici, pas davantage KO que OK).
    """
    exiger_hors_demo("WhatsApp")  # rien ne part de la démo publique (#1902)
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            #  202 : le bridge a ÉMIS le message et n'a pas vu l'accusé du serveur
            #  WhatsApp dans son délai. Ce n'est ni un succès (rien n'est confirmé)
            #  ni un échec (le message est parti) — et c'est le cas le plus
            #  fréquent d'incertitude, pas un cas limite : il se produit chaque
            #  fois que la session est lente à répondre.
            #
            #  Avant le 19/08/2026 le bridge répondait 500 ici, ce qui rendait ce
            #  cas indistinguable d'un envoi jamais parti. L'historique affichait
            #  « réponse 500 du bridge » sur des messages que WhatsApp montrait
            #  remis — signalé à l'écran par l'utilisateur, double coche à l'appui.
            if resp.status_code == 202:
                raise EnvoiIncertain(
                    "message émis, accusé de réception non observé — il a très "
                    "probablement été remis au groupe"
                )
            resp.raise_for_status()
            return resp
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
        #  Aucune connexion n'a été établie : la requête n'a jamais atteint le
        #  bridge, le groupe n'a rien reçu. Rejouer est sûr.
        raise
    except httpx.HTTPStatusError as exc:
        #  Le bridge a répondu et refusé. 4xx : requête invalide (clé d'API,
        #  destinataire) — elle n'a pas été traitée. 5xx : il a échoué en cours
        #  de route, sans dire de quel côté de l'envoi.
        if exc.response.status_code < 500:
            raise
        #  502 « refusé » (12/10/2026) : le serveur WhatsApp a rendu un accusé
        #  d'ERREUR. Le message a été émis : il reste incertain, donc jamais
        #  rejoué — mais l'alerte dit pourquoi, au lieu d'un code nu.
        motif = _motif_du_bridge(exc.response)
        raison = f"réponse {exc.response.status_code} du bridge"
        raise EnvoiIncertain(f"{raison} — {motif}" if motif else raison) from exc
    except httpx.HTTPError as exc:
        #  Délai dépassé après émission, coupure en cours d'échange, réponse
        #  tronquée : le message a pu partir.
        raise EnvoiIncertain(str(exc) or exc.__class__.__name__) from exc


def verdict_envoi(envoi: Callable[[], Any]) -> tuple[str, str | None]:
    """Exécute `envoi` et rend `(statut, erreur)` — jamais « échec » sur un doute.

    Une notion, une écriture : les trois chemins d'envoi (message planifié,
    publication, test manuel) qualifiaient chacun leur résultat avec un
    `except Exception` qui écrivait « échec ». L'historique de l'administration
    affirmait donc qu'un message n'était pas parti alors qu'il l'était.
    """
    try:
        envoi()
        return STATUT_ENVOYE, None
    except EnvoiIncertain as exc:
        return STATUT_INCERTAIN, str(exc)
    except Exception as exc:
        return STATUT_ECHEC, str(exc)


#: Clés de `ConfigSite` qui décrivent le canal WhatsApp.
#:
#: Elles étaient recopiées dans QUATRE routers (publications, calendrier,
#: sondages, tickets) — et la copie de `publications` incluait `site_url` en
#: plus des autres, si bien que le lien « consulter l'application » ne pouvait
#: apparaître que dans les messages d'actualité. Une notion, une écriture
#: (`standards/02-factorisation.md` §2).
#:
#: `site_nom` en fait partie : `_build_message_restreint` nomme l'application quand
#: la publication est à public restreint (#1725 — elle s'appelait « 5Hostachy » en
#: dur) ; son adresse vient du contexte (`liens.adresse_du_site`, #2058).
CLES_CONFIG = frozenset(
    {
        cle_actif(SERVICE_DIFFUSION),
        "whatsapp_api_url",
        "whatsapp_group_jid",
        "whatsapp_footer",
        "site_nom",
    }
)


class CleBridgeRefusee(RuntimeError):
    """Le bridge répond 401 : la clé de l'API n'est pas la sienne."""


def entetes_bridge(json: bool = False) -> dict[str, str]:
    """Les en-têtes d'une requête au bridge — la clé ne se lit qu'ICI (#1596).

    Elle vient de l'environnement (`WHATSAPP_API_KEY`, celle que compose donne
    au bridge), jamais de `ConfigSite` : deux écritures d'un même secret
    divergent en silence. Toujours en EN-TÊTE — le bridge refuse la clé en
    paramètre d'URL, qui finirait dans les journaux d'accès.
    """
    from app.config import get_settings

    entetes = {"x-api-key": get_settings().whatsapp_api_key.strip()}
    if json:
        entetes["Content-Type"] = "application/json"
    return entetes


#: 🔴 Les seuls noms sous lesquels on joint le bridge (#2151) : son service Compose
#: et son conteneur, sur le réseau interne de l'installation.
#:
#: `whatsapp_api_url` s'écrit par `PUT /config`, donc par l'administrateur de la
#: copropriété — qui n'est pas l'opérateur de la plateforme (#1750). Libre, elle
#: envoyait la clé du bridge (`x-api-key`, tenue hors de `ConfigSite` exprès,
#: #1596) à l'hôte de son choix, et `GET /config/whatsapp-qr` lui renvoyait le
#: corps de n'importe quelle page du réseau interne.
HOTES_DU_BRIDGE = frozenset({"whatsapp-bridge", "hostachy_whatsapp"})


class AdresseBridgeRefusee(ValueError):
    """`whatsapp_api_url` ne désigne pas le bridge : rien ne part vers elle."""


def refus_adresse_bridge(url: str) -> str | None:
    """PURE. Pourquoi cette adresse n'est pas celle du bridge — `None` si elle l'est.

    Un schéma web, un hôte de `HOTES_DU_BRIDGE`, un port, et rien d'autre : ni
    identifiants, ni chemin, ni requête — on n'y ajoute que `/send`, `/status`
    ou `/qr`.
    """
    try:
        parts = urlsplit((url or "").strip())
        parts.port  # lève sur un port illisible (« :abc », hors bornes)
    except ValueError:
        return "Adresse illisible."
    if parts.scheme not in ("http", "https"):
        return "L'adresse du bridge commence par http:// ou https://."
    if parts.hostname not in HOTES_DU_BRIDGE:
        noms = " ou ".join(sorted(HOTES_DU_BRIDGE))
        return f"Le bridge se joint par son nom sur le réseau de l'installation : {noms}."
    if parts.username or parts.password or parts.query or parts.fragment:
        return "L'adresse du bridge ne porte ni identifiant, ni paramètre."
    if parts.path not in ("", "/"):
        return "L'adresse du bridge s'arrête au port (http://whatsapp-bridge:8090)."
    return None


def adresse_du_bridge(config: dict) -> str:
    """L'adresse du bridge, sans « / » final — `""` si elle n'est pas réglée.

    🔴 La SEULE lecture de `whatsapp_api_url` qui mène à une requête : l'adresse
    est revérifiée à chaque usage, et pas seulement à l'écriture — une valeur
    posée avant #2151, ou écrite en base par un autre chemin, ne part pas non
    plus. Lève `AdresseBridgeRefusee` si elle n'est pas celle du bridge.
    """
    url = (config.get("whatsapp_api_url") or "").strip()
    if not url:
        return ""
    motif = refus_adresse_bridge(url)
    if motif:
        raise AdresseBridgeRefusee(motif)
    return url.rstrip("/")


def config_whatsapp(session, *cles_en_plus: str) -> dict:
    """Configuration WhatsApp lue en une requête, avec d'éventuelles clés de contexte.

    Les appelants ont souvent besoin, dans la même passe, de `site_nom` ou de
    `reference_copro` pour composer leur message : les demander ici évite une
    seconde requête et surtout une seconde liste de clés à maintenir.
    """
    from sqlmodel import select

    from app.models.core import ConfigSite

    voulues = CLES_CONFIG | set(cles_en_plus)
    lignes = session.exec(select(ConfigSite).where(ConfigSite.cle.in_(voulues))).all()
    return {r.cle: r.valeur for r in lignes}


#  La COMPOSITION du message vit dans `utils/whatsapp_message.py` depuis le
#  28/09/2026 (#779) ; ré-exportée ici pour les importeurs existants.
from app.utils.whatsapp_message import (  # noqa: E402,F401
    TITRE_CONFIDENTIEL,
    construire_message,
    message_sans_contenu,
)


def envoyer_whatsapp(
    titre: str,
    contenu: str,
    urgente: bool,
    perimetre_cible: str | None,
    image_url: str | None,
    config: dict,
    public_cible: str | None = None,
    confidentiel: bool = False,
    *,
    lien: str | None = None,
) -> None:
    """Envoie un message sur le groupe WhatsApp. Silencieux en cas d'échec."""
    if not service_actif(config, SERVICE_DIFFUSION):
        return
    try:
        api_url = adresse_du_bridge(config)
    except AdresseBridgeRefusee as exc:
        logger.warning("WhatsApp : adresse du bridge refusée — %s", exc)
        return
    group_jid = config.get("whatsapp_group_jid", "").strip()
    if not api_url or not group_jid:
        logger.warning("WhatsApp activé mais whatsapp_api_url ou whatsapp_group_jid manquant.")
        return

    url = f"{api_url}/send"
    headers = entetes_bridge(json=True)

    message = construire_message(
        titre,
        contenu,
        urgente,
        perimetre_cible,
        config,
        public_cible,
        confidentiel,
        lien=lien,
    )
    payload = {"number": group_jid, "text": message}
    #  La photo ne part QUE avec le message complet : sur une actualité
    #  confidentielle ou à public restreint, l'image dirait au groupe entier ce
    #  que le texte s'abstient de dire.
    if not message_sans_contenu(public_cible, confidentiel):
        image_b64 = image_pour_bridge(image_url)
        if image_b64:
            payload["imageBase64"] = image_b64
        elif image_url:
            # La photo existe mais n'a pas pu être jointe. Le message part quand
            # même — un envoi perdu est bien pire qu'un envoi sans image — et il
            # dit où la voir plutôt que de laisser croire qu'il n'y en a pas.
            payload["text"] += renvoi_photos(config, lien)

    try:
        _poster_au_bridge(url, payload, headers)
    except httpx.HTTPStatusError as exc:
        #  🔴 413 : le bridge a refusé le CORPS, donc la photo — il ne l'a même
        #  pas lu. Le texte seul, lui, passe. Le repli juste au-dessus ne couvrait
        #  que la photo ILLISIBLE sur le disque : la garde était posée sur l'autre
        #  mode de défaillance, et le message entier était perdu (#1057,
        #  19/09/2026 — deux tickets jamais arrivés dans le groupe).
        #
        #  Une seule reprise, et seulement si c'est bien l'image qui pèse :
        #  rejouer en boucle un corps refusé ne le rendrait pas plus léger.
        if exc.response.status_code != 413 or "imageBase64" not in payload:
            logger.warning("Échec envoi WhatsApp : %s", exc)
            raise
        logger.warning(
            "Corps refusé par le bridge (413) — réémission sans la photo : %s",
            exc,
        )
        payload.pop("imageBase64")
        payload["text"] += renvoi_photos(config, lien)
        _poster_au_bridge(url, payload, headers)
    except EnvoiIncertain as exc:
        logger.warning("Envoi WhatsApp au résultat inconnu : %s", exc)
        raise
    except Exception as exc:
        logger.warning("Échec envoi WhatsApp : %s", exc)
        raise


def envoyer_whatsapp_avec_log(
    titre: str,
    contenu: str,
    urgente: bool,
    perimetre_cible: str | None,
    image_url: str | None,
    config: dict,
    public_cible: str | None = None,
    confidentiel: bool = False,
    *,
    lien: str | None = None,
) -> None:
    """Envoie un message WhatsApp et crée un log (pour background tasks)."""
    from app import contexte
    from app.models.core import WhatsAppLog
    from app.utils.whatsapp_scheduler import _prune_logs

    session = contexte.nouvelle_session()
    try:
        message = construire_message(
            titre,
            contenu,
            urgente,
            perimetre_cible,
            config,
            public_cible,
            confidentiel,
            lien=lien,
        )
        log = WhatsAppLog(label=titre, message=message)
        log.statut, log.erreur = verdict_envoi(
            #  ⚠️ `lien=lien` ICI AUSSI, et pas seulement au-dessus : le texte
            #  journalisé et le texte envoyé sont deux constructions distinctes de
            #  la même chose. L'oublier ferait apparaître dans le journal un lien
            #  que le groupe n'a jamais reçu — et c'est le journal qu'on relit
            #  quand on cherche ce qui est parti.
            lambda: envoyer_whatsapp(
                titre,
                contenu,
                urgente,
                perimetre_cible,
                image_url,
                config,
                public_cible,
                confidentiel,
                lien=lien,
            )
        )
        if log.statut == STATUT_ENVOYE:
            logger.info("Message WhatsApp '%s' envoyé.", titre)
        else:
            logger.warning("Envoi WhatsApp '%s' — %s : %s", titre, log.statut, log.erreur)
            #  🔴 Un envoi raté doit avoir un DESTINATAIRE. Il était enregistré,
            #  lisible dans Admin → WhatsApp, et personne n’allait le lire : les
            #  deux partages de ticket refusés le 19/09/2026 ont été découverts
            #  par l’utilisateur dans son fil WhatsApp (#1057, `standards/04` §7).
            from app.utils.whatsapp_alerte import alerter_envoi

            alerter_envoi(session, titre, log.statut, log.erreur)

        session.add(log)
        session.commit()
        _prune_logs(session)
    except Exception as exc:
        logger.error("Erreur lors de l'enregistrement du log WhatsApp: %s", exc)
    finally:
        session.close()


def envoyer_whatsapp_raw(text: str, config: dict) -> dict:
    """Envoie un message brut sur le groupe WhatsApp. Lève une exception en cas d'échec."""
    api_url = adresse_du_bridge(config)
    group_jid = config.get("whatsapp_group_jid", "").strip()
    if not api_url or not group_jid:
        raise ValueError("whatsapp_api_url ou whatsapp_group_jid manquant.")

    url = f"{api_url}/send"
    payload = {"number": group_jid, "text": text}

    return _poster_au_bridge(url, payload, entetes_bridge(json=True)).json()


def get_whatsapp_status(config: dict) -> dict:
    """Interroge le bridge pour connaître l'état de la connexion WhatsApp.

    Un 401 se NOMME (#1596) : la clé de l'API n'est pas celle du bridge, et
    « 401 Unauthorized » n'aurait rien dit de plus qu'une panne.
    """
    api_url = adresse_du_bridge(config)
    if not api_url:
        raise ValueError("whatsapp_api_url manquant.")

    exiger_hors_demo("WhatsApp")  # même une lecture d'état est un appel sortant (#1902)
    with httpx.Client(timeout=5) as client:
        resp = client.get(f"{api_url}/status", headers=entetes_bridge())
    if resp.status_code == 401:
        raise CleBridgeRefusee(
            "Le bridge WhatsApp refuse la clé de l'API : WHATSAPP_API_KEY n'est pas la même "
            "des deux côtés. Après toute modification de .env : "
            "docker compose up -d api whatsapp-bridge"
        )
    resp.raise_for_status()
    return resp.json()


_SIGNATURE_PNG = b"\x89PNG\r\n\x1a\n"


def qr_du_bridge(config: dict) -> bytes:
    """L'image du QR code d'appairage — une image PNG, et rien d'autre (#2151).

    Le corps de la réponse était renvoyé tel quel à l'écran : c'était la porte
    par laquelle une adresse détournée faisait lire une page du réseau interne.
    Ce qui n'est pas un PNG ne sort pas.
    """
    api_url = adresse_du_bridge(config)
    if not api_url:
        raise ValueError("whatsapp_api_url manquant.")
    exiger_hors_demo("WhatsApp")
    with httpx.Client(timeout=5) as client:
        resp = client.get(f"{api_url}/qr", headers=entetes_bridge())
    resp.raise_for_status()
    if not resp.content.startswith(_SIGNATURE_PNG):
        raise ValueError("Le bridge n'a pas rendu une image PNG.")
    return resp.content
