"""Le prix d'une petite annonce, en centimes entiers (#3011).

`PetiteAnnonce.prix` était la seule colonne monétaire en flottant du dépôt (socle
06 §7). L'expansion (0352, v3.125.0) a ajouté `prix_centimes` ; la contraction se
fait en deux temps (`tests/test_migrations_compatibles.py`) :

1. **ce temps-ci** — le code ne lit ni n'écrit plus que `prix_centimes`, et la 0353
   vide l'ancienne colonne après y avoir appliqué la règle de lecture de la version
   précédente : un retour arrière vers elle lit donc les centimes, jamais un prix
   d'avant une correction ;
2. **le suivant**, dans une version ultérieure — `drop_column`, avec sa preuve sans
   perte lue sur la production.

Le champ SERVI `prix` (euros) reste : l'app iOS 1.0 le lit (`contrat/circulation/`).
Il se calcule ici, depuis les centimes.
"""

from __future__ import annotations

from app.models.communaute import PetiteAnnonce
from app.utils.montants import en_centimes, en_euros


def poser_prix(annonce: PetiteAnnonce, euros: float | int | None) -> None:
    """Le prix saisi, en euros, écrit en centimes entiers."""
    annonce.prix_centimes = en_centimes(euros)


def prix_euros(annonce: PetiteAnnonce) -> float | None:
    """Le prix lu, en euros — pour le champ `prix` servi et le fil d'activité."""
    return en_euros(annonce.prix_centimes)
