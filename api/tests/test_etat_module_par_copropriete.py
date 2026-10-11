"""La mémoire du processus : aucun état de module de plus (#1743, 08/10/2026).

Chantier multi-copropriétés, `specs/architecture/multi-coproprietes.md` §4.5.
Avec une application pour plusieurs copropriétés (option B), tout état gardé EN
MÉMOIRE et indexé par un simple identifiant fuit d'une copropriété à l'autre :
l'utilisateur n° 12 de la copro A lirait le cache de l'utilisateur n° 12 de la
copro B. La règle : **tout état mutable de module est indexé par la copropriété,
ou n'existe pas.**

Tant qu'il n'y a qu'une copropriété, ces états ne fuient nulle part — mais chacun
de plus est un correctif de plus à la phase 2. Ce contrôle les fige.

## Ce qu'il appelle « état mutable de module »

Relevé sur l'AST de `app/`, trois formes :

- un nom posé au niveau du module, puis **modifié depuis une fonction** :
  `X[k] = …`, `del X[k]`, `X.append(…)`, `X.setdefault(…)`, `X.clear()`… ;
- un nom **réaffecté** depuis une fonction par `global X` ;
- une fonction décorée par `@lru_cache` ou `@cache` : son cache est un état de
  module, indexé par ses arguments.

Le relevé du 07/10/2026, fait à la main, en citait quatre ; ce contrôle en a
trouvé neuf le lendemain, dont le cache de l'arbre des périmètres — une donnée de
la copropriété.

## Ce qu'il ne voit pas — dit, pour ne pas le croire plus large

- un état modifié **depuis un autre module** (`autre_module._cache.clear()`) : il
  est vu chez son module d'origine dès qu'il y est modifié, ce qui est le cas de
  tous ceux d'aujourd'hui ;
- un état porté par un **attribut de classe** ou par un objet (un ordonnanceur, un
  limiteur de débit) dont on appelle les méthodes : leur état est celui d'une
  bibliothèque, pas une donnée rangée par l'application.

## Les trois listes

- `A_INDEXER` : la dette. Ces états portaient une donnée d'UNE copropriété ; ils
  sont passés sous sa clé au lot du contexte (#1744, six le 10/10/2026). Elle
  est VIDE et le reste : son plafond est à zéro.
- `PAR_COPROPRIETE` : la seule porte — le registre `contexte.etat(nom)`, indexé
  par l'identifiant de la copropriété. Un module qui tient un cache le lui
  demande à chaque usage, et ne garde rien à lui.
- `DU_PROCESSUS` : des états qui ne portent aucune donnée de copropriété, chacun
  avec sa raison. En ajouter un se justifie là, à la vue de la revue.

Une entrée qui ne correspond plus à rien fait échouer : une exception qui ne sert
plus est un oubli qui ressemble à une décision.
"""

from __future__ import annotations

import ast

from tests.aides_sources import modules_app

#: Les méthodes qui modifient un conteneur sur place.
METHODES_QUI_MODIFIENT = frozenset(
    {
        "append",
        "appendleft",
        "add",
        "clear",
        "discard",
        "extend",
        "insert",
        "move_to_end",
        "pop",
        "popitem",
        "popleft",
        "remove",
        "setdefault",
        "update",
    }
)

#: Les décorateurs qui gardent un cache au niveau du module.
DECORATEURS_DE_CACHE = frozenset({"lru_cache", "cache"})

#: Les états qui portent une donnée d'UNE copropriété sans passer par le contexte,
#: par (module, nom). Un cache décoré se nomme `fonction()`. 🔴 Soldée au lot du
#: contexte de copropriété (#1744) : rien ne s'y ajoute.
A_INDEXER: dict = {}

#: Le plafond de la dette. Il ne fait que BAISSER.
PLAFOND_A_INDEXER = 0

#: LA porte des états de copropriété : le registre du contexte, indexé par
#: l'identifiant de la copropriété. Un module qui tient un cache le demande à
#: `contexte.etat(nom)` à chaque usage, et ne garde rien à lui (#1744).
PAR_COPROPRIETE = {
    ("contexte.py", "_etats"): "les états de processus, un dictionnaire par (copropriété, nom)",
    ("contexte.py", "_moteurs"): "les moteurs des copropriétés, par (identifiant, URL de base)",
}

#: Les états qui ne portent aucune donnée de copropriété, avec leur raison.
DU_PROCESSUS = {
    ("config.py", "get_settings()"): (
        "la configuration de la plateforme, lue une fois ; ce qui est propre à une "
        "copropriété en sort par le module contexte (#1744)"
    ),
    ("utils/recherche_affaires.py", "_plat()"): (
        "le repli d'UN caractère (accents, casse) : fonction pure d'un caractère"
    ),
    ("utils/pdf_theme.py", "_icones_cache"): (
        "le catalogue d'icônes, lu d'un fichier versionné avec le code"
    ),
    ("utils/pdf_rendu.py", "dernier_temoin"): (
        "diagnostic du dernier rendu PDF, lu par les tests seulement ; aucune route ne le rend"
    ),
    ("utils/pdf_rendu.py", "dernier_journal"): (
        "journal technique du dernier rendu PDF, lu par les tests seulement"
    ),
}


def _noms_du_module(arbre: ast.Module) -> set[str]:
    """Les noms posés au niveau du module — y compris sous un `if` ou un `try` de tête."""
    noms: set[str] = set()
    a_lire = list(arbre.body)
    while a_lire:
        noeud = a_lire.pop()
        if isinstance(noeud, (ast.If, ast.Try)):
            a_lire += noeud.body + noeud.orelse
            a_lire += [h for g in getattr(noeud, "handlers", []) for h in g.body]
            a_lire += getattr(noeud, "finalbody", [])
            continue
        if isinstance(noeud, ast.Assign):
            cibles = noeud.targets
        elif isinstance(noeud, ast.AnnAssign):
            cibles = [noeud.target]
        else:
            continue
        noms |= {c.id for c in cibles if isinstance(c, ast.Name)}
    return noms


def _nom_du_decorateur(decorateur: ast.expr) -> str | None:
    """`lru_cache` pour `@lru_cache`, `@lru_cache(maxsize=…)` et `@functools.lru_cache`."""
    cible = decorateur.func if isinstance(decorateur, ast.Call) else decorateur
    if isinstance(cible, ast.Attribute):
        return cible.attr
    if isinstance(cible, ast.Name):
        return cible.id
    return None


def etats_du_module(source: str) -> set[str]:
    """Les états mutables d'un module : noms modifiés depuis une fonction, et caches."""
    arbre = ast.parse(source)
    du_module = _noms_du_module(arbre)
    etats: set[str] = set()
    for fonction in ast.walk(arbre):
        if not isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(_nom_du_decorateur(d) in DECORATEURS_DE_CACHE for d in fonction.decorator_list):
            etats.add(f"{fonction.name}()")
        for noeud in ast.walk(fonction):
            if isinstance(noeud, ast.Global):
                etats |= set(noeud.names)
            elif (
                isinstance(noeud, ast.Call)
                and isinstance(noeud.func, ast.Attribute)
                and noeud.func.attr in METHODES_QUI_MODIFIENT
                and isinstance(noeud.func.value, ast.Name)
                and noeud.func.value.id in du_module
            ):
                etats.add(noeud.func.value.id)
            elif isinstance(noeud, (ast.Assign, ast.AugAssign, ast.Delete)):
                cibles = [noeud.target] if isinstance(noeud, ast.AugAssign) else noeud.targets
                etats |= {
                    c.value.id
                    for c in cibles
                    if isinstance(c, ast.Subscript)
                    and isinstance(c.value, ast.Name)
                    and c.value.id in du_module
                }
    return etats


def releve() -> set[tuple[str, str]]:
    """Chaque état mutable de `app/`, par (module relatif, nom)."""
    return {(m.rel, nom) for m in modules_app() for nom in etats_du_module(m.source)}


def ecarts(trouves: set, a_indexer: dict, du_processus: dict, plafond: int) -> list[str]:
    """Ce qui rend les listes fausses — vide si chaque état est dit, et rien de plus."""
    declares = set(a_indexer) | set(du_processus) | set(PAR_COPROPRIETE)
    sortie = [
        f"app/{module} : `{nom}` est un état mutable de module que rien ne déclare. Avec "
        "plusieurs copropriétés dans un processus, il fuirait de l'une à l'autre "
        "(spec §4.5). Le ranger dans la base, ou le passer par le contexte de "
        "copropriété — ou, s'il ne porte aucune donnée de copropriété, le déclarer dans "
        "DU_PROCESSUS avec sa raison"
        for module, nom in sorted(trouves - declares)
    ]
    sortie += [
        f"app/{module} : `{nom}` est déclaré, mais le relevé ne le trouve plus — retirer "
        "l'entrée (et baisser PLAFOND_A_INDEXER si elle était à indexer)"
        for module, nom in sorted(declares - trouves)
    ]
    sortie += [
        f"app/{module} : `{nom}` est déclaré dans les DEUX listes — une seule"
        for module, nom in sorted(set(a_indexer) & set(du_processus))
    ]
    if len(a_indexer) > plafond:
        sortie.append(
            f"A_INDEXER compte {len(a_indexer)} états pour un plafond de {plafond} : la "
            "dette ne fait que baisser"
        )
    elif len(a_indexer) < plafond:
        sortie.append(
            f"A_INDEXER compte {len(a_indexer)} états : baisser PLAFOND_A_INDEXER à "
            f"{len(a_indexer)}, sinon la place libérée se reprendrait sans un mot"
        )
    return sortie


def test_chaque_etat_de_module_est_declare():
    """Le contrôle : le relevé réel, confronté aux deux listes et au plafond."""
    trouves = ecarts(releve(), A_INDEXER, DU_PROCESSUS, PLAFOND_A_INDEXER)
    assert not trouves, "\n".join(trouves)


def test_la_porte_des_etats_de_copropriete_est_le_contexte_seul():
    """Une seconde « porte » serait un état de copropriété qui échappe au contexte."""
    assert {module for module, _nom in PAR_COPROPRIETE} == {"contexte.py"}


def test_le_releve_voit_les_etats_connus():
    """Cas zéro : un relevé qui ne verrait rien rendrait le contrôle vert pour toujours."""
    trouves = releve()
    connus = set(A_INDEXER) | set(DU_PROCESSUS) | set(PAR_COPROPRIETE)
    assert len(trouves) >= len(connus), f"le relevé ne trouve que {len(trouves)} état(s)"
    assert connus <= trouves, f"déclarés, pas vus par le relevé : {sorted(connus - trouves)}"


def test_le_controle_refuse_un_etat_de_plus():
    """Les cas fautifs : un état non déclaré, une entrée périmée, un double compte, le plafond."""
    reel = releve()
    assert ecarts(reel | {("utils/neuf.py", "_cache")}, A_INDEXER, DU_PROCESSUS, PLAFOND_A_INDEXER)
    connu = ("utils/pdf_theme.py", "_icones_cache")
    assert ecarts(reel - {connu}, A_INDEXER, DU_PROCESSUS, PLAFOND_A_INDEXER)
    assert ecarts(reel - set(PAR_COPROPRIETE), A_INDEXER, DU_PROCESSUS, PLAFOND_A_INDEXER)
    double = {connu: "dit deux fois"}
    assert ecarts(reel, double, DU_PROCESSUS, PLAFOND_A_INDEXER + 1)
    assert ecarts(reel, A_INDEXER, DU_PROCESSUS, PLAFOND_A_INDEXER + 1)
    assert ecarts(reel, A_INDEXER, DU_PROCESSUS, PLAFOND_A_INDEXER - 1)


def test_le_releve_reconnait_chaque_forme():
    """Le témoin du détecteur : chaque forme est vue, et une constante ne l'est pas."""
    source = (
        "import functools\n"
        "from functools import lru_cache\n"
        "REGISTRE = {'a': 1}\n"
        "_par_cle = {}\n"
        "_liste = []\n"
        "_ensemble = set()\n"
        "_compteur = {}\n"
        "_vide = {}\n"
        "_instant = 0.0\n"
        "try:\n"
        "    _sous_try = {}\n"
        "except ImportError:\n"
        "    _sous_try = None\n"
        "def lire(k):\n"
        "    return REGISTRE.get(k)\n"
        "def ecrire(k, v):\n"
        "    _par_cle[k] = v\n"
        "    _liste.append(v)\n"
        "    _ensemble.add(v)\n"
        "    _compteur[k] += 1\n"
        "    del _vide[k]\n"
        "    _sous_try.setdefault(k, v)\n"
        "def poser():\n"
        "    global _instant\n"
        "    _instant = 1.0\n"
        "@lru_cache(maxsize=8)\n"
        "def calcul(x):\n"
        "    return x\n"
        "@functools.cache\n"
        "def autre(x):\n"
        "    return x\n"
        "def local():\n"
        "    vu = {}\n"
        "    vu['a'] = 1\n"
    )
    assert etats_du_module(source) == {
        "_par_cle",
        "_liste",
        "_ensemble",
        "_compteur",
        "_vide",
        "_sous_try",
        "_instant",
        "calcul()",
        "autre()",
    }
