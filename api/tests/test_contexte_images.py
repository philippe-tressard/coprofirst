"""Les images se construisent dès la PR, depuis un contexte qui n'emporte que l'exécution (#2963).

Deux trous relevés à l'audit du 23/11/2026 :

- seule l'image de l'API était construite avant la fusion (`image-api.yml`) ; un
  Dockerfile du front, de Caddy ou du bridge cassé par une montée ne se voyait
  qu'après la fusion dans `main`, quand `images.yml` publie — puis le nœud se
  rabattait sur la construction de secours ;
- aucun `.dockerignore` : `COPY . .` emportait dans l'image de l'API sa suite de
  tests, et, construite depuis un dossier de travail (secours d'un nœud, poste),
  ses caches et un éventuel `api/.env`.

Ce que ce test tient :

- chaque Dockerfile que publie `images.yml` est construit par un workflow de PR qui
  se déclenche sur ce Dockerfile, son `.dockerignore` et son verrou ;
- le contexte ignoré de l'API garde la photo témoin (`scripts/verifier_heif.py` la
  décode pendant la construction) et écarte `.env`, les caches et les tests ; celui
  du front écarte `node_modules`, que `COPY . .` recopierait après `npm ci`.
"""

from __future__ import annotations

import re

import pytest

from tests.aides_compose import RACINE, lire_yaml

WORKFLOWS = RACINE / ".github" / "workflows"


def _matrice_publiee() -> list[dict]:
    jobs = lire_yaml(WORKFLOWS / "images.yml")["jobs"]
    services = jobs["construire"]["strategy"]["matrix"]["service"]
    assert len(services) >= 4, "matrice d'« Images » illisible : contrôle impossible"
    return services


def _workflows_de_pr() -> dict[str, tuple[list[str], str]]:
    """Nom → (chemins qui le déclenchent sur une PR, texte du workflow)."""
    trouves = {}
    for fichier in sorted(WORKFLOWS.glob("*.yml")):
        donnees = lire_yaml(fichier)
        declencheurs = donnees.get("on", donnees.get(True, {})) or {}
        pr = declencheurs.get("pull_request") if isinstance(declencheurs, dict) else None
        if isinstance(pr, dict) and pr.get("paths"):
            trouves[fichier.name] = (pr["paths"], fichier.read_text(encoding="utf-8"))
    return trouves


def _verrou(contexte: str) -> str | None:
    if contexte == ".":  # Caddy : construit depuis la racine, sans verrou de paquets
        return None
    for nom in ("package-lock.json", "requirements.txt"):
        if (RACINE / contexte / nom).is_file():
            return f"{contexte}/{nom}"
    return None


@pytest.mark.parametrize("service", _matrice_publiee(), ids=lambda s: s["nom"])
def test_chaque_image_publiee_est_construite_des_la_pr(service):
    fichier = service["fichier"]
    construit = re.compile(rf"(?:file|fichier):\s*{re.escape(fichier)}\b")
    porteurs = [
        nom
        for nom, (chemins, texte) in _workflows_de_pr().items()
        if fichier in chemins and construit.search(texte)
    ]
    assert porteurs, f"{fichier} n'est construit par aucun workflow de PR qui le suit"
    chemins = _workflows_de_pr()[porteurs[0]][0]
    verrou = _verrou(service["contexte"])
    if verrou:
        assert verrou in chemins, f"{porteurs[0]} ne suit pas le verrou {verrou}"
    contexte = service["contexte"]
    ignore_ = ".dockerignore" if contexte == "." else f"{contexte}/.dockerignore"
    if (RACINE / ignore_).is_file():
        assert ignore_ in chemins, f"{porteurs[0]} ne suit pas {ignore_}"


# ── Le contexte ignoré, évalué comme Docker l'évalue ─────────────────────────


def _motif(motif: str) -> re.Pattern:
    """Un motif de `.dockerignore` (syntaxe de `filepath.Match`, plus `**`)."""
    sortie, i = "", 0
    while i < len(motif):
        if motif.startswith("**", i):
            sortie, i = sortie + ".*", i + 2
            if motif.startswith("/", i):
                sortie, i = sortie + "/?", i + 1
        elif motif[i] == "*":
            sortie, i = sortie + "[^/]*", i + 1
        elif motif[i] == "?":
            sortie, i = sortie + "[^/]", i + 1
        else:
            sortie, i = sortie + re.escape(motif[i]), i + 1
    return re.compile(sortie + r"\Z")


def ignore(dockerignore, chemin: str) -> bool:
    """Le chemin (relatif au contexte) est-il écarté ? La DERNIÈRE règle qui le vise
    — lui ou l'un de ses dossiers parents — décide ; `!` la renverse."""
    regles = []
    for ligne in dockerignore.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#"):
            exception = ligne.startswith("!")
            regles.append((exception, _motif(ligne.lstrip("!").strip("/"))))
    parties = chemin.split("/")
    prefixes = ["/".join(parties[: i + 1]) for i in range(len(parties))]
    ecarte = False
    for exception, motif in regles:
        if any(motif.match(p) for p in prefixes):
            ecarte = not exception
    return ecarte


@pytest.mark.parametrize(
    ("contexte", "chemin", "ecarte"),
    [
        ("api", "tests/donnees/photo.heic", False),
        ("api", "app/main.py", False),
        ("api", "scripts/verifier_heif.py", False),
        ("api", "requirements.txt", False),
        ("api", ".env", True),
        ("api", ".env.local", True),
        ("api", "tests/test_horloge.py", True),
        ("api", "tests/donnees/autre.txt", True),
        ("api", "app/__pycache__/main.cpython-312.pyc", True),
        ("api", ".venv/bin/python", True),
        ("front", "src/app.html", False),
        ("front", "package-lock.json", False),
        ("front", "node_modules/svelte/package.json", True),
        ("front", ".env", True),
        ("front", ".svelte-kit/output/x.js", True),
    ],
)
def test_le_contexte_n_emporte_que_l_execution(contexte, chemin, ecarte):
    dockerignore = RACINE / contexte / ".dockerignore"
    assert dockerignore.is_file(), f"{contexte}/.dockerignore absent"
    assert ignore(dockerignore, chemin) is ecarte, chemin


def test_la_photo_temoin_entre_dans_l_image():
    """Ce que l'ancienne assertion « pas de `.dockerignore` » voulait dire (#2389)."""
    assert (RACINE / "api" / "tests" / "donnees" / "photo.heic").is_file()
    assert not ignore(RACINE / "api" / ".dockerignore", "tests/donnees/photo.heic")
