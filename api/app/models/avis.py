"""L'AVIS d'un utilisateur sur l'application — note, titre, description (#2075).

## Pourquoi un module à part, et pas `communaute.py`

L'avis s'affiche dans la rubrique Communauté (un onglet à côté de la Boîte à
idées), mais il ne parle pas de la résidence : il parle de **l'application**.
Les meilleurs, avec l'accord de leur auteur, partent sur le site vitrine
(coprofirst.fr). C'est un autre domaine, qui n'a ni périmètre, ni public visé,
ni vote — il a donc son module.

## Ce qui n'est PAS une colonne

- le **nom affiché** (« Prénom N. ») et le **rôle** : lus sur le compte, au
  moment où on les montre (`utils/avis`). Les figer ici ferait deux vérités
  qui divergent au premier changement de rôle.
- « archivé » en booléen : l'avis se RETIRE par un geste daté (`archive_le`),
  et `archive_par_id` dit qui l'a fait — l'auteur peut ressortir ce qu'il a
  rangé, pas ce que le gestionnaire a retiré.
"""

from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel

from app.utils import horloge


class Avis(SQLModel, table=True):
    __tablename__ = "avis"
    id: Optional[int] = Field(default=None, primary_key=True)
    #  OBLIGATOIRE : l'avis part avec le compte (`suppression_compte.
    #  CONTENUS_PERSONNELS`) — un témoignage nominatif, publié avec l'accord de
    #  son auteur, ne survit pas à l'effacement de celui-ci.
    #  UNIQUE : un avis par compte, qu'il modifie — la base le tient, pas
    #  seulement la route (deux envois simultanés).
    auteur_id: int = Field(foreign_key="utilisateur.id", unique=True)
    note: int  # 1 à 5 — la règle vit dans `utils/avis`
    titre: str
    description: str  # texte riche (HTML), assaini à l'affichage
    #  Ce qui a manqué — obligatoire sous 3 étoiles (`utils/avis.NOTE_REMARQUE`).
    remarque: Optional[str] = None
    #  L'accord de l'auteur pour coprofirst.fr : `None` = pas de réponse (ou
    #  note trop basse pour qu'on le lui demande), jamais un oui présumé.
    consentement_publication: Optional[bool] = None
    #  Retenu par le gestionnaire pour coprofirst.fr. Remis à `None` dès que
    #  l'auteur change ce qui a été relu.
    publication_validee_le: Optional[NaiveDatetime] = None
    reponse: Optional[str] = None
    reponse_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    reponse_le: Optional[NaiveDatetime] = None
    archive_le: Optional[NaiveDatetime] = None
    archive_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    mis_a_jour_le: Optional[NaiveDatetime] = None
