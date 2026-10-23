"""Le CONTRAT DE DONNÉES entre une installation et la référence (spec §4.11, R1 #1877).

Ce qui part d'une installation vers le registre de la référence est écrit ICI, et nulle
part ailleurs : l'installation (R2, R3) construit ses envois depuis ces schémas, la
référence (`registre/routeur.py`) les valide avec les mêmes. Deux copies divergeraient
au premier champ ajouté — et un champ qui part sans être écrit ici est une donnée
qui sort sans finalité.

## Les règles

1. **Chaque champ dit sa FINALITÉ** (`description`) : pourquoi la référence en a
   besoin. Un champ sans finalité n'a pas de base légale (`standards/14` §1).
2. **Aucune donnée de résident** (D5) : des nombres, jamais un nom, un courriel ni un
   contenu. Les seules données personnelles du contrat sont celles de
   l'ADMINISTRATEUR de l'installation (`AdministrateurInstallation`), et elles se
   DÉCLARENT (`personnel=True`). 🔒 `tests/test_registre_contrat.py`.
3. **Le contrat est versionné** (`VERSION_CONTRAT`) : un champ s'AJOUTE, optionnel,
   dans la même version ; en retirer un ou en changer le sens ouvre la suivante.
4. **Ce qu'une installation accepte** en s'inscrivant se lit dans
   `registre/conditions/` : elle déclare la version ET l'empreinte du texte montré
   à son administrateur, et la référence archive ce texte (`AcceptationConditions`).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

#: La version du contrat que ce code parle. Une installation qui en annonce une
#: autre est refusée avec un message qui le dit — jamais lue de travers.
VERSION_CONTRAT = 1

#: L'issue d'une mise à jour nocturne, telle que `deploiement/standard/mise-a-jour.sh`
#: la nomme (#1981) : rien touché, réussie, revenue à la version précédente, ou
#: sauvegarde restaurée. Les deux dernières sont un retour en arrière (alerte).
ISSUES_MISE_A_JOUR = ("echouee", "reussie", "revenue", "restauree")

#: L'état des correctifs du SYSTÈME de l'installation, jugé par `utils/sante_correctifs`
#: sur le contrôle quotidien de `deploiement/standard/correctifs-systeme.sh` : à jour,
#: en défaut (un correctif ne passe pas, la configuration n'est plus en service, l'état
#: est illisible), ou muet (le contrôle ne rend plus compte). Les deux derniers alertent.
ETATS_CORRECTIFS = ("a_jour", "en_defaut", "muet")

#: L'en-tête qui porte la signature d'un envoi de l'installation (Ed25519, base64),
#: sur les octets du corps — écrit ici : l'installation l'envoie, la référence le lit.
EN_TETE_SIGNATURE = "X-Signature-Installation"


def _personnel(finalite: str, **kw):
    """Un champ qui porte une donnée personnelle — de l'administrateur, jamais d'un résident."""
    return Field(description=finalite, json_schema_extra={"personnel": True}, **kw)


class _Contrat(BaseModel):
    #  Un champ inconnu est REFUSÉ : ce qui n'est pas au contrat n'entre pas,
    #  même par erreur d'une installation plus récente.
    model_config = ConfigDict(extra="forbid")


class AdministrateurInstallation(_Contrat):
    """Qui administre l'installation — le contact de la référence pour cette installation."""

    prenom: str = _personnel("s'adresser à l'administrateur", min_length=1, max_length=80)
    nom: str = _personnel("s'adresser à l'administrateur", min_length=1, max_length=80)
    courriel: EmailStr = _personnel(
        "le prévenir d'un incident de son installation (bail, mise à jour, sauvegarde)"
    )
    telephone: Optional[str] = _personnel(
        "le joindre quand un courriel ne suffit pas — facultatif",
        default=None,
        max_length=30,
    )


class DemandeInscription(_Contrat):
    """Ce qu'une installation envoie à la référence pour s'inscrire (R2 l'enverra)."""

    version_contrat: int = Field(description="lire la demande avec le bon contrat")
    conditions_acceptees: int = Field(
        description="prouver que les conditions en vigueur ont été acceptées"
    )
    empreinte_conditions: str = Field(
        description="prouver que le texte accepté est celui que la référence archive (SHA-256)",
        min_length=64,
        max_length=64,
    )
    cle_publique: str = Field(
        description="vérifier les signatures de l'installation (Ed25519, base64)",
        min_length=40,
        max_length=60,
    )
    version_logicielle: str = Field(
        description="savoir quelle version tourne, pour le canal et les vagues",
        min_length=1,
        max_length=40,
    )
    administrateur: AdministrateurInstallation = Field(
        description="le contact de la référence pour cette installation"
    )


class ReponseInscription(_Contrat):
    """Ce que la référence répond : l'identifiant qu'elle attribue, et l'état de l'inscription."""

    identifiant: str = Field(description="l'identifiant unique de l'installation, attribué ici")
    etat: str = Field(description="en_attente tant que l'opérateur n'a pas validé")


# ── Le bail (R2) — l'installation le demande chaque nuit, la référence le signe ──


class DemandeBail(_Contrat):
    """Ce qu'une installation envoie, signé de SA clé, pour obtenir ou renouveler son bail."""

    version_contrat: int = Field(description="lire la demande avec le bon contrat")
    identifiant: str = Field(
        description="retrouver l'inscription, attribuée par la référence", max_length=20
    )
    cle_publique: str = Field(
        description="vérifier la signature, et voir deux clés sous un même identifiant (clone)",
        min_length=40,
        max_length=60,
    )
    version_logicielle: str = Field(
        description="savoir quelle version tourne, pour le canal et les vagues",
        min_length=1,
        max_length=40,
    )


class Bail(_Contrat):
    """Ce que la référence ACCORDE : la seule chose qu'une installation croit d'elle (D19)."""

    identifiant: str = Field(description="l'installation à qui le bail est accordé")
    empreinte_cle: str = Field(
        description="attacher le bail à la clé de l'installation : une copie ne s'en sert pas"
    )
    etat: str = Field(description="en_attente, active, suspendue ou resiliee (§4.11)")
    canal: str = Field(description="la branche que l'installation suit (D21)")
    version_cible: Optional[str] = Field(
        default=None, description="la version vers laquelle la mettre à jour (R5)"
    )
    services_autorises: list[str] = Field(
        default_factory=list, description="les services du registre ouverts à l'installation (R6)"
    )
    epoque: int = Field(description="refuser le bail d'une référence d'avant un transfert (D24)")
    delivre_le: datetime = Field(description="dater le bail")
    echeance: datetime = Field(
        description="au-delà, le bail est échu : mode limité, jamais un arrêt (D19)"
    )


class BailSigne(_Contrat):
    """Le bail et la signature de la référence, sur `canonique(bail)`."""

    bail: Bail = Field(description="ce qui est accordé")
    signature: str = Field(description="prouver que la référence l'a accordé (Ed25519, base64)")


# ── Le rapport nocturne (R3) — écrit dès R1 : c'est le contrat qu'on accepte ──


class Identite(_Contrat):
    identifiant: str = Field(description="rattacher le rapport à son inscription")
    canal: str = Field(description="vérifier que l'installation suit le canal attribué")
    version_logicielle: str = Field(description="mesurer le retard de version")
    revision_base: Optional[str] = Field(
        default=None, description="savoir si la dernière migration est passée"
    )
    derniere_mise_a_jour: Optional[str] = Field(
        default=None,
        description="voir une mise à jour revenue en arrière (`ISSUES_MISE_A_JOUR`)",
    )
    se_declare_reference: Optional[bool] = Field(
        default=None,
        description="voir deux installations qui se déclarent référence (D24, R4b #1960)",
    )
    #  Le résultat des mises à jour du SYSTÈME — même famille que la dernière mise à
    #  jour de CoproFirst (conditions v1, §3 : « résultat de la dernière mise à
    #  jour »). Ajouté, optionnel, dans la version 1 du contrat (règle 3).
    correctifs_systeme: Optional[str] = Field(
        default=None,
        description="voir un serveur qui ne reçoit plus ses correctifs de sécurité "
        "(`ETATS_CORRECTIFS`)",
    )


class Hebergement(_Contrat):
    hebergeur: Optional[str] = Field(default=None, description="savoir où l'installation tourne")
    pays_donnees: Optional[str] = Field(
        default=None, description="vérifier que les données restent dans l'Union européenne"
    )
    architecture: Optional[str] = Field(default=None, description="publier les bonnes images")
    memoire_mo: Optional[int] = Field(default=None, description="prévenir une saturation")
    disque_total_mo: Optional[int] = Field(default=None, description="prévenir une saturation")
    disque_occupe_mo: Optional[int] = Field(default=None, description="prévenir une saturation")
    moteur_base: Optional[str] = Field(default=None, description="suivre les moteurs en service")
    taille_bases_mo: Optional[int] = Field(default=None, description="prévenir une saturation")
    certificat_expire_le: Optional[datetime] = Field(
        default=None, description="prévenir l'expiration du certificat TLS"
    )
    erreurs_5xx_24h: Optional[int] = Field(
        default=None, description="voir une installation en difficulté"
    )


class Sauvegarde(_Contrat):
    derniere_reussie_le: Optional[datetime] = Field(
        default=None, description="voir une sauvegarde qui ne se fait plus"
    )
    copie_hors_machine: Optional[bool] = Field(
        default=None, description="sur un seul serveur, la seule sauvegarde qui protège (D15)"
    )
    dernier_essai_restauration_le: Optional[datetime] = Field(
        default=None, description="savoir que la sauvegarde se restaure"
    )
    attendue: Optional[bool] = Field(
        default=None,
        description="ne pas alerter sur une sauvegarde coupée exprès (démo régénérée, #1982)",
    )


class Posture(_Contrat):
    documentation_api_coupee: Optional[bool] = Field(
        default=None, description="signaler une surface exposée"
    )
    cookie_securise: Optional[bool] = Field(
        default=None, description="signaler une session exposée"
    )
    secret_suffisant: Optional[bool] = Field(default=None, description="signaler un secret faible")
    lien_source_present: Optional[bool] = Field(
        default=None, description="vérifier l'obligation de l'AGPL §13"
    )


class CoproprieteRapport(_Contrat):
    identifiant: str = Field(description="distinguer les copropriétés d'une installation")
    #: Le nom d'une COPROPRIÉTÉ (« Résidence des Tilleuls »), pas d'une personne.
    nom: str = Field(description="reconnaître la copropriété dans le registre", max_length=120)
    lots: Optional[int] = Field(default=None, description="mesurer la taille servie")
    utilisateurs_actifs: Optional[int] = Field(
        default=None, description="mesurer l'usage, et le plafond du mode limité"
    )
    utilisateurs_inscrits: Optional[int] = Field(default=None, description="mesurer l'usage")
    volume_mo: Optional[int] = Field(default=None, description="mesurer le stockage")
    services_actifs: list[str] = Field(
        default_factory=list, description="savoir quels services sont employés"
    )


class Consommation(_Contrat):
    appels_ia: Optional[int] = Field(default=None, description="relevé de consommation (R7)")
    cout_ia_usd: Optional[float] = Field(default=None, description="relevé de consommation (R7)")
    messages_diffusion: Optional[int] = Field(
        default=None, description="relevé de consommation (R7)"
    )
    courriels_envoyes: Optional[int] = Field(
        default=None, description="relevé de consommation (R7)"
    )
    serveurs: Optional[int] = Field(default=None, description="relevé de consommation (R7)")


class Rapport(_Contrat):
    """Le rapport nocturne d'une installation (envoyé par R3)."""

    version_contrat: int = Field(description="lire le rapport avec le bon contrat")
    identite: Identite = Field(description="rattacher le rapport et suivre la version")
    hebergement: Hebergement = Field(description="prévenir les pannes d'hébergement")
    sauvegarde: Sauvegarde = Field(description="prévenir la perte de données")
    posture: Posture = Field(description="signaler une installation exposée")
    coproprietes: list[CoproprieteRapport] = Field(
        default_factory=list, description="mesurer ce que l'installation sert"
    )
    consommation: Consommation = Field(description="relevé de consommation (R7)")


#: Tous les schémas du contrat — ceux que le test parcourt.
SCHEMAS = (
    AdministrateurInstallation,
    DemandeInscription,
    ReponseInscription,
    DemandeBail,
    Bail,
    BailSigne,
    Identite,
    Hebergement,
    Sauvegarde,
    Posture,
    CoproprieteRapport,
    Consommation,
    Rapport,
)


def canonique(corps: dict) -> bytes:
    """La forme d'octets qu'on SIGNE : JSON trié, sans espaces, en UTF-8.

    La référence vérifie la signature sur les octets REÇUS (`routeur.py`), pas sur
    une resérialisation : cette forme sert à l'installation qui signe (R2).
    """
    return json.dumps(corps, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def octets_du_bail(bail: Bail) -> bytes:
    """Les octets SIGNÉS d'un bail — les mêmes chez la référence qui signe et chez
    l'installation qui vérifie : la forme canonique de sa forme JSON."""
    return canonique(bail.model_dump(mode="json"))
