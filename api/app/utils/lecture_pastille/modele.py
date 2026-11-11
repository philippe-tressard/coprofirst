"""Le MODÈLE de la pastille de lecture — sans dépendance au reste du projet.

Les schémas qui la servent (`schemas_affaire_servie`, les lectures de la
communauté) l'importent seul : la règle (`regle.py`) lit la visibilité, qui lit
l'authentification — l'importer depuis un schéma ferait un cycle.
"""

from __future__ import annotations

from pydantic import BaseModel


class Lecture(BaseModel):
    """La pastille de lecture, telle que les deux clients l'affichent."""

    #: `tous`, `residents`, `coproprietaires`, `cs`, `concerne`, ou les codes joints par « + ».
    cle: str
    icones: list[str]
    #: Le libellé de la carte — « Copropriétaires », « CS ».
    court: str
    #: Le libellé de la section — « Copropriétaires (occupants et bailleurs) ».
    long: str
    #: Le titre de la pastille longue : le libellé, et le cadenas en toutes lettres.
    titre: str
    #: Les profils qui lisent, dans l'ordre d'affichage ; vide : le conseil seul.
    profils: list[str]
    #: Le cadenas : seuls ceux du périmètre lisent.
    perimetre_reserve: bool
    #: Ceux qui lisent HORS du périmètre.
    hors_perimetre: list[str]
    #: Ceux qui ne lisent que dans le périmètre, quand d'autres lisent partout.
    du_perimetre: str
    #: La phrase de l'infobulle : « Lue par… ».
    phrase: str
    #: Ceux qui ne lisent pas : « Pas les locataires, ni… ».
    exclus: str
    #: Personne n'est exclu : rien sur la carte, « Tous » dans la section.
    par_defaut: bool
    #: Le piège d'une actualité : un périmètre choisi mais non réservé.
    avertissement: str
