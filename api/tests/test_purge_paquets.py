"""La purge des paquets suit la règle de l'API, et ne touche à rien d'autre (#2210).

`scripts/ci/purge-paquets.sh` retire les releases et les images GHCR que plus aucune
vague ne peut servir. Ce qui se garde est décidé par `app/registre/versions.py`, le
module PUR que lit aussi le registre : une règle recopiée en bash divergerait au
premier changement des vagues — et la purge supprimerait une version servie.
"""

from __future__ import annotations

import re

from tests.aides_compose import RACINE
from tests.aides_compose import lire_yaml as _yaml

WORKFLOW = RACINE / ".github" / "workflows" / "purge-paquets.yml"
SCRIPT = RACINE / "scripts" / "ci" / "purge-paquets.sh"
VERSIONS = RACINE / "api" / "app" / "registre" / "versions.py"


def test_le_script_execute_la_regle_de_l_api():
    texte = SCRIPT.read_text(encoding="utf-8")
    assert "api/app/registre/versions.py" in texte
    assert '"$VERSIONS_PY" garder' in texte and '"$VERSIONS_PY" fenetre' in texte
    #  Aucune règle de sélection recopiée : ni le nombre de mineures, ni les 7 jours.
    assert not re.search(r"\b(VERSIONS_PROPOSEES|ATTENTE|7 jours de)\b", texte)


def test_le_module_de_la_regle_se_lit_sans_l_application():
    """Le script le lance par `python3 -I` sur le runner : aucun import du projet."""
    imports = re.findall(r"^(?:from|import) (\S+)", VERSIONS.read_text(encoding="utf-8"), re.M)
    assert not [m for m in imports if m.startswith("app")], imports


def test_droits_au_plus_juste_et_le_constat_par_defaut():
    flux = _yaml(WORKFLOW)
    assert flux["permissions"] == {}
    assert flux["jobs"]["purger"]["permissions"] == {"contents": "write", "packages": "write"}
    texte = WORKFLOW.read_text(encoding="utf-8")
    assert "bash scripts/ci/purge-paquets.sh" in texte
    #  À la main : le constat, sauf demande explicite ; la nuit : la suppression.
    assert "default: false" in texte
    assert "github.event_name == 'schedule' || inputs.supprimer" in texte


def test_le_selftest_tourne_en_ci():
    ci = (RACINE / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert re.search(r"bash scripts/ci/purge-paquets\.sh\s+--selftest", ci)


def test_le_tag_git_ne_part_jamais():
    texte = SCRIPT.read_text(encoding="utf-8")
    suppressions = [
        ligne
        for ligne in texte.splitlines()
        if "gh release delete" in ligne and not ligne.lstrip().startswith("#")
    ]
    assert suppressions and not [s for s in suppressions if "--cleanup-tag" in s]
    assert "git push" not in texte and "git tag -d" not in texte
