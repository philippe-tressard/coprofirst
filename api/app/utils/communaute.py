"""L'accès à la rubrique Communauté — sondages, boîte à idées, petites annonces.

## Pourquoi ce module (28/08/2026)

La règle était écrite **quatre fois** — `routers/idees.py`,
`routers/annonces.py`, `routers/signalements.py` et `routers/sondages/commun.py` —
et elle avait **déjà divergé** : `signalements.py` répondait « Votre accès à la
Communauté est suspendu. », sans la durée ni l'avertissement sur la 2ᵉ infraction
que les trois autres donnaient. Un même refus, deux vérités pour l'utilisateur
selon l'écran d'où il venait. L'échappement Unicode différait lui aussi, ce qui
rendait les copies invisibles à un grep naïf.

⚠️ C'est la forme la plus coûteuse de la duplication : elle ne casse rien, aucun
test ne rougit, et c'est la copie **la moins relue** qui devient fausse.

Elle vit donc ici, une fois, sous **deux formes** :

  • `motif_de_refus` répond sans lever — c'est ce dont un COMPTEUR a besoin :
    il ne peut pas lever une 403, il doit rendre zéro ;
  • `exiger_acces` lève la 403 — c'est ce dont un ENDPOINT a besoin.

⚠️ La seconde appelle la première. Deux formulations de la même règle finiraient
par diverger, et c'est du côté non testé qu'elles seraient fausses.

## Le vocabulaire de la sanction vit ici AUSSI (29/08/2026)

Le message de refus (« vous ne pouvez pas entrer ») et la notification de pose du
ban (« voici pourquoi ») disaient la même chose à la même personne, en des termes
différents : « **rubrique** Communauté » côté refus, « **section** Communauté »
côté administration, et deux apostrophes distinctes. Le front en portait une
troisième copie, réécrite dans `sondages/+page.svelte`.

Un même utilisateur lisait donc jusqu'à trois formulations d'une seule décision.
Le module porte désormais les deux faces — `MOTIF_*` pour le refus, `NOTIFICATION_BAN`
pour l'annonce — et **le front ne réécrit plus rien** : `UserRead` expose le motif
calculé (`communaute_motif_refus`), l'écran l'affiche. La règle ne franchit pas la
frontière front/API en double, c'est sa CONCLUSION qui la franchit.

## Ce que la règle dit

| Cas | Pourquoi |
|---|---|
| syndic, mandataire | la rubrique est un espace **entre résidents** ; ces profils n'en sont pas |
| accès définitivement suspendu | décision d'administration, sans terme |
| suspension probatoire en cours | un mois, après une première infraction |
"""

from datetime import datetime
from app.utils import horloge
from typing import Optional

from fastapi import HTTPException

from app.models.core import StatutUtilisateur, Utilisateur


#  Le vocabulaire, écrit une fois. « rubrique » et non « section » : c'est le
#  terme employé par le front, la documentation et les quatre routeurs — trois
#  contre un, et c'est le mot que l'utilisateur voit dans la navigation.
MOTIF_PROFIL = "La rubrique Communauté n'est pas accessible à votre profil"
MOTIF_BAN_DEFINITIF = "Votre accès à la rubrique Communauté a été définitivement suspendu."
MOTIF_BAN_PROBATOIRE = (
    "Votre accès à la rubrique Communauté est suspendu pour une période probatoire "
    "d’un mois. À la 2ᵉ infraction, vous serez banni définitivement."
)

#  L'autre face de la même décision : ce que l'administration ANNONCE en la
#  posant. Le corps reprend le motif mot pour mot — c'est le même fait.
NOTIFICATION_BAN = {
    True: (
        "Accès à la Communauté suspendu définitivement",
        MOTIF_BAN_DEFINITIF + " Cette décision fait suite à une 2ᵉ infraction.",
    ),
    False: ("Accès à la Communauté suspendu (1 mois)", MOTIF_BAN_PROBATOIRE),
}


def notification_de_ban(definitif: bool) -> tuple[str, str]:
    """(titre, corps) de la notification envoyée quand un ban est posé.

    ⚠️ Le corps reprend `MOTIF_*` : l'utilisateur qui reçoit l'annonce et celui
    qui se heurte au refus doivent lire la même phrase, sinon il croit à deux
    décisions distinctes.
    """
    return NOTIFICATION_BAN[bool(definitif)]


def motif_de_refus(
    user: Utilisateur, maintenant: Optional[datetime] = None, *, profil: bool = True
) -> Optional[str]:
    """Le motif du refus d'accès à la Communauté, ou `None` si l'accès est ouvert.

    ⚠️ Ne lève pas : un compteur doit pouvoir poser la question sans interrompre
    sa réponse. `exiger_acces` s'en charge pour les endpoints.

    `profil=False` : la seule rubrique ouverte au syndic et au mandataire, l'avis
    sur l'application (#2075, arbitrage du 18/10/2026) — un bannissement, lui,
    s'applique toujours.
    """
    maintenant = maintenant or horloge.maintenant()
    if profil and user.statut in (StatutUtilisateur.syndic, StatutUtilisateur.mandataire):
        return MOTIF_PROFIL
    if user.communaute_interdit:
        return MOTIF_BAN_DEFINITIF
    if user.communaute_ban_jusqu_au and user.communaute_ban_jusqu_au > maintenant:
        return MOTIF_BAN_PROBATOIRE
    return None


def acces_ouvert(user: Utilisateur, maintenant: Optional[datetime] = None) -> bool:
    """L'accès est-il ouvert ? La forme que lisent les compteurs."""
    return motif_de_refus(user, maintenant) is None


def exiger_acces(user: Utilisateur, *, profil: bool = True) -> None:
    """Lève une 403 si l'accès est refusé. La forme que lisent les endpoints."""
    motif = motif_de_refus(user, profil=profil)
    if motif:
        raise HTTPException(403, motif)
