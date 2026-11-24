"""Le prix d'une petite annonce, en centimes entiers — expansion de #3011.

`PetiteAnnonce.prix` était la seule colonne monétaire en flottant du dépôt (socle
06 §7). La migration 0351 ajoute `prix_centimes` et la remplit ; ce module est la
SEULE écriture et la seule lecture du prix, pour la durée de l'expansion :

- **écrire** (`poser_prix`) pose les DEUX colonnes, du même montant : la version
  précédente du code, qui ne lit que `prix`, reste juste après un retour arrière ;
- **lire** (`prix_centimes`) lit la nouvelle colonne — sauf quand elle manque ou
  contredit l'ancienne. Les deux ne peuvent diverger que si une version antérieure
  a écrit `prix` seule (un retour arrière, puis une correction d'annonce) : c'est
  alors `prix` qui porte la dernière saisie, et elle l'emporte.

La contraction (une version ultérieure, #3011) retire `prix` : elle exige d'abord
que les deux colonnes s'accordent sur chaque ligne de la production — la même
comparaison que `prix_centimes`, comptée en base.

Le champ servi `prix` (euros) reste : l'app iOS 1.0 le lit (`contrat/circulation/`).
"""

from __future__ import annotations

from app.models.communaute import PetiteAnnonce
from app.utils.montants import en_centimes, en_euros


def poser_prix(annonce: PetiteAnnonce, euros: float | int | None) -> None:
    """Le prix saisi, en euros, écrit dans les deux colonnes."""
    annonce.prix_centimes = en_centimes(euros)
    annonce.prix = en_euros(annonce.prix_centimes)


def prix_centimes(annonce: PetiteAnnonce) -> int | None:
    """Le prix lu, en centimes — `prix` l'emporte s'il dit autre chose (voir l'en-tête)."""
    ancien = en_centimes(annonce.prix)
    if annonce.prix_centimes is None or (ancien is not None and ancien != annonce.prix_centimes):
        return ancien
    return annonce.prix_centimes


def prix_euros(annonce: PetiteAnnonce) -> float | None:
    """Le prix lu, en euros — pour le champ `prix` servi et le fil d'activité."""
    return en_euros(prix_centimes(annonce))
