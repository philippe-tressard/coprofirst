"""La reprise après sinistre tourne comme le service `api` durci — et son banc aussi (#2547).

`restaurer-copie-hors-site.sh` installait les fichiers téléversés en `--user root`.
Le service `api` est durci (#2368) : son root n'a ni DAC_OVERRIDE ni FOWNER, et un
volume `uploads` neuf naît à `app` — l'extraction aurait échoué le jour du sinistre.
Le banc ne le voyait pas : ses `docker run` n'avaient pas les options du compose, donc
les capacités par défaut de Docker. Il éprouvait autre chose que la procédure.

Ce contrôle tient les deux moitiés :

1. chaque LANCEUR (`lancer_base`, `lancer_fichiers`, en vrai et au banc) prend le
   compte `app`, jamais root — `test_conteneurs_non_root.py` ne juge que la forme
   Compose, pas un `docker run` d'image ;
2. ceux du banc passent les options DURCIES que `compose_options_durcies` lit dans le
   compose, et cette lecture rend ce que le compose déclare (mesuré sur le fichier).
"""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from tests.aides_compose import COMPOSE, RACINE, lire_yaml

SCRIPT = RACINE / "scripts" / "exploitation" / "restaurer-copie-hors-site.sh"
LIB = RACINE / "scripts" / "lib" / "lib-audit-conteneurs.sh"
_LANCEUR = re.compile(r"^\s*(lancer_base|lancer_fichiers)\(\) \{\n(.*?)^\s*\}$", re.M | re.S)
_ROOT = re.compile(r"(?:^|\s)(?:-u|--user)(?:\s+|=)(?:root|0)\b")


def _lanceurs() -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in _LANCEUR.finditer(SCRIPT.read_text("utf-8"))]


def test_chaque_lanceur_prend_le_compte_app():
    lanceurs = _lanceurs()
    #  Cas zéro : deux en vrai, deux au banc — une portée cassée n'en verrait aucun.
    assert sorted(n for n, _ in lanceurs) == ["lancer_base"] * 2 + ["lancer_fichiers"] * 2, (
        f"lanceurs lus : {[n for n, _ in lanceurs]}"
    )
    for nom, corps in lanceurs:
        assert not _ROOT.search(corps), (
            f"{nom} lance l'API en root : sous le service durci, ce root n'écrit pas dans "
            f"un volume né à `app` (#2547) → `--user app`\n{corps}"
        )
        assert re.search(r"(?:-u|--user)(?:\s+|=)app\b", corps), f"{nom} ne nomme pas `app`"


def test_les_fichiers_arrivent_en_flux():
    """L'archive n'est ni montée (illisible à `app`) ni copiée (le disque doublé)."""
    for nom, corps in _lanceurs():
        assert "archive" not in corps, f"{nom} monte encore l'archive : {corps}"
        if nom == "lancer_fichiers":
            assert re.search(r"\s-(?:i|T)\s", corps), f"{nom} n'ouvre pas l'entrée standard"


def test_le_banc_durcit_ses_conteneurs_comme_le_compose():
    banc = [c for _n, c in _lanceurs() if '"$IMAGE_API"' in c]
    assert len(banc) == 2, 'les lanceurs du banc (`docker run … "$IMAGE_API"`) ne sont plus vus'
    for corps in banc:
        assert '"${DURCI_API[@]}"' in corps, f"un lanceur du banc n'est pas durci : {corps}"
    assert re.search(
        r"^\s*DURCI_API=\$\(compose_options_durcies \"\$\(cat docker-compose\.yml\)\" api\)",
        SCRIPT.read_text("utf-8"),
        re.M,
    ), "DURCI_API ne vient plus du compose"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash absent : la lecture non mesurée")
def test_la_lecture_du_compose_rend_ce_qu_il_declare():
    res = subprocess.run(
        [
            "bash",
            "-c",
            f"source '{LIB.as_posix()}'; compose_options_durcies \"$(cat '{COMPOSE.as_posix()}')\" api",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert res.returncode == 0, f"compose_options_durcies a refusé : {res.stdout}{res.stderr}"
    api = lire_yaml(COMPOSE)["services"]["api"]
    attendu = {"--read-only"} if api["read_only"] else set()
    attendu |= {f"--cap-drop={c}" for c in api["cap_drop"]}
    attendu |= {f"--security-opt={o}" for o in api["security_opt"]}
    attendu |= {f"--cap-add={c}" for c in api["cap_add"]}
    attendu |= {f"--tmpfs={t}" for t in api["tmpfs"]}
    assert set(res.stdout.split()) == attendu
    assert "--cap-drop=ALL" in attendu and api["tmpfs"], "cas zéro : le service n'est plus durci"
