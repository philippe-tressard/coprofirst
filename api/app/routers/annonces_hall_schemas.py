"""Les schémas de l'affiche de hall — ce qui entre, ce qui sort.

Extrait de `routers/annonces_hall.py` le 02/09/2026, quand le plafond de
modularité a refusé le branchement de la règle d'archivage (#515). Troisième
découpage du même fichier, après `annonces_hall_courriels` et
`annonces_hall_apercu` — la couture est la même à chaque fois : ce qui DÉCLARE
part, ce qui DÉCIDE reste.

`AnnonceHallRead` est la SEULE description de la lecture depuis #2525 : elle
n'existait pas (« la déclarer ferait une seconde description de `_to_read` »), et
le contrat annonçait donc `{}` à l'app iOS. `_to_read` la remplit, sans se décrire
à côté.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.utils.assiste_ia import AssisteIAEntree
from app.utils.perimetres import perimetre_defaut_liste
from app.utils.perimetres.servi import AvecPerimetreLibelle


class AnnonceHallBase(BaseModel):
    titre: str
    message: str
    perimetre_cible: list[str] = Field(default_factory=perimetre_defaut_liste)
    format_demande: str = "auto"
    images: list[str] = []


class AnnonceHallCreate(AnnonceHallBase, AssisteIAEntree):
    #  🔴 La DIFFUSION est un ACTE, et elle se coche (section 9 du cadre #430).
    #
    #  L'envoi au CS était AUTOMATIQUE jusqu'au 18/08, puis supprimé le même jour
    #  parce qu'il partait au moindre essai de mise en page. Il revient ici sous sa
    #  forme juste : un choix, décoché par défaut.
    #
    #  ⚠️ Décoché par défaut, et c'est le point : la valeur par défaut d'un envoi
    #  est « ne pas envoyer ». Un défaut à `True` reproduirait l'automatisme qu'on
    #  vient de retirer, en donnant l'illusion du choix.
    envoyer_cs: bool = False
    #  Les deux autres canaux de la Diffusion (#480). Mêmes règles : décochés par
    #  défaut, et CONSOMMÉS — un champ ouvert dans l'interface que le serveur
    #  ignorerait est ce que le cadre interdit.
    envoyer_syndic: bool = False
    partager_whatsapp: bool = False
    #  La 4e case : « Envoyer une copie à … ». Le destinataire est l'auteur de
    #  l'AFFICHE — voir `app/utils/copie_auteur.py`.
    envoyer_auteur: bool = False


class AnnonceHallArchive(BaseModel):
    """« Archiver » ou « Restaurer » une affiche : la DÉCISION HUMAINE, et elle seule.

    En LECTURE (`_to_read`), une affiche porte deux états : `archivee`, l'état
    EFFECTIF (archivée à la main, **ou** par la règle du site 30 jours après l'envoi,
    `utils/archivage`, #515), et `archivee_manuellement`, la décision humaine qui dit
    si « Restaurer » a un effet. En ENTRÉE, le geste ne porte que la décision :
    `archivee_manuellement` avait été recopié ici, requis, et le site, qui n'envoie
    que `{ archivee }`, recevait 422 (#2524). Un client qui l'envoie encore est
    accepté : le champ en trop est ignoré. 🔒 test_annonce_hall_archiver.py
    """

    archivee: bool


class AnnonceHallRead(AvecPerimetreLibelle):
    """Une affiche de hall telle que l'Historique la montre, ses gestes compris (#2525)."""

    id: int
    titre: str
    message: str
    assiste_ia: bool = False
    apercu: str
    perimetre_cible: list[str]
    perimetre_label: str
    format_demande: str
    format_effectif: str
    format_label: str
    images: list[str]
    pdf_nom: str
    taille_octets: Optional[int] = None
    destinataires: list[str]
    envoye_le: Optional[datetime] = None
    #: EFFECTIF : archivée à la main, ou par la règle du site (#515).
    archivee: bool
    #: La décision humaine seule — ce que « Restaurer » défait.
    archivee_manuellement: bool
    ticket_id: Optional[int] = None
    cree_le: datetime
    auteur_nom: str
    #: 📦 « Archiver » : tant qu'elle n'est pas rangée.
    peut_archiver: bool
    #: ↩️ « Restaurer » : rangée À LA MAIN — rangée par le temps, le geste n'aurait
    #: aucun effet, et il ne s'offre pas (#515).
    peut_restaurer: bool
    #: 🗑️ « Supprimer définitivement » : l'administrateur (`require_admin`).
    peut_supprimer: bool


class SourceReprenable(BaseModel):
    """Un élément du fil qu'une affiche peut reprendre (`utils/sources_affiche`)."""

    cle: str
    type: str
    famille: str
    id: int
    titre: str
    date: datetime
    epingle: bool


class PrefillAffiche(BaseModel):
    """Les champs d'un élément du fil, prêts à garnir le formulaire d'affiche."""

    titre: str
    message: str
    perimetre_cible: list[str]
    images: list[str]
