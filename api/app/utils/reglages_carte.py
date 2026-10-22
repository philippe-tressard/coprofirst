"""La carte des réglages — qui règle quoi, et où — déduite des registres (#2061).

`docs/carte-reglages.md` est **généré** depuis ce module (`reglages_carte_rendu`),
jamais tenu à la main : une carte écrite une fois divergeait au premier réglage
ajouté. Le fichier versionné est comparé à ce que le code produit
(`test_carte_reglages.py`).

Ce que ce module déclare, et ce qu'il lit :
  - les **clés** de `config_site` viennent de `utils/reglages.PAR_ONGLET` (la liste
    blanche de `PUT /config`) — jamais recopiées ici ;
  - le **public** et le **secret** d'une clé viennent de `routers/config`
    (`_est_public`, `_SECRETS`), son **défaut d'amorce** du seed ;
  - les **variables d'environnement** viennent de `Settings` ; ici seul leur thème
    se déclare, et le test échoue pour un champ sans thème (ou un thème sans champ) ;
  - **qui règle** une notion est déclaré (`Acces`) — et confronté à la dépendance
    d'autorisation que la route prend réellement (`ecarts_d_acces`).

🔴 Pourquoi confronter : le réglage de la sauvegarde se montrait à l'opérateur seul
alors que sa route acceptait tout administrateur (commentaire de #2055) — l'écran
disait une chose, le serveur une autre, et seul le serveur compte.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from enum import Enum


class Acces(str, Enum):
    """Qui règle une notion."""

    EXPLOITANT = "exploitant"  # l'exploitant du serveur, dans `.env`
    OPERATEUR = "operateur"  # l'opérateur de la plateforme (`require_operateur`)
    ADMIN = "admin"  # l'administrateur de la copropriété (`require_admin`)
    CS = "cs"  # le conseil syndical, ou l'administrateur (`require_cs_or_admin`)
    PERSONNE = "personne"  # personne : une constante du code


#: La dépendance que la route d'un accès DOIT prendre — la lecture sur la route
#: montée, pas sur sa déclaration. `EXPLOITANT` et `PERSONNE` n'ont pas de route.
DEPENDANCE_DE_L_ACCES: dict[Acces, str] = {
    Acces.OPERATEUR: "require_operateur",
    Acces.ADMIN: "require_admin",
    Acces.CS: "require_cs_or_admin",
}

LIBELLE_ACCES: dict[Acces, str] = {
    Acces.EXPLOITANT: "Exploitant du serveur (`.env`)",
    Acces.OPERATEUR: "Opérateur de la plateforme",
    Acces.ADMIN: "Administrateur de la copropriété",
    Acces.CS: "Conseil syndical (ou administrateur)",
    Acces.PERSONNE: "Personne (constante du code)",
}

#: Les groupes d'Admin, tels que `front/src/lib/pages-roles.ts` les range depuis #2062
#: (`test_carte_reglages` confronte chaque écran déclaré à ce fichier).
G_PERSONNES = "👥 Personnes"
G_COPROPRIETE = "🏢 Copropriété"
G_SERVICES = "🔌 Services"
G_PRESENTATION = "🎨 Présentation"
G_EXPLOITATION = "🛠 Exploitation"


@dataclass(frozen=True)
class Notion:
    """Un réglage ou une famille de réglages qui se règlent au même endroit."""

    code: str
    libelle: str
    acces: Acces
    #: L'écran qui le règle : `Admin › <groupe> › <onglet>` pour un onglet d'Admin (lu et
    #: confronté à `pages-roles.ts`), sinon le chemin de menus.
    ecran: str
    #: Où la valeur vit : `config_site`, une table, `.env`, le code.
    stockage: str
    #: La route qui l'écrit (méthode, chemin monté) — `None` si aucune.
    route: tuple[str, str] | None = None
    #: L'onglet de `utils/reglages.PAR_ONGLET` dont la notion écrit les clés.
    onglet: str | None = None
    #: Pour une notion « code » : les constantes qui portent la valeur
    #: (`module:NOM`), confrontées au code par le test.
    constantes: tuple[str, ...] = ()
    #: L'écart connu entre l'écran et le serveur, avec ce qu'il reste à trancher.
    ecart: str = ""


PUT_CONFIG = ("PUT", "/config")

NOTIONS: tuple[Notion, ...] = (
    # ── Administrateur : PUT /config, onglet par onglet (#2057) ──────────────────
    Notion(
        "fonctionnement",
        "Paramètres de fonctionnement : e-mail et gestionnaire du site, délais d'archivage et de relance, notifications",
        Acces.ADMIN,
        f"Admin › {G_COPROPRIETE} › Fonctionnement",
        "config_site",
        PUT_CONFIG,
        "fonctionnement",
    ),
    Notion(
        "connexion",
        "Sous-titre de la page de connexion",
        Acces.ADMIN,
        f"Admin › {G_PRESENTATION} › Connexion et pied de page",
        "config_site",
        PUT_CONFIG,
        "connexion",
    ),
    Notion(
        "pied_de_page",
        "Pied de page du site",
        Acces.ADMIN,
        f"Admin › {G_PRESENTATION} › Connexion et pied de page",
        "config_site",
        PUT_CONFIG,
        "pied_de_page",
    ),
    Notion(
        "legal",
        "Pages légales et adresse des droits sur les données",
        Acces.ADMIN,
        f"Admin › {G_COPROPRIETE} › Pages légales",
        "config_site",
        PUT_CONFIG,
        "legal",
    ),
    Notion(
        "reference_copro",
        "Référence de copropriété du syndic",
        Acces.ADMIN,
        f"Admin › {G_COPROPRIETE} › Identité",
        "config_site",
        PUT_CONFIG,
        "copropriete",
    ),
    Notion(
        "pages",
        "Menu et pages : ordre, icône, libellé, titre, description",
        Acces.ADMIN,
        f"Admin › {G_PRESENTATION} › Menu et pages",
        "config_site",
        PUT_CONFIG,
        "pages",
    ),
    Notion(
        "services",
        "Interrupteurs des services",
        Acces.ADMIN,
        f"Admin › {G_SERVICES} › Services",
        "config_site",
        PUT_CONFIG,
        "services",
    ),
    Notion(
        "smtp",
        "Envoi des courriels (SMTP) et signature",
        Acces.ADMIN,
        f"Admin › {G_SERVICES} › Courriel",
        "config_site",
        PUT_CONFIG,
        "smtp",
    ),
    Notion(
        "reception",
        "Relève des réponses par courriel (IMAP)",
        Acces.ADMIN,
        f"Admin › {G_SERVICES} › Courriel",
        "config_site",
        PUT_CONFIG,
        "reception",
    ),
    Notion(
        "whatsapp",
        "Canal WhatsApp : pont, groupe, pied des messages",
        Acces.ADMIN,
        f"Admin › {G_SERVICES} › WhatsApp",
        "config_site",
        PUT_CONFIG,
        "whatsapp",
    ),
    Notion(
        "ia",
        "Assistant IA : fournisseur, clé, réglage de chaque usage",
        Acces.ADMIN,
        f"Admin › {G_SERVICES} › Assistant IA",
        "config_site",
        PUT_CONFIG,
        "ia",
    ),
    # ── Administrateur : les réglages qui ont leur propre route ─────────────────
    Notion(
        "logo",
        "Logo de la résidence",
        Acces.ADMIN,
        f"Admin › {G_COPROPRIETE} › Identité",
        "fichier + config_site (`site_logo`)",
        ("POST", "/config/logo"),
    ),
    Notion(
        "fiche_copropriete",
        "Fiche de la copropriété : identité, adresse, syndic, références",
        Acces.ADMIN,
        f"Admin › {G_COPROPRIETE} › Identité ; Ma résidence",
        "table `copropriete` (+ `config_site.site_nom`)",
        ("PATCH", "/copropriete"),
        ecart=(
            "Ma résidence offre la modification à tout le conseil syndical (`isCS`), "
            "mais la route est réservée à l'administrateur : un membre du CS qui "
            "enregistre reçoit un refus (#2096)."
        ),
    ),
    Notion(
        "perimetres",
        "Périmètres (arbre des bâtiments et espaces) et leurs accès fixes",
        Acces.ADMIN,
        f"Admin › {G_COPROPRIETE} › Périmètres",
        "table `perimetre`",
        ("PATCH", "/perimetres/{perimetre_id}"),
    ),
    Notion(
        "modeles_email",
        "Modèles de courriel",
        Acces.ADMIN,
        f"Admin › {G_PRESENTATION} › Modèles e-mail",
        "table `modele_email`",
        ("PATCH", "/admin/modeles-email/{modele_id}"),
    ),
    Notion(
        "provenance_reglement",
        "Provenance du règlement",
        Acces.ADMIN,
        "Ma résidence › Règlement (mode administration)",
        "table / `config_site`",
        ("PUT", "/reglement/provenance"),
    ),
    # ── Conseil syndical ────────────────────────────────────────────────────────
    Notion(
        "annuaire_syndic",
        "Annuaire du syndic",
        Acces.CS,
        "Espace CS › Annuaire CS & Syndic",
        "table / `config_site`",
        ("PUT", "/admin/annuaire/syndic"),
    ),
    Notion(
        "annuaire_cs",
        "Annuaire du conseil syndical (composition)",
        Acces.CS,
        "Espace CS › Annuaire CS & Syndic",
        "table / `config_site`",
        ("PUT", "/admin/annuaire/cs"),
    ),
    Notion(
        "consignes_arrivant",
        "Consignes aux arrivants",
        Acces.CS,
        "Espace CS › Annuaire CS & Syndic (consignes aux arrivants)",
        "`config_site.consignes_arrivant`",
        ("PUT", "/admin/consignes-arrivant"),
    ),
    Notion(
        "compteurs",
        "Compteurs (relevés)",
        Acces.CS,
        "Espace CS › Compteurs (configuration des catégories)",
        "table `compteur_config`",
        ("POST", "/prestataires/compteurs-config"),
    ),
    # ── Opérateur de la plateforme ──────────────────────────────────────────────
    Notion(
        "sauvegarde",
        "Sauvegarde : heure et nombre de versions conservées",
        Acces.OPERATEUR,
        f"Admin › {G_EXPLOITATION} › Maintenance",
        "table `config_sauvegarde`",
        ("PUT", "/admin/sauvegardes/config"),
    ),
    Notion(
        "inscription",
        "Inscription de l'installation au registre",
        Acces.OPERATEUR,
        f"Admin › {G_EXPLOITATION} › Installation",
        "volume `installation` (clé et état d'inscription)",
        ("POST", "/admin/installation/inscription"),
    ),
    Notion(
        "bail",
        "Bail de l'installation",
        Acces.OPERATEUR,
        f"Admin › {G_EXPLOITATION} › Installation",
        "volume `installation`",
        ("POST", "/admin/installation/bail"),
    ),
    Notion(
        "registre_installations",
        "Registre des installations (décisions, services, distribution) — sur la référence",
        Acces.OPERATEUR,
        f"Admin › {G_EXPLOITATION} › Installations",
        "base `plateforme`",
        ("PUT", "/admin/installations/{identifiant}/services"),
    ),
    Notion(
        "taches",
        "Tâches planifiées : déclenchement manuel",
        Acces.OPERATEUR,
        f"Admin › {G_EXPLOITATION} › Maintenance",
        "`utils/taches.TACHES_PERMANENTES` (le calendrier est dans le code)",
        ("POST", "/admin/maintenance/lancer"),
    ),
    # ── Personne : des constantes du code ───────────────────────────────────────
    Notion(
        "conservation",
        "Durées de conservation des données (courriels relevés, journal IA, erreurs du navigateur, comptes)",
        Acces.PERSONNE,
        "— (aucun écran)",
        "constantes du code",
        constantes=(
            "app.utils.courriel_journal:CONSERVATION_RELEVES_JOURS",
            "app.utils.maintenance:CONSERVATION_COURRIELS_JOURS",
            "app.utils.llm_journal:CONSERVATION_MOIS",
            "app.utils.erreurs_navigateur:CONSERVATION_JOURS",
            "app.utils.purge_comptes.regles:DELAI_AVANT_SUPPRESSION_JOURS",
        ),
    ),
)


def ecarts_d_acces(
    notions: tuple[Notion, ...], dependances: dict[tuple[str, str], frozenset[str]]
) -> list[str]:
    """PURE. Ce qui sépare l'accès DÉCLARÉ de la dépendance que la route prend.

    `dependances` : (méthode, chemin monté) → les dépendances d'autorisation de la
    route (`require_*`). Une route introuvable est un écart — jamais un succès :
    une carte qui cite une route qui n'existe plus ment.
    """
    ecarts = []
    for n in notions:
        if n.route is None:
            continue
        prises = dependances.get(n.route)
        if prises is None:
            ecarts.append(f"{n.code} : la route {n.route[0]} {n.route[1]} n'existe pas")
            continue
        attendue = DEPENDANCE_DE_L_ACCES[n.acces]
        if prises != {attendue}:
            ecarts.append(
                f"{n.code} : la route prend {sorted(prises)}, la carte annonce {attendue}"
            )
    return ecarts


# ── L'environnement ─────────────────────────────────────────────────────────────

#: Le thème de chaque variable de `Settings` et la liste de ses secrets : une DONNÉE, dans
#: `reglages_environnement.json`, et non des littéraux de ce module. Les gardiens « une seule
#: lecture » (rôle de l'installation, mode démo, clé du pont WhatsApp…) refusent
#: qu'un module de l'API cite le nom d'une variable qu'un seul module lit : une table de
#: documentation n'est pas une lecture, mais ils ne savent pas le distinguer.
#: `test_carte_reglages` échoue pour un champ sans thème et pour un thème sans champ.
_ENVIRONNEMENT = json.loads(
    pathlib.Path(__file__).with_name("reglages_environnement.json").read_text(encoding="utf-8")
)
THEMES_ENV: dict[str, tuple[str, ...]] = {
    theme: tuple(noms) for theme, noms in _ENVIRONNEMENT["themes"].items()
}
#: Les variables dont la valeur est un secret : le défaut ne s'imprime pas.
SECRETS_ENV = frozenset(_ENVIRONNEMENT["secrets"])

# ── Le type d'une clé de `config_site` ──────────────────────────────────────────

OUI_NON = "oui/non (`1`/`0`)"
NOMBRE = "nombre"
DATE = "date (AAAA-MM-JJ)"
JSON = "JSON"
SECRET = "secret"
TEXTE = "texte"

#: Les clés qui ne sont pas du texte. Tout le reste est du texte libre.
TYPES: dict[str, str] = {
    "notify_ticket_bug_email": OUI_NON,
    "notify_new_user_created_email": OUI_NON,
    "smtp_enabled": OUI_NON,
    "smtp_starttls": OUI_NON,
    "smtp_ssl_tls": OUI_NON,
    "llm_envoi_document": OUI_NON,
    "site_manager_user_id": NOMBRE,
    "archivage_delai_jours": NOMBRE,
    "relance_syndic_delai_jours": NOMBRE,
    "smtp_port": NOMBRE,
    "imap_port": NOMBRE,
    "llm_delai_s": NOMBRE,
    "courriels_affiches": NOMBRE,
    "pied_de_page_annee_debut": NOMBRE,
    "imap_plancher": DATE,
    "pages_order": JSON,
    "pied_de_page_masques": JSON,
    "pied_de_page_ordre": JSON,
    "smtp_password": SECRET,
    "imap_password": SECRET,
    "llm_api_key": SECRET,
}

#: Le type d'un champ de réglage d'usage de l'IA (`llm_<usage>_<champ>`).
TYPES_CHAMP_USAGE: dict[str, str] = {
    "actif": OUI_NON,
    "coproprietaires": OUI_NON,
    "max_jetons": NOMBRE,
    "appels_mois": NOMBRE,
    "appels_heure": NOMBRE,
    "prix_entree": "nombre décimal ($ / million de jetons)",
    "prix_sortie": "nombre décimal ($ / million de jetons)",
    "prix_cache": "nombre décimal ($ / million de jetons)",
}
