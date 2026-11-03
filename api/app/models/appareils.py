"""Un téléphone qui sonne pour une personne — l'appareil des notifications push (#2493).

Spécification : `specs/architecture/notifications-push.md` §6.1. L'application
iOS enregistre son appareil à la connexion (`POST /appareils`) et le retire à la
déconnexion ; la porte d'envoi (`utils/push/porte.py`) le lit quand la cloche sonne.

⚠️ **Le jeton APNs se garde en clair, et c'est une exception déclarée** à la
règle « un jeton se stocke par son empreinte » (#1389) : celle-ci vise les jetons
qu'on VÉRIFIE, qu'une copie de la base rendrait utilisables. Un jeton APNs ne sert
qu'avec la clé `.p8`, que l'installation n'a pas, et on doit le TRANSMETTRE — une
empreinte ne servirait à rien. 🔒 `test_push_porte.py` tient l'exception : aucune
ligne de journal ne le porte.

Aucune `Relationship` : un seul lien, `utilisateur.id`, déclaré par nom de table.
"""

from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel

from app.utils import horloge

#: L'APNs à viser : celui de l'App Store, ou celui d'une application de développement.
ENVIRONNEMENTS = ("production", "developpement")


class Appareil(SQLModel, table=True):
    __tablename__ = "appareil"
    id: Optional[int] = Field(default=None, primary_key=True)
    #  À qui l'appareil sonne.
    utilisateur_id: int = Field(foreign_key="utilisateur.id", index=True)
    jeton: str = Field(unique=True)
    environnement: str = "production"
    #  L'identifiant opaque tiré par l'application (§5) — le seul qui part chez Apple.
    abonnement: str = Field(unique=True)
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    #  Rafraîchi à chaque enregistrement : un appareil muet depuis 60 jours se purge.
    vu_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
