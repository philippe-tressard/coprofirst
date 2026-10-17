"""Le canal SMTP : quelles clés le décrivent, et comment on s'y connecte.

Sorti de `email.py` le 08/08/2026, le jour où le garde-fou de modularité a
refusé le lot : y ajouter `connexion_smtp` faisait passer ce fichier de 656 à
663 lignes, alors qu'il dépassait déjà largement le plafond de 500.

Le découpage n'est pas qu'arithmétique. **Configurer un canal** et **composer
un message** sont deux sujets : le premier tient en trois éléments et ne change
que lorsque l'hébergeur change ; le second occupe six cents lignes de gabarits,
de rendu Jinja et de pièces jointes.

## Deux SMTP, deux niveaux, une source chacun (#2058, 17/10/2026)

| SMTP | Niveau | Source | Lu par |
|---|---|---|---|
| celui d'une COPROPRIÉTÉ — ses courriels, de sécurité compris | la copropriété | sa **base** (`ConfigSite`, écran Admin) | `connexion_smtp` |
| celui de l'INSTALLATION — les alertes à l'opérateur (`sante_plateforme`) | l'installation | le **`.env`** (`MAIL_*`) | `connexion_smtp_installation` |

`connexion_smtp` retombait champ par champ sur `MAIL_*` : une configuration à moitié
en base, à moitié dans le `.env`, sans que l'écran le montre. `MAIL_*` n'est plus,
pour une copropriété, qu'une **amorce** : `amorcer` recopie une fois, dans sa base, la
configuration que le repli produisait (rien ne change au premier démarrage), puis la
base décide seule. Sur une installation commune, seule l'adresse d'expédition
déclarée amorce : les identifiants SMTP de l'hébergeur n'entrent jamais dans la base
d'une copropriété, dont l'administrateur les lirait.
"""

from sqlmodel import Session, select

from app import contexte
from app.config import get_settings
from app.models.core import ConfigSite

#  ⚠️ `smtp_from_reponse` est la SECONDE adresse d'expédition (05/09/2026) :
#  `contact@` pour ce qui appelle une réponse, `smtp_from` (`noreply@`) pour ce
#  qui n'en appelle aucune. Une clé absente ou vide se replie sur `smtp_from` —
#  une installation qui n'a pas encore renseigné la seconde adresse continue
#  d'envoyer exactement comme avant, plutôt que depuis une adresse vide.
_SMTP_KEYS = {
    "smtp_enabled",
    "smtp_server",
    "smtp_port",
    "smtp_from",
    "smtp_from_reponse",
    #  L'adresse des AFFAIRES (#1314) : expéditeur et `Reply-To` d'un courriel
    #  d'affaire. Vide : repli sur `smtp_from_reponse`.
    "smtp_from_affaires",
    "smtp_from_name",
    "smtp_username",
    "smtp_password",
    "smtp_starttls",
    "smtp_ssl_tls",
}


def _get_smtp_config(session: Session) -> dict:
    rows = session.exec(select(ConfigSite).where(ConfigSite.cle.in_(_SMTP_KEYS))).all()
    return {r.cle: r.valeur for r in rows}


def adresse_expedition(smtp_cfg: dict, genre: str) -> str:
    """L'adresse d'expédition pour ce genre d'envoi (`expediteur_du_modele`).

    Repli explicite : sans seconde adresse configurée, tout part de `smtp_from`
    comme avant. Le silence de la configuration ne doit pas produire une adresse
    vide — un message sans expéditeur est refusé par le serveur, et l'envoi
    échouerait sans que le motif ait quoi que ce soit à voir avec son contenu.
    """
    from app.seed.emails import EXPEDITEUR_AFFAIRE, EXPEDITEUR_REPONSE

    defaut = smtp_cfg.get("smtp_from") or ""
    if genre not in (EXPEDITEUR_REPONSE, EXPEDITEUR_AFFAIRE):
        return defaut
    reponse = (smtp_cfg.get("smtp_from_reponse") or "").strip() or defaut
    if genre == EXPEDITEUR_AFFAIRE:
        #  L'adresse des affaires (#1314), repliée sur celle des réponses : une
        #  affaire appelle une réponse, elle ne part jamais de `noreply@` par oubli.
        return (smtp_cfg.get("smtp_from_affaires") or "").strip() or reponse
    return reponse


def entete_reponse(smtp_cfg: dict, jeton_reponse: str | None) -> dict[str, str]:
    """L'en-tête `Reply-To` d'un envoi d'affaire (#703), écrit ICI et nulle part
    ailleurs — à côté de l'adresse d'expédition dont il est le pendant.

    Rend un dictionnaire vide quand il n'y a pas de jeton (l'envoi n'est pas une
    affaire) ou pas d'adresse exploitable.

    🔴 **L'adresse des affaires, plus l'adresse à jeton** (#1314, 25/09/2026).
    `tickets+<jeton>@` rattachait la réponse par le jeton — mais OVH n'achemine
    pas le sous-adressage, et la réponse du syndic partait dans le vide (#754
    l'avait constaté le 05/09 et ajouté le repli par le sujet, sans changer
    l'adresse). La réponse revient désormais à l'adresse d'où l'affaire part,
    et se rattache par « Affaire #TK-… » dans le sujet.
    """
    if not jeton_reponse:
        return {}
    from app.seed.emails import EXPEDITEUR_AFFAIRE

    adresse = adresse_expedition(smtp_cfg, EXPEDITEUR_AFFAIRE)
    return {"Reply-To": adresse} if adresse else {}


def adresses_a_tester(smtp_cfg: dict) -> list[str]:
    """Les adresses d'expédition distinctes, dans l'ordre où on les éprouve.

    🔴 **Le bouton « tester » n'exerçait qu'une adresse sur deux** (05/09/2026).
    Depuis #756 un message part de `noreply@` ou de `contact@` selon son
    intention ; le test, lui, partait toujours de la première. Un serveur qui
    refuserait la seconde — c'est le cas courant quand elle est un **alias** et
    non un compte — l'aurait laissé passer, et l'échec ne serait apparu que sur
    un vrai ticket, dans un journal que personne ne lit à ce moment-là.

    C'est la règle du dépôt appliquée à un contrôle : *la fonction qui vérifie
    doit être celle qui sert* (#498, et le P3 du post-check qui l'a apprise deux
    fois). Une seule adresse configurée rend une seule entrée : on ne fabrique
    pas un second envoi pour faire nombre.
    """
    from app.seed.emails import EXPEDITEUR_AFFAIRE, EXPEDITEUR_MUET, EXPEDITEUR_REPONSE

    vues: list[str] = []
    for genre in (EXPEDITEUR_MUET, EXPEDITEUR_REPONSE, EXPEDITEUR_AFFAIRE):
        adresse = adresse_expedition(smtp_cfg, genre)
        if adresse and adresse not in vues:
            vues.append(adresse)
    return vues


#: La clé qui dit que la base d'une copropriété a reçu son amorce (#2058) : posée une
#: fois, elle n'est jamais relue pour décider d'un envoi.
CLE_AMORCE = "smtp_amorce_le"


def _amorce(s) -> dict[str, str]:
    """Ce que le repli d'avant #2058 produisait, champ par champ — l'amorce d'une base."""
    copro = contexte.courante()
    expedition = {"smtp_from": copro.expediteur, "smtp_from_name": copro.nom_expediteur}
    if contexte.est_commune():
        return expedition
    return expedition | {
        "smtp_enabled": "1" if s.mail_enabled else "0",
        "smtp_server": s.mail_server,
        "smtp_port": str(s.mail_port),
        "smtp_username": s.mail_username,
        "smtp_password": s.mail_password,
        "smtp_starttls": "1" if s.mail_starttls else "0",
        "smtp_ssl_tls": "1" if s.mail_ssl_tls else "0",
    }


#: Les booléens se reprennent sur leur ABSENCE seulement : « 0 » est une case décochée,
#: pas un champ vide — l'ancien repli le traitait déjà ainsi.
_PRIS_SUR_ABSENCE = {"smtp_enabled", "smtp_starttls", "smtp_ssl_tls"}


def amorcer(session: Session) -> int:
    """Une fois par base : recopie l'amorce dans chaque clé que le repli remplissait.

    Rend le nombre de clés écrites ; ne valide pas la transaction (le seed le fait).
    Une clé déjà renseignée n'est jamais touchée.
    """
    from app.utils.config_site import ecrire_cle

    if session.get(ConfigSite, CLE_AMORCE) is not None:
        return 0
    actuel = _get_smtp_config(session)
    ecrites = 0
    for cle, valeur in _amorce(get_settings()).items():
        deja = actuel.get(cle)
        manque = deja is None if cle in _PRIS_SUR_ABSENCE else not deja
        if manque and valeur:
            ecrire_cle(session, cle, valeur)
            ecrites += 1
    from app.utils import horloge

    ecrire_cle(session, CLE_AMORCE, horloge.maintenant().isoformat(timespec="seconds"))
    return ecrites


def _connexion(*, server, port, username, password, starttls, ssl_tls, expediteur, nom_expediteur):
    """La SEULE construction d'une connexion — les deux niveaux la partagent."""
    from fastapi_mail import ConnectionConfig

    return ConnectionConfig(
        MAIL_USERNAME=username,
        MAIL_PASSWORD=password,
        MAIL_FROM=expediteur,
        MAIL_FROM_NAME=nom_expediteur,
        MAIL_PORT=int(port),
        MAIL_SERVER=server,
        MAIL_STARTTLS=starttls,
        MAIL_SSL_TLS=ssl_tls,
        USE_CREDENTIALS=bool(username),
    )


def connexion_smtp_installation(*, expediteur: str, nom_expediteur: str):
    """Le SMTP de l'INSTALLATION (`MAIL_*` du `.env`) — les alertes de la plateforme,
    jamais un courriel de copropriété (#2058)."""
    s = get_settings()
    return _connexion(
        server=s.mail_server,
        port=s.mail_port,
        username=s.mail_username,
        password=s.mail_password,
        starttls=s.mail_starttls,
        ssl_tls=s.mail_ssl_tls,
        expediteur=expediteur,
        nom_expediteur=nom_expediteur,
    )


def connexion_smtp(smtp_cfg: dict, *, expediteur: str | None = None):
    """La connexion SMTP d'une copropriété : sa configuration en BASE, et elle seule (#2058).

    Ces dix-sept lignes étaient écrites **trois fois** — deux dans ce module
    (envoi simple et envoi groupé) et une dans `routers/config.py` pour l'e-mail
    de test. C'est la duplication la plus coûteuse qui soit sur ce chemin : le
    bouton « tester la configuration SMTP » n'a d'intérêt que s'il emprunte
    exactement la même construction que les envois réels. Trois écritures, c'est
    trois occasions de tester autre chose que ce qui part vraiment.

    Elle retombait champ par champ sur `MAIL_*` jusqu'au 17/10/2026 : la base de
    chaque copropriété a reçu, par `amorcer`, la valeur que ce repli produisait. Un
    champ vide reste vide — et l'écran le montre.
    """
    return _connexion(
        server=smtp_cfg.get("smtp_server") or "",
        port=smtp_cfg.get("smtp_port") or 587,
        username=smtp_cfg.get("smtp_username") or "",
        password=smtp_cfg.get("smtp_password") or "",
        starttls=smtp_cfg.get("smtp_starttls") == "1",
        ssl_tls=smtp_cfg.get("smtp_ssl_tls") == "1",
        #  L'expéditeur peut être imposé par l'appelant : c'est l'INTENTION du
        #  modèle qui le décide, pas la connexion (voir `adresse_expedition`).
        expediteur=expediteur or smtp_cfg.get("smtp_from") or "",
        nom_expediteur=smtp_cfg.get("smtp_from_name") or "",
    )
