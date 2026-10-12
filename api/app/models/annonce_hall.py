"""La table des annonces de hall — l'affiche PDF punaisée dans les halls.

Extraite de `models/core.py` le 15/08/2026, au fil de l'eau : ce fichier était à
1 433 lignes et le contrôle de modularité refuse qu'un fichier déjà au-dessus de
500 grossisse (rang 1 §4). Il fallait y ajouter le drapeau `confidentiel` des
actualités (#347) — et c'est justement l'affiche de hall que la confidentialité
interdit, les deux notions se touchent donc dans le même lot.

Même parti pris que `models/sauvegarde.py` : c'est un bloc qui se détache
proprement — une table sans aucune `Relationship` vers le reste du modèle, dont
les seuls liens sont deux clés étrangères déclarées par nom de table.

⚠️ `core.py` la **ré-exporte** : les fichiers qui écrivent
`from app.models.core import AnnonceHall` continuent de fonctionner, et c'est cet
import qui enregistre la table dans les métadonnées SQLModel.
"""

from app.utils import horloge
from typing import Optional

from sqlmodel import Field

from app.utils.perimetres import perimetre_cible_json

from app.utils.assiste_ia import AssisteIAMixin
from pydantic import NaiveDatetime


class AnnonceHall(AssisteIAMixin, table=True):
    """Annonce imprimable affichée dans le hall des bâtiments (PDF A4 / A5).

    Le PDF est généré à la création puis figé sur disque : il fait foi (c'est
    lui qui a été envoyé au CS et affiché dans le hall). Une correction passe
    donc par une nouvelle annonce, jamais par une régénération silencieuse.
    """

    __tablename__ = "annonce_hall"
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    message: str  # HTML riche (RichEditor)
    #  JSON de codes de l'arbre ; le défaut se lit dans les données (#1567).
    perimetre_cible: str = Field(default_factory=perimetre_cible_json)
    format_demande: str = "auto"  # auto | a4 | a5
    format_effectif: str = "a4"  # a4 | a5
    images_json: str = "[]"  # JSON: photos facultatives (max 2)
    #  La clé du PDF (`annonces-hall/…`, #1816) — voir `Document.fichier_cle`.
    pdf_cle: Optional[str] = None
    pdf_chemin: str = ""  # chemin absolu, relu par la version précédente seule
    pdf_nom: str = ""  # nom proposé au téléchargement
    taille_octets: Optional[int] = None
    destinataires: str = "[]"  # JSON: emails notifiés
    envoye_le: Optional[NaiveDatetime] = None
    archivee: bool = False
    #  L'affaire « Actualité » d'origine (#1091, migration 0209). ⚠️ PAS de
    #  `foreign_key=` : la migration 0117 a tenté d'en poser une sur la colonne
    #  voisine et a crashé (SQLite refuse d'altérer les contraintes d'une table
    #  existante). La déclarer ferait porter à une base neuve (`create_all`) un
    #  schéma que les bases migrées n'ont pas. (`publication_id` : retirée par
    #  la 0238, #1177.)
    ticket_id: Optional[int] = Field(default=None)
    auteur_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
