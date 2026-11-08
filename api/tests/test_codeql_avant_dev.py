"""CodeQL juge la PR vers `dev`, et ne touche pas à ce qui garde `main` (#2571).

La configuration par défaut de GitHub n'analyse que les PR vers `main` : l'alerte de
ReDoS de #2569 n'est apparue qu'à la PR dev→main, un cycle de MEP perdu.
`codeql-avant-dev.yml` refait l'analyse sur la PR vers `dev`, sans l'envoyer (GitHub
refuse l'envoi d'une analyse avancée tant que la configuration par défaut est active),
et `scripts/ci/codeql_nouvelles_alertes.py` en tire les alertes neuves.
"""

from __future__ import annotations

from tests.aides_compose import RACINE, declencheurs, lire_yaml

WORKFLOW = RACINE / ".github" / "workflows" / "codeql-avant-dev.yml"
SCRIPT = "scripts/ci/codeql_nouvelles_alertes.py"


def _job() -> dict:
    return lire_yaml(WORKFLOW)["jobs"]["analyser"]


def test_declenche_par_la_pr_vers_dev_seulement():
    on = declencheurs(lire_yaml(WORKFLOW))
    #  Vers `main`, la configuration par défaut juge déjà : la doubler ne dirait rien de plus.
    assert on["pull_request"]["branches"] == ["dev"], on


def test_l_analyse_n_est_jamais_envoyee():
    """Un envoi serait refusé par GitHub, et ferait échouer le job à chaque PR."""
    etapes = _job()["steps"]
    analyses = [
        e for e in etapes if str(e.get("uses", "")).startswith("github/codeql-action/analyze@")
    ]
    assert len(analyses) == 1, "l'étape d'analyse a disparu ou est doublée"
    assert analyses[0]["with"]["upload"] == "never"
    assert analyses[0]["with"]["category"] == "/language:${{ matrix.langage }}"


def test_droits_en_lecture_seule_et_delai_borne():
    flux = lire_yaml(WORKFLOW)
    assert flux["permissions"] == {}
    job = flux["jobs"]["analyser"]
    assert job["permissions"] == {"contents": "read", "security-events": "read"}
    assert 0 < job["timeout-minutes"] <= 30


def test_les_langages_de_la_configuration_par_defaut():
    """Ceux que `code-scanning/default-setup` analyse sur `main` (relevé le 08/11/2026)."""
    assert _job()["strategy"]["matrix"]["langage"] == ["actions", "javascript-typescript", "python"]


def test_le_jugement_et_son_selftest_tournent():
    texte = WORKFLOW.read_text(encoding="utf-8")
    assert f"python3 -I {SCRIPT}" in texte
    ci = (RACINE / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert f"python {SCRIPT} --selftest" in ci
