"""La RÉPARTITION du Suivi des affaires — par catégorie et par bâtiment, croisées (#2043).

Deux graphiques en barres, chacune découpée selon l'autre (arbitré le 17/10/2026) :

- **Par catégorie**, chaque barre découpée PAR BÂTIMENT ;
- **Par bâtiment**, chaque barre découpée PAR CATÉGORIE.

## Où se compte une affaire (arbitré le 17/10/2026)

| Elle vise… | « Par bâtiment » | sa tranche dans « Par catégorie » |
|---|---|---|
| un bâtiment | sa ligne | ce bâtiment |
| plusieurs bâtiments | la ligne de CHACUN | « Plusieurs bâtiments » — une barre ne compte jamais deux fois une affaire |
| aucun bâtiment (toute la résidence, un parking…) | la ligne du périmètre racine | le périmètre racine |

Les clés : `CLE_RACINE`, `CLE_PLUSIEURS`, et `bat:<id>` pour un bâtiment. Le
libellé de la racine est celui de l'arbre (`perimetre_label`), jamais écrit ici.

PUR : rien ne lit la base. `releve` donne les affaires et les libellés.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

#: La ligne des affaires qui ne visent aucun bâtiment.
CLE_RACINE = "racine"
#: La tranche des affaires qui en visent plusieurs.
CLE_PLUSIEURS = "plusieurs"
LIBELLE_PLUSIEURS = "Plusieurs bâtiments"


def cle_batiment(batiment_id: int) -> str:
    return f"bat:{batiment_id}"


@dataclass(frozen=True)
class Tranche:
    cle: str
    libelle: str
    nombre: int


@dataclass(frozen=True)
class Barre:
    cle: str
    libelle: str
    nombre: int
    tranches: list[Tranche] = field(default_factory=list)


def _tranches(compte: Counter, ordre: list[str], libelles: dict[str, str]) -> list[Tranche]:
    return [Tranche(c, libelles.get(c, c), compte[c]) for c in ordre if compte[c]]


def par_categorie(
    affaires: list,
    libelles_categorie: dict[str, str],
    ordre_categories: list[str],
    libelles_batiment: dict[str, str],
    ordre_batiments: list[str],
) -> list[Barre]:
    """PURE. Une barre par catégorie, la plus nombreuse en tête ; tranches par bâtiment."""
    tranches: dict[str, Counter] = {}
    for a in affaires:
        bats = a.batiments
        cle = (
            CLE_RACINE if not bats else (cle_batiment(bats[0]) if len(bats) == 1 else CLE_PLUSIEURS)
        )
        tranches.setdefault(a.categorie, Counter())[cle] += 1
    ordre_tranches = [CLE_RACINE, *ordre_batiments, CLE_PLUSIEURS]
    libelles = {**libelles_batiment, CLE_PLUSIEURS: LIBELLE_PLUSIEURS}
    barres = [
        Barre(
            cat,
            libelles_categorie.get(cat, cat),
            sum(compte.values()),
            _tranches(compte, ordre_tranches, libelles),
        )
        for cat, compte in tranches.items()
    ]
    rang = {c: i for i, c in enumerate(ordre_categories)}
    return sorted(barres, key=lambda b: (-b.nombre, rang.get(b.cle, len(rang)), b.libelle))


def par_batiment(
    affaires: list,
    libelles_categorie: dict[str, str],
    ordre_categories: list[str],
    libelles_batiment: dict[str, str],
    ordre_batiments: list[str],
) -> list[Barre]:
    """PURE. Une barre par bâtiment (la racine en tête) ; tranches par catégorie.

    Une affaire sur plusieurs bâtiments compte dans CHACUN : la somme des barres
    peut dépasser le nombre d'affaires, et c'est voulu.
    """
    tranches: dict[str, Counter] = {}
    for a in affaires:
        for cle in [cle_batiment(b) for b in a.batiments] or [CLE_RACINE]:
            tranches.setdefault(cle, Counter())[a.categorie] += 1
    ordre = [CLE_RACINE, *ordre_batiments]
    return [
        Barre(
            cle,
            libelles_batiment.get(cle, cle),
            sum(tranches[cle].values()),
            _tranches(tranches[cle], ordre_categories, libelles_categorie),
        )
        for cle in ordre
        if cle in tranches
    ]
