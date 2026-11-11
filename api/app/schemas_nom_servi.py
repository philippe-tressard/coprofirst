"""« Prénom NOM » SERVI avec la personne — les deux clients le lisent (#2633).

## Pourquoi

Le site composait le nom d'une personne dans son front (`nomAffiche`, jumeau de
`utils/noms.nom_affiche`) ; l'app iOS l'aurait recopié à son tour depuis le front
publié (`standards/09` §8, règle 1). Le serveur le rend désormais avec l'objet,
et les deux clients LISENT `nom_affiche`.

## Deux formes, une règle

- **`NomServi`** : la personne porte `prenom` et `nom` (un compte, un contact) —
  le mélanger au schéma de lecture suffit ;
- la personne est APLATIE dans son porteur (`locataire_prenom`, `bailleur_nom`…) :
  le schéma déclare son propre champ calculé (`locataire_nom_affiche`…).

Les deux appellent `utils/noms.nom_affiche`, jamais une copie : c'est la règle
arbitrée le 31/08/2026 (le prénom garde sa casse, le nom passe en capitales).
Un champ calculé est vrai partout où le schéma est rendu, sans qu'un routeur
puisse l'oublier ; le contrat le déclare en lecture, jamais en entrée.
"""

from __future__ import annotations

from pydantic import BaseModel, computed_field

from app.utils import noms


class NomServi(BaseModel):
    """Mêlé au schéma de lecture d'une personne qui porte `prenom` et `nom`."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def nom_affiche(self) -> str:
        """« Jean-Baptiste FORT » (`utils/noms.nom_affiche`) — `''`, jamais `None`."""
        return noms.nom_affiche(getattr(self, "prenom", None), getattr(self, "nom", None))
