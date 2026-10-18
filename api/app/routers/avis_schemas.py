"""Les corps et réponses des routes `/avis` (#2075) — propres à ce routeur."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AvisCreate(BaseModel):
    note: int
    titre: str
    description: str
    remarque: Optional[str] = None
    #  Sans valeur par défaut qui vaille « oui » : `None` est une absence de
    #  réponse, refusée à partir de 4 étoiles (`utils/avis`).
    consentement_publication: Optional[bool] = None


class AvisUpdate(BaseModel):
    """Corriger son avis — tout `Optional`, PATCH partiel."""

    note: Optional[int] = None
    titre: Optional[str] = None
    description: Optional[str] = None
    remarque: Optional[str] = None
    consentement_publication: Optional[bool] = None


class AvisRead(BaseModel):
    id: int
    note: int
    titre: str
    description: str
    auteur_nom: str = ""
    auteur_role: Optional[str] = None
    est_auteur: bool = False
    reponse: Optional[str] = None
    reponse_le: Optional[datetime] = None
    cree_le: datetime
    mis_a_jour_le: Optional[datetime] = None
    archivee: bool = False
    restaurable: bool = False
    #  Ce qui ne regarde que l'auteur et le gestionnaire du site : `None` /
    #  `False` pour tout autre lecteur.
    remarque: Optional[str] = None
    consentement_publication: Optional[bool] = None
    publiable: bool = False
    publication_validee: bool = False

    class Config:
        from_attributes = True


class AvisListe(BaseModel):
    """La liste, et ce que le lecteur peut y faire — l'écran ne le redérive pas."""

    avis: list[AvisRead]
    #  Le lecteur gère-t-il le site (répondre, retenir, exporter) ?
    gestionnaire: bool
    #  L'avis du lecteur, s'il en a donné un — archivé compris.
    mon_avis_id: Optional[int] = None


class ReponseAvis(BaseModel):
    """La réponse du gestionnaire ; vide, elle se retire."""

    reponse: str


class PublicationAvis(BaseModel):
    """`true` retient l'avis pour coprofirst.fr, `false` le retire de l'export."""

    validee: bool
