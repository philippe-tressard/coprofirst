"""Les réponses de la Communauté — idées, petites annonces, sondages (#2506).

Partagés par trois routeurs (`idees`, `annonces`, `sondages`) : ils vivent donc
ici, ré-exportés par `schemas.py`. Jusqu'à #2506, ces réponses sortaient en
dictionnaires sans `response_model` : le contrat les déclarait `{}`, et l'app iOS
les relisait en miroir de `#lib/api/communaute.ts` — une dérive du serveur serait
passée sans un mot.

La forme est celle de `utils/reponses.enrich_reponse` et `auteur_meta`, seule
écriture d'une réponse lue.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReponseCommunauteRead(BaseModel):
    """Une réponse à une idée ou une annonce, ou le commentaire d'un sondage."""

    id: int
    #: Vide quand le compte de l'auteur a été supprimé (#1821).
    auteur_id: Optional[int] = None
    contenu: str
    cree_le: datetime
    #: « Utilisateur supprimé » quand le compte n'existe plus — jamais absent.
    auteur_nom: str
    auteur_batiment: Optional[str] = None
    auteur_role: Optional[str] = None
    #: CS ou admin : réponse mise en avant, et triée en tête par le serveur.
    est_cs: bool = False
    #: Le lecteur peut-il la supprimer ? La conclusion de `peut_commenter`, le
    #: prédicat de la route qui supprime (#2506).
    peut_supprimer: bool = False


class MessageRead(BaseModel):
    """Un geste qui ne rend qu'une phrase, que l'écran affiche telle quelle
    (« Vote enregistré », « Vote retiré »)."""

    message: str
