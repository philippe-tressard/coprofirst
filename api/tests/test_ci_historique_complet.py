"""Tout job qui joue la suite pytest clone l'historique COMPLET (#2964).

POURQUOI (25/11/2026) — le premier SHA posé dans `.git-blame-ignore-revs` a fait
rendre INCONNU à `test_documentation` (« clone partiel ou sans git ») dans DEUX
workflows : « Tests Python (pytest) » de `ci.yml` (PR vers dev), puis « Suite pytest
sur PostgreSQL » de `postgresql.yml` (PR vers main) — le second a arrêté une MEP
à mi-course, `dev` déjà fusionné. Les deux clonaient en profondeur 1 : un test qui
mesure l'historique n'y mesure rien. Corriger le premier n'avait pas vu le second.

CE QUE CE TEST TIENT : chaque job, dans chaque workflow, qui lance la suite
(`scripts/ci/mesure-postgresql.sh`, hors son `--selftest`, qui ne la joue pas) a un
`actions/checkout` à `fetch-depth: 0`.
Cas zéro : au moins deux jobs la lancent ; un renommage du script ne rend pas vert.
"""

from __future__ import annotations

from tests.aides_compose import RACINE, lire_yaml

WORKFLOWS = RACINE / ".github" / "workflows"
LANCEUR = "scripts/ci/mesure-postgresql.sh"


def joue_la_suite(job: dict) -> bool:
    """Une ligne d'une étape lance la suite : le lanceur, sans son `--selftest`."""
    return any(
        LANCEUR in ligne and "--selftest" not in ligne
        for etape in job.get("steps", [])
        for ligne in str(etape.get("run", "")).splitlines()
    )


def _jobs_qui_jouent_la_suite() -> dict[str, dict]:
    jobs = {}
    for chemin in sorted(WORKFLOWS.glob("*.yml")):
        for nom, job in (lire_yaml(chemin).get("jobs") or {}).items():
            if joue_la_suite(job):
                jobs[f"{chemin.name}:{nom}"] = job
    return jobs


def historique_incomplet(job: dict) -> bool:
    """Vrai si aucun `actions/checkout` du job ne clone l'historique complet."""
    clones = [e for e in job.get("steps", []) if "actions/checkout" in str(e.get("uses", ""))]
    return not any((e.get("with") or {}).get("fetch-depth") == 0 for e in clones)


def test_chaque_job_de_la_suite_clone_l_historique_complet():
    jobs = _jobs_qui_jouent_la_suite()
    assert len(jobs) >= 2, f"cas zéro : la suite n'est plus lancée par {LANCEUR} — {sorted(jobs)}"
    fautifs = sorted(n for n, job in jobs.items() if historique_incomplet(job))
    assert not fautifs, (
        "job qui joue la suite pytest sans l'historique complet — `test_documentation` "
        f"y rendrait INCONNU sur `.git-blame-ignore-revs` : donner `fetch-depth: 0` à {fautifs}"
    )


def test_le_controle_voit_un_clone_partiel():
    """Témoin (`standards/04` §2) : la forme du 25/11 est vue, la forme juste passe."""
    clone = {"uses": "actions/checkout@abc # v7"}
    assert historique_incomplet({"steps": [clone, {"run": f"bash ../{LANCEUR}"}]})
    assert historique_incomplet({"steps": [{**clone, "with": {"fetch-depth": 1}}]})
    assert not historique_incomplet({"steps": [{**clone, "with": {"fetch-depth": 0}}]})
    assert joue_la_suite({"steps": [{"run": f"bash ../{LANCEUR}"}]})
    assert not joue_la_suite({"steps": [{"run": f"bash {LANCEUR}      --selftest"}]})
