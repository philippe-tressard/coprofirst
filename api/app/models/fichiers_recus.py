"""Qui a TÉLÉVERSÉ un fichier servi en direct (#2154, 23/10/2026).

Un fichier se téléverse AVANT l'objet qui le cite : le formulaire d'une affaire
envoie ses photos par `/uploads/fichier`, puis leurs adresses dans la création.
Entre les deux — et pour toujours si le formulaire est abandonné —, aucun objet
ne dit qui peut le lire. Arbitrage de Philippe le 23/10/2026 : **son auteur
seul**. Cette table le note, une ligne par fichier reçu dans un dossier servi
(`utils/fichiers.enregistrer_fichier_recu`, la seule porte d'écriture) ; la règle
de lecture vit dans `utils/visibility/fichiers`.

L'auteur est facultatif : un compte supprimé laisse le fichier sans auteur
(`purge_referentielle`), et il ne se lit plus alors que par le conseil et
l'administration — comme les fichiers reçus avant cette table.
"""

from __future__ import annotations

from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, Session, SQLModel

from app.utils import horloge


class FichierRecu(SQLModel, table=True):
    __tablename__ = "fichier_recu"

    id: Optional[int] = Field(default=None, primary_key=True)
    #: La clé du fichier dans le stockage (`fichiers/<uuid>_<radical>.jpg`).
    cle: str = Field(index=True, unique=True)
    auteur_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


def noter_auteur(session: Session | None, user: object, cle: str) -> None:
    """Note l'auteur d'un fichier reçu dans un dossier SERVI — appelée par la seule
    porte d'écriture (`utils/fichiers.enregistrer_fichier_recu`).

    Tant qu'aucun objet ne le cite, le fichier ne se lit que par lui
    (`utils/visibility/fichiers`, règle 4).
    `session` et `user` y sont donc exigés : un appelant qui les oublierait
    rendrait le fichier illisible à son propre auteur, et le refus se lève ici,
    avant l'écriture, plutôt qu'à l'affichage.
    """
    from app.utils.stockage import JAMAIS_SERVIS  # utils → models, jamais l'inverse au chargement

    if cle.split("/", 1)[0] in JAMAIS_SERVIS:
        return
    if session is None or getattr(user, "id", None) is None:
        raise ValueError(f"un fichier servi ({cle}) note son auteur : session et user")
    session.add(FichierRecu(cle=cle, auteur_id=user.id))
    session.commit()
