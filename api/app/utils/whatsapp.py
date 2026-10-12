"""Utilitaire envoi WhatsApp via whatsapp-bridge."""

import logging
from typing import Any, Callable

import httpx

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
#: `site_url` fait partie de l'ensemble : `_build_message_restreint` en a besoin
#: pour renvoyer vers l'application quand la publication est à public restreint ;
#: `site_nom` aussi, pour la nommer (#1725 — elle s'appelait « 5Hostachy » en dur).
CLES_CONFIG = frozenset(
    {
        cle_actif(SERVICE_DIFFUSION),
        "whatsapp_api_url",
        "whatsapp_group_jid",
        "whatsapp_footer",
        "site_url",
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
    api_url = config.get("whatsapp_api_url", "").strip()
    group_jid = config.get("whatsapp_group_jid", "").strip()
    if not api_url or not group_jid:
        logger.warning("WhatsApp activé mais whatsapp_api_url ou whatsapp_group_jid manquant.")
        return

    url = f"{api_url.rstrip('/')}/send"
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
    api_url = config.get("whatsapp_api_url", "").strip()
    group_jid = config.get("whatsapp_group_jid", "").strip()
    if not api_url or not group_jid:
        raise ValueError("whatsapp_api_url ou whatsapp_group_jid manquant.")

    url = f"{api_url.rstrip('/')}/send"
    payload = {"number": group_jid, "text": text}

    return _poster_au_bridge(url, payload, entetes_bridge(json=True)).json()


def get_whatsapp_status(config: dict) -> dict:
    """Interroge le bridge pour connaître l'état de la connexion WhatsApp.

    Un 401 se NOMME (#1596) : la clé de l'API n'est pas celle du bridge, et
    « 401 Unauthorized » n'aurait rien dit de plus qu'une panne.
    """
    api_url = config.get("whatsapp_api_url", "").strip()
    if not api_url:
        raise ValueError("whatsapp_api_url manquant.")

    with httpx.Client(timeout=5) as client:
        resp = client.get(f"{api_url.rstrip('/')}/status", headers=entetes_bridge())
    if resp.status_code == 401:
        raise CleBridgeRefusee(
            "Le bridge WhatsApp refuse la clé de l'API : WHATSAPP_API_KEY n'est pas la même "
            "des deux côtés. Après toute modification de .env : "
            "docker compose up -d api whatsapp-bridge"
        )
    resp.raise_for_status()
    return resp.json()
