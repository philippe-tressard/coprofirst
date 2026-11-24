"""L'écran de hall — un appareil appairé qui lit les affiches de son périmètre (#2770).

Une Apple TV branchée sur un écran du hall fait défiler les affiches de la résidence.
Elle ne fait que LIRE : aucune personne connectée derrière l'écran, aucun compte.

- `Ecran` : l'objet que voit le conseil (Espace CS › Écrans du hall) — un nom, un périmètre,
  sa dernière lecture. Il porte l'EMPREINTE de son jeton (#1389), jamais le brut, qui ne
  vit que sur l'appareil. Retirer l'écran, c'est supprimer la ligne : le jeton tombe.
- `AppairageEcran` : une demande d'appairage en cours (RFC 8628, *device authorization
  grant*). L'écran la crée sans être authentifié ; un membre du conseil la CONFIRME en
  saisissant le code court ; l'écran échange alors son code d'appareil contre son jeton,
  et la demande disparaît. Les deux codes se gardent par leur empreinte.

Les règles — portée, échéance, révocation — vivent dans `auth/jetons_appareil.py` (le
mécanisme commun aux montres et aux écrans) et `auth/appairage_ecran.py` (l'appairage).
Aucune donnée personnelle ici : ni auteur, ni adresse — le geste du conseil se lit au
journal de sécurité, par identifiant.

Aucune `Relationship` : un seul lien, `ecran.id`, déclaré par nom de table.
"""

from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel

from app.utils import horloge


class Ecran(SQLModel, table=True):
    __tablename__ = "ecran"
    id: Optional[int] = Field(default=None, primary_key=True)
    #  « Hall bât. 2 » — choisi par le conseil à l'appairage.
    nom: str
    #  UN code de l'arbre des périmètres : l'écran montre les affiches qui le couvrent.
    perimetre: str
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    #  L'empreinte du jeton d'écran (`auth/empreinte_jeton`) — le brut ne vit que sur l'écran.
    empreinte: str = Field(unique=True)
    #  Glissante : chaque lecture la repousse (`jetons_appareil.PORTEES["ecran"]`).
    expire_le: NaiveDatetime
    #  La dernière lecture des affiches par l'écran — `None` tant qu'il n'a rien lu.
    vu_le: Optional[NaiveDatetime] = None


class AppairageEcran(SQLModel, table=True):
    __tablename__ = "appairage_ecran"
    id: Optional[int] = Field(default=None, primary_key=True)
    #  Le code d'appareil (secret, long) que l'écran garde pour interroger.
    empreinte_code_appareil: str = Field(unique=True)
    #  Le code court affiché à l'écran, que le conseil saisit sur le site.
    empreinte_code_court: str = Field(unique=True)
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    expire_le: NaiveDatetime
    #  L'intervalle imposé entre deux interrogations, en secondes ; il grandit à chaque
    #  interrogation trop pressée (RFC 8628 §3.5, `slow_down`).
    intervalle: int = 5
    interroge_le: Optional[NaiveDatetime] = None
    #  Posés par le conseil à la confirmation : ce que deviendra l'écran.
    nom: Optional[str] = None
    perimetre: Optional[str] = None
    confirme_le: Optional[NaiveDatetime] = None
