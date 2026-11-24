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
| `lint:quelquechose` | les skills du front et `user-manual` | un script de ce nom dans `front/package.json` |
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

#: Les skills dont les `lint:*` cités se vérifient aussi (#2936) : `user-manual`
#: nomme les contrôles qui lisent le manuel. La famille « linter » seule s'y
#: applique — les composants et `#lib/` restent l'affaire des skills du front.
SKILLS_LINTERS = SKILLS_FRONT + ("user-manual",)

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
    """Les skills lues avant d'écrire dans `front/src/` — `SKILL.md` ET ses annexes.

    🔴 #2910 : `ux-patterns` est découpée en annexes chargées à la demande. Un
    contrôle qui ne lirait que `SKILL.md` perdrait, au jour de la découpe, tout ce
    qu'il gardait : la portée suit le dossier, pas un nom de fichier.
    """
    return [
        (f"{skill}/{p.name}" if p.name != "SKILL.md" else skill, p)
        for skill in SKILLS_FRONT
        for p in sorted((_SKILLS / skill).glob("*.md"))
    ]


def _documents_linters() -> list[tuple[str, pathlib.Path]]:
    """Les skills dont les `lint:*` cités doivent exister (#2936)."""
    return [(skill, _SKILLS / skill / "SKILL.md") for skill in SKILLS_LINTERS]


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
        _documents_linters,
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
    for skill in SKILLS_LINTERS:
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


# ── Les noms IMPORTÉS dans un exemple, et les règles parties au serveur (#2913) ──
#
#  🔴 Récidive de #1035, onze semaines après : `CLAUDE.md` et `svelte-patterns`
#  enseignaient `import { fmtMontant, perimetreLabel } from '#lib/utils.ts'` — un
#  import qui ne compile plus depuis le 11/11/2026, quand le libellé d'un lieu est
#  parti au serveur (#2633). Les familles ci-dessus vérifient le MODULE (`#lib/x.ts`
#  existe), jamais le NOM qu'on en importe ; et `perimetreLabel` n'est pas un
#  composant. Deux contrôles de plus :
#
#  1. chaque nom d'un `import { … } from '#lib/…'` écrit dans une consigne du front
#     est exporté par ce module (réexportations `export * from` suivies) ;
#  2. aucune règle servie de `REGLES_PARTAGEES` — celles que `lint:regles-partagees`
#     refuse au front — n'est nommée sur une ligne vivante : la consigne la ferait
#     réécrire.

_LIB = _FRONT / "src" / "lib"
_IMPORT_LIB = re.compile(r"import\s*\{([^}]*)\}\s*from\s*'#lib/([^']+)'")
_EXPORT_NOMME = re.compile(
    #  Indenté : le `<script context="module">` d'un composant (`toast`, `Toast.svelte`).
    r"^[ \t]*export\s+(?:declare\s+)?(?:async\s+)?"
    r"(?:function\*?|const|let|var|class|interface|type|enum)\s+(\w+)",
    re.MULTILINE,
)
_EXPORT_LISTE = re.compile(r"^export\s+(?:type\s+)?\{([^}]*)\}", re.MULTILINE)
_EXPORT_ETOILE = re.compile(r"^export\s+\*\s+from\s+'([^']+)'", re.MULTILINE)

#: Les noms de GABARIT d'un exemple, qui ne désignent aucun export : `entity` est
#: la ressource que l'exemple de page invite à remplacer (`svelte-patterns`).
JOKERS_D_IMPORT = frozenset({"entity", "Entity"})


def _documents_front_et_claude() -> list[tuple[str, pathlib.Path]]:
    return [*_documents_front(), ("CLAUDE.md", _RACINE / "CLAUDE.md")]


def _resoudre_lib(chemin: str, depuis: pathlib.Path | None = None) -> pathlib.Path | None:
    """`#lib/x`, `#lib/x.ts`, `./x` → le fichier ; un dossier → son `index.ts`."""
    base = (depuis.parent / chemin) if depuis else (_LIB / chemin)
    for candidat in (base, base.with_name(base.name + ".ts"), base / "index.ts"):
        if candidat.is_file():
            return candidat
    return None


def _exports(fichier: pathlib.Path, vus: frozenset = frozenset()) -> set[str]:
    """Les noms exportés par un module du front, réexportations comprises."""
    if fichier in vus:
        return set()
    source = fichier.read_text(encoding="utf-8")
    noms = set(_EXPORT_NOMME.findall(source))
    for liste in _EXPORT_LISTE.findall(source):
        for element in liste.split(","):
            element = element.strip().removeprefix("type ").strip()
            if element:
                noms.add(element.split(" as ")[-1].strip())
    for cible in _EXPORT_ETOILE.findall(source):
        sous = _resoudre_lib(cible, fichier) if cible.startswith(".") else None
        if cible.startswith("#lib/"):
            sous = _resoudre_lib(cible.removeprefix("#lib/"))
        if sous:
            noms |= _exports(sous, vus | {fichier})
    return noms


def _imports_morts(texte: str) -> list[tuple[int, str]]:
    """(ligne, `nom` de `#lib/x`) des noms importés que le module n'exporte pas."""
    morts = []
    for correspondance in _IMPORT_LIB.finditer(texte):
        numero = texte.count("\n", 0, correspondance.start()) + 1
        module = _resoudre_lib(correspondance.group(2))
        if module is None:
            morts.append((numero, f"#lib/{correspondance.group(2)} (module absent)"))
            continue
        exportes = _exports(module)
        for element in correspondance.group(1).split(","):
            nom = element.strip().removeprefix("type ").strip().split(" as ")[0].strip()
            if nom and nom not in exportes and nom not in JOKERS_D_IMPORT:
                morts.append((numero, f"{nom} de #lib/{correspondance.group(2)}"))
    return morts


def _regles_servies() -> list[str]:
    """Les clés de `REGLES_PARTAGEES` que le serveur sert (`api`, sans `migration`)."""
    source = (_FRONT / "scripts" / "check-regles-partagees.regles.mjs").read_text(encoding="utf-8")
    entrees = re.findall(r"^\t(\w+): \{(.*?)^\t\},?$", source, re.MULTILINE | re.DOTALL)
    return [cle for cle, corps in entrees if "api:" in corps and "migration:" not in corps]


def test_les_imports_enseignes_existent():
    """Un `import { x } from '#lib/y'` d'exemple : `y` exporte `x` (#2913)."""
    fautes = [
        f"  {etiquette}:{numero} — {quoi}"
        for etiquette, chemin in _documents_front_et_claude()
        for numero, quoi in _imports_morts(chemin.read_text(encoding="utf-8"))
    ]
    assert not fautes, "Ces consignes enseignent un import qui ne compile pas :\n" + "\n".join(
        fautes
    )


def test_aucune_regle_servie_n_est_enseignee_au_front():
    """Une règle que le serveur sert ne se nomme pas comme vivante au front (#2913)."""
    regles = _regles_servies()
    motif = re.compile(r"\b(" + "|".join(map(re.escape, regles)) + r")\b")
    fautes = [
        f"  {etiquette}:{numero} — {m.group(1)}"
        for etiquette, chemin in _documents_front_et_claude()
        for numero, ligne in _lignes_vivantes(chemin.read_text(encoding="utf-8"))
        for m in motif.finditer(ligne)
    ]
    assert not fautes, (
        "Ces consignes nomment comme vivante une règle que le serveur sert — "
        "`lint:regles-partagees` la refuse au front, la consigne la ferait "
        "réécrire. Renvoyer au champ servi :\n" + "\n".join(fautes)
    )


def test_les_deux_controles_d_import_savent_refuser():
    """Cas zéro : la table est lue, les réexportations sont suivies, et le défaut
    exact de #2913 est refusé."""
    regles = _regles_servies()
    assert {"nomProprietaire", "lectureDe"} <= set(regles), regles
    assert "estPerimetreParDefaut" in _exports(_LIB / "perimetres" / "index.ts"), (
        "`export * from` n'est plus suivi"
    )
    forge = "import { fmtMontant, perimetreLabel } from '#lib/utils.ts';"
    assert _imports_morts(forge) == [(1, "perimetreLabel de #lib/utils.ts")]
    assert _imports_morts("import { fmtMontant, type X as Y } from '#lib/absent.ts';") == [
        (1, "#lib/absent.ts (module absent)")
    ]


# ── Les EXEMPLES ```svelte que la CI refuserait (#2930) ─────────────────────────
#
#  Récidive de #1556 : `ux-patterns` enseignait six blocs qu'un linter du front
#  refuse ou qui visaient une API partie (le conteneur `.carte-liste` écrit à la
#  main, l'astérisque tapée, un bouton d'action en émoji, un `<slot>` que
#  `ChampsCommuns` ne rend plus). Les linters ne lisent que `front/src` ; ce relevé
#  porte LEUR motif sur les blocs des skills, et nomme le linter qui fait foi. Un
#  bloc volontairement fautif le dit sur sa ligne (marqueur d'historique, ou ❌).
#
#  ⚠️ Un motif par défaut CONSTATÉ, pas une copie des linters : chaque entrée
#  exige que son linter existe encore — sinon c'est le motif qui est périmé.
FORMES_REFUSEES = (
    (re.compile(r'class="carte-liste\b'), "lint:carte-liste", "poser `<CarteListe …>`"),
    (re.compile(r"\*\s*<input"), "lint:champs", "écrire `<EtoileRequis vide={…} />`"),
    (
        re.compile(r'class="btn-icon"[^>]*>\s*(?:🔄|✏️|🗑️|➕)'),
        "lint:actions-au-trait",
        "dessiner l'action par `<IconeAction icone=… />`",
    ),
    (
        re.compile(r'<svelte:fragment slot="diffusion"'),
        "lint:diffusion-auteur",
        "`ChampsCommuns` prend des snippets : `{#snippet creneauDiffusion()}`",
    ),
    (re.compile(r"Nouvelle publication"), "lint:vocabulaire-ecran", "lire `libelleNouveau`"),
)


def _lignes_de_blocs_svelte(texte: str):
    """(numéro, ligne) des lignes vivantes d'un bloc ```svelte."""
    dans = False
    for numero, ligne in enumerate(texte.split("\n"), 1):
        if ligne.strip().startswith("```"):
            dans = ligne.strip().startswith("```svelte") and not dans
            continue
        minuscule = ligne.lower()
        if dans and "❌" not in ligne and not any(m in minuscule for m in MARQUEURS_HISTORIQUE):
            yield numero, ligne


def test_les_exemples_svelte_passent_les_linters_du_front():
    """Un bloc d'exemple d'une skill du front ne porte aucune forme refusée (#2930)."""
    scripts = _scripts_npm()
    fautes = [
        f"  {lint} n'existe plus — le motif est périmé"
        for _m, lint, _a in FORMES_REFUSEES
        if lint not in scripts
    ]
    for etiquette, chemin in _documents_front():
        for numero, ligne in _lignes_de_blocs_svelte(chemin.read_text(encoding="utf-8")):
            for motif, lint, a_la_place in FORMES_REFUSEES:
                if motif.search(ligne):
                    fautes.append(f"  {etiquette}:{numero} — refusé par {lint} : {a_la_place}")
    assert not fautes, "Ces exemples enseignent ce que la CI refuse :\n" + "\n".join(fautes)


def test_le_releve_des_exemples_voit_un_bloc():
    """Cas zéro : un bloc forgé est lu, son motif refusé ; hors bloc, rien."""
    forge = '```svelte\n<div class="carte-liste x">\n```\n<div class="carte-liste">'
    lignes = list(_lignes_de_blocs_svelte(forge))
    assert lignes == [(2, '<div class="carte-liste x">')], lignes
