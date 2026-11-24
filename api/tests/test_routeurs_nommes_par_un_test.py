"""Aucun module de `app/routers/` n'échappe à tous les tests — par leur NOM (#1569).

## Pourquoi

L'audit du 02/10/2026 (axe 5) relevait seize modules de `app/` qu'aucun fichier de
`tests/` ne nomme, dont deux routeurs, `annonces_hall_sources` et `tickets/suite_groupe` :
montés (`test_routeurs_montes`), jamais exercés. La passe de #1569 a ramené ce relevé à
ZÉRO ; ce contrôle empêche qu'il remonte en silence pour la partie qui expose des URL.

Un routeur est ce qu'un test oublie le plus facilement : l'import réussit, l'application
démarre, et les droits qu'il applique (401, 403, 404) ne sont vérifiés par personne.

## Ce que ce contrôle mesure — et ne mesure pas

Il mesure l'absence de **nom**, et un nom est une clé qui ne se confond pas (#2914) :

- l'**import** du module (`app.routers.bailleur.objets`, `from app.routers.bailleur
  import objets`) ou son **chemin** (`routers/bailleur/objets.py`) ;
- ou l'une de ses **URL**, écrite comme chaîne (`"/bailleur/baux/{id}/objets"`, un
  paramètre valant n'importe quel segment ; une URL plus longue ne compte pas).

🔴 Jusqu'au 23/11/2026, « nommé » voulait dire « le nom de FICHIER paraît comme mot
entier quelque part dans `tests/` » (la méthode de #1569, `grep -rlw`). Un homonyme
suffisait : `bailleur/objets.py` passait parce que le mot « objets » paraissait
cinquante-trois fois pour autre chose, `flux/epingles.py` parce qu'il était la clé de
la table d'un autre contrôle, `copropriete_patrimoine.py` par une docstring — trois
routeurs qu'aucun test n'appelait (audit du 23/11/2026) — et un quatrième, `manuel.py`,
que le mot « manuel » couvrait.

**Portée** : les modules de `app/routers/` qui portent au moins une route MONTÉE dans
l'application (`__init__.py` d'un paquet compris). Un module sans route — schémas,
collecteurs du fil, aides d'un paquet — n'expose rien : il s'exerce par la route qui
l'appelle. Qu'un routeur déclaré soit bien monté, c'est `test_routeurs_montes`.

⚠️ Il ne mesure PAS l'exécution : un module peut être nommé sans être exercé, ou exercé
par un autre routeur sans être nommé. Un plancher de couverture le dirait — `coverage`
n'est pas dans `requirements-dev.txt`. Ce contrôle est un filet à grosses mailles, pas
une mesure.

## Pourquoi il s'arrête à `app/routers/`

Hors des routeurs, vingt-deux modules de `app/` ne sont nommés par aucun test (relevé du
23/11/2026). Ils ne sont pas pour autant hors d'atteinte : un utilitaire s'exerce par
les routes qui l'appellent, et c'est la seule exposition qui compte pour un résident.
Exiger son NOM ferait écrire des tests qui l'importent pour le nommer — de quoi
satisfaire ce contrôle sans rien mesurer de plus. Le relevé juste, pour eux, est la
couverture d'exécution, pas une recherche de nom.

## Une exception se déclare

`EXCEPTIONS` : chemin relatif → raison. Une exception non écrite est un oubli qui ressemble
à une décision ; une exception qui cesse de servir (le module est nommé, ou a disparu) fait
ÉCHOUER le contrôle : la liste ne fait que baisser. Elle est vide aujourd'hui, et le reste
doit se tenir.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

from tests.aides_sources import APP, modules_app

TESTS = pathlib.Path(__file__).resolve().parent
CE_FICHIER = pathlib.Path(__file__).name

#: Les modules de `app/routers/` qu'aucun test ne nomme, et pourquoi on l'accepte.
#: Vide au 02/10/2026 — ne s'allonge pas : on écrit le test du routeur neuf.
EXCEPTIONS: dict[str, str] = {}

#: Sous ce nombre de fichiers de tests lus, la portée est cassée : le contrôle ne
#: mesurerait plus rien (cas zéro).
PLANCHER_TESTS = 100
PLANCHER_ROUTEURS = 50


def _corpus() -> str:
    """Tous les fichiers de tests — SAUF celui-ci, qui ne doit pas se nommer lui-même."""
    fichiers = [
        p
        for p in sorted(TESTS.glob("*.py"))
        if p.name != CE_FICHIER and "__pycache__" not in p.parts
    ]
    assert len(fichiers) >= PLANCHER_TESTS, (
        f"`tests/` ne rend que {len(fichiers)} fichier(s) (plancher {PLANCHER_TESTS}) : "
        "la portée a bougé, et ce contrôle ne mesure plus rien."
    )
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in fichiers)


def _cles_d_import(rel: str) -> list[re.Pattern[str]]:
    """L'import du module ou son chemin — jamais son seul nom de fichier.

    Le module d'un `__init__.py` est son paquet : `app.routers.flux`.
    """
    pointe = "app." + rel.removesuffix(".py").removesuffix("/__init__").replace("/", ".")
    paquet, _, nom = pointe.rpartition(".")
    return [
        re.compile(rf"(?<![\w.]){re.escape(pointe)}(?![\w])"),
        re.compile(rf"from {re.escape(paquet)} import \(?[^)\n]*(?<![\w]){re.escape(nom)}(?![\w])"),
        re.compile(rf"(?<![\w])routers/{re.escape(rel.removeprefix('routers/'))}(?![\w])"),
    ]


def motif_d_url(chemin: str) -> re.Pattern[str]:
    """Une URL de route, écrite comme chaîne : chaque `{paramètre}` vaut un segment —
    une valeur (`12`) ou un champ de f-string (`{bail.id}`, `{o['id']}`).

    Elle s'ouvre sur un guillemet et se ferme sur un guillemet, une requête (`?`) ou
    un champ de f-string (`{suite}`) : `"/avis/export"` ne nomme pas `/avis`.
    """
    segment = r"(?:\{[^}\n]*\}|[^/\"'?\s{}]+)"
    corps = re.sub(r"\\\{[^}]*\\\}", lambda _: segment, re.escape(chemin))
    return re.compile(rf"[\"']{corps}[\"'?{{]")


def nomme(corpus: str, rel: str, urls: tuple[str, ...] = ()) -> bool:
    """Le module est-il nommé — par son import, son chemin, ou l'une de ses URL ?"""
    if any(m.search(corpus) for m in _cles_d_import(rel)):
        return True
    return any(motif_d_url(url).search(corpus) for url in urls)


def non_nommes(
    rels: list[str], corpus: str, urls: dict[str, tuple[str, ...]] | None = None
) -> list[str]:
    urls = urls or {}
    return [rel for rel in rels if not nomme(corpus, rel, urls.get(rel, ()))]


def _urls_par_module() -> dict[str, tuple[str, ...]]:
    """Les URL de chaque module de routeur, telles que l'application les MONTE."""
    from app.main import app
    from tests.aides_sources import operations_montees

    urls: dict[str, set[str]] = {}
    for _methode, chemin, route in operations_montees(app):
        module = sys.modules.get(getattr(getattr(route, "endpoint", None), "__module__", ""))
        fichier = pathlib.Path(getattr(module, "__file__", "") or "")
        if APP / "routers" in fichier.parents:
            #  Le FICHIER du module : `app.routers.flux` est `routers/flux/__init__.py`.
            urls.setdefault(fichier.relative_to(APP).as_posix(), set()).add(chemin)
    assert len(urls) >= PLANCHER_ROUTEURS, (
        f"seuls {len(urls)} modules portent une route montée : le parcours de l'application "
        "ne voit plus les routes, et ce contrôle ne mesurerait plus rien."
    )
    return {rel: tuple(sorted(chemins)) for rel, chemins in urls.items()}


def _routeurs() -> list[str]:
    modules = modules_app("routers", minimum=PLANCHER_ROUTEURS)
    return [m.rel for m in modules]


def _routeurs_a_url() -> list[str]:
    """Les modules qui EXPOSENT une URL — la portée du contrôle (voir l'en-tête)."""
    urls = _urls_par_module()
    return [rel for rel in _routeurs() if rel in urls]


# ── Le témoin : le contrôle SAIT échouer ────────────────────────────────────


def test_temoin_un_module_que_personne_ne_nomme_est_releve():
    corpus = "from app.routers.alpha import router\nimport beta_utile"

    assert non_nommes(["routers/alpha.py", "routers/gamma.py", "routers/pkg/delta.py"], corpus) == [
        "routers/gamma.py",
        "routers/pkg/delta.py",
    ]


def test_temoin_un_homonyme_ne_nomme_pas_le_module():
    """Le cas fautif de #2914 : le mot, une clé de table, un autre chemin — aucun ne nomme."""
    corpus = (
        "objets = {}\n"
        'REGLE = ("utils/visibility/objets.py", "adresse")\n'
        'TABLE = {"epingles.py": "une raison"}\n'
        '"""Un routeur sorti (`copropriete_patrimoine`, `auth_profil`)."""\n'
        "def test_bailleur_objets(): ...\n"
    )
    urls = {"routers/bailleur/objets.py": ("/bailleur/baux/{bail_id}/objets",)}

    assert non_nommes(
        [
            "routers/bailleur/objets.py",
            "routers/flux/epingles.py",
            "routers/copropriete_patrimoine.py",
        ],
        corpus,
        urls,
    ) == [
        "routers/bailleur/objets.py",
        "routers/flux/epingles.py",
        "routers/copropriete_patrimoine.py",
    ]


@pytest.mark.parametrize(
    "corpus",
    [
        "from app.routers.bailleur import objets",
        "from app.routers.bailleur import (baux, objets)",
        "from app.routers.bailleur.objets import router",
        "import app.routers.bailleur.objets as module",
        "voir api/app/routers/bailleur/objets.py",
    ],
)
def test_temoin_l_import_ou_le_chemin_nomme(corpus):
    assert nomme(corpus, "routers/bailleur/objets.py")


def test_temoin_le_module_d_un_paquet_est_le_paquet():
    assert nomme('"app.routers.publications"', "routers/publications/__init__.py")
    assert nomme("from app.routers import publications", "routers/publications/__init__.py")
    assert not nomme("from app.routers import flux", "routers/publications/__init__.py")


def test_temoin_un_import_voisin_ne_nomme_pas():
    """`objets_extra` n'est pas `objets`, ni `app.routers.bailleur.objetsx`."""
    assert not nomme("from app.routers.bailleur import objets_extra", "routers/bailleur/objets.py")
    assert not nomme("import app.routers.bailleur.objetsx", "routers/bailleur/objets.py")
    assert not nomme("routers/bailleur/objets_v2.py", "routers/bailleur/objets.py")


@pytest.mark.parametrize(
    "corpus",
    [
        'http.get("/bailleur/baux/12/objets")',
        "http.post(f\"/bailleur/baux/{bail.id}/objets/{o['id']}/retour\", json={})",
        'http.get(f"/bailleur/baux/{bail_id}/objets{suite}")',
        "http.get('/bailleur/baux/3/objets?page=2')",
    ],
)
def test_temoin_une_url_appelee_nomme(corpus):
    urls = ("/bailleur/baux/{bail_id}/objets", "/bailleur/baux/{bail_id}/objets/{obj_id}/retour")
    assert nomme(corpus, "routers/bailleur/objets.py", urls)


def test_temoin_une_url_plus_longue_ou_un_segment_vide_ne_nomme_pas():
    assert not nomme('http.get("/avis/export")', "routers/avis.py", ("/avis",))
    assert not nomme(
        'http.get("/bailleur/baux//objets")', "routers/b.py", ("/bailleur/baux/{id}/objets",)
    )
    assert not nomme("le chemin /avis en prose", "routers/avis.py", ("/avis",))


# ── Le contrôle réel ────────────────────────────────────────────────────────


def test_chaque_module_de_routeur_est_nomme_par_un_test():
    corpus = _corpus()

    orphelins = [
        rel
        for rel in non_nommes(_routeurs_a_url(), corpus, _urls_par_module())
        if rel not in EXCEPTIONS
    ]

    assert not orphelins, (
        "Ces modules de `app/routers/` ne sont nommés par AUCUN fichier de `tests/` : "
        f"{orphelins}. Écrire le test du routeur — droits (401/403/404), cas nominal, cas "
        "limite — ou, si c'est vraiment voulu, déclarer l'exception avec sa raison."
    )


def test_une_exception_qui_ne_sert_plus_est_retiree():
    """La liste ne fait que baisser : un module nommé, ou disparu, sort des exceptions."""
    corpus = _corpus()
    existants = set(_routeurs_a_url())

    urls = _urls_par_module()
    perimees = [
        rel for rel in EXCEPTIONS if rel not in existants or nomme(corpus, rel, urls.get(rel, ()))
    ]

    assert not perimees, (
        f"exception(s) à retirer de EXCEPTIONS (module nommé ou disparu) : {perimees}"
    )


def test_chaque_exception_porte_sa_raison():
    vides = [rel for rel, raison in EXCEPTIONS.items() if not raison.strip()]

    assert not vides, f"exception(s) sans raison : {vides}"


def test_cas_zero_les_routeurs_et_les_tests_sont_lus():
    assert len(_routeurs()) >= PLANCHER_ROUTEURS
    assert len(_corpus()) > 100_000
    #  Chaque module qui porte une route montée est un module de `app/routers/` lu ici :
    #  un écart dirait que les deux parcours ne parlent plus des mêmes fichiers.
    assert set(_urls_par_module()) <= set(_routeurs())
