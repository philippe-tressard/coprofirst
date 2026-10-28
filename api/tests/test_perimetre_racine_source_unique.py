"""Garde-fou : le code du périmètre racine (« résidence ») n'est écrit nulle part.

## Le défaut (02/10/2026, #1567)

Côté interface, la question « cette sélection désigne-t-elle toute la
copropriété ? » se pose à `estPerimetreParDefaut` (`#lib/perimetres`), et la
sélection initiale d'un formulaire vient de `perimetreDefautListe` : le front ne
contient plus un seul `'résidence'`. Côté API, le même code était écrit en dur
**vingt-trois fois dans dix-neuf modules** (l'audit en avait compté treize) —
défauts de colonne, défauts de schéma, replis
`x or ["résidence"]`, et deux comparaisons `lieux[0] == "résidence"` dans le
message du groupe.

C'est un CODE, immuable une fois posé (`routers/patrimoine.py`) — pas le libellé
administrable. Mais le nœud qui le porte est une DONNÉE : une autre copropriété
peut l'avoir désactivé, ou n'avoir jamais semé l'arbre. `code_par_defaut()` le
lit dans l'arbre depuis août, `parse_json_perimetres` s'en sert pour lire — et
chaque écriture le recopiait quand même.

## La source

`app/utils/perimetres/arbre.py` : `perimetre_defaut_liste()`,
`perimetre_defaut_json()` (ce qu'un contenu reçoit quand on ne lui en donne
pas) et `est_perimetre_par_defaut(codes)` (la question). Les trois lisent
`code_par_defaut()`, miroirs de `perimetreDefautListe` et `estPerimetreParDefaut`.
Le seul module qui écrit le code est le SEED, qui pose le nœud.

## Ce que le contrôle refuse

Une chaîne littérale du code de `app/` — docstrings exclues, l'AST ignore les
commentaires — qui vaut le code racine en toute casse et en toute forme
Unicode (`"Résidence"`, `"RÉSIDENCE"`, un `é` décomposé), ou qui le CITE
entre guillemets (`'["résidence"]'`, un `DEFAULT` SQL).

La forme sans accent (`"residence"`) n'est refusée que là où elle ferait office
de code : comparée (`== "residence"`) ou élément d'une liste. Ailleurs, elle
nomme autre chose — la variable de gabarit `residence` des courriels
(`utils/email/variables.py`), une clé de taille de l'affiche, un dossier de
téléversement — et la refuser partout ferait déclarer une vingtaine d'exceptions
qui n'en sont pas.

⚠️ `alembic/` est hors de la portée (`modules_app` ne lit que `app/`) : une
migration appliquée ne se modifie jamais, ses littéraux sont de l'historique.
"""

from __future__ import annotations

import ast
import unicodedata

from tests.aides_sources import docstrings, modules_app

_CODE = "résidence"

#: Les modules qui écrivent encore le littéral, avec leur NOMBRE d'occurrences et
#: leur raison. Un compte qui change fait échouer le test dans les deux sens :
#: une occurrence de plus est une copie, une de moins rend l'exception à réduire.
EXCEPTIONS: dict[str, tuple[int, str]] = {
    "seed/patrimoine.py": (2, "le seed POSE le nœud racine : c'est la donnée qui naît"),
    #  Granularité documentaire — `résidence` / `bâtiment` / `lot` : QUI LIT un
    #  fichier, pas OÙ se passe un contenu. Même mot, autre axe
    #  (`models/perimetre.py`, docstring de `Perimetre`).
    "models/documents.py": (2, "granularité documentaire, autre axe que l'arbre"),
    "routers/documents.py": (1, "granularité documentaire, autre axe que l'arbre"),
    "seed/profils_documents.py": (6, "granularité documentaire, autre axe que l'arbre"),
}


def _forme(texte: str) -> str:
    return unicodedata.normalize("NFC", texte).casefold()


def _sans_accent(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c)).casefold()


def _en_position_de_code(arbre: ast.AST) -> set[int]:
    """Les constantes comparées, ou rangées dans une liste, un tuple, un ensemble."""
    vus: set[int] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Compare):
            for terme in (noeud.left, *noeud.comparators):
                #  `x in ("residence", …)` compare aussi : on entre dans la collection.
                elements = terme.elts if isinstance(terme, (ast.List, ast.Tuple, ast.Set)) else []
                vus.update(id(e) for e in (terme, *elements))
        elif isinstance(noeud, (ast.List, ast.Tuple)):
            #  Pas les ensembles : `{"annee", "residence"}` est une liste de NOMS
            #  (les variables d'un gabarit), jamais une sélection de périmètres.
            vus.update(id(e) for e in noeud.elts)
    return vus


def occurrences(source: str) -> int:
    """Le nombre de littéraux qui écrivent le code racine dans ce source."""
    arbre = ast.parse(source)
    exclues = docstrings(arbre)
    en_code = _en_position_de_code(arbre)
    code, cite = _forme(_CODE), f'"{_forme(_CODE)}"'
    compte = 0
    for noeud in ast.walk(arbre):
        if not (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)):
            continue
        if id(noeud) in exclues:
            continue
        valeur = _forme(noeud.value)
        if valeur.strip() == code or cite in valeur:
            compte += 1
        elif id(noeud) in en_code and _sans_accent(noeud.value).strip() == _sans_accent(_CODE):
            compte += 1
    return compte


def test_aucun_code_racine_hors_de_sa_source():
    fautes = []
    for m in modules_app():
        n = occurrences(m.source)
        attendu = EXCEPTIONS.get(m.rel, (0, ""))[0]
        if n != attendu:
            fautes.append(f"{m.rel} : {n} occurrence(s), {attendu} déclarée(s)")
    assert not fautes, (
        "Code du périmètre racine écrit en dur — employer `perimetre_defaut_liste()`, "
        "`perimetre_defaut_json()` ou `est_perimetre_par_defaut()` "
        "(`app.utils.perimetres`) :\n  " + "\n  ".join(fautes)
    )


def test_chaque_exception_sert_encore():
    """Une exception qui ne désigne plus aucun module n'excuse rien."""
    connus = {m.rel for m in modules_app()}
    mortes = sorted(rel for rel in EXCEPTIONS if rel not in connus)
    assert not mortes, f"Exceptions qui ne désignent plus aucun module : {mortes}"


def test_le_releve_voit_chaque_forme():
    """Cas zéro : chaque écriture refusée est vue, chaque écriture permise ne l'est pas."""
    vues = [
        'x = "résidence"',
        'x = "Résidence"',
        'x = "RÉSIDENCE"',
        f'x = "{unicodedata.normalize("NFD", "résidence")}"',
        "x = '[\"résidence\"]'",
        'x = codes or ["résidence"]',
        'ok = lieux[0] == "résidence"',
        'ok = lieux[0] == "residence"',
        'ok = code in ("x", "residence")',
        'x = ["Residence"]',
        'sql = "ALTER TABLE t ADD COLUMN p TEXT DEFAULT \'[\\"résidence\\"]\'"',
    ]
    for source in vues:
        assert occurrences(source) == 1, source
    permises = [
        '"""Le périmètre « résidence » vit dans les données."""',
        '# lieux[0] == "résidence"\nx = 1',
        'ctx = {"residence": {"nom": nom}}',
        'url = enregistrer(f, "residence")',
        'code = "résidence_tous"',
        'NOMS = frozenset({"annee", "residence"})',
        'texte = "Plan de la résidence"',
    ]
    for source in permises:
        assert occurrences(source) == 0, source
