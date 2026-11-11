"""Un arbre déjà jugé vert ne se rejoue pas — et rien d'autre ne saute (#2632).

Chaque job requis de `ci.yml` dépend du job `arbre`, qui lui dit si l'arbre jugé
porte déjà sa marque ; il est alors SAUTÉ, ce que GitHub compte comme un succès du
check requis. Un saut est donc un vert : ce test tient les trois conditions sans
lesquelles il en deviendrait un faux.

1. Un job ne saute QUE sur la marque de son propre nom (`!= 'oui'`) et jamais quand
   l'exécution est annulée ; un job `arbre` en échec laisse la sortie vide, et le
   job JOUE (`!cancelled()`, jamais `success()` du job `arbre`).
2. La marque est la DERNIÈRE étape de son job : posée seulement si toutes les
   autres ont réussi. Son nom porte le job et l'arbre — arbre modifié, marque
   inutile (le cas est éprouvé par `arbre_deja_vert.py --selftest`).
3. La liste des jobs cherchés par `arbre` est celle des jobs qui dépendent de lui.

Les règles de validité d'une marque (expirée, fourche, API muette) sont éprouvées
par l'autotest du script, que ce test lance.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
CI = RACINE / ".github" / "workflows" / "ci.yml"
SCRIPT = RACINE / "scripts" / "ci" / "arbre_deja_vert.py"
MARQUE = "arbre-vert-{job}-${{{{ needs.arbre.outputs.arbre }}}}"
#  Les tranches de Playwright ne posent pas leur marque : l'agrégat la pose pour elles.
MARQUE_POSEE_PAR = {"e2e-frontend": "e2e-verdict"}


def _jobs() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]


def _guettes(jobs: dict) -> list[str]:
    return sorted(k for k, j in jobs.items() if j.get("needs") == "arbre")


def test_chaque_job_requis_passe_par_arbre():
    jobs = _jobs()
    #  Tous les jobs de ci.yml sont requis : aucun autre que `arbre` et l'agrégat
    #  ne peut échapper à la règle.
    assert set(jobs) - set(_guettes(jobs)) == {"arbre", "e2e-verdict"}
    for cle in _guettes(jobs):
        attendu = f"${{{{ !cancelled() && needs.arbre.outputs['{cle}'] != 'oui' }}}}"
        assert jobs[cle].get("if") == attendu, f"{cle} : `if: {attendu}`"


def test_arbre_cherche_exactement_les_jobs_qui_le_guettent():
    jobs = _jobs()
    arbre = jobs["arbre"]
    corps = "\n".join(str(e.get("run", "")) for e in arbre["steps"])
    cherches = re.search(r'JOBS="([^"]+)"', corps)
    assert cherches, "le job arbre ne dit pas quels jobs il cherche"
    assert sorted(cherches.group(1).split()) == _guettes(jobs)
    assert sorted(k for k in arbre["outputs"] if k != "arbre") == _guettes(jobs)
    assert arbre["permissions"] == {"contents": "read", "actions": "read"}
    assert "if" not in arbre, "le job arbre tourne toujours"


def test_la_marque_est_la_derniere_etape_et_porte_job_et_arbre():
    jobs = _jobs()
    for cle in _guettes(jobs):
        porteur = jobs[MARQUE_POSEE_PAR.get(cle, cle)]
        derniere = porteur["steps"][-1]
        assert "actions/upload-artifact@" in derniere.get("uses", ""), (
            f"{cle} : pas de marque en fin"
        )
        assert derniere["with"]["name"] == MARQUE.format(job=cle)
        #  Un fichier absent n'est qu'un avertissement par défaut : la marque de
        #  Playwright a manqué ainsi, l'agrégat n'ayant pas de checkout.
        assert derniere["with"].get("if-no-files-found") == "error", f"{cle} : marque muette"
        if not any("actions/checkout@" in str(e.get("uses", "")) for e in porteur["steps"]):
            assert "runner.temp" in derniere["with"]["path"], f"{cle} : fichier hors du dépôt"
        assert "needs.arbre.outputs.arbre != ''" in derniere.get("if", ""), (
            f"{cle} : sans arbre lu, aucune marque"
        )
    #  Les tranches : la marque ne se pose que si toutes ont réussi.
    assert "needs.e2e-frontend.result == 'success'" in jobs["e2e-verdict"]["steps"][-1]["if"]


def test_l_agregat_ne_lit_un_saut_comme_vert_que_sur_la_marque():
    verdict = _jobs()["e2e-verdict"]
    assert verdict["if"] == "always()"
    assert verdict["env"]["DEJA_VERT"] == "${{ needs.arbre.outputs['e2e-frontend'] }}"
    corps = verdict["steps"][0]["run"]
    assert '[ "$RESULTAT_TRANCHES" = skipped ] && [ "${DEJA_VERT:-}" = oui ]' in corps


def test_l_autotest_du_script_passe():
    r = subprocess.run([sys.executable, str(SCRIPT), "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ÉCHEC" not in r.stdout, r.stdout
