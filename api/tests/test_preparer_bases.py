"""Chaque base est préparée avant de servir, et l'échec de l'une ne bloque pas les autres (#2053).

`app/utils/preparer_bases` porte la décision que `start.sh` écrivait en shell —
attendre, sauter une base en avance, poser le schéma d'une base neuve, migrer — et
l'applique à chaque base d'une installation commune. Éprouvé sur son COMPORTEMENT :

- l'ordre des gestes, et ce qui n'est PAS fait (on ne migre jamais ce qu'on n'a pas lu) ;
- deux vraies bases du serveur des tests : une neuve reçoit son schéma et devient
  servable, une seconde passe ne la touche plus ;
- une installation commune : une base injoignable n'empêche pas l'autre d'être prête,
  sa ligne le dit sans URL ni mot de passe ; aucune prête → code 1 ;
- `start.sh` affecte le verdict avant de l'afficher (sous `set -e`, l'échec compte).
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from app import contexte
from app.utils import preparer_bases as module
from app.utils.revision_base import servable
from tests.aides_base import adresse_de_test

START = Path(__file__).resolve().parents[1] / "start.sh"
INJOIGNABLE = "postgresql+psycopg://personne:motdepassesecret@127.0.0.1:9/aucune?connect_timeout=1"


@pytest.fixture()
def gestes(monkeypatch):
    """Remplace les quatre gestes par des témoins qui notent leur appel."""
    journal: list[str] = []
    reponses = {"attendre": True, "revision": "connue", "schema": "existante"}

    def attendre(url, delai):
        journal.append("attendre")
        return reponses["attendre"]

    def revision(url):
        journal.append("revision")
        return reponses["revision"]

    def schema(url):
        journal.append("schema")
        return reponses["schema"]

    monkeypatch.setattr(module, "attendre", attendre)
    monkeypatch.setattr(module, "etat_revision", revision)
    monkeypatch.setattr(module, "poser_si_neuve", schema)
    monkeypatch.setattr(module, "_migrer", lambda url: journal.append("migrer"))
    return journal, reponses


def test_une_base_qui_a_ses_tables_est_attendue_puis_migree(gestes):
    journal, _ = gestes
    assert module.preparer_base("x") == "migree"
    assert journal == ["attendre", "revision", "schema", "migrer"]


def test_une_base_illisible_n_est_jamais_migree(gestes):
    journal, reponses = gestes
    reponses["attendre"] = False
    assert module.preparer_base("x") == "illisible"
    assert journal == ["attendre"]


def test_une_base_en_avance_n_est_ni_marquee_ni_migree(gestes):
    journal, reponses = gestes
    reponses["revision"] = "en_avance"
    assert module.preparer_base("x") == "en_avance"
    assert journal == ["attendre", "revision"]


def test_une_base_inconnue_est_migree_on_ne_devine_pas(gestes):
    journal, reponses = gestes
    reponses["revision"] = "inconnu"
    assert module.preparer_base("x") == "migree"
    assert journal[-1] == "migrer"


def test_une_base_illisible_au_moment_du_schema_n_est_pas_migree(gestes):
    journal, reponses = gestes
    reponses["schema"] = "inconnu"
    assert module.preparer_base("x") == "illisible"
    assert "migrer" not in journal


def test_une_base_neuve_recoit_son_schema_et_devient_servable():
    adresse, retirer = adresse_de_test()
    try:
        assert servable(adresse) is False  # cas zéro : une base vide ne se sert pas
        assert module.preparer_base(adresse, delai=5) == "posee"
        assert servable(adresse) is True
        assert module.preparer_base(adresse, delai=5) == "migree"
    finally:
        retirer()


def test_une_base_injoignable_ne_bloque_pas_l_autre(monkeypatch):
    monkeypatch.setattr(module, "DELAI_SECONDES", 1)
    adresse, retirer = adresse_de_test()
    base = contexte.de_la_configuration()
    bonne = replace(base, identifiant="bonne", url_base=adresse)
    mauvaise = replace(base, identifiant="mauvaise", url_base=INJOIGNABLE)
    lignes: list[str] = []
    try:
        #  La mauvaise D'ABORD : son échec ne doit pas arrêter la boucle.
        assert module.preparer_commune([mauvaise, bonne], ecrire=lignes.append) == 0
        assert servable(adresse) is True
    finally:
        retirer()
    assert lignes[0] == "copropriete mauvaise : illisible"
    assert lignes[1] == "copropriete bonne : posee"
    assert lignes[-1] == "1 base(s) prete(s) sur 2"
    assert "motdepassesecret" not in "\n".join(lignes)


def test_aucune_base_prete_rend_un(monkeypatch):
    monkeypatch.setattr(module, "DELAI_SECONDES", 0.5)
    base = replace(contexte.de_la_configuration(), url_base=INJOIGNABLE)
    assert module.preparer_commune([base], ecrire=lambda _ligne: None) == 1


def test_une_migration_qui_leve_est_isolee_et_ne_cite_pas_l_url(monkeypatch):
    def leve(url, delai):
        raise RuntimeError(f"connexion refusée à {url}")

    monkeypatch.setattr(module, "preparer_base", leve)
    lignes: list[str] = []
    base = replace(contexte.de_la_configuration(), identifiant="x", url_base=INJOIGNABLE)
    assert module.preparer_commune([base], ecrire=lignes.append) == 1
    assert lignes[0] == "copropriete x : echec (RuntimeError)"


def test_start_sh_affecte_le_verdict_avant_de_l_afficher():
    code = "\n".join(
        ligne
        for ligne in START.read_text(encoding="utf-8").splitlines()
        if not ligne.lstrip().startswith("#")
    )
    appel = "BASES=$(python -m app.utils.preparer_bases)"
    assert code.count(appel) == 1, "affecté, pas passé à echo : sous `set -e`, l'échec compte"
    assert code.index(appel) < code.index("exec uvicorn")
    #  Plus aucune migration écrite à côté : une seule décision.
    assert "alembic upgrade head" not in code


# ── La ligne de start.sh, exécutée telle quelle sous `set -e` (exigence de la MEP) ──


def _start_sh(environnement: dict, tmp_path) -> subprocess.CompletedProcess:
    """Exécute la ligne de `start.sh` qui prépare les bases, sous `set -e`, puis un
    témoin : il ne s'affiche que si le démarrage continue."""
    import os
    import shutil
    import sys

    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash introuvable")
    ligne = next(
        x for x in START.read_text(encoding="utf-8").splitlines() if x.startswith("BASES=$(")
    )
    script = tmp_path / "extrait.sh"
    python = sys.executable.replace("\\", "/")
    script.write_text(
        "set -e\n" + ligne.replace("python ", f'"{python}" ') + '\necho "$BASES"\necho SUITE\n',
        encoding="utf-8",
    )
    return subprocess.run(
        [bash, str(script)],
        cwd=str(START.parent),
        env={**os.environ, **environnement},
        capture_output=True,
        text=True,
        timeout=180,
    )


def _declaree(identifiant: str, code_postal: str, cle: str) -> dict:
    return {
        "identifiant": identifiant,
        "code_postal": code_postal,
        "nom": f"Essai {cle.title()}",
        "base": f"ESSAI_{cle}_BASE",
        "secret": f"ESSAI_{cle}_SECRET",
        "racine_fichiers": f"/app/uploads/{identifiant}",
        "expediteur": "contact@exemple.fr",
    }


def test_sous_set_e_une_base_declaree_illisible_ne_bloque_pas_le_demarrage(tmp_path):
    """Installation commune : la base injoignable dit son verdict, l'autre est
    préparée, et `start.sh` CONTINUE (le témoin s'affiche). La lisible est déclarée
    d'abord : la suivante n'attend que `DELAI_SUIVANTES`."""
    import json

    adresse, retirer = adresse_de_test()
    declaration = tmp_path / "coproprietes.json"
    declaration.write_text(
        json.dumps(
            {
                "coproprietes": [
                    _declaree("lisible", "75002", "DEUX"),
                    _declaree("illisible", "75001", "UN"),
                ]
            }
        ),
        encoding="utf-8",
    )
    try:
        fait = _start_sh(
            {
                "COPROPRIETES_FICHIER": str(declaration),
                "ORIGIN": "https://acces.example",
                "ESSAI_UN_BASE": INJOIGNABLE,
                "ESSAI_UN_SECRET": "u" * 40,
                "ESSAI_DEUX_BASE": adresse,
                "ESSAI_DEUX_SECRET": "d" * 40,
            },
            tmp_path,
        )
        assert servable(adresse) is True
    finally:
        retirer()
    assert fait.returncode == 0, fait.stderr[-2000:]
    assert "copropriete lisible : posee" in fait.stdout
    assert "copropriete illisible : illisible" in fait.stdout
    assert fait.stdout.rstrip().endswith("SUITE")
    assert "motdepassesecret" not in fait.stdout + fait.stderr


def test_la_base_illisible_d_une_installation_propre_arrete_comme_avant(monkeypatch):
    """Témoin : 5Hostachy (une base) rend toujours 1 sur une base illisible — `start.sh`
    s'arrête sous `set -e`, Docker relance, et aucune migration n'est tentée."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "coproprietes_fichier", "")
    monkeypatch.setattr(get_settings(), "database_url", INJOIGNABLE)
    monkeypatch.setattr(module, "DELAI_SECONDES", 0.5)
    monkeypatch.setattr(module, "_migrer", lambda url: pytest.fail("migration tentée"))
    assert module.main() == 1
