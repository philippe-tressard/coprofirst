"""Le journal des gestes de sécurité — **une seule porte**.

## Pourquoi ce module (#1040, audit du 19/09/2026)

Aucun événement de sécurité n'était journalisé : ni une connexion refusée, ni un
mot de passe changé, ni une élévation de rôle. Un compte compromis ou une attaque
par force brute — que le rate limit freine sans la **signaler** — ne laissaient
donc aucune trace exploitable après coup.

On pouvait constater qu'un mot de passe avait changé ; on ne pouvait pas savoir
**qui** l'avait changé, **quand**, ni combien de tentatives avaient précédé.
« Ce qu'on ne journalise pas n'a pas eu lieu » (`standards/07` §1).

## 🔴 Ce qui n'entre PAS dans une ligne de journal

**Aucune donnée personnelle**, et le précédent est dans ce dépôt : #777 a trouvé
des adresses e-mail journalisées en clair sur échec d'envoi. Un journal de
sécurité nomme un **identifiant** — un entier, celui de la base — jamais une
adresse, un mot de passe ou un jeton, **même tronqué** : un condensé partiel
d'adresse reste une donnée personnelle (`standards/14`).

C'est aussi la raison pour laquelle ce module ne reçoit pas d'objet `Utilisateur`
mais des identifiants : on ne peut pas journaliser par mégarde un champ qu'on n'a
pas reçu.

🔒 `api/tests/test_journal_securite.py` refuse un `email`, un `password` ou un
`jeton` ici **et** chez les appelants, exige un appel dans chacun des gestes
sensibles déclarés, et confronte cette liste à ce que les routeurs écrivent
(#1548) ; `test_journal_gestes_comptes.py` vérifie la ligne émise par les routes.

## Le niveau dit la lecture, pas la gravité du geste

`WARNING` pour ce qui mérite d'être **relu** — une connexion refusée, une
élévation de rôle —, `INFO` pour ce qui est normal mais doit rester traçable. Un
journal où tout est au même niveau ne se filtre pas, donc ne se lit pas.

⚠️ `WARNING` **n'est pas une alerte** : rien n'est envoyé à personne. Le canal
d'alerte est `check-reliability.sh`, et il compte les `ERROR`/`CRITICAL` de
l'API — journaliser une connexion refusée en `ERROR` ferait sonner le téléphone
à chaque faute de frappe sur un mot de passe.
"""

import logging
from typing import Optional

_logger = logging.getLogger("securite")

#: Les gestes tracés, et le niveau auquel ils se lisent.
#:
#: La table est ici et pas chez les appelants : c'est elle qui dit ce que le
#: projet considère comme sensible, et elle se relit d'un coup d'œil.
_NIVEAUX: dict[str, int] = {
    "connexion_refusee": logging.WARNING,
    "role_ajoute": logging.WARNING,
    "role_retire": logging.WARNING,
    "ban_communaute": logging.WARNING,
    "mot_de_passe_change": logging.INFO,
    "mot_de_passe_reinitialise": logging.WARNING,
    #  Un jeton de rafraîchissement déjà échangé qui revient : un vol probable,
    #  toutes les sessions du compte ont été fermées (27/09/2026).
    "jeton_rejoue": logging.WARNING,
    #  Un locataire lié à un lot par le seul nom (#1136) : il en porte les badges.
    "rattachement_auto": logging.WARNING,
    #  Un locataire qui se déclare lui-même sur les lots de son propriétaire,
    #  lus au fichier du syndic : il en reçoit les badges (04/10/2026). Et la
    #  déclaration d'un lot qui ne lui était pas proposé — requête forgée.
    "rattachement_declare": logging.WARNING,
    "rattachement_hors_proposition": logging.WARNING,
    #  Un bail demandé sur un lot dont on n'est pas copropriétaire (#1535) :
    #  l'écran ne le propose pas, la requête a donc été forgée.
    "bail_hors_de_ses_lots": logging.WARNING,
    #  Le cycle de vie d'un compte (#1548) : qui l'a ouvert, fermé, effacé.
    #  Après une suppression, cette ligne est la SEULE trace de qui l'a faite.
    "compte_valide": logging.WARNING,
    "compte_refuse": logging.WARNING,
    "compte_desactive": logging.WARNING,
    "compte_reactive": logging.WARNING,
    "compte_supprime": logging.WARNING,
    #  Une délégation : un tiers qui lit au nom d'un résident. La cible est le
    #  MANDANT — celui dont on lit —, l'aidant va dans le détail.
    "delegation_creee": logging.WARNING,
    "delegation_acceptee": logging.WARNING,
    "delegation_revoquee": logging.WARNING,
    #  L'adresse d'un compte qui va changer, puis qui a changé (#1549) : le
    #  chemin d'un détournement — nouvelle adresse, puis « mot de passe oublié ».
    "adresse_changement_demande": logging.WARNING,
    "adresse_changee": logging.WARNING,
    #  La purge des comptes inactifs (#1580, `utils/purge_comptes`) : personne
    #  n'agit, l'acteur est donc `-`. L'avertissement ouvre le délai de trente
    #  jours ; la suppression est, après elle, la seule trace du compte ; un
    #  compte d'administration inactif est épargné et SIGNALÉ — dormant, il est
    #  aussi un risque.
    "compte_purge_averti": logging.INFO,
    "compte_purge_inactivite": logging.WARNING,
    "compte_purge_epargne": logging.WARNING,
    "compte_purge_fermeture": logging.WARNING,
    #  Le compte rendu d'un point CS / Syndic validé (#2042) : par le lien d'un
    #  présent (sans compte — le jeton seul l'identifie), par le conseil, ou
    #  d'office au bout de 7 jours. Il rend des textes lisibles à l'affaire.
    "cr_valide_par_lien": logging.INFO,
    "cr_valide_force": logging.INFO,
    "cr_valide_auto": logging.INFO,
    #  L'administrateur valide POUR un présent qui a donné son accord (#2082) :
    #  un geste au nom d'autrui — WARNING, pour qu'il se lise.
    "cr_valide_par_derogation": logging.WARNING,
    #  Ce qu'un badge ouvre, posé ou changé par le conseil (#2217) : une porte
    #  PHYSIQUE. La dérivation des lots ne fait que proposer ; ce geste décide.
    "acces_perimetre_pose": logging.WARNING,
    #  Une fusion d'affaires conciliée (restreindre / élargir) : la principale
    #  change de lecteurs, des personnes liront ce qu'elles ne lisaient pas, sur
    #  confirmation nominative du conseil (`utils/fusion_conciliation`).
    "fusion_conciliation": logging.WARNING,
    #  L'EMPLOI d'un leurre (#2365, `utils/leurres`) : une connexion sur le faux
    #  compte, la fausse clé de maintenance présentée. Personne de légitime ne le
    #  fait — S6 de l'audit nocturne en fait un FAIL. WARNING et non ERROR : le
    #  point 6 du pré-check compte les ERROR, et un attaquant bloquerait la MEP.
    "connexion_leurre": logging.WARNING,
    "cle_maintenance_leurre": logging.WARNING,
}


def journaliser_securite(
    evenement: str,
    *,
    acteur_id: Optional[int] = None,
    cible_id: Optional[int] = None,
    detail: str = "",
) -> None:
    """Écrire une ligne de journal pour un geste de sécurité.

    `evenement` — une clé de `_NIVEAUX`. Une clé inconnue est journalisée en
    `WARNING` plutôt que refusée : un geste tracé sous un nom qu'on a oublié de
    déclarer vaut mieux qu'une exception qui ferait échouer la requête. Le journal
    ne doit jamais casser ce qu'il observe.

    `acteur_id` — **qui agit**. `None` quand l'acteur n'est pas identifié, ce qui
    est précisément le cas d'une connexion refusée, ou quand personne n'agit : la
    purge des comptes inactifs, que le planificateur déroule seul (#1580). Dans
    les deux cas, c'est une information en soi.

    `cible_id` — **sur qui**. Identique à `acteur_id` quand on agit sur soi-même
    (changer son propre mot de passe), et c'est voulu : la ligne reste lisible
    sans que l'appelant ait à choisir un cas particulier.

    `detail` — un complément **sans donnée personnelle** : un rôle, un motif, un
    compteur. Jamais une adresse, jamais un extrait de message.
    """
    niveau = _NIVEAUX.get(evenement, logging.WARNING)
    _logger.log(
        niveau,
        "securite %s acteur=%s cible=%s%s",
        evenement,
        acteur_id if acteur_id is not None else "-",
        cible_id if cible_id is not None else "-",
        f" {detail}" if detail else "",
    )
