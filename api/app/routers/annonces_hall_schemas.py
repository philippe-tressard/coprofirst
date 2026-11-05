"""Les schémas de l'affiche de hall — ce qui entre, ce qui sort.

Extrait de `routers/annonces_hall.py` le 02/09/2026, quand le plafond de
modularité a refusé le branchement de la règle d'archivage (#515). Troisième
découpage du même fichier, après `annonces_hall_courriels` et
`annonces_hall_apercu` — la couture est la même à chaque fois : ce qui DÉCLARE
part, ce qui DÉCIDE reste.

⚠️ `AnnonceHallRead` n'existe pas : la lecture est construite à la main par
`_to_read`, qui compose le PDF, les destinataires et l'état d'archivage. La
déclarer ici en ferait une seconde description de la même sortie.
"""

from pydantic import BaseModel, Field

from app.utils.assiste_ia import AssisteIAEntree
from app.utils.perimetres import perimetre_defaut_liste


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
