"""Chaque job d'un workflow de `main` ou planifié finit par l'alerte d'échec (#2988).

`standards/07` §1 bis : un rouge de la branche de production ou d'un passage
planifié ouvre (ou complète) un ticket, par un pas final `if: failure()`, et un
contrôle refuse un job ajouté qui ne l'a pas. La règle vit dans
`scripts/ci/signaler_echec_ci.py` (une fonction, jamais une copie par workflow) ;
ce test tient le BRANCHEMENT :

- la portée : tout workflow déclenché par un `push` sur `main` ou un `schedule`.
  Un workflow de PR seulement en est exclu, et c'est voulu : son rouge se voit sur
  la PR, là où l'on travaille ;
- chaque job de la portée : dernier pas `if: failure()` qui lance le script avec
  `--signaler` (l'avant-dernier devant la marque « arbre jugé vert ») ; le droit
  `issues: write` déclaré dans le job (les droits d'un workflow restent en lecture,
  `test_ci_installations_epinglees.py`) ; le script présent sur le runner (un job
  sans `actions/checkout` en extrait un, au même `if: failure()`).
"""

from __future__ import annotations

import pytest
import yaml

from tests.conftest import racine_depot

RACINE = racine_depot()
WORKFLOWS = RACINE / ".github" / "workflows"
SCRIPT = "scripts/ci/signaler_echec_ci.py"


def _declencheurs(donnees: dict) -> dict:
    on = donnees.get("on", donnees.get(True)) or {}
    return on if isinstance(on, dict) else {cle: None for cle in on}


def dans_la_portee(donnees: dict) -> bool:
    on = _declencheurs(donnees)
    push = on.get("push") or {}
    return "schedule" in on or "main" in (push.get("branches") or [])


def fautes_du_job(donnees: dict, nom: str, job: dict) -> list[str]:
    fautes = []
    etapes = job.get("steps") or []
    #  La marque « arbre jugé vert » reste la dernière (`test_ci_arbre_deja_vert.py`) :
    #  elle ne se pose que sur un vert, l'alerte se place donc juste avant elle.
    if etapes and "arbre-vert-" in str((etapes[-1].get("with") or {}).get("name", "")):
        etapes = etapes[:-1]
    dernier = etapes[-1] if etapes else {}
    lance = str(dernier.get("run", ""))
    if "failure()" not in str(dernier.get("if", "")) or not (
        SCRIPT in lance and "--signaler" in lance
    ):
        fautes.append(f"{nom} : le dernier pas n'est pas l'alerte `if: failure()`")
    droits = job.get("permissions") or {}
    if not (isinstance(droits, dict) and droits.get("issues") == "write"):
        fautes.append(f"{nom} : pas de `issues: write` effectif, le ticket ne s'ouvrirait pas")
    if not any("actions/checkout" in str(e.get("uses", "")) for e in etapes):
        fautes.append(f"{nom} : aucun `actions/checkout` — le script n'est pas sur le runner")
    return fautes


def _workflows() -> list:
    trouves = sorted(WORKFLOWS.glob("*.yml"))
    assert len(trouves) >= 8, "relevé des workflows vide : contrôle impossible"
    return trouves


def test_la_portee_comprend_main_et_les_passages_planifies():
    portee = {f.name for f in _workflows() if dans_la_portee(yaml.safe_load(f.read_text()))}
    assert {"ci.yml", "images.yml", "veille-securite.yml"} <= portee, portee  # cas zéro


@pytest.mark.parametrize("fichier", _workflows(), ids=lambda f: f.name)
def test_chaque_job_de_la_portee_finit_par_l_alerte(fichier):
    donnees = yaml.safe_load(fichier.read_text(encoding="utf-8"))
    if not dans_la_portee(donnees):
        pytest.skip("workflow de PR : son rouge se voit sur la PR")
    fautes = [f for nom, job in donnees["jobs"].items() for f in fautes_du_job(donnees, nom, job)]
    assert not fautes, f"{fichier.name} :\n" + "\n".join(fautes)


def test_le_controle_refuse_un_job_sans_alerte():
    #  Le contrôle lui-même : la forme fautive d'avant le correctif.
    sans = {"permissions": {"contents": "read"}, "jobs": {}}
    job = {"steps": [{"uses": "actions/checkout@x"}, {"run": "echo"}]}
    assert len(fautes_du_job(sans, "j", job)) == 2
    avec = {
        "steps": [
            {"uses": "actions/checkout@x"},
            {"if": "failure()", "run": f"python3 {SCRIPT} --signaler"},
        ],
        "permissions": {"issues": "write"},
    }
    assert not fautes_du_job(sans, "j", avec)
    assert dans_la_portee({"on": {"schedule": [{"cron": "0 1 * * *"}]}})
    assert not dans_la_portee({"on": {"pull_request": {"branches": ["dev"]}}})
