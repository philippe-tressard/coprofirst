"""Ce que le code importe, `requirements.txt` le déclare (24/09/2026, #1048).

`pydantic`, `pydantic_settings` et `sqlalchemy` étaient importés directement —
près de 300 fois à eux trois — sans figurer dans `requirements.txt` : ils
arrivaient par `fastapi`, `sqlmodel` et `fastapi-mail`. Une montée de l'un de
ceux-là pouvait donc changer leur version, voire les retirer, sans que le fichier
des dépendances bouge d'une ligne. Le dépôt épinglait tout, sauf ce dont il se
servait le plus.

Ce contrôle lit les `import` de chaque ENVIRONNEMENT, rattache chaque module tiers
à sa distribution par les métadonnées installées — `PIL` vient de `Pillow`, `jwt`
de `PyJWT` : un nom de module n'est pas un nom de paquet — et exige que cette
distribution soit écrite dans le fichier de dépendances de cet environnement :

- la production (`app/`, `alembic/`, `alembic_plateforme/`, `scripts/`) →
  `requirements.txt` ;
- les tests (`tests/`) → `requirements-dev.txt`, qui inclut le premier.

🔴 Jusqu'au 23/11/2026 il ne lisait que `app/` et `alembic/` (#2955) : `yaml`
(neuf fichiers de tests) et `starlette` (quatre) n'étaient déclarés nulle part et
n'arrivaient que par `uvicorn[standard]` et `fastapi` ; la chaîne
`alembic_plateforme/` et `scripts/` échappaient aussi.

⚠️ Le sens inverse — un paquet déclaré que rien n'importe — ne se contrôle pas
ainsi : `python-dotenv` n'est jamais importé et sert pourtant (il lit le `.env`
de `pydantic-settings`), `uvicorn` et `bcrypt` sont chargés par leur nom. Chaque
ligne de `requirements.txt` qui n'est pas importée dit pourquoi elle est là.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
from importlib.metadata import packages_distributions

import pytest

from tests.aides_sources import modules_app

RACINE = pathlib.Path(__file__).resolve().parents[1]
REQUIREMENTS = RACINE / "requirements.txt"

#: Chaque environnement : les dossiers de `api/` qu'il exécute, et le fichier qui
#: déclare ce qu'il installe.
ENVIRONNEMENTS = {
    "production": (("app", "alembic", "alembic_plateforme", "scripts"), REQUIREMENTS),
    "tests": (("tests",), RACINE / "requirements-dev.txt"),
}
PORTEE = ENVIRONNEMENTS["production"][0]

#: Les modules du DÉPÔT que les tests chargent par leur chemin (`scripts/ci/*.py`,
#: posés sur `sys.path`) : ils ne viennent d'aucune distribution.
MODULES_DU_DEPOT = frozenset(p.stem for p in (RACINE.parent / "scripts").rglob("*.py"))


def _normaliser(nom: str) -> str:
    """PEP 503 : `SQLAlchemy`, `pydantic_settings` et `pydantic-settings` se valent."""
    return re.sub(r"[-_.]+", "-", nom).lower()


def _declarees(fichier: pathlib.Path = REQUIREMENTS) -> set[str]:
    """Les distributions d'un fichier de dépendances, `-r` suivi."""
    noms = set()
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if ligne.startswith("-r "):
            noms |= _declarees(fichier.parent / ligne[3:].strip())
            continue
        if not ligne or ligne.startswith("-"):
            continue
        noms.add(_normaliser(re.split(r"[\[=<>~!;\s]", ligne, maxsplit=1)[0]))
    return noms


def _arbres(portee: tuple[str, ...] = PORTEE):
    """(chemin relatif à `api/`, arbre) de chaque module d'une portée.

    `app/` vient de l'aide partagée ; les autres dossiers n'en ont pas, et se lisent ici.
    """
    for dossier in portee:
        if dossier == "app":
            for module in modules_app():
                yield f"app/{module.rel}", module.arbre
            continue
        fichiers = [p for p in (RACINE / dossier).rglob("*.py") if "__pycache__" not in p.parts]
        assert fichiers, f"`api/{dossier}/` ne rend aucun module : la portée a bougé"
        for chemin in fichiers:
            yield (
                chemin.relative_to(RACINE).as_posix(),
                ast.parse(chemin.read_text(encoding="utf-8")),
            )


def _modules_tiers(portee: tuple[str, ...] = PORTEE) -> dict[str, set[str]]:
    """Module de premier niveau → fichiers qui l'importent, hors stdlib et code du dépôt."""
    trouves: dict[str, set[str]] = {}
    for rel, arbre in _arbres(portee):
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                noms = [a.name for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0 and noeud.module:
                noms = [noeud.module]
            else:
                continue
            for nom in noms:
                tete = nom.split(".")[0]
                if tete in sys.stdlib_module_names or tete in {"app", "tests"} | MODULES_DU_DEPOT:
                    continue
                trouves.setdefault(tete, set()).add(rel)
    return trouves


def non_declares(
    modules: dict[str, set[str]], declarees: set[str], distributions
) -> dict[str, str]:
    """Module importé → pourquoi il n'est pas couvert par `declarees`. PURE."""
    fautifs = {}
    for module, fichiers in sorted(modules.items()):
        candidates = {_normaliser(d) for d in distributions.get(module, [])}
        if not candidates:
            fautifs[module] = f"module introuvable dans l'environnement — {sorted(fichiers)[:3]}"
        elif not candidates & declarees:
            fautifs[module] = (
                f"vient de {sorted(candidates)}, non déclaré — importé par {sorted(fichiers)[:3]}"
            )
    return fautifs


def test_cas_zero_le_parcours_voit_les_imports_et_le_fichier():
    """Sans quoi le contrôle ne verrait rien, et ne refuserait donc rien."""
    modules = _modules_tiers(PORTEE)
    assert {"fastapi", "sqlmodel", "pydantic"} <= modules.keys(), (
        f"le parcours de {PORTEE} ne voit plus les imports : {sorted(modules)}"
    )
    assert {"fastapi", "sqlmodel"} <= _declarees(), "`requirements.txt` n'est plus lu"


@pytest.mark.parametrize("environnement", sorted(ENVIRONNEMENTS))
def test_tout_module_tiers_importe_vient_d_une_dependance_declaree(environnement):
    portee, fichier = ENVIRONNEMENTS[environnement]
    fautifs = non_declares(_modules_tiers(portee), _declarees(fichier), packages_distributions())
    assert not fautifs, (
        f"Des modules importés par {portee} ne sont pas déclarés dans {fichier.name} :\n  "
        + "\n  ".join(f"{m} : {raison}" for m, raison in fautifs.items())
        + "\nLes déclarer et les épingler — une dépendance transitive peut changer "
        "de version, ou disparaître, au gré d'une autre."
    )


@pytest.mark.parametrize("environnement", sorted(ENVIRONNEMENTS))
def test_cas_zero_chaque_environnement_est_lu(environnement):
    portee, fichier = ENVIRONNEMENTS[environnement]
    assert _modules_tiers(portee), f"aucun import tiers vu dans {portee} : le parcours est aveugle"
    assert {"fastapi", "sqlmodel"} <= _declarees(fichier), f"`{fichier.name}` n'est plus lu"


def test_temoin_le_cas_fautif_de_2955_est_refuse():
    """`yaml` importé par les tests, `PyYAML` absent : refusé ; déclaré : admis."""
    modules = {"yaml": {"tests/aides_compose.py"}, "fastapi": {"tests/conftest.py"}}
    distributions = {"yaml": ["PyYAML"], "fastapi": ["fastapi"]}

    assert list(non_declares(modules, {"fastapi"}, distributions)) == ["yaml"]
    assert non_declares(modules, {"fastapi", "pyyaml"}, distributions) == {}
    assert list(non_declares({"inconnu": {"x.py"}}, set(), {})) == ["inconnu"]


def test_temoin_un_fichier_inclus_par_r_est_lu(tmp_path):
    (tmp_path / "base.txt").write_text("fastapi==1.0\n", encoding="utf-8")
    (tmp_path / "dev.txt").write_text("-r base.txt\npytest==9.0  # tests\n", encoding="utf-8")

    assert _declarees(tmp_path / "dev.txt") == {"fastapi", "pytest"}


# ── Les dépendances LATENTES : chargées à l'exécution, sans `import` (#1570) ──
#
#  `from pydantic import EmailStr` ne mentionne pas `email_validator`, et le
#  contrôle ci-dessus, qui lit les `import`, ne le voit donc pas : pydantic
#  l'importe à l'EXÉCUTION, quand un modèle qui porte `EmailStr` se construit.
#  Il arrivait par `fastapi-mail` — le cas exact que #1048 avait corrigé pour
#  `pydantic`. Chaque symbole qui exige un paquet sans l'importer se déclare ici.

#: symbole importé → distribution que son emploi exige à l'exécution.
DEPENDANCES_LATENTES = {"EmailStr": "email-validator", "NameEmail": "email-validator"}


def _symboles_importes() -> dict[str, set[str]]:
    """Nom importé (`from x import NOM`) ou attribut (`pydantic.NOM`) → fichiers."""
    trouves: dict[str, set[str]] = {}
    for rel, arbre in _arbres():
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom):
                noms = [a.name for a in noeud.names]
            elif isinstance(noeud, ast.Attribute):
                noms = [noeud.attr]
            else:
                continue
            for nom in noms:
                trouves.setdefault(nom, set()).add(rel)
    return trouves


def _manquantes(symboles: dict[str, set[str]], declarees: set[str]) -> dict[str, str]:
    return {
        f"{symbole} → {_normaliser(paquet)}": f"importé par {sorted(symboles[symbole])[:3]}"
        for symbole, paquet in DEPENDANCES_LATENTES.items()
        if symbole in symboles and _normaliser(paquet) not in declarees
    }


def test_cas_zero_le_parcours_voit_un_symbole_latent():
    """`EmailStr` est employé : sinon ce contrôle serait vert sur un parcours aveugle."""
    assert "EmailStr" in _symboles_importes(), "plus aucun `EmailStr` : retirer la ligne ou le test"


def test_un_symbole_latent_exige_sa_dependance_declaree():
    manquantes = _manquantes(_symboles_importes(), _declarees())
    assert not manquantes, (
        "Un symbole qui charge un paquet à l'exécution, sans `import`, exige ce paquet "
        "dans requirements.txt (épinglé) :\n  "
        + "\n  ".join(f"{m} : {r}" for m, r in manquantes.items())
    )


def test_le_controle_des_dependances_latentes_sait_REFUSER():
    """Le cas fautif — `EmailStr` employé, `email-validator` absent — est refusé."""
    employes = {"EmailStr": {"app/routers/config.py"}}
    assert _manquantes(employes, {"pydantic", "fastapi"}) != {}
    assert _manquantes(employes, {"pydantic", "email-validator"}) == {}
    assert _manquantes({"BaseModel": {"app/x.py"}}, {"pydantic"}) == {}
