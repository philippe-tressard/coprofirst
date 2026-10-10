"""Les règles de la purge des comptes inactifs — seuils et questions, rien d'autre.

Aucun accès à la base, aucun envoi : chaque fonction prend un compte (ou deux
nombres) et répond. C'est ce qui les rend vérifiables sans monter la tâche, et
lisibles par le gabarit de la politique sans tirer le moteur de courriel.

## Les décisions, et leur pourquoi (#1580, 04/10/2026)

**Inactif** — la dernière connexion, ou, à défaut, la plus tardive de la création
et de la validation du compte. La connexion compte aussi quand elle est
silencieuse : l'échange du jeton de rafraîchissement l'écrit (`marquer_activite`),
sans quoi un résident resté connecté des mois paraîtrait inactif.

**Exclus, jamais supprimés** :

- un **administrateur**, et le **gestionnaire du site** (qui en est un, mais la
  question se pose aussi par son identifiant) : supprimer un compte d'administration
  peut retirer au site sa seule administration. La purge les **signale** au
  journal de sécurité, chaque jour où ils sont inactifs — un compte
  d'administration dormant est aussi un risque ;
- un compte qui **ne peut pas se connecter** (`actif` faux) — en attente de
  validation, refusé ou désactivé. Le courriel dirait « il suffit de vous
  connecter », et ce serait faux ; un compte en attente attend d'ailleurs une
  décision du conseil syndical, que la purge ne prend pas à sa place. Leur
  suppression reste un geste de l'administration (Admin › Utilisateurs).

**Banni de la Communauté** : la règle commune. Le bannissement restreint une
rubrique ; il ne justifie pas de conserver un compte au-delà de la durée annoncée.

## Le volume — ce qui protège d'une horloge faussée ou d'une base restaurée

Les avertissements partent **un par passage** (`PLAFOND_AVERTISSEMENTS_PAR_PASSAGE`) :
les suppressions, trente jours plus tard, s'échelonnent de même. Un passage qui
s'apprête à en supprimer davantage que `SURETE_NOMBRE_MAX`, ou plus de
`SURETE_PROPORTION_MAX` des comptes, n'est pas normal : il n'en supprime
**aucun** (`suppressions_anormales`).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

#: La durée d'inactivité annoncée par la politique, en années.
INACTIVITE_ANS = 2
#: …et telle qu'elle se compte : 731 jours, soit TOUJOURS au moins deux années
#: civiles, année bissextile comprise — jamais un jour plus tôt que l'annonce.
INACTIVITE = timedelta(days=365 * INACTIVITE_ANS + 1)

#: Le délai entre l'avertissement et la suppression.
DELAI_AVANT_SUPPRESSION_JOURS = 30
DELAI_AVANT_SUPPRESSION = timedelta(days=DELAI_AVANT_SUPPRESSION_JOURS)

#: Au-delà, un avertissement resté sans suite ne vaut plus : la personne est
#: prévenue de nouveau au lieu d'être supprimée. C'est le cas d'un compte
#: désactivé puis réactivé, ou d'une purge suspendue des semaines par le seuil.
VALIDITE_AVERTISSEMENT = timedelta(days=90)

#: Combien de comptes sont avertis à chaque passage, du plus anciennement inactif
#: au plus récent. Un seul : les suppressions qui suivent s'échelonnent de même,
#: et restent sous le seuil de sûreté.
PLAFOND_AVERTISSEMENTS_PAR_PASSAGE = 1

#: Le seuil de sûreté : au-delà de l'un OU de l'autre, aucun compte n'est supprimé.
SURETE_NOMBRE_MAX = 5
SURETE_PROPORTION_MAX = 0.10

#: Les motifs d'exclusion. Les deux premiers sont SIGNALÉS au journal.
MOTIF_ADMINISTRATEUR = "administrateur"
MOTIF_GESTIONNAIRE = "gestionnaire du site"
MOTIF_SANS_CONNEXION = "ne peut pas se connecter"
MOTIFS_SIGNALES = frozenset({MOTIF_ADMINISTRATEUR, MOTIF_GESTIONNAIRE})


def date_de_reference(user) -> datetime:
    """Depuis quand ce compte n'a plus donné signe de vie."""
    if user.derniere_connexion is not None:
        return user.derniere_connexion
    return max(d for d in (user.cree_le, user.decision_compte_le) if d is not None)


def est_inactif(user, maintenant: datetime) -> bool:
    return date_de_reference(user) <= maintenant - INACTIVITE


def exclusion(user, gestionnaire_id: Optional[int]) -> Optional[str]:
    """Le motif pour lequel la purge pour INACTIVITÉ ne touche pas ce compte, ou `None`.

    Un compte qui ne peut pas se connecter relève de `fermeture_echue`.
    """
    if not user.actif:
        return MOTIF_SANS_CONNEXION
    return compte_d_administration(user, gestionnaire_id)


def compte_d_administration(user, gestionnaire_id: Optional[int]) -> Optional[str]:
    """Jamais supprimé par la purge, ouvert ou fermé : il peut être la seule administration."""
    from app.models.roles import RoleUtilisateur

    if user.has_role(RoleUtilisateur.admin):
        return MOTIF_ADMINISTRATEUR
    if gestionnaire_id is not None and user.id == gestionnaire_id:
        return MOTIF_GESTIONNAIRE
    return None


def avertissement_echu(user, maintenant: datetime) -> bool:
    """L'avertissement est parti il y a au moins 30 jours — et pas trop longtemps —,
    et aucune activité ne l'a suivi : la suppression est permise."""
    averti = user.purge_avertie_le
    if averti is None:
        return False
    age = maintenant - averti
    return DELAI_AVANT_SUPPRESSION <= age <= VALIDITE_AVERTISSEMENT and (
        date_de_reference(user) < averti
    )


def avertissement_perime(user, maintenant: datetime) -> bool:
    averti = user.purge_avertie_le
    return averti is not None and maintenant - averti > VALIDITE_AVERTISSEMENT


#: Les comptes FERMÉS ou jamais décidés (#1822, arbitrage du 10/10/2026). Ils ne
#: peuvent pas se connecter : aucun avertissement ne leur part — « connectez-vous
#: pour le garder » serait faux —, la suppression est journalisée.
DELAI_REFUS_JOURS = 30
DELAI_REFUS = timedelta(days=DELAI_REFUS_JOURS)
#: Un compte désactivé suit la durée des comptes inactifs, comptée depuis sa
#: désactivation : `INACTIVITE`.
DELAI_ATTENTE_MOIS = 6
#: Six mois, toujours au moins : 31 jours par mois, jamais un jour plus tôt.
DELAI_ATTENTE = timedelta(days=31 * DELAI_ATTENTE_MOIS)

MOTIF_REFUSE = "refusé"
MOTIF_DESACTIVE = "désactivé"
MOTIF_EN_ATTENTE = "en attente de validation"


def fermeture_echue(user, maintenant: datetime) -> Optional[str]:
    """Le motif pour lequel ce compte fermé — ou jamais décidé — se supprime, ou `None`.

    Un compte OUVERT n'est jamais concerné : il relève de l'inactivité. Un compte
    ancien, fermé avant que la fermeture soit notée, porte la date de la migration
    qui l'a classé « désactivé » (#1822) : jamais plus tôt que l'annonce.
    """
    from app.utils.comptes import DESACTIVATION, REFUS

    if user.actif:
        return None
    if user.fermeture_compte == REFUS and user.compte_ferme_le is not None:
        return MOTIF_REFUSE if maintenant - user.compte_ferme_le >= DELAI_REFUS else None
    if user.fermeture_compte == DESACTIVATION and user.compte_ferme_le is not None:
        return MOTIF_DESACTIVE if maintenant - user.compte_ferme_le >= INACTIVITE else None
    if user.decision_compte_le is None and user.fermeture_compte is None:
        return MOTIF_EN_ATTENTE if maintenant - user.cree_le >= DELAI_ATTENTE else None
    return None


def suppressions_anormales(nb: int, total: int) -> bool:
    """Ce passage s'apprête-t-il à supprimer un volume anormal de comptes ?

    Une suppression seule n'est jamais anormale : sur une petite instance, elle
    dépasse 10 % à elle seule, et la règle n'appliquerait alors plus rien.
    """
    if nb <= 1:
        return False
    return nb > SURETE_NOMBRE_MAX or nb > total * SURETE_PROPORTION_MAX


def marquer_activite(user, maintenant: datetime) -> None:
    """Le compte vient de servir : il n'est plus inactif, l'avertissement tombe.

    Appelée par la connexion ET par l'échange du jeton de rafraîchissement — au
    plus une écriture par session de deux heures, jamais une par requête.
    """
    user.derniere_connexion = maintenant
    user.purge_avertie_le = None


__all__ = [
    "DELAI_AVANT_SUPPRESSION",
    "DELAI_AVANT_SUPPRESSION_JOURS",
    "INACTIVITE",
    "INACTIVITE_ANS",
    "PLAFOND_AVERTISSEMENTS_PAR_PASSAGE",
    "SURETE_NOMBRE_MAX",
    "SURETE_PROPORTION_MAX",
    "VALIDITE_AVERTISSEMENT",
    "avertissement_echu",
    "avertissement_perime",
    "date_de_reference",
    "compte_d_administration",
    "est_inactif",
    "exclusion",
    "fermeture_echue",
    "marquer_activite",
    "suppressions_anormales",
]
