"""Une skill ne nomme que du code qui existe (#1035).

## 🔴 Pourquoi — la consigne périmée régénère le défaut

Les deux skills chargées **avant d'écrire dans `front/src/`** enseignaient des
motifs que le code avait supprimés — dont trois qu'un linter refuse. Ce n'est
pas une imprécision de documentation : c'est la première cause de récidive que
`standards/02` §5 nomme.

Le précédent est daté : `svelte-patterns` a produit `renderContent` (#429) en
enseignant un motif d'assainissement remplacé depuis. Le code était corrigé, la
skill non — et la skill est ce qu'on lit **avant** d'écrire.

## Ce que ce contrôle vérifie

Quatre familles de noms, choisies parce qu'elles se vérifient sans ambiguïté —
une table (`FAMILLES`), un seul balayage, et tous les écarts nommés d'un coup :

| Forme citée | Lue dans | Doit exister |
|---|---|---|
| `Quelquechose.svelte` | les skills du front | un fichier de ce nom sous `front/src` |
| `lint:quelquechose` | les skills du front | un script de ce nom dans `front/package.json` |
| `#lib/x.ts` | les skills du front | le fichier correspondant |
| `test_x.py`, ou `` `test_x` `` | **toutes** les skills et `CLAUDE.md` | un fichier de `api/tests/` — ou, sans extension, une fonction de test |

🔴 La quatrième est née le 30/09/2026 : une skill ou `CLAUDE.md` cite un test
comme **garde-fou** (« 🔒 `test_x.py` refuse… »), et rien ne vérifiait qu'il
existe encore. Un test supprimé ou renommé laissait la consigne affirmer une
protection disparue — le garde-fou cité mais absent, pire qu'absent. Sa portée
est donc plus large que celle des trois autres : un test se cite partout, pas
seulement dans ce qu'on lit avant d'écrire un écran.

⚠️ **Une mention historique n'est pas une faute.** Une skill a le droit — et le
devoir — de dire « `PhotosUpload` a été remplacé par `FichiersUpload` » : c'est
ce qui empêche le nom mort de revenir. Le contrôle ignore donc toute ligne qui
porte un marqueur d'historique (`supprimé`, `retiré`, `n'existe plus`,
`remplacé`, `renommé`…).

C'est la distinction qui rend ce contrôle tenable : il ne cherche pas les noms
morts, il cherche **les noms morts présentés comme vivants**.

## Ce qu'il ne fait pas

Il ne vérifie pas que la skill enseigne le **bon** motif — seulement qu'elle ne
renvoie pas vers un fichier absent. Une skill peut être à jour sur les noms et
périmée sur le fond ; c'est ce que l'audit de cohérence mesure, et il ne
s'automatise pas.
"""

from __future__ import annotations

import functools
import json
import pathlib
import re
from collections.abc import Callable
from typing import NamedTuple

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_SKILLS = _RACINE / ".claude" / "skills"
_FRONT = _RACINE / "front"
_TESTS = _RACINE / "api" / "tests"

#: Les skills qui parlent du front, donc celles dont les noms se vérifient ici.
#: ⚠️ La portée fait partie du contrôle : une skill ajoutée qui parle du front
#: doit rejoindre cette liste, et le premier test échoue si l'une disparaît.
SKILLS_FRONT = ("svelte-patterns", "ux-patterns")

#: Une ligne qui porte l'un de ces mots parle du PASSÉ : le nom qu'elle cite a
#: le droit de ne plus exister, et c'est même le but.
MARQUEURS_HISTORIQUE = (
    #  ⚠️ « n'existe pas » autant que « n'existe plus » : une skill qui CORRIGE
    #  une mention morte écrit souvent la première forme — « cette ligne nommait
    #  X, qui n'existe pas ». Le marqueur ne reconnaissait que la seconde, et le
    #  contrôle accusait la correction elle-même.
    "supprim",
    "retir",
    "n'existe plus",
    "nexiste plus",
    "n'existe pas",
    "nexiste pas",
    "remplac",
    "renomm",
    "disparu",
    "avant le",
    "jusqu'au",
    "jusquau",
    "périmé",
    "perime",
    "ne porte plus",
    "cessé",
    "cesse de",
    "obsolèt",
    "obsolet",
    "plus aucun",
)


def _lignes_vivantes(texte: str):
    """(numéro, ligne) des lignes qui ne parlent pas du passé."""
    for numero, ligne in enumerate(texte.split("\n"), 1):
        minuscule = ligne.lower()
        if any(marqueur in minuscule for marqueur in MARQUEURS_HISTORIQUE):
            continue
        yield numero, ligne


def _documents_front() -> list[tuple[str, pathlib.Path]]:
    """Les skills lues avant d'écrire dans `front/src/`."""
    return [(skill, _SKILLS / skill / "SKILL.md") for skill in SKILLS_FRONT]


def _documents_consignes() -> list[tuple[str, pathlib.Path]]:
    """Toutes les skills du projet, et `CLAUDE.md` — tout ce qui cite un garde-fou."""
    skills = [(p.parent.name, p) for p in sorted(_SKILLS.glob("*/SKILL.md"))]
    return skills + [("CLAUDE.md", _RACINE / "CLAUDE.md")]


@functools.cache
def _composants_existants() -> frozenset[str]:
    return frozenset(p.name for p in (_FRONT / "src").rglob("*.svelte"))


@functools.cache
def _scripts_npm() -> frozenset[str]:
    paquet = json.loads((_FRONT / "package.json").read_text(encoding="utf-8"))
    return frozenset(paquet.get("scripts", {}))


@functools.cache
def _fichiers_de_tests() -> frozenset[str]:
    return frozenset(p.name for p in _TESTS.rglob("test_*.py"))


@functools.cache
def _fonctions_de_tests() -> frozenset[str]:
    motif = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)", re.MULTILINE)
    return frozenset(
        nom
        for p in _TESTS.rglob("test_*.py")
        for nom in motif.findall(p.read_text(encoding="utf-8"))
    )


def _test_existe(nom: str) -> bool:
    """`test_x.py` : le fichier. `test_x` sans extension : le fichier ou la fonction."""
    if nom.endswith(".py"):
        return nom in _fichiers_de_tests()
    return f"{nom}.py" in _fichiers_de_tests() or nom in _fonctions_de_tests()


class Famille(NamedTuple):
    nom: str
    documents: Callable[[], list[tuple[str, pathlib.Path]]]
    #: Le nom cité est le premier groupe NON VIDE de la correspondance.
    motif: re.Pattern[str]
    existe: Callable[[str], bool]


#: Les formes de noms vérifiées, où elles se lisent, et ce qui doit exister.
FAMILLES = (
    Famille(
        "composant",
        _documents_front,
        re.compile(r"\b([A-Z][A-Za-z0-9]*\.svelte)\b"),
        lambda nom: nom in _composants_existants(),
    ),
    #  Un composant cité SANS extension, entre accents graves (#1555) :
    #  `CarteEvenement` et `FormulaireEvenement` étaient présentés comme vivants
    #  dans les deux skills du front, un mois après leur suppression (#1092),
    #  et la forme `X.svelte` seule ne les voyait pas. Préfixes des familles de
    #  composants du dépôt — un mot en majuscule de la prose n'y entre pas.
    Famille(
        "composant sans extension",
        _documents_front,
        re.compile(r"`((?:Carte|Formulaire|Section|Onglet|Liste)[A-Z][A-Za-z0-9]*)`"),
        lambda nom: f"{nom}.svelte" in _composants_existants(),
    ),
    Famille(
        "linter",
        _documents_front,
        re.compile(r"\b(lint:[a-z0-9-]+)\b"),
        lambda nom: nom in _scripts_npm(),
    ),
    Famille(
        "module de lib",
        _documents_front,
        re.compile(r"#lib/([a-z0-9_/-]+\.ts)\b"),
        lambda nom: (_FRONT / "src" / "lib" / nom).exists(),
    ),
    #  🔴 Deux formes : `test_x.py` (le fichier, où qu'il soit écrit —
    #  `api/tests/test_x.py`, `test_x.py::test_y`) et `` `test_x` `` entre
    #  accents graves, sans extension, qui nomme un fichier OU une fonction. Un
    #  `test_x` nu hors accents graves n'est pas lu : trop proche de la prose.
    Famille(
        "test",
        _documents_consignes,
        re.compile(r"\b(test_[A-Za-z0-9_]+\.py)\b|`(test_[A-Za-z0-9_]+)`"),
        _test_existe,
    ),
)


def _noms_cites(famille: Famille, texte: str):
    """(numéro, nom) de chaque nom de cette famille cité sur une ligne vivante."""
    for numero, ligne in _lignes_vivantes(texte):
        for correspondance in famille.motif.finditer(ligne):
            yield numero, next(g for g in correspondance.groups() if g)


def test_la_portee_du_controle_est_intacte():
    """Cas zéro : une skill absente, et le contrôle ne vérifie plus rien."""
    for skill in SKILLS_FRONT:
        assert (_SKILLS / skill / "SKILL.md").exists(), (
            f"{skill}/SKILL.md est introuvable — le contrôle a perdu sa portée"
        )
    composants = _composants_existants()
    assert len(composants) > 50, (
        f"seulement {len(composants)} composant(s) trouvé(s) : le scan ne voit "
        "probablement pas `front/src`"
    )
    assert _scripts_npm(), "aucun script npm lu"
    assert len(_fichiers_de_tests()) > 100, (
        f"seulement {len(_fichiers_de_tests())} fichier(s) de test sous {_TESTS} : le "
        "scan ne voit probablement pas `api/tests`"
    )

    #  Chaque famille doit VOIR quelque chose dans ses documents : une regex
    #  cassée ne trouverait rien, et le balayage rendrait un vert à vide.
    for famille in FAMILLES:
        cites = [
            nom
            for _etiquette, chemin in famille.documents()
            for _n, nom in _noms_cites(famille, chemin.read_text(encoding="utf-8"))
        ]
        assert cites, f"la famille « {famille.nom} » ne trouve aucun nom cité"

    #  …et la famille des tests doit savoir REFUSER, sous ses deux formes, sans
    #  accuser un nom vivant ni une ligne historique.
    test = next(f for f in FAMILLES if f.nom == "test")
    forge = "\n".join(
        (
            "🔒 `api/tests/test_absent_du_depot.py` refuse la récidive.",
            "tenu par `test_fonction_absente_du_depot`.",
            "voir `test_skills_nomment_du_code_existant.py::test_la_portee_du_controle_est_intacte`",
            "`test_disparu_du_depot.py` a été supprimé le 30/09/2026.",
        )
    )
    morts = [nom for _n, nom in _noms_cites(test, forge) if not test.existe(nom)]
    assert morts == ["test_absent_du_depot.py", "test_fonction_absente_du_depot"], morts


def test_aucun_nom_cite_n_a_disparu():
    """Le défaut exact : `PhotosUpload.svelte` n'existe pas — ni aucun des noms
    que les consignes présentent comme vivants, famille par famille."""
    fautes = []
    for famille in FAMILLES:
        for etiquette, chemin in famille.documents():
            texte = chemin.read_text(encoding="utf-8")
            for numero, nom in _noms_cites(famille, texte):
                if not famille.existe(nom):
                    fautes.append(f"  {etiquette}:{numero} — {famille.nom} — {nom}")

    assert not fautes, (
        "Ces consignes renvoient vers des noms qui n'existent pas :\n" + "\n".join(fautes) + "\n\n"
        "Une skill est lue AVANT d'écrire : un nom mort présenté comme vivant "
        "fait recréer le motif qu'il désignait (`standards/02` §5 — c'est ainsi "
        "que `renderContent` est né, #429). Un garde-fou cité mais absent — un "
        "`lint:*`, un `test_*.py` — est pire qu'un garde-fou absent : il fait "
        "croire que la règle est tenue.\n"
        "Si la mention est historique, la ligne doit le dire (« remplacé par… », "
        "« supprimé le… ») : le contrôle ignore alors la ligne, et le lecteur "
        "sait à quoi s'en tenir."
    )
