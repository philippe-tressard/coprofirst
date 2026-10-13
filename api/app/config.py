from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings

from app.dialecte import url_fichier

_INSECURE_KEY_DEFAULTS = {
    "dev-secret-key-change-in-production",
    "changez-cette-valeur-secrete-en-production-min-32-chars",
}


class Settings(BaseSettings):
    # Identité du nœud — lue dans `.env` (`env_file`) ; le front la reçoit à
    # l'exécution sous `PUBLIC_INSTANCE_ID` pour afficher « RPi1 » au pied de
    # page (#1758). L'API l'ignorait, si bien qu'elle ne pouvait pas
    # dire sur quel nœud elle exécutait ses propres tâches (sauvegarde, maintenance
    # déclenchée à la main) : la colonne « Nœud » restait vide. Vide en local.
    instance_id: str = ""

    # Rôle de l'installation dans la distribution (#1761) : `reference` ou
    # `replique`. Lu par `utils/installation.role_installation` et nulle part
    # ailleurs ; vide ou mal écrit, l'installation se dit « Inconnu ».
    role_installation: str = ""
    # Le commit de l'image, posé à la construction (`GIT_HASH`, api/Dockerfile).
    git_hash: str = ""
    # La DÉMO PUBLIQUE de CoproFirst (spec `mode-demo.md`, #1901) : `oui` ferme les
    # gestes du registre `utils/demo.GESTES_FERMES`. Lu par `utils/demo.est_demo` et
    # nulle part ailleurs ; vide ou mal écrit, l'installation n'est pas une démo.
    mode_demo: str = ""
    # L'ÉDITEUR et l'adresse de CONTACT de la démo, dans ses textes légaux (#1907) :
    # le dépôt public ne nomme personne. Lus par `app/demo/legal.py` et nulle part
    # ailleurs ; sans éditeur, la démo se déclare éditée à titre non professionnel.
    demo_editeur: str = ""
    demo_contact: str = ""
    # La version promue qu'une RÉPLIQUE installe (`deploiement/standard`, même `.env`) ;
    # vide chez la référence. Lue par `utils/installation.version_logicielle`.
    coprofirst_version: str = ""

    # Le REGISTRE DES INSTALLATIONS, tenu par la référence seule (spec §4.11, R1 #1877) :
    # sa base, DISTINCTE de celle de la résidence, et le nom DÉDIÉ sous lequel il
    # répond. Vides → registre éteint (`app/registre/base.registre_actif`), et
    # c'est l'état de toute réplique. Lus là-bas et nulle part ailleurs.
    plateforme_database_url: str = ""
    hote_registre: str = ""

    # L'adresse de l'OPÉRATEUR de l'installation (#1814, arbitré le 13/10/2026) : le
    # destinataire des alertes de la PLATEFORME (le disque du serveur), qui ne lisent
    # aucune base de copropriété (D5). Une coordonnée de l'installation, pas d'une
    # copropriété ; elle part par le SMTP de l'installation (`MAIL_*`). Lue par
    # `utils/sante_plateforme` et nulle part ailleurs ; vide → l'alerte se journalise.
    courriel_operateur: str = ""
    # Et l'adresse qui les EXPÉDIE : celle de l'installation, pas celle d'une
    # copropriété (`MAIL_FROM` en est une, D6). Vide → l'alerte se journalise.
    mail_from_plateforme: str = ""

    # La clé qui SIGNE les baux (R2 #1878, D19) — chez la référence SEULE : 32 octets
    # bruts en base64, créée sur l'actif par `scripts/exploitation/creer-cle-baux.sh`
    # et posée dans le `.env` des deux nœuds. La seule pièce secrète du registre :
    # jamais dans le code, jamais sur le poste. Vide → aucun bail n'est délivré.
    cle_signature_baux: str = ""

    # CÔTÉ INSTALLATION (R2 #1878) : où joindre le registre de la référence (son nom
    # dédié, D17), où ranger la clé et l'état d'inscription de CETTE installation —
    # le volume `app_data`, jamais une image ni une base de copropriété —, et le mode
    # ESSAI (CI, tests, poste), qui n'appelle jamais la référence. Lus par
    # `app/inscription/` et nulle part ailleurs.
    registre_url: str = "https://registre.coprofirst.fr"
    installation_dir: str = "/app/data/installation"
    installation_essai: bool = False

    # Le REGISTRE des hôtes de la copropriété (#1751, P2-9) : le nom de
    # l'`ORIGIN` — le même `.env` que le front —, plus ceux qu'on déclare ici,
    # séparés par des virgules. Lus par `app/contexte.py` et nulle part ailleurs.
    origin: str = "http://localhost"
    hotes_copropriete: str = ""

    # Sécurité
    secret_key: str = "dev-secret-key-change-in-production"

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_secure(cls, v: str) -> str:
        if v in _INSECURE_KEY_DEFAULTS:
            raise ValueError(
                "SECRET_KEY n'est pas configuré. Définissez une valeur aléatoire "
                "d'au moins 32 caractères dans votre fichier .env."
            )
        if len(v) < 32:
            raise ValueError("SECRET_KEY doit faire au moins 32 caractères.")
        return v

    cookie_secure: bool = True  # False uniquement pour dev HTTP local
    access_token_expire_minutes: int = 120
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    # Base de données
    database_url: str = url_fichier("/app/data/app.db")

    # Email
    mail_enabled: bool = False
    mail_from: str = "noreply@localhost"
    mail_from_name: str = "Ma Résidence"
    mail_username: str = ""
    mail_password: str = ""
    mail_server: str = "localhost"
    mail_port: int = 587
    mail_starttls: bool = True
    mail_ssl_tls: bool = False

    # Sauvegardes
    backup_dir: str = "/backups"

    #: Racine du volume des fichiers téléversés.
    #:
    #: 🔴 Elle était lue à SIX endroits avant le 19/09/2026 (#1026) : trois
    #: `os.getenv("UPLOADS_DIR")` et trois chemins écrits en dur
    #: (`RACINE_UPLOADS`, `UPLOADS_ROOT`, `PDF_DIR`). Six écritures d'un même
    #: chemin, c'est cinq occasions d'en oublier une le jour où le volume bouge
    #: — et un fichier écrit hors du volume n'est ni répliqué vers le standby
    #: par `bascule.sh`, ni sauvegardé par `backup.py`. Il est perdu à la
    #: première bascule, sans aucun signal. Elle ne se lit plus que par le
    #: contexte de copropriété (#1744), et un fichier ne se situe que par
    #: `utils/stockage` (#1748).
    uploads_dir: str = "/app/uploads"
    backup_hour: int = 3
    backup_keep_versions: int = 7

    # Maintenance cron — clé partagée pour l'endpoint /admin/maintenance/rapport
    # Laisser vide pour désactiver l'enregistrement depuis le script cron
    maintenance_key: str = ""

    #  Clé du bridge WhatsApp — la MÊME variable que lit le bridge : compose la
    #  lui donne sous le nom `WA_API_KEY`, l'API la reçoit par `env_file: .env`.
    #
    #  🔴 Elle était écrite DEUX fois avant le 02/10/2026 (#1596) : dans `.env`
    #  pour le bridge, et dans `ConfigSite.whatsapp_api_key`, saisie à l'écran
    #  d'administration pour l'API. Rien ne les confrontait, et un écart ne se
    #  voyait qu'au 401 de l'envoi. Elle ne se lit que par
    #  `utils/whatsapp.entetes_bridge`.
    #
    #  Pas de refus au démarrage ICI, contrairement à `secret_key` : c'est le
    #  bridge qui refuse une clé vide, d'exemple ou trop courte. Arrêter le site
    #  entier pour la clé d'un canal de diffusion serait disproportionné.
    whatsapp_api_key: str = ""

    #  Budget d'une photo jointe à un message WhatsApp, en kio.
    #
    #  🔴 Déclaré dans `docker-compose.yml` (`WA_PHOTO_BUDGET_KO`) et lu des DEUX
    #  côtés : ici, et par le bridge qui en dérive la borne de son corps JSON.
    #  Ce défaut-ci n'est qu'un repli hors conteneur — la valeur qui fait foi est
    #  celle de compose. Deux nombres écrits séparément divergeraient, et c'est
    #  ce qui a coûté un message le 19/09/2026 (#1057).
    wa_photo_budget_ko: int = 400

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
