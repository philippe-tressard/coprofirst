"""L'essai de mise à jour éprouve aussi une installation COMMUNE (#3007, 24/11/2026).

POURQUOI — #3006 éprouvait l'installation commune par morceaux (la pile, le
`Caddyfile`, le refus de `/auth/verifier-acces`) ; l'assemblage sur des conteneurs
réels n'était joué par rien : `grep commune scripts/ci/essai-mise-a-jour.sh` ne
rendait rien. Ce test tient que le mode existe et qu'il est branché de bout en bout ;
le constat lui-même tourne sur un runner (workflow « Essai de mise à jour »), et sa
décision est PURE, éprouvée par `lib-essai-commune.sh --selftest` (job test-scripts).
"""

from __future__ import annotations

import re
import subprocess

from tests.aides_compose import RACINE, lire_yaml

SCRIPT = RACINE / "scripts" / "ci" / "essai-mise-a-jour.sh"
LIB = RACINE / "scripts" / "ci" / "lib-essai-commune.sh"
WORKFLOW = RACINE / ".github" / "workflows" / "essai-mise-a-jour.yml"
CI = RACINE / ".github" / "workflows" / "ci.yml"


def test_le_workflow_propose_le_mode_commune_et_le_transmet():
    flux = lire_yaml(WORKFLOW)
    #  `on:` se lit `True` en YAML 1.1.
    entrees = (flux.get("on") or flux.get(True))["workflow_dispatch"]["inputs"]
    assert entrees["mode"]["options"] == ["propre", "commune"]
    assert entrees["mode"]["default"] == "propre", "sans mode, l'essai reste celui d'avant"
    texte = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r'essai-mise-a-jour\.sh "\$DE" "\$VERS" "\$MODE"', texte), texte


def test_le_mode_commune_constate_avant_et_apres_la_mise_a_jour():
    texte = SCRIPT.read_text(encoding="utf-8")
    assert "lib-essai-commune.sh" in texte
    i_installer = texte.index("installer_commune")
    i_avant = texte.index("constater_commune avant")
    i_maj = texte.index("bash deploiement/standard/mise-a-jour.sh")
    i_apres = texte.index("constater_commune après")
    assert i_installer < i_avant < i_maj < i_apres, (
        "le constat commun se joue après la création des copropriétés, AVANT la mise à "
        "jour (sinon un défaut de <de> passerait pour une régression) et APRÈS elle"
    )
    #  Le verdict final porte les deux : un essai vert ne masque pas un commun rouge.
    assert re.search(r'VERDICT=\$\(joindre_verdicts "\$VERDICT" "\$APRES"\)', texte)


def test_les_coproprietes_se_creent_par_l_outillage_de_l_hebergeur():
    """Le vrai `creer-copropriete.sh` de <de>, jamais une déclaration écrite à la main."""
    texte = LIB.read_text(encoding="utf-8")
    assert "bash deploiement/standard/commune/creer-copropriete.sh" in texte
    assert "coproprietes.json" in texte  # COPROPRIETES_FICHIER, posé avant elles


def test_l_autotest_de_la_decision_est_branche_et_vert():
    assert "bash scripts/ci/lib-essai-commune.sh      --selftest" in CI.read_text(encoding="utf-8")
    res = subprocess.run(["bash", str(LIB), "--selftest"], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "tous les cas passent" in res.stdout
