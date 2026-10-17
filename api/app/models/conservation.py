"""Les ARCHIVES de la conservation des affaires (#2014, lots L2 et L3).

Une ligne par archive produite : les pièces jointes des affaires échues d'UN
exercice et d'UN type, rangées dans un zip avec leur sommaire
(`utils/conservation_archive`). La ligne suit l'archive de sa naissance à son
retrait du serveur :

| Colonne | Posée par | Ce qu'elle dit |
|---|---|---|
| `cree_le` | la tâche nocturne | l'archive est écrite, relue, et les fichiers d'origine retirés |
| `copiee_le` | l'accusé du poste (`export-hors-site.sh`) | la copie sur le PC a la même empreinte |
| `retiree_le` | la tâche nocturne, 30 jours après `copiee_le` | le serveur n'en a plus de copie |

L'`empreinte` est celle que le serveur a calculée en écrivant : l'accusé du poste
ne vaut que s'il annonce la même (`utils/conservation_copie`). Spécification :
`specs/architecture/conservation-affaires.md` §5 et §6.
"""

from __future__ import annotations

from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel

from app.utils import horloge


class ArchiveAffaires(SQLModel, table=True):
    __tablename__ = "archive_affaires"

    id: Optional[int] = Field(default=None, primary_key=True)
    #: `affaires-<copropriété>-<exercice>-<type>[-<rang>].zip` — unique, il nomme
    #: aussi la copie sur le PC.
    nom: str = Field(unique=True, index=True)
    #: la clé du fichier dans le stockage de la copropriété (`prive/…`)
    cle: str
    #: l'exercice de clôture des affaires (« 2026 », « 2025-2026 »)
    exercice: str
    #: `utils/conservation_affaires.TYPES` — travaux · entretien · breves
    type: str
    #: SHA-256 du zip, calculé à l'écriture
    empreinte: str
    octets: int = 0
    affaires: int = 0
    fichiers: int = 0
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    copiee_le: Optional[NaiveDatetime] = None
    retiree_le: Optional[NaiveDatetime] = None
