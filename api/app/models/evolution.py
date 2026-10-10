"""**Une entrée de fil** — ce que les trois objets suivis ont en commun.

## La notion

Un ticket, une actualité et un événement portent chacun un **Historique** : une
suite d'entrées datées, signées, qui racontent ce qui s'est passé. Deux natures
SAISIES, partout :

| `type` | ce que l'entrée dit |
|---|---|
| `commentaire` | quelqu'un a écrit quelque chose |
| `etat` | l'objet a changé d'étape (`ancien_statut` → `nouveau_statut`) |

Et trois que le PRODUIT écrit, jamais un formulaire (`utils/evolutions.TYPES_SAISIS`
les refuse à la saisie, à la correction et à l'effacement) : `reponse` (un
message posté), `relance` (au syndic) et — depuis #1643 — **`synthese`**, la
Suite porteuse de la synthèse d'une affaire close. Celle-ci ne porte AUCUN
texte (`contenu` vide, il vit dans `synthese_affaire`) et c'est la seule entrée
du fil qui ait une visibilité propre : brouillon, le conseil seul la lit
(`utils/synthese_affaire/lecture`). Cet en-tête disait « jamais un troisième
type » : vrai des types saisis, faux du fil.

⚠️ Une **correction** n'est pas un type de plus : c'est un `commentaire`
préfixé (`utils/corrections`). Le noter ici parce que la tentation revient à
chaque écran.

## 🔴 Pourquoi ce mixin (15/09/2026)

Les trois modèles — `TicketEvolution`, `PublicationEvolution`,
`EvenementEvolution` — déclaraient **les mêmes sept champs**, dans le même
ordre, avec les mêmes valeurs par défaut. Trois écritures d'une notion qui n'en
est qu'une.

Ce n'est pas théorique : `fichiers_urls` a été ajouté aux trois à des dates
différentes, et l'un d'eux a porté `"[]"` comme défaut pendant que les autres
avaient `None` — deux comportements pour « aucune pièce jointe ».

## Ce que le mixin ne porte PAS, et pourquoi

* **La clé du porteur** (`ticket_id`, `publication_id`, `evenement_id`) : elle
  nomme la table d'en face. C'est précisément ce qui distingue les trois.
* **Les `Relationship`** : elles citent le modèle porteur, donc elles ne peuvent
  pas vivre ici sans que ce fichier connaisse les trois entités — l'inverse de
  ce qu'un socle doit faire.
* **`perimetre_cible`** : le ticket seul en a un. Un commentaire de ticket peut
  préciser un périmètre, une évolution de publication non — c'est une différence
  de **modèle**, pas un oubli, exactement comme pour « Saisi pour »
  (`utils/saisi_pour`).

## ⚠️ `auteur_id` GARDE sa clé étrangère ici — et ce n'est pas une inconséquence

`SaisiPourMixin` s'en prive, parce que deux de ses trois tables reçoivent la
colonne **par migration** et que SQLite refuse d'ajouter une colonne contrainte.
Ici, les trois tables portent `auteur_id` **depuis leur création**, avec la
contrainte : une base neuve et une base migrée décrivent donc la même chose, et
il n'y a aucune migration à écrire.

La règle n'est pas « jamais de clé étrangère dans un mixin » — c'est « le modèle
doit décrire ce que la base porte réellement ».
"""

from __future__ import annotations

from app.utils import horloge
from typing import Optional

from sqlmodel import Field

from app.utils.assiste_ia import AssisteIAMixin
from pydantic import NaiveDatetime


class EvolutionMixin(AssisteIAMixin):
    """Les sept champs d'une entrée de fil, hérités plutôt que recopiés — plus
    la marque `assiste_ia`, que le commentaire porte comme l'objet (#985)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    #: `commentaire` ou `etat` à la saisie ; `reponse`, `relance`, `synthese` écrits
    #: par le produit (voir l'en-tête).
    type: str
    contenu: Optional[str] = None
    #: Remplis pour une transition, vides pour un commentaire. Les deux
    #: ensemble : une étape sans son avant ne dessine aucun mouvement.
    ancien_statut: Optional[str] = None
    nouveau_statut: Optional[str] = None
    #: Facultatif depuis #1688 : l'entrée d'un compte supprimé reste au fil, sans nom.
    auteur_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    #: Tableau JSON d'URLs. `"[]"` et non `None` : « aucune pièce jointe » est
    #: une liste vide, pas une absence de réponse — c'est ce qui permet de lire
    #: la colonne sans garde à chaque appel.
    fichiers_urls: str = "[]"
    #: Le texte REÇU d'une réponse par courriel, quand l'assistant l'a mis en
    #: forme (#1322) ; `contenu` porte alors la version mise en forme. Vide
    #: partout ailleurs — sur le mixin pour que les trois fils se lisent pareil.
    contenu_origine: Optional[str] = None
