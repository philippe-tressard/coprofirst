"""Les réglages que `PUT /config` écrit — et rien d'autre (#2055).

🔴 Jusqu'au 17/10/2026, `PUT /config` refusait trois clés et écrivait **toutes
les autres** dans `config_site`, connues ou non : le premier essai d'un usage de
l'IA (`llm_<usage>_reference`, que le serveur seul écrit), les consignes aux
arrivants et la provenance du règlement sans les bornes de leurs routes, toute
faute de frappe. L'inverse de la règle du socle : ce qui entre se déclare
(`standards/03-securite.md`).

Ce module est la **liste blanche** : chaque clé écrivable, rangée sous l'onglet
d'Admin qui l'écrit. Les familles dont les membres se déduisent d'un autre
registre (usages de l'IA, interrupteurs de service, pied de page, pages) en sont
lues, jamais recopiées. Une clé refusée l'est avec sa raison (`REFUSEES`).

C'est le premier pas du registre des réglages (#2061) : la carte des réglages
versionnée se déduira de lui.
"""

from __future__ import annotations

import re

from app.utils import demo, pied_de_page
from app.utils.llm_usages import USAGES, champs
from app.utils.services import CLES_ACTIVATION

#: Les clés écrites par l'administration, par onglet — celui qui les écrit
#: aujourd'hui, pas celui de la réorganisation à venir (#2062).
PAR_ONGLET: dict[str, frozenset[str]] = {
    #  `ecrireConfigSite` (front `configSite.ts`) : Paramétrage site, Pied de page,
    #  Pages légales et pied des messages WhatsApp partagent son enregistrement (#2057).
    "site": frozenset(
        {
            "site_nom",
            "site_url",
            "site_email",
            "site_manager_user_id",
            "login_sous_titre",
            "mentions_legales",
            "politique_confidentialite",
            "archivage_delai_jours",
            "relance_syndic_delai_jours",
            "notify_ticket_bug_email",
            "notify_new_user_created_email",
            "whatsapp_footer",
            "email_footer",
            "reference_copro",
        }
    )
    | pied_de_page.CLES_PUBLIQUES,
    "copropriete": frozenset({"reference_copro"}),
    "pages": frozenset({"pages_order"}),  # + `page_config_<page>`, voir PREFIXES
    "services": CLES_ACTIVATION,
    "smtp": frozenset(
        {
            "smtp_enabled",
            "smtp_server",
            "smtp_port",
            "smtp_from",
            "smtp_from_reponse",
            "smtp_from_affaires",
            "smtp_from_name",
            "smtp_username",
            "smtp_password",
            "smtp_starttls",
            "smtp_ssl_tls",
            "email_footer",
        }
    ),
    "reception": frozenset(
        {
            "imap_server",
            "imap_port",
            "imap_username",
            "imap_password",
            "imap_dossier",
            "imap_plancher",
            "courriels_affiches",
        }
    ),
    "whatsapp": frozenset({"whatsapp_group_name", "whatsapp_api_url", "whatsapp_group_jid"}),
    "ia": frozenset(
        {
            "llm_fournisseur",
            "llm_api_key",
            "llm_base_url",
            "llm_api_version",
            "llm_delai_s",
            "llm_envoi_document",
        }
    )
    #  Les réglages de chaque usage, lus sur le registre des usages : l'écran
    #  renvoie exactement ces clés (`GET /config/llm-usages`, champ `cles`).
    | frozenset(u.cle(c) for u in USAGES.values() for c in champs(u)),
    #  ⚠️ Lus par le serveur, sans écran (#2060) : `PUT /config` reste leur seule
    #  porte tant qu'ils n'ont pas d'onglet. Les refuser les rendrait irréglables.
    "sans_ecran": frozenset({"acces_fixes_vigik", "acces_fixes_telecommande", "site_icone"}),
}

#: Les familles dont le dernier segment est une donnée : `page_config_<page>`,
#: une entrée par page du menu (`front/src/lib/pages*.ts`).
PREFIXES: dict[str, re.Pattern[str]] = {
    "page_config_": re.compile(r"page_config_[a-z0-9][a-z0-9_-]{0,63}"),
}

#: 🔴 Refusées, avec ce qu'il faut faire à la place.
REFUSEES: dict[str, str] = {
    #  La clé du bridge n'a qu'une source, `.env` (#1596).
    "whatsapp_api_key": "La clé du bridge WhatsApp se définit dans .env (WHATSAPP_API_KEY).",
    #  Posé par le téléversement, qui contrôle le fichier (#1728).
    "site_logo": "Le logo se téléverse par POST /config/logo.",
    #  Un réglage de l'INSTALLATION (spec `mode-demo.md` M1).
    demo.CLE_PUBLIQUE: "Le mode démo se règle dans .env (MODE_DEMO).",
    #  Leurs routes portent des bornes que `PUT /config` n'appliquerait pas.
    "consignes_arrivant": "Les consignes aux arrivants se modifient par PUT /admin/arrivants/consignes.",
    "reglement_provenance": "La provenance du règlement se modifie par PUT /reglement/provenance.",
    "whatsapp_community_url": "Le lien de la communauté WhatsApp se modifie dans l'annuaire du CS.",
}

#: Le premier essai d'un usage de l'IA : le serveur seul l'écrit (`llm_limites`).
RESERVEES_AU_SERVEUR = frozenset(u.cle("reference") for u in USAGES.values())

ECRIVABLES: frozenset[str] = frozenset().union(*PAR_ONGLET.values())


def est_ecrivable(cle: str) -> bool:
    """PURE. `PUT /config` peut-il écrire cette clé ?"""
    if cle in REFUSEES or cle in RESERVEES_AU_SERVEUR:
        return False
    return cle in ECRIVABLES or any(
        cle.startswith(p) and motif.fullmatch(cle) for p, motif in PREFIXES.items()
    )


def refus_d_ecriture(cle: str) -> str | None:
    """PURE. Pourquoi `PUT /config` refuse cette clé — `None` s'il l'accepte."""
    if cle in REFUSEES:
        return REFUSEES[cle]
    if cle in RESERVEES_AU_SERVEUR:
        return f"« {cle} » est écrit par le serveur seul."
    if not est_ecrivable(cle):
        return f"Réglage inconnu : « {cle} »."
    return None


__all__ = [
    "ECRIVABLES",
    "PAR_ONGLET",
    "PREFIXES",
    "REFUSEES",
    "RESERVEES_AU_SERVEUR",
    "est_ecrivable",
    "refus_d_ecriture",
]
