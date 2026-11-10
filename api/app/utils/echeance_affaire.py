"""L'ÉCHÉANCE d'une affaire datée — « dans combien de jours ? », dérivé, jamais saisi.

## Pourquoi un module (10/11/2026, maquette C « Échéance », choisie parmi cinq)

Au fil, une affaire de nature Calendrier ne disait pas QUAND elle a lieu : sa
gouttière portait l'heure de la dernière nouvelle, puis « CAL. », et la date de
l'événement se cherchait dans le texte. La gouttière porte désormais une
vignette : le délai d'abord (« J-8 »), la ou les dates ensuite.

Le délai est une règle d'affichage que le site ET l'app iOS montrent : elle se
calcule ici, en **jours civils de Paris** (`horloge`), et le client LIT le
libellé (`standards/09` §8, règle 1 ; #2501). Les dates, elles, restent des
valeurs typées (`debut`, `fin`) que chaque client rend avec son formateur.

| État | Quand | Libellé |
|---|---|---|
| `a_venir` | le jour du début n'est pas arrivé | « J-8 » |
| `jour_j` | c'est le jour du début | « Jour J » |
| `en_cours` | après le début, jusqu'au jour de fin compris | « En cours » |
| `passee` | le dernier jour est derrière nous | « Passé » |
| `close` | l'affaire est close (résolue, annulée…) | aucun — la date seule |

Une affaire close ne compte plus : « J-3 » sur une intervention annulée
annoncerait ce qui n'aura pas lieu. La date reste, elle dit quand c'était prévu.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.utils import horloge
from app.utils.etat_affaire import affaire_close

#: Le libellé d'un état qui n'a pas de nombre à dire.
LIBELLES_ETAT: dict[str, Optional[str]] = {
    "jour_j": "Jour J",
    "en_cours": "En cours",
    "passee": "Passé",
    "close": None,
}


def echeance(ticket: Any, *, aujourd_hui: Optional[date] = None) -> Optional[dict]:
    """L'échéance d'une affaire DATÉE, ou `None` si elle n'a pas de date.

    `jours` : jours civils jusqu'au début (négatif une fois le début passé).
    `plusieurs_jours` : la fin tombe un autre jour que le début — le client
    montre alors les deux dates. Une fin antérieure au début est ignorée.
    """
    debut = getattr(ticket, "debut", None)
    if debut is None:
        return None
    jour = aujourd_hui or horloge.aujourd_hui()
    premier = horloge.jour_civil(debut)
    fin = getattr(ticket, "fin", None)
    dernier = max(premier, horloge.jour_civil(fin)) if fin is not None else premier
    jours = (premier - jour).days

    if affaire_close(getattr(ticket, "statut", None)):
        etat = "close"
    elif jours > 0:
        etat = "a_venir"
    elif jours == 0:
        etat = "jour_j"
    elif jour <= dernier:
        etat = "en_cours"
    else:
        etat = "passee"

    libelle = f"J-{jours}" if etat == "a_venir" else LIBELLES_ETAT[etat]
    return {
        "etat": etat,
        "jours": jours,
        "libelle": libelle,
        "plusieurs_jours": dernier != premier,
    }
