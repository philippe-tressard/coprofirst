"""Ce que le bail IMPOSE à cette installation — la porte des trois effets de R6 (#1882).

Le constat (`inscription/constat`) dit ce que vaut l'inscription ; ce module dit
s'il S'APPLIQUE ici. Trois effets le lisent, et lui seul :

| Effet | Où | Depuis |
|---|---|---|
| les services du bail | `utils/services.autorise_par_la_reference` | v2.149.0 (#1947) |
| le plafond de comptes actifs du mode limité (D18) | `inscription/plafond` | R6 |
| la lecture seule d'une installation suspendue (D20) | `inscription/suspension` | R6 |

## Les règles

1. **Seule une RÉPLIQUE est tenue par un bail** (§4.11, règles 7 et 9) : la
   référence ne passe jamais en mode limité, une installation d'essai n'appelle
   personne, et un rôle inconnu n'est pas une réplique.
2. **Aucun appel à la référence** : le constat se lit sur le bail RANGÉ
   (`client.constat_courant`). Une référence éteinte ne change rien à une
   installation active tant que son bail court (règle 4, D17).
3. **Un bail échu ramène au mode limité, jamais à la lecture seule** (D19) : c'est
   `constat.constater` qui le décide, l'échéance passant avant l'état du bail.
4. **Le retour au constat** (`REGISTRE_CONSTAT`) : le plafond et la lecture seule
   cessent de s'appliquer, sans nouvelle image — la soupape d'un faux positif.
   Les services restent ceux du bail : ils s'appliquent depuis v2.149.0.
"""

from __future__ import annotations

from typing import Optional

from app.config import get_settings
from app.inscription.constat import LIMITEE, SUSPENDUE, Constat

#: Le plafond du mode limité (D18) : au plus ce nombre de comptes actifs.
PLAFOND_COMPTES_ACTIFS = 5


def constat_de_la_replique() -> Optional[Constat]:
    """Le constat d'une RÉPLIQUE, ou None : ni la référence, ni un rôle inconnu (règle 1)."""
    from app.inscription.client import constat_courant
    from app.utils.installation import est_replique

    return constat_courant() if est_replique() else None


def en_constat_seulement() -> bool:
    """`REGISTRE_CONSTAT` : le plafond et la lecture seule ne s'appliquent plus (règle 4)."""
    return get_settings().registre_constat


def regime_applique() -> Optional[Constat]:
    """Le constat qui S'APPLIQUE ici — None quand rien ne s'applique (règles 1 et 4)."""
    if en_constat_seulement():
        return None
    return constat_de_la_replique()


def est_suspendue() -> bool:
    """L'installation est-elle en lecture seule ? Seul un bail cru, à jour et suspendu le dit."""
    regime = regime_applique()
    return regime is not None and regime.etat == SUSPENDUE


def plafond_applique() -> Optional[Constat]:
    """Le constat LIMITÉ qui plafonne les comptes actifs, ou None.

    La démo publique en est exemptée (spec `mode-demo.md` §9 et §11 q.3) : ses
    personnages sont des comptes partagés, recréés chaque nuit.
    """
    from app.utils.demo import est_demo

    if est_demo():
        return None
    regime = regime_applique()
    return regime if regime is not None and regime.etat == LIMITEE else None
