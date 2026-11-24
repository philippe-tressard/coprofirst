"""Ce que les modules d'autorisation et leurs garde-fous CITENT existe (#2973).

## Pourquoi (audit du 23/11/2026)

`auth/deps.py` renvoyait à son « jumeau » du front, supprimé depuis ;
`test_autorisation.py` situait les règles de visibilité dans un module devenu un
paquet. Un renvoi mort dans un module de sécurité se lit comme une garantie : il
envoie le relecteur vérifier au mauvais endroit, ou nulle part.

## Ce que ce fichier tient

Dans `PORTEE` — les modules d'`app/auth/` et les tests d'autorisation —, chaque chemin
cité entre accents graves (`app/…`, `#lib/…`, `utils/…`, `auth/…`, `routers/…`,
`registre/…`, `models/…`) désigne un fichier ou un dossier qui existe ; cité sous la
forme `module.symbole`, le symbole est défini (ou importé) au niveau du module.

Une ligne qui parle du PASSÉ (`MARQUEURS_HISTORIQUE`) a le droit de nommer un mort.

## Ce qu'il ne fait pas

Il ne dit pas qu'un renvoi est JUSTE — seulement qu'il ne mène pas dans le vide.
"""

from __future__ import annotations

import ast
import functools
import pathlib
import re

_API = pathlib.Path(__file__).resolve().parents[1]
_APP = _API / "app"
_RACINE = _API.parent

#: Les fichiers dont les renvois se vérifient. La portée fait partie du contrôle.
PORTEE = (
    *sorted(_APP.glob("auth/*.py")),
    *sorted(_API.glob("tests/test_autorisation*.py")),
    *sorted(_API.glob("tests/test_appartenance*.py")),
    _API / "tests" / "test_moderateur_source_unique.py",
    _API / "tests" / "test_signature_registre_source_unique.py",
)

MARQUEURS_HISTORIQUE = ("supprim", "retir", "n'existe plus", "a disparu", "remplac", "renomm")

_CITE = re.compile(
    r"`((?:api/app/|app/|#lib/|front/src/|utils/|auth/|routers/|registre/|models/)[\w./-]+)`"
)


@functools.lru_cache(maxsize=None)
def _noms_du_module(chemin: pathlib.Path) -> frozenset[str]:
    noms = set()
    for noeud in ast.parse(chemin.read_text(encoding="utf-8-sig")).body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            noms.add(noeud.name)
        elif isinstance(noeud, ast.Assign):
            for cible in noeud.targets:  # `A, B = …` compris
                noms |= {getattr(c, "id", None) for c in getattr(cible, "elts", [cible])}
        elif isinstance(noeud, ast.AnnAssign):
            noms.add(getattr(noeud.target, "id", None))
        elif isinstance(noeud, (ast.Import, ast.ImportFrom)):
            noms |= {a.asname or a.name.split(".")[0] for a in noeud.names}
    return frozenset(noms - {None})


def renvoi_mort(cite: str) -> str | None:
    """Ce qui manque au renvoi `cite` — ou None s'il mène quelque part."""
    if cite.startswith("#lib/"):
        return None if (_RACINE / "front/src/lib" / cite[5:]).exists() else "fichier absent"
    if cite.startswith("front/"):
        return None if (_RACINE / cite.rstrip("/")).exists() else "fichier absent"
    cite = cite.removeprefix("api/").removeprefix("app/").rstrip("/")
    if (_APP / cite).exists() or (_APP / f"{cite}.py").exists():
        return None
    module, _, symbole = cite.rpartition(".")
    if symbole == "py" or not module:
        return "fichier absent"
    for chemin in (_APP / f"{module}.py", _APP / module / "__init__.py"):
        if chemin.exists():
            return None if symbole in _noms_du_module(chemin) else f"`{symbole}` absent du module"
    return "module absent"


def renvois_morts(fichiers) -> list[str]:
    morts = []
    for fichier in fichiers:
        for num, ligne in enumerate(fichier.read_text(encoding="utf-8-sig").splitlines(), 1):
            if any(m in ligne.lower() for m in MARQUEURS_HISTORIQUE):
                continue
            for cite in _CITE.findall(ligne):
                if (faute := renvoi_mort(cite)) is not None:
                    morts.append(f"{fichier.relative_to(_RACINE)}:{num} `{cite}` — {faute}")
    return morts


def test_la_portee_voit_ce_qu_elle_annonce():
    assert len(PORTEE) >= 15 and all(f.exists() for f in PORTEE), "portée perdue"
    cites = sum(len(_CITE.findall(f.read_text(encoding="utf-8-sig"))) for f in PORTEE)
    assert cites >= 50, f"{cites} renvoi(s) relevé(s) : le motif ne lit plus rien"


def test_aucun_renvoi_mort_dans_l_autorisation():
    morts = renvois_morts(PORTEE)
    assert not morts, "Renvoi(s) vers ce qui n'existe pas :\n  " + "\n  ".join(morts)


def test_temoins_les_deux_renvois_de_l_audit_sont_refuses():
    assert renvoi_mort("#lib/droits.ts") == "fichier absent"
    assert renvoi_mort("app/utils/visibility.py") == "fichier absent"
    assert renvoi_mort("utils/visibility/") is None
    assert renvoi_mort("auth/deps.peut_editer") is None
    assert renvoi_mort("auth/deps.symbole_disparu") == "`symbole_disparu` absent du module"


def test_une_exception_a_trancher_cite_son_ticket():
    """Une raison d'exception qui laisse un arbitrage « à trancher » nomme le ticket qui le
    porte — celui qu'elle citait était clos, et la question n'était plus portée nulle part
    (#2973).

    ⚠️ Limite : hors ligne, le contrôle ne sait pas si le ticket est OUVERT ; il exige
    qu'un numéro soit cité. L'état se relit à l'audit de cohérence.
    """
    sans_ticket = []
    for fichier in sorted(_API.glob("tests/test_*.py")):
        if fichier.name == pathlib.Path(__file__).name:
            continue  # ce fichier NOMME la règle, il ne laisse rien à trancher
        arbre = ast.parse(fichier.read_text(encoding="utf-8-sig"))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
                if "à trancher" in noeud.value.lower() and not re.search(r"#\d{3,}", noeud.value):
                    sans_ticket.append(f"{fichier.name}:{noeud.lineno}")
    assert not sans_ticket, "Arbitrage « à trancher » sans ticket : " + ", ".join(sans_ticket)
