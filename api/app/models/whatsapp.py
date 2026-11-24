"""Les tables du canal WhatsApp — messages planifiés et journal d'envoi.

Extrait de `core.py` le 05/09/2026, **au fil de l'eau** : le fichier faisait
1 078 lignes et le garde-fou de modularité (rang 1, `standards/02` §6) a refusé
qu'il grossisse pour recevoir `Ticket.epingle`. La règle est « on découpe le
fichier QUAND on y touche » — et ce sont ces deux tables-ci qui partent, parce
qu'elles sont les seules du fichier à **ne porter aucun `Relationship`** : elles
se déplacent sans créer de cycle d'import, là où `Ticket` et `Utilisateur` se
tiennent l'un l'autre.

C'est le même découpage que `copropriete.py` (13/08), `communaute.py` (16/08),
`validations.py` et `tickets.py` (17/08) : les noms restent **ré-exportés par
`core.py`**, donc aucun module appelant n'a une ligne à changer.

⚠️ `models/__init__.py` doit importer ce module : c'est l'import qui enregistre
la table auprès de SQLModel avant `create_all`. Un modèle que personne n'a
importé n'existe pas pour `metadata`, et la table manquerait sans le moindre
message — c'est écrit dans l'en-tête de `__init__.py`, et ça vaut ici.
"""

from app.utils import horloge
from typing import Optional

from sqlmodel import Field, SQLModel
from pydantic import NaiveDatetime


class WhatsAppScheduled(SQLModel, table=True):
    __tablename__ = "whatsapp_scheduled"
    id: Optional[int] = Field(default=None, primary_key=True)
    label: str  # ex. "Encombrants Bd Hostachy"
    message: str  # texte du message
    cron_rule: str  # ex. "3eme_samedi" ou "4eme_samedi"
    enabled: bool = True
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    mis_a_jour_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class WhatsAppLog(SQLModel, table=True):
    __tablename__ = "whatsapp_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    scheduled_id: Optional[int] = Field(default=None, foreign_key="whatsapp_scheduled.id")
    label: str = ""
    message: str
    #  envoyé | échec | incertain | en cours — les constantes `STATUT_*` de
    #  `utils/whatsapp`, seules écrites ici (🔒 `test_colonnes_etat_fermees.py`).
    statut: str = "envoyé"
    erreur: Optional[str] = None
    envoye_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
