"""L'état descriptif du règlement, en attente d'être appliqué — la table de passage (#2213).

Deux natures d'import, un seul atelier (l'onglet Imports) : la liste du SYNDIC dit
qui possède quoi (`lot_import`) ; l'état descriptif du RÈGLEMENT dit ce qu'est
chaque lot — nature, porte ou place, niveau, circulation qui le dessert, tantièmes.
Les deux se rapprochent sur le **numéro de lot**.

Une table à part plutôt que des colonnes de plus sur `lot_import` : les deux
fichiers n'ont ni les mêmes états (un lot du règlement n'a pas d'occupant à
rapprocher) ni la même purge, et les mêler aurait fait passer chaque lot du
règlement pour une ligne du syndic « en attente ».

🔴 Le fichier d'une copropriété réelle n'entre jamais dans le dépôt (public) : il est
tenu en local par la copropriété et téléversé par l'administration.
"""

from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel

from app.utils import horloge


class ImportEtatDescriptif(SQLModel, table=True):
    """Un fichier téléversé — un seul en attente à la fois ; le suivant le remplace."""

    __tablename__ = "import_etat_descriptif"
    id: Optional[int] = Field(default=None, primary_key=True)
    #: Ce que les en-têtes ont dit : `{cles: [{code, libelle, denominateur}],
    #: avec_circulation, erreurs}` — les lignes, elles, sont dans `ligne_etat_descriptif`.
    entete_json: str = Field(default="{}")
    importe_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    #: Posé quand l'import a été appliqué au patrimoine ; il reste alors en trace.
    applique_le: Optional[NaiveDatetime] = None


class LigneEtatDescriptif(SQLModel, table=True):
    """Une ligne de l'état descriptif, telle que le fichier l'écrit."""

    __tablename__ = "ligne_etat_descriptif"
    id: Optional[int] = Field(default=None, primary_key=True)
    import_id: int = Field(foreign_key="import_etat_descriptif.id", index=True)
    rang: int
    lot: str
    batiment: Optional[str] = None
    nature: Optional[str] = None
    numero_usage: Optional[str] = None
    niveau: Optional[str] = None
    #: La lettre du bâtiment qui dessert ; vide ou « / » = accès direct.
    circulation: Optional[str] = None
    #: `{code_de_cle: numerateur}`.
    quotes_json: str = Field(default="{}")
    #: Une DIVISION postérieure au recueil : le numéro du lot d'origine.
    lot_origine: Optional[str] = None
    #: L'acte ou la page qui fonde la ligne.
    source: Optional[str] = None
