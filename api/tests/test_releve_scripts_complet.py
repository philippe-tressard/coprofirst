"""Le relevé des scripts shell voit TOUS les `.sh` du dépôt, où qu'ils soient (#1965).

`conftest.scripts_shell_versionnes()` nourrit une douzaine de contrôles (règle d'or
de la base, SSH, verrou de bascule, tâches planifiées…). Il ne lisait que la
racine, `scripts/**` et `.githooks/` : huit scripts lui échappaient, dont ceux que
chaque RÉPLIQUE exécute (`deploiement/standard/`), le démarrage de l'API
(`api/start.sh`) et l'initialisation de la réplication PostgreSQL. Une règle
posée sur « tous les scripts » ne valait donc pas pour eux — #1964 l'a montré :
l'envoi fautif de la réplique n'était vu par aucun contrôle partagé.

Ce test confronte le relevé à ce que git suit — rien d'écrit à la main, donc rien
qui diverge au prochain dossier créé.
"""

from __future__ import annotations

import subprocess

from tests.conftest import racine_depot, scripts_shell_versionnes


def _suivis_par_git() -> set[str]:
    sortie = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.sh"],
        cwd=racine_depot(),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return set(sortie)


def test_le_releve_contient_tout_script_du_depot():
    suivis = _suivis_par_git()
    assert len(suivis) > 50, f"cas zéro : git ne rend que {len(suivis)} script(s)"
    racine = racine_depot()
    releves = {p.relative_to(racine).as_posix() for p in scripts_shell_versionnes()}
    manquants = sorted(suivis - releves)
    assert not manquants, (
        f"ces scripts échappent aux contrôles partagés (`scripts_shell_versionnes`) : {manquants}"
    )


def test_les_hooks_git_restent_releves():
    """Les hooks n'ont pas d'extension : git ne les rend pas sous `*.sh`."""
    racine = racine_depot()
    releves = {p.relative_to(racine).as_posix() for p in scripts_shell_versionnes()}
    assert ".githooks/pre-commit" in releves and ".githooks/pre-push" in releves


def test_le_releve_ne_lit_ni_dependances_ni_fichiers_ignores():
    """`node_modules` peut porter des `.sh` tiers : ils ne sont pas les nôtres."""
    releves = [p.as_posix() for p in scripts_shell_versionnes()]
    assert not [p for p in releves if "/node_modules/" in p]
