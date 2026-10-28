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

## La TEINTE d'une tranche (#2043, au serveur depuis #2082)

Une teinte suit l'ENTITÉ, jamais son rang : la catégorie « Panne » porte la même
série dans les deux graphiques et d'un jour à l'autre. Les catégories prennent
les séries `s1`…`s8` dans l'ordre `ORDRE_SERIES` (au-delà : `autre`) ; les
bâtiments, des paliers de gris `p1`…`p4` — la racine en premier, dans l'ordre de
« Par bâtiment » —, et « Plusieurs bâtiments » la sienne. La règle vivait dans
`#lib/repartition` ; le PDF du point (#2082) la lit aussi : elle est ICI, et
l'écran comme le papier reçoivent la teinte, jamais la règle. Les couleurs des
teintes : `utils/suivi_affaires/pdf_barres.TEINTES` (papier) et `socle.css`
(écran) — 🔒 `test_teintes_repartition.py` les tient d'accord.

PUR : rien ne lit la base. `releve` donne les affaires et les libellés.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace

#: La ligne des affaires qui ne visent aucun bâtiment.
CLE_RACINE = "racine"
#: La tranche des affaires qui en visent plusieurs.
CLE_PLUSIEURS = "plusieurs"
LIBELLE_PLUSIEURS = "Plusieurs bâtiments"


#: L'ordre des séries de couleur des catégories — celui de `CategorieTicket`,
#: sans les deux qui n'entrent jamais au rapport (bogue, actualité).
ORDRE_SERIES = (
    "panne",
    "nuisance",
    "espaces_verts",
    "sinistre",
    "etude_travaux",
    "acces_accueil",
    "question",
    "entretien",
)
#: Les paliers de gris des bâtiments.
PALIERS = 4


def cle_batiment(batiment_id: int) -> str:
    return f"bat:{batiment_id}"


def teinte_categorie(cle: str) -> str:
    """PURE. `s1`…`s8` dans l'ordre des séries, sinon `autre`."""
    return f"s{ORDRE_SERIES.index(cle) + 1}" if cle in ORDRE_SERIES else "autre"


def teinte_batiment(cle: str, ordre: list[str]) -> str:
    """PURE. Le palier d'un bâtiment dans l'ordre de « Par bâtiment » ; « Plusieurs » a le sien."""
    if cle == CLE_PLUSIEURS:
        return CLE_PLUSIEURS
    rang = ordre.index(cle) if cle in ordre else 0
    return f"p{min(rang, PALIERS - 1) + 1}"


@dataclass(frozen=True)
class Tranche:
    cle: str
    libelle: str
    nombre: int
    #: La teinte de la tranche (`teinte_categorie`, `teinte_batiment`) — posée par `teinter`.
    teinte: str = ""


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


def teinter(par_cat: list[Barre], par_bat: list[Barre]) -> tuple[list[Barre], list[Barre]]:
    """PURE. Les deux répartitions, chaque tranche avec sa teinte : les tranches de
    « Par catégorie » sont des bâtiments, celles de « Par bâtiment » des catégories."""
    ordre = [b.cle for b in par_bat]

    def avec(barres: list[Barre], teinte) -> list[Barre]:
        return [
            replace(b, tranches=[replace(t, teinte=teinte(t.cle)) for t in b.tranches])
            for b in barres
        ]

    return (
        avec(par_cat, lambda c: teinte_batiment(c, ordre)),
        avec(par_bat, teinte_categorie),
    )
