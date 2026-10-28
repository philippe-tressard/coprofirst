"""Les SERVICES de la copropriété : ce qui se coupe, et ce qui ne se coupe pas (#1718).

## Pourquoi ce registre (07/10/2026)

Premier lot du chantier multi-copropriétés (`specs/architecture/multi-coproprietes.md`
§4.8, D6 : « les canaux sont par copro, et les services sont désactivables »).
Trois services avaient chacun son interrupteur, et chacun sa façon de le lire :

| Service | Clé | La lecture d'avant |
|---|---|---|
| Assistant IA | `llm_actif` | `cfg.get(CLE_ACTIF) == "1"`, dans `llm.py` |
| Diffusion WhatsApp | `whatsapp_enabled` | `whatsapp_actif(cfg)`, dans `whatsapp.py` |
| Réponses par courriel | `imap_enabled` | `.lower() in ("1", "true", "oui")`, écrit DEUX fois |

Trois règles pour une seule question — « ce service est-il activé ? » —, et la
troisième n'avait pas le même sens que les deux autres. La migration 0267 a
ramené à `"1"` les valeurs qu'elle seule acceptait : la règle d'ici est la seule,
et aucun service n'a changé d'état en production.

C'est la forme de `llm_usages.py` : **une liste unique, un écran qui s'en
déduit** (`GET /config/services`, onglet « Services » de l'administration).
Ajouter un service, c'est ajouter une entrée ici — pas un écran.

## 🔴 Ce qui n'est PAS un service

Les **courriels de sécurité** — mot de passe oublié, vérification et changement
d'adresse, alerte système à l'administration — ne se coupent pas : un compte
qu'on ne peut plus récupérer est un compte perdu. Ils passent par le SMTP, qui
est déclaré ici comme **infrastructure** (`coupable=False`) : l'écran montre son
état et renvoie à ses réglages, il ne propose aucun interrupteur.
🔒 `test_courriels_securite_hors_service.py` refuse qu'un de ces envois soit
soumis à un interrupteur de service.

⚠️ `smtp_enabled` reste lu par `utils/email.envoi_actif`, et c'est voulu : sa
règle n'est pas celle d'un service (absente de la base, c'est `MAIL_ENABLED` de
l'environnement qui tranche). La faire passer par `service_actif` l'aurait
changée en silence.

## Évalués et NON retenus (07/10/2026)

- **Le partage d'un lien par courriel** (`routers/partage.py`) : il n'a aucun
  interrupteur aujourd'hui, et c'est un courriel ordinaire porté par le SMTP. En
  faire un service serait une décision fonctionnelle — rien ne la demande.
- **Les affiches de hall** (PDF) : elles ne sortent pas de l'application, aucun
  tiers ne les reçoit. Rien à couper au sens de D6.

🔒 `test_services_registre.py` : aucune clé d'activation n'est lue hors d'ici.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Les codes des services — la seule écriture de chacun.
SERVICE_IA = "assistant_ia"
SERVICE_DIFFUSION = "diffusion"
SERVICE_REPONSES_COURRIEL = "reponses_courriel"
SERVICE_VERIF_VERSION = "verification_version"
SERVICE_CONSERVATION = "conservation_affaires"
INFRA_SMTP = "envoi_courriels"

#: La valeur qui dit « activé ». Une seule, pour toutes les clés.
ACTIVE = "1"
DESACTIVE = "0"


@dataclass(frozen=True)
class Service:
    """Un service de la copropriété — ou une infrastructure, qui ne se coupe pas."""

    code: str
    libelle: str
    #: Ce que fait le service, dit à l'administrateur.
    description: str
    #: Ce qu'on perd quand il est coupé — la question qu'on se pose avant de couper.
    perte: str
    #: L'onglet d'administration de ses réglages détaillés (`pages-roles.ts`).
    onglet: str
    #: Son tracé, pris dans le catalogue du front (`#lib/icones-svg.json`).
    icone: str
    #: La clé `ConfigSite` qui l'active. `None` pour une infrastructure.
    cle_actif: str | None = None
    #: Les réglages sans lesquels il ne peut pas fonctionner, même activé :
    #: (clé, libellé). Activé sans eux, il est « incomplet ».
    requis: tuple[tuple[str, str], ...] = ()
    #: Son plafond, s'il en a un — dit en clair, il se règle dans son onglet.
    plafond: str = ""
    coupable: bool = True
    #: Son onglet de réglages ne porte QUE lui : coupé, l'onglet se grise dans la
    #: rangée de l'administration. Faux pour un onglet partagé (SMTP porte aussi
    #: l'envoi des courriels, Maintenance la supervision) : le griser mentirait.
    onglet_dedie: bool = False


SERVICES: dict[str, Service] = {
    SERVICE_IA: Service(
        code=SERVICE_IA,
        libelle="Assistant IA",
        description=(
            "Rédaction d'une description, synthèse d'un contrat ou d'une affaire close, "
            "mise en forme des réponses par courriel, questions au règlement."
        ),
        perte=(
            "Les icônes ✨ disparaissent ; une réponse par courriel entre dans le fil sans "
            "mise en forme, et la synthèse d'une affaire close naît vide, à rédiger."
        ),
        onglet="ia",
        icone="lightbulb",
        cle_actif="llm_actif",
        onglet_dedie=True,
        requis=(("llm_api_key", "la clé d'API"),),
        plafond="Par usage : un nombre d'appels par mois, et par heure et par personne.",
    ),
    SERVICE_DIFFUSION: Service(
        code=SERVICE_DIFFUSION,
        libelle="Diffusion sur le groupe WhatsApp",
        description="Annonces, affaires et messages planifiés envoyés au groupe de la résidence.",
        perte=(
            "Plus rien ne part au groupe : la case « WhatsApp » disparaît des formulaires "
            "et les messages planifiés ne s'envoient plus."
        ),
        onglet="whatsapp",
        icone="whatsapp",
        cle_actif="whatsapp_enabled",
        onglet_dedie=True,
        requis=(("whatsapp_api_url", "l'adresse du relais WhatsApp"),),
    ),
    SERVICE_REPONSES_COURRIEL: Service(
        code=SERVICE_REPONSES_COURRIEL,
        libelle="Réponses par courriel",
        description=(
            "La boîte des affaires est relevée toutes les dix minutes : une réponse du "
            "syndic entre dans le fil de l'affaire qu'elle cite."
        ),
        perte=(
            "Les réponses restent dans la boîte de réception ; il faut les recopier "
            "dans le fil à la main."
        ),
        onglet="smtp",
        icone="inbox",
        cle_actif="imap_enabled",
        requis=(
            ("imap_server", "le serveur"),
            ("imap_username", "l'identifiant"),
            ("imap_password", "le mot de passe"),
        ),
    ),
    SERVICE_VERIF_VERSION: Service(
        code=SERVICE_VERIF_VERSION,
        libelle="Vérification de la version",
        description=(
            "Compare la version qui tourne à la branche que suit l'installation (main pour "
            "la référence, replica pour une réplique), sur le dépôt public, quand "
            "Administration › Exploitation › Installation s'ouvre. Seul le commit de l'image part."
        ),
        perte="Le bloc « Installation » dit « non vérifié » : un retard ou un écart ne se voit plus.",
        onglet="installation",
        icone="refresh-cw",
        cle_actif="verification_version_active",
    ),
    SERVICE_CONSERVATION: Service(
        code=SERVICE_CONSERVATION,
        libelle="Conservation des affaires",
        description=(
            "Chaque nuit, une affaire close arrivée à son échéance (2, 5 ou 10 exercices "
            "selon sa catégorie) perd ses pièces jointes, archivées puis copiées sur le PC "
            "de l'administration, et ses auteurs ; son texte reste, et le carnet d'entretien "
            "avec lui. Les échéances se lisent dans Administration › Maintenance. Cocher la case "
            "ajoute à la politique de confidentialité la phrase qui annonce ces durées."
        ),
        perte=(
            "Rien n'est archivé ni retiré : les affaires gardent leurs pièces jointes et "
            "leurs auteurs sans limite, et la politique de confidentialité ne peut annoncer "
            "aucune durée pour elles."
        ),
        onglet="maintenance",
        icone="archive",
        cle_actif="conservation_affaires_active",
    ),
    INFRA_SMTP: Service(
        code=INFRA_SMTP,
        libelle="Envoi des courriels",
        description=(
            "Le serveur d'envoi de tous les courriels du site — y compris ceux de "
            "sécurité : mot de passe oublié, vérification d'adresse, alertes."
        ),
        perte="Ne se coupe pas d'ici : sans lui, un compte perdu ne se récupère plus.",
        onglet="smtp",
        icone="message-square-text",
        coupable=False,
    ),
}

#: 🔴 Les courriels qu'AUCUN interrupteur de service ne coupe — codes de modèle.
#: `test_courriels_securite_hors_service.py` exige que chacun soit réellement
#: envoyé quelque part, et qu'aucun de ses envois ne lise un service.
COURRIELS_DE_SECURITE = frozenset(
    {
        "reinitialisation_mdp",
        "verification_email",
        "adresse_changement_avis",
        "alerte_systeme",
    }
)


#: Les services qu'une RÉPLIQUE garde sans que la référence les autorise (§4.11,
#: arbitré le 13/10/2026) : la vérification de la version ne coûte rien et sert à
#: suivre les mises à jour ; la conservation des affaires (#2014) est l'obligation
#: de la copropriété elle-même, que rien de la référence ne porte. Tous les autres
#: passent par le bail.
SERVICES_HORS_BAIL = frozenset({SERVICE_VERIF_VERSION, SERVICE_CONSERVATION})

#: Ce que la référence peut accorder dans un bail — la seule liste, lue par le
#: registre (`registre/decisions.py`) comme par l'installation.
SERVICES_AUTORISABLES = tuple(
    code for code, s in SERVICES.items() if s.coupable and code not in SERVICES_HORS_BAIL
)


def service(code: str) -> Service:
    """Le service demandé — `KeyError` si personne ne l'a déclaré ici."""
    return SERVICES[code]


def cle_actif(code: str) -> str:
    """La clé d'activation d'un service coupable — `ValueError` pour une infrastructure."""
    cle = SERVICES[code].cle_actif
    if cle is None:
        raise ValueError(f"« {code} » est une infrastructure : il ne se coupe pas.")
    return cle


def service_actif(cfg: dict, code: str) -> bool:
    """Le service est-il activé, d'après la configuration lue ?

    🔴 La SEULE lecture d'une clé d'activation. Seul `"1"` vaut oui — l'écran
    écrit `"1"`/`"0"`, et `normaliser_activation` ramène toute autre saisie.

    En démo publique, aucun service ne s'allume, quoi que dise la base (#1902) :
    sa configuration est réécrite par n'importe quel visiteur administrateur.

    🔴 Sur une RÉPLIQUE, un service que la référence n'a pas autorisé dans le bail
    est coupé, quoi que dise la base (§4.11, part de R6 #1882 avancée le 13/10/2026).
    """
    from app.utils.demo import est_demo

    return (
        not est_demo() and cfg.get(cle_actif(code)) == ACTIVE and autorise_par_la_reference(code)[0]
    )


def autorise_par_la_reference(code: str) -> tuple[bool, str]:
    """La référence autorise-t-elle ce service ici ? `(oui, "")`, ou `(non, pourquoi)`.

    La règle ne vaut que pour une installation qui se déclare RÉPLIQUE : la
    référence ne se limite pas elle-même, une installation d'essai n'appelle
    personne (§4.11, règles 7 et 9), et un rôle inconnu n'est pas une réplique.
    L'autorisation se lit dans le bail CRU — signé, à jour (`inscription.constat`) ;
    sans bail cru, aucun service.
    """
    if code in SERVICES_HORS_BAIL:
        return True, ""
    from app.utils.installation import est_replique

    if not est_replique():
        return True, ""
    from app.inscription.client import constat_courant

    constat = constat_courant()
    if constat.services is None or code in constat.services:
        return True, ""
    if constat.etat == "active":
        return False, "Non autorisé par la référence."
    return False, f"Non autorisé par la référence : {constat.raison}."


def normaliser_activation(valeur: str) -> str:
    """PURE. Ce qu'une clé d'activation enregistre : `"1"` ou `"0"`, rien d'autre.

    Ce sont les variantes acceptées par l'ancienne lecture IMAP — elles ne
    réapparaissent pas en base par une saisie à la main dans `PUT /config`.
    """
    return ACTIVE if (valeur or "").strip().lower() in ("1", "true", "oui") else DESACTIVE


#: Les clés d'activation, pour `PUT /config` qui les normalise à l'écriture.
CLES_ACTIVATION = frozenset(s.cle_actif for s in SERVICES.values() if s.cle_actif)

#: Le service que chaque clé d'activation allume — pour refuser à l'écriture ce
#: que la référence n'autorise pas.
SERVICE_DE_CLE = {s.cle_actif: s.code for s in SERVICES.values() if s.cle_actif}


def refus_d_activation(cle: str, nouvelle: str, ancienne: str | None) -> str:
    """Pourquoi `PUT /config` refuse d'écrire `nouvelle` dans `cle` — `""` s'il l'accepte.

    Une réplique n'ALLUME que ce que la référence autorise : la lecture le coupe de
    toute façon (`service_actif`), et l'écran ne doit pas laisser croire qu'il est
    allumé. Seul le PASSAGE à « 1 » se refuse : un onglet de réglages renvoie la clé
    telle qu'il l'a lue, et ne doit pas cesser de s'enregistrer pour un service
    allumé avant.
    """
    if cle not in SERVICE_DE_CLE or nouvelle != ACTIVE or ancienne == ACTIVE:
        return ""
    return autorise_par_la_reference(SERVICE_DE_CLE[cle])[1]


ETAT_ACTIF = "actif"
ETAT_COUPE = "coupe"
ETAT_INCOMPLET = "incomplet"


def etat(cfg: dict, s: Service, *, infra_active: bool = False) -> tuple[str, list[str]]:
    """L'état d'un service et ce qui lui manque pour fonctionner.

    Un service activé à qui manque un réglage est « incomplet » : il ne coupe
    rien, il échoue. L'écran le dit plutôt que de l'annoncer actif.
    """
    actif = infra_active if not s.coupable else service_actif(cfg, s.code)
    if not actif:
        return ETAT_COUPE, []
    manque = [libelle for cle, libelle in s.requis if not (cfg.get(cle) or "").strip()]
    return (ETAT_INCOMPLET if manque else ETAT_ACTIF), manque


def decrire(session) -> list[dict]:
    """Ce que l'écran reçoit : chaque service, son état et ce qui lui manque.

    Les VALEURS de réglage ne sortent pas : seulement leur présence — la clé
    d'API de l'assistant ou le mot de passe IMAP restent au serveur.
    """
    from app.utils.config_site import config_site
    from app.utils.email import envoi_actif

    cles = {c for s in SERVICES.values() for c, _ in s.requis} | CLES_ACTIVATION
    cfg = config_site(session, *cles)
    smtp = envoi_actif(session)
    rendu = []
    for s in SERVICES.values():
        code_etat, manque = etat(cfg, s, infra_active=smtp)
        autorise, refus = autorise_par_la_reference(s.code) if s.coupable else (True, "")
        rendu.append(
            {
                "code": s.code,
                "libelle": s.libelle,
                "description": s.description,
                "perte": s.perte,
                "plafond": s.plafond,
                "onglet": s.onglet,
                "onglet_dedie": s.onglet_dedie,
                "icone": s.icone,
                "coupable": s.coupable,
                "cle_actif": s.cle_actif,
                "etat": code_etat,
                "manque": manque,
                "autorise": autorise,
                "refus": refus,
            }
        )
    return rendu


__all__ = [
    "ACTIVE",
    "CLES_ACTIVATION",
    "COURRIELS_DE_SECURITE",
    "DESACTIVE",
    "ETAT_ACTIF",
    "ETAT_COUPE",
    "ETAT_INCOMPLET",
    "INFRA_SMTP",
    "SERVICES",
    "SERVICES_AUTORISABLES",
    "SERVICES_HORS_BAIL",
    "SERVICE_DE_CLE",
    "SERVICE_DIFFUSION",
    "SERVICE_IA",
    "SERVICE_REPONSES_COURRIEL",
    "SERVICE_VERIF_VERSION",
    "Service",
    "autorise_par_la_reference",
    "cle_actif",
    "decrire",
    "etat",
    "normaliser_activation",
    "refus_d_activation",
    "service",
    "service_actif",
]
