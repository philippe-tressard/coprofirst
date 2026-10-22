"""Les deux tables de sauvegarde — configuration et historique des exécutions.

Extraites de `models/core.py` le 14/08/2026, au fil de l'eau : ce fichier avait
atteint 1 460 lignes et le contrôle de modularité refuse qu'un fichier déjà
au-dessus de 500 grossisse (rang 1 §4). Il fallait y ajouter la préférence
d'affichage du profil (#339).

C'est le bloc qui s'en détache le plus proprement : deux tables sans aucune
`Relationship` vers le reste du modèle, dont le sujet — quand sauvegarder, et ce
qui s'est passé la dernière fois — n'a rien à voir avec la vie de la copropriété.

⚠️ `core.py` les **ré-exporte** : les quelque vingt fichiers qui écrivent
`from app.models.core import HistoriqueSauvegarde` continuent de fonctionner. Un
déplacement de modèle ne doit pas se payer d'un diff de vingt fichiers, ni du
risque d'en oublier un — un import manquant ne se voit qu'à l'exécution du
chemin concerné, c'est-à-dire ici la nuit, pendant la sauvegarde.
"""

from app.utils import horloge
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel
from pydantic import NaiveDatetime


class StatutSauvegarde(str, Enum):
    en_cours = "en_cours"
    reussie = "reussie"
    echouee = "echouee"


class ConfigSauvegarde(SQLModel, table=True):
    """Le réglage de la sauvegarde : l'heure et le nombre de versions conservées.

    🔴 `frequence`, `jour_semaine` et `jour_mois` ont QUITTÉ le modèle (#2059, premier
    temps) : la sauvegarde est quotidienne depuis la 0139 et rien ne les lisait. Les
    colonnes restent en base le temps d'une version (migration compatible, #1757 :
    `CONTRACTIONS` annonce leur retrait) ; la 0307 leur donne un défaut pour que le
    code, qui ne les écrit plus, puisse insérer la ligne.
    """

    __tablename__ = "config_sauvegarde"
    id: Optional[int] = Field(default=None, primary_key=True)
    active: bool = True
    heure_execution: int = 3  # 0-23
    nb_versions_conservees: int = 7
    modifie_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    modifie_le: Optional[NaiveDatetime] = None


class HistoriqueSauvegarde(SQLModel, table=True):
    __tablename__ = "historique_sauvegarde"
    id: Optional[int] = Field(default=None, primary_key=True)
    declenchee_par: str = "automatique"  # automatique | manuelle
    declenchee_par_user_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    statut: StatutSauvegarde = StatutSauvegarde.en_cours
    #: Nœud qui a exécuté la tâche — renseigné À L'ÉCRITURE, jamais déduit à
    #: la lecture (cf. `utils/noeud.py`). Nullable et sans valeur par défaut :
    #: les lignes antérieures au 12/08/2026 resteront `None`, et c'est correct
    #: — personne ne sait sur quel nœud elles ont tourné, et l'inventer serait
    #: la faute retirée le 11/08 (#312).
    noeud: Optional[str] = Field(default=None, index=True)  # rpi1 | rpi2
    fichier_nom: Optional[str] = None
    fichier_chemin: Optional[str] = None
    taille_octets: Optional[int] = None
    message_erreur: Optional[str] = None
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    terminee_le: Optional[NaiveDatetime] = None
