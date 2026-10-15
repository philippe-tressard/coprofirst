"""La suite pytest tourne sur PostgreSQL, UNE fois par événement de CI (#2004).

Deux checks REQUIS de `main` la portent, et aucun ne se renomme sans toucher la
protection de branche :

- « Tests Python (pytest) » (`ci.yml`) la joue pour les PR vers `dev` et le
  lancement à la main ;
- « Suite pytest sur PostgreSQL » (`postgresql.yml`) la joue pour ce qui vise
  `main` — PR et push.

La condition de l'étape de `ci.yml` n'a de sens que contre les déclencheurs de
`postgresql.yml` : l'un change sans l'autre, et la suite tourne deux fois — ou,
pire, ne tourne plus pour `main` derrière un check vert.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
SCRIPT = "scripts/ci/mesure-postgresql.sh"
CONDITION_CI = "github.base_ref == 'dev' || github.event_name == 'workflow_dispatch'"


def _flux(nom: str) -> dict:
    return yaml.safe_load((WORKFLOWS / nom).read_text(encoding="utf-8"))


def _declencheurs(flux: dict) -> dict:
    #  PyYAML lit la clé `on` comme le booléen True (YAML 1.1).
    return flux.get("on") or flux.get(True) or {}


def _job(flux: dict, nom: str) -> dict:
    jobs = [j for j in flux["jobs"].values() if j.get("name") == nom]
    assert len(jobs) == 1, f"le job « {nom} » — check requis de main — a disparu ou est doublé"
    return jobs[0]


def _etape_suite(job: dict) -> dict:
    etapes = [e for e in job["steps"] if SCRIPT in str(e.get("run", ""))]
    assert len(etapes) == 1, f"{SCRIPT} doit être lancé par une étape et une seule"
    return etapes[0]


def test_postgresql_yml_joue_la_suite_pour_main_seulement():
    flux = _flux("postgresql.yml")
    declencheurs = _declencheurs(flux)
    assert declencheurs["push"]["branches"] == ["main"]
    assert declencheurs["pull_request"]["branches"] == ["main"]
    job = _job(flux, "Suite pytest sur PostgreSQL")
    etape = _etape_suite(job)
    assert "if" not in etape and "if" not in job, "la suite y tourne sans condition"
    assert etape["env"]["TESTS_BASE_URL"].startswith("postgresql+psycopg://")


def test_ci_yml_joue_la_suite_quand_postgresql_yml_ne_tourne_pas():
    flux = _flux("ci.yml")
    assert "dev" in _declencheurs(flux)["pull_request"]["branches"]
    job = _job(flux, "Tests Python (pytest)")
    etape = _etape_suite(job)
    assert etape.get("if") == CONDITION_CI, (
        f"l'étape de la suite doit tourner exactement quand postgresql.yml ne tourne pas : "
        f"`if: {CONDITION_CI}`"
    )
    #  Au niveau du job : le rejeu du poste ne lit que l'`env:` des étapes.
    assert job["env"]["TESTS_BASE_URL"].startswith("postgresql+psycopg://")
    assert "TESTS_BASE_URL" not in etape.get("env", {})
    assert "postgres" in job.get("services", {}), "la suite n'a pas de serveur PostgreSQL"
