"""L'état descriptif du règlement : lire le fichier, le contrôler — fonctions PURES (#2213).

L'état descriptif dit ce qu'est chaque lot : sa nature, sa porte ou sa place, son
niveau, la circulation qui le dessert et ses tantièmes par clé de charges (spec
`specs/architecture/lots-et-perimetres.md` §2 et §8). Il entre par l'atelier
d'import, ligne à ligne dans une table de passage, et ne touche au patrimoine
qu'une fois ses contrôles passés (`utils/etat_descriptif_application`).

## Le fichier

Un classeur, première feuille, une ligne d'en-têtes. Les colonnes se reconnaissent
à leur EN-TÊTE, pas à leur rang (`COLONNES`) ; toute autre colonne dont l'en-tête
se termine par `/<dénominateur>` est une **clé de charges** — « Charges générales
/10000 » — dont le dénominateur est ainsi DÉCLARÉ, jamais déduit. Le gabarit vide
se télécharge depuis l'atelier : il est produit par `en_tetes_du_gabarit`, la même
source que la lecture.

🔴 Le fichier d'une copropriété réelle n'entre jamais dans le dépôt (public).

## Les contrôles

Bloquants — ce que l'application écrirait FAUX ou ne saurait pas placer : numéro de
lot en double ; lettre de bâtiment sans correspondance ; nature illisible ; logement
dont le bâtiment diffère de celui de l'application ; circulation dont le bâtiment n'a
pas de nœud dans l'arbre. Un contrôle qui ne peut pas se calculer rend INCONNU —
bloquant lui aussi, jamais OK.

À savoir — ce qui est INCOMPLET sans rendre faux ce qui s'écrit (25/10/2026) : somme
d'une clé ≠ son dénominateur (le règlement lui-même ne tombe pas toujours juste, après
ses modificatifs), lot de l'application absent du fichier (il garde sa désignation
actuelle, à récupérer dans le règlement), lot du fichier absent de l'application (sa
ligne est ignorée, rien n'est créé). Ils restent affichés, avec leur écart, et
l'écran de confirmation les rappelle : on applique en connaissance de cause, puis on
complète — un fichier incomplet ne bloquait que le travail qu'il permettait déjà.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel

from app.models.copropriete import NatureLot
from app.utils.constats import AVERTISSEMENT, BLOQUANT, INCONNU, Constat, constat
from app.utils.import_xlsx import etage_de_lot, normaliser

#: En-tête normalisé (`normaliser`) → champ de la ligne. Plusieurs en-têtes par
#: champ : l'acte dit « desserte », l'usage dit « circulation ».
COLONNES: dict[str, str] = {
    "LOT": "lot",
    "BATIMENT": "batiment",
    "NATURE": "nature",
    "NUMERO USAGE": "numero_usage",
    "NUMERO_USAGE": "numero_usage",
    "PORTE OU PLACE": "numero_usage",
    "NIVEAU": "niveau",
    "CIRCULATION": "circulation",
    "CIRCULATION DESSERVANTE": "circulation",
    "CIRCULATION_DESSERVANTE": "circulation",
    "DESSERTE": "circulation",
    "LOT ORIGINE": "lot_origine",
    "LOT_ORIGINE": "lot_origine",
    "SOURCE": "source",
}

#: Les en-têtes du gabarit, dans l'ordre — un par champ, celui que `COLONNES` lit.
EN_TETES_FIXES = (
    "lot",
    "batiment",
    "nature",
    "numero_usage",
    "niveau",
    "circulation",
    "lot_origine",
    "source",
)

#: Une colonne de clé : « <libellé> /<dénominateur> ».
_EN_TETE_CLE = re.compile(r"^(?P<libelle>.+?)\s*/\s*(?P<denominateur>\d+)\s*$")

#: Mention de nature → `NatureLot`. Les abréviations sont celles des classeurs du
#: syndic (`import_xlsx.TYPE_*`) ; les mots, ceux d'un état descriptif.
_NATURES: dict[str, NatureLot] = {
    **{m: NatureLot.logement for m in ("LOGEMENT", "APPARTEMENT", "AP", "ST", "STUDIO")},
    **{f"T{n}": NatureLot.logement for n in range(1, 8)},
    **{m: NatureLot.commerce for m in ("COMMERCE", "LC", "BOUTIQUE", "LOCAL COMMERCIAL")},
    **{m: NatureLot.cave for m in ("CAVE", "CA")},
    **{m: NatureLot.parking for m in ("PARKING", "PS", "PLACE", "EMPLACEMENT", "BOX")},
    **{m: NatureLot.divers for m in ("DIVERS", "DIV", "LOCAL", "REMISE")},
}

#: Ce qu'une cellule de circulation écrit pour dire « accès direct ».
_ACCES_DIRECT = {"", "/", "-", "AUCUNE", "DIRECT", "ACCES DIRECT"}

#: Ce que la lecture du règlement par l'assistant ajoute à la source d'une ligne
#: qu'elle n'a pas lue avec certitude (#2218) — un constat « À savoir » la relève.
MARQUE_DOUTEUX = "à vérifier sur l'acte"


class Cle(BaseModel):
    """Une clé déclarée par un en-tête — `code` dérivé du libellé, dénominateur déclaré."""

    code: str
    libelle: str
    denominateur: int


class Ligne(BaseModel):
    """Une ligne de l'état descriptif, telle que le fichier l'écrit.

    Un modèle et non une simple structure : la réponse de l'atelier l'étend
    (`routers/lots_etat_descriptif.LigneLue`) au lieu d'en recopier les champs.
    """

    rang: int
    lot: str
    batiment: Optional[str] = None
    nature: Optional[str] = None
    numero_usage: Optional[str] = None
    niveau: Optional[str] = None
    circulation: Optional[str] = None
    lot_origine: Optional[str] = None
    source: Optional[str] = None
    quotes: dict[str, int] = {}


@dataclass
class Lecture:
    cles: list[Cle]
    lignes: list[Ligne]
    #: Faux quand le fichier n'a pas de colonne de circulation : il s'importe alors
    #: comme la liste du syndic, sans rien dire de ce qui dessert un lot — et
    #: l'atelier le dit (cas zéro).
    avec_circulation: bool
    erreurs: list[str] = field(default_factory=list)


#: Le « prime » d'un libellé — « Escalier A' » est une AUTRE clé qu'« Escalier A » :
#: un règlement répartit souvent l'escalier en deux colonnes (25/10/2026). Toutes ses
#: graphies : apostrophe droite, typographique, prime, lettre modificative.
_PRIME = re.compile("['’′ʼ]")


def code_de_cle(libelle: str) -> str:
    """« Charges générales » → `charges-generales` : la clé de réimport d'une clé.

    Le prime se dit en toutes lettres (`escalier-a-prime`) : sinon il tombait avec
    la ponctuation, et deux colonnes partageaient un code — la seconde écrasait les
    tantièmes de la première, et l'écran ne se rendait plus.
    """
    sans_accents = "".join(
        c
        for c in unicodedata.normalize("NFD", _PRIME.sub(" prime ", libelle))
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", "-", sans_accents.lower()).strip("-")


def numero_de_lot(brut) -> str:
    """Un numéro de lot comparable d'un fichier à l'autre (« 012 », 12.0 → « 12 »)."""
    if isinstance(brut, float) and brut.is_integer():
        brut = int(brut)
    texte = normaliser(str(brut)) if brut is not None else ""
    return texte.lstrip("0") or texte


def _cellule(valeur) -> Optional[str]:
    if valeur is None:
        return None
    if isinstance(valeur, float) and valeur.is_integer():
        valeur = int(valeur)
    texte = str(valeur).strip()
    return texte or None


def lire(rows: list) -> Lecture:
    """Les lignes d'un classeur → clés déclarées et lignes, sans rien écrire."""
    if not rows:
        return Lecture(cles=[], lignes=[], avec_circulation=False, erreurs=["Fichier vide."])
    champs: dict[int, str] = {}
    cles: dict[int, Cle] = {}
    for rang, en_tete in enumerate(rows[0]):
        brut = _cellule(en_tete)
        if brut is None:
            continue
        champ = COLONNES.get(normaliser(brut))
        if champ:
            champs[rang] = champ
            continue
        trouve = _EN_TETE_CLE.match(brut)
        if trouve:
            libelle = trouve["libelle"].strip()
            cles[rang] = Cle(
                code=code_de_cle(libelle), libelle=libelle, denominateur=int(trouve["denominateur"])
            )
    erreurs = []
    vus: dict[str, str] = {}
    for cle in cles.values():
        #  Deux colonnes, une clé : la seconde écraserait la première sans un mot.
        if cle.code in vus:
            erreurs.append(
                f"Deux colonnes désignent la même clé : « {vus[cle.code]} » et « {cle.libelle} »."
            )
        vus.setdefault(cle.code, cle.libelle)
    if "lot" not in champs.values():
        erreurs.append("Aucune colonne « lot » : le numéro de lot est obligatoire.")
    lignes: list[Ligne] = []
    for rang_ligne, row in enumerate(rows[1:], start=2):
        valeurs = {champ: _cellule(row[i]) for i, champ in champs.items() if i < len(row)}
        if not valeurs.get("lot"):
            continue
        ligne = Ligne(rang=rang_ligne, lot=numero_de_lot(valeurs.pop("lot")))
        for champ, valeur in valeurs.items():
            setattr(ligne, champ, valeur)
        if ligne.lot_origine:
            ligne.lot_origine = numero_de_lot(ligne.lot_origine)
        for i, cle in cles.items():
            brut = _cellule(row[i]) if i < len(row) else None
            if brut is None:
                continue
            try:
                ligne.quotes[cle.code] = int(float(brut.replace(",", ".")))
            except ValueError:
                erreurs.append(
                    f"Ligne {rang_ligne} — tantièmes illisibles ({cle.libelle}) : {brut}"
                )
        lignes.append(ligne)
    return Lecture(
        cles=list(cles.values()),
        lignes=lignes,
        avec_circulation="circulation" in champs.values(),
        erreurs=erreurs,
    )


def nature_de(brut: Optional[str]) -> Optional[NatureLot]:
    return _NATURES.get(normaliser(brut)) if brut else None


def niveau_de(brut: Optional[str]) -> Optional[int]:
    """« RDC », « 2SS », « -2 » → un entier ; `None` si illisible."""
    if not brut:
        return None
    mention = etage_de_lot(brut)
    if mention is not None:
        return mention
    try:
        return int(brut)
    except ValueError:
        return None


def lettre_de(brut: Optional[str]) -> Optional[str]:
    """La lettre d'un bâtiment telle qu'on la compare — `None` pour un accès direct."""
    texte = normaliser(brut)
    return None if texte in _ACCES_DIRECT else texte


@dataclass(frozen=True)
class LotConnu:
    """Ce que l'application sait d'un lot, pour le confronter au fichier."""

    numero: str
    batiment_id: Optional[int]
    nature: Optional[NatureLot]


def controler(
    lecture: Lecture,
    lots_app: list[LotConnu],
    lettres: dict[str, int],
    batiments_avec_noeud: set[int],
) -> list[Constat]:
    """Les constats d'une lecture confrontée à l'application — fonction PURE.

    `lettres` : lettre RCP normalisée → `batiment.id` ; `batiments_avec_noeud` :
    les bâtiments qui ont un nœud dans l'arbre (une circulation doit en avoir un).
    """
    constats: list[Constat] = [constat("lecture", BLOQUANT, message) for message in lecture.erreurs]
    lignes = lecture.lignes
    if not lignes:
        constats.append(constat("vide", INCONNU, "Aucune ligne de lot lue : rien à contrôler."))
        return constats

    def _signaler(code, gravite, message, lots):
        if lots:
            constats.append(constat(code, gravite, message, sorted(set(lots))))

    def _bloquant(code, message, lots):
        _signaler(code, BLOQUANT, message, lots)

    def _a_savoir(code, message, lots):
        _signaler(code, AVERTISSEMENT, message, lots)

    vus: dict[str, int] = {}
    for ligne in lignes:
        vus[ligne.lot] = vus.get(ligne.lot, 0) + 1
    _bloquant(
        "double_fichier",
        "Numéro de lot en double dans le fichier.",
        [n for n, c in vus.items() if c > 1],
    )

    numeros_app: dict[str, int] = {}
    for lot in lots_app:
        numeros_app[lot.numero] = numeros_app.get(lot.numero, 0) + 1
    _bloquant(
        "double_application",
        "Numéro de lot en double dans l'application : le rapprochement par numéro est impossible.",
        [n for n, c in numeros_app.items() if c > 1],
    )

    origines = {ligne.lot_origine for ligne in lignes if ligne.lot_origine}
    _a_savoir(
        "absent_application",
        "Lot du règlement absent de l'application (lot sans propriétaire dans la liste du "
        "syndic) : sa ligne est ignorée, rien n'est créé.",
        [
            ligne.lot
            for ligne in lignes
            if ligne.lot not in numeros_app and ligne.lot not in origines
        ],
    )
    du_fichier = {ligne.lot for ligne in lignes}
    _a_savoir(
        "absent_fichier",
        "Lot de l'application absent de l'état descriptif : il garde sa désignation actuelle, "
        "à récupérer dans le règlement.",
        [n for n in numeros_app if n not in du_fichier],
    )
    if origines:
        constats.append(
            constat(
                "divise",
                AVERTISSEMENT,
                "Lot d'origine divisé : il reste en historique, ses tantièmes comptent dans "
                "les sommes sans être répartis sur ses divisions.",
                tuple(sorted(origines)),
            )
        )
    sans_acte = [ligne.lot for ligne in lignes if ligne.lot_origine and not ligne.source]
    if sans_acte:
        constats.append(
            constat(
                "division_sans_acte",
                AVERTISSEMENT,
                "Division sans acte : aucune source n'est citée.",
                tuple(sorted(sans_acte)),
            )
        )
    douteuses = [ligne.lot for ligne in lignes if MARQUE_DOUTEUX in (ligne.source or "")]
    if douteuses:
        constats.append(
            constat(
                "douteux",
                AVERTISSEMENT,
                "Lu par l'assistant sans certitude : vérifier ces lots sur l'acte avant "
                "d'appliquer — leur source dit où.",
                tuple(sorted(douteuses)),
            )
        )

    _bloquant(
        "nature",
        "Nature illisible ou absente.",
        [ligne.lot for ligne in lignes if nature_de(ligne.nature) is None],
    )
    lettres_inconnues = sorted(
        {
            brut
            for ligne in lignes
            for brut in (ligne.batiment, ligne.circulation)
            if lettre_de(brut) is not None and lettre_de(brut) not in lettres
        }
    )
    if lettres_inconnues:
        constats.append(
            constat(
                "lettre",
                BLOQUANT,
                "Lettre de bâtiment sans correspondance : saisir la lettre de l'acte de chaque "
                "bâtiment (« " + " », « ".join(lettres_inconnues) + " »).",
            )
        )
    circulations_sans_noeud = [
        ligne.lot
        for ligne in lignes
        if lettre_de(ligne.circulation) in lettres
        and lettres[lettre_de(ligne.circulation)] not in batiments_avec_noeud
    ]
    _bloquant(
        "circulation_sans_noeud",
        "Circulation dont le bâtiment n'a pas de nœud dans "
        "l'arbre des périmètres (Admin › Périmètres).",
        circulations_sans_noeud,
    )

    par_numero = {lot.numero: lot for lot in lots_app}
    _bloquant(
        "batiment_different",
        "Logement dont le bâtiment diffère de celui de "
        "l'application : à corriger d'un côté ou de l'autre, jamais en silence.",
        [
            ligne.lot
            for ligne in lignes
            if ligne.lot in par_numero
            and nature_de(ligne.nature) not in (NatureLot.cave, NatureLot.parking, None)
            and lettre_de(ligne.batiment) in lettres
            and par_numero[ligne.lot].batiment_id != lettres[lettre_de(ligne.batiment)]
        ],
    )

    for cle in lecture.cles:
        somme = sum(ligne.quotes.get(cle.code, 0) for ligne in lignes)
        if somme != cle.denominateur:
            ecart = cle.denominateur - somme
            constats.append(
                constat(
                    "somme",
                    AVERTISSEMENT,
                    f"« {cle.libelle} » : la somme des tantièmes vaut {somme} pour un "
                    f"dénominateur déclaré de {cle.denominateur} — "
                    + (f"il en manque {ecart}." if ecart > 0 else f"il y en a {-ecart} de trop.")
                    + " Les tantièmes lus sont posés tels quels.",
                )
            )
    if not lecture.cles:
        constats.append(
            constat(
                "sans_cle",
                AVERTISSEMENT,
                "Aucune clé de charges déclarée : aucun tantième ne sera posé.",
            )
        )
    if not lecture.avec_circulation:
        constats.append(
            constat(
                "sans_circulation",
                AVERTISSEMENT,
                "Aucune colonne de circulation : les caves et les places restent sans "
                "circulation, comme avant.",
            )
        )
    return constats
