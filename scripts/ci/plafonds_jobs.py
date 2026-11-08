#!/usr/bin/env python3
"""Le plafond de chaque job de CI, confronté à sa durée MESURÉE (#2576).

POURQUOI — un job qui atteint son `timeout-minutes` est ANNULÉ, et un check requis
annulé bloque une PR sans un mot. Le 06/11/2026, « Tests de navigateur (Playwright) »
a été coupé deux fois de suite à 25 min, tests verts : la suite avait grossi, le
plafond était resté. La MEP de v3.69.2 a manqué sa butée. Le plafond est passé à
40 min (v3.73.8) ; ce contrôle dit le prochain qui s'approche, AVANT la coupure.

CE QU'IL MESURE — les plafonds sont lus dans `.github/workflows/*.yml` ; les durées,
dans les dernières exécutions RÉUSSIES de chaque workflow, par l'API GitHub
(`GITHUB_TOKEN`, dépôt `GITHUB_REPOSITORY` ou le remote `origin`). La durée d'un job
est celle que GitHub confronte au plafond : de son départ sur le runner à sa fin (la
file d'attente n'y entre pas). Les variantes d'une matrice partagent un plafond et
se jugent ensemble.

LA MARGE DÉCLARÉE — un plafond doit valoir au moins `p95 × (1 + MARGE_RELATIVE)` et
`p95 + MARGE_MINIMALE_MIN` minutes. Mesure du 06/11 : la tentative coupée de #2574
dépassait de ~10 % le p95 des exécutions vertes ; 30 % couvre un runner lent sans
masquer une suite qui grossit. Un job sans `timeout-minutes` est refusé (la règle de
`ci.yml` : sans plafond, GitHub laisse pendre six heures).

CE QU'IL NE JUGE PAS — un job qui compte moins de `MIN_MESURES` exécutions réussies
(un workflow lancé à la main, un job neuf) est NOMMÉ « non mesuré », sans faire
échouer : son plafond reste celui que son auteur a écrit. Mais si AUCUN job n'est
mesuré, ou si l'API ne répond pas, le verdict est INCONNU — code 2 —, jamais OK
(`standards/04` §1) : une comparaison à rien dirait toujours oui.

Hors de la CI des PR : l'historique ne se lit que par l'API. Le contrôle tourne chaque
semaine (`.github/workflows/plafonds-jobs.yml`) et rend compte dans UNE issue —
ouverte au premier écart, commentée tant qu'il dure, fermée au retour au vert.

Usage : plafonds_jobs.py               le tableau et le verdict
        plafonds_jobs.py --rapport     idem, puis l'issue (gh, `GH_TOKEN`)
        plafonds_jobs.py --selftest
Codes : 0 toutes les marges tenues · 1 une marge franchie ou un job sans plafond · 2 INCONNU
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
WORKFLOWS = RACINE / ".github" / "workflows"
API = "https://api.github.com"

#: Le plafond doit valoir p95 × 1,30 et p95 + 3 min (voir l'en-tête).
MARGE_RELATIVE = 0.30
MARGE_MINIMALE_MIN = 3.0
#: En deçà, le p95 n'est pas une mesure : le job est nommé « non mesuré ».
MIN_MESURES = 5
#: Exécutions réussies lues par workflow — assez récentes pour suivre une suite qui grossit.
EXECUTIONS_PAR_WORKFLOW = 40

TITRE_ISSUE = "Plafonds des jobs de CI : marge franchie"
ETIQUETTE_ISSUE = "bug"

_EXPRESSION = re.compile(r"\$\{\{.*?\}\}")
_CLE_JOB = re.compile(r"^  ([A-Za-z0-9_-]+):\s*(#.*)?$")
_CHAMP_JOB = re.compile(r"^    (name|timeout-minutes):\s*(.*?)\s*(#.*)?$")


class Inconnu(Exception):
    """La mesure ne peut pas se faire : API injoignable, refus, réponse illisible."""


# ── Lecture des plafonds (pure : texte → déclarations) ──────────────────────────


def lire_jobs(texte: str, fichier: str) -> list[dict]:
    """Les jobs d'un workflow : clé, nom (modèle), plafond (minutes, ou None).

    Lecture à la FORME que tous les workflows du dépôt respectent (job à deux espaces
    sous `jobs:`, ses champs à quatre) : la CI des PR n'a pas PyYAML, et ce contrôle
    ne lit que deux champs.
    """
    jobs: list[dict] = []
    dans_jobs = False
    for ligne in texte.splitlines():
        if re.match(r"^jobs:\s*(#.*)?$", ligne):
            dans_jobs = True
            continue
        if not dans_jobs:
            continue
        if ligne and not ligne[0].isspace() and not ligne.startswith("#"):
            break  # clé de premier niveau suivante
        if m := _CLE_JOB.match(ligne):
            jobs.append({"fichier": fichier, "cle": m.group(1), "nom": None, "plafond": None})
        elif jobs and (m := _CHAMP_JOB.match(ligne)):
            valeur = m.group(2).strip().strip("\"'")
            if m.group(1) == "name":
                jobs[-1]["nom"] = valeur
            else:
                jobs[-1]["plafond"] = int(valeur) if valeur.isdigit() else None
    return jobs


def motif_du_nom(job: dict) -> re.Pattern:
    """Le nom que GitHub affiche, en motif : une expression `${{ … }}` vaut « .+ ».

    Sans `name:`, GitHub prend la clé — suivie des valeurs de la matrice entre
    parenthèses quand il y en a une.
    """
    if not job["nom"]:
        return re.compile(re.escape(job["cle"]) + r"( \(.+\))?")
    morceaux = _EXPRESSION.split(job["nom"])
    return re.compile(".+".join(re.escape(m) for m in morceaux))


def job_du_nom(nom: str, jobs: list[dict]) -> dict | None:
    """Le job déclaré qui porte ce nom. Un nom littéral prime sur un modèle :
    « Publier la version (release et archive) » n'est pas « Publier ${{ … }} »."""
    candidats = [j for j in jobs if motif_du_nom(j).fullmatch(nom)]
    exacts = [j for j in candidats if j["nom"] and not _EXPRESSION.search(j["nom"])]
    retenus = exacts or candidats
    return retenus[0] if len(retenus) == 1 else None


# ── Le verdict (pur) ────────────────────────────────────────────────────────────


def centile(valeurs: list[float], q: float) -> float:
    """Centile au rang le plus proche : une durée qui a réellement été observée."""
    tri = sorted(valeurs)
    return tri[max(0, math.ceil(q * len(tri)) - 1)]


def seuil(p95: float) -> float:
    return max(p95 * (1 + MARGE_RELATIVE), p95 + MARGE_MINIMALE_MIN)


def juger(plafond: int | None, durees_min: list[float]) -> dict:
    """État d'un job : `sans_plafond`, `non_mesure`, `marge` (franchie) ou `ok`."""
    v: dict = {"n": len(durees_min), "mediane": None, "p95": None, "seuil": None}
    if durees_min:
        v["mediane"] = centile(durees_min, 0.5)
        v["p95"] = centile(durees_min, 0.95)
        v["seuil"] = seuil(v["p95"])
    if plafond is None:
        v["etat"] = "sans_plafond"
    elif len(durees_min) < MIN_MESURES:
        v["etat"] = "non_mesure"
    else:
        v["etat"] = "marge" if plafond < v["seuil"] else "ok"
    return v


def code_global(etats: list[str]) -> int:
    """1 si un job est en défaut ; 2 si rien n'a pu être mesuré ; 0 sinon."""
    if any(e in ("marge", "sans_plafond") for e in etats):
        return 1
    if not any(e == "ok" for e in etats):
        return 2
    return 0


def geste_issue(issue_ouverte: int | None, code: int) -> str:
    """`creer`, `commenter`, `fermer` ou `rien` — jamais un rouge silencieux."""
    if code == 0:
        return "fermer" if issue_ouverte else "rien"
    return "commenter" if issue_ouverte else "creer"


# ── L'API (effets de bord) ──────────────────────────────────────────────────────


def _depot() -> str:
    if d := os.environ.get("GITHUB_REPOSITORY"):
        return d
    try:
        url = subprocess.run(
            ["git", "-C", str(RACINE), "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as e:
        raise Inconnu(f"dépôt introuvable (ni GITHUB_REPOSITORY ni origin) : {e}") from e
    m = re.search(r"github\.com[:/](.+?)(\.git)?$", url)
    if not m:
        raise Inconnu(f"remote origin hors GitHub : {url}")
    return m.group(1)


def _lire(chemin: str, jeton: str) -> dict | None:
    """Une réponse de l'API ; None pour un 404 (workflow jamais exécuté)."""
    requete = urllib.request.Request(
        API + chemin,
        headers={
            "Authorization": f"Bearer {jeton}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "coprofirst-plafonds-jobs",
        },
    )
    try:
        with urllib.request.urlopen(requete, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise Inconnu(f"API {chemin} : HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise Inconnu(f"API {chemin} : {e}") from e


def _minutes(job: dict) -> float | None:
    try:
        debut = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
        fin = datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError):
        return None
    return (fin - debut).total_seconds() / 60


def mesurer(jobs: list[dict], jeton: str) -> dict[tuple[str, str], list[float]]:
    """Durées (minutes) des jobs réussis, par (fichier, clé)."""
    depot = _depot()
    durees: dict[tuple[str, str], list[float]] = {(j["fichier"], j["cle"]): [] for j in jobs}
    for fichier in sorted({j["fichier"] for j in jobs}):
        du_fichier = [j for j in jobs if j["fichier"] == fichier]
        runs = _lire(
            f"/repos/{depot}/actions/workflows/{fichier}/runs"
            f"?status=success&per_page={EXECUTIONS_PAR_WORKFLOW}",
            jeton,
        )
        for run in (runs or {}).get("workflow_runs", []):
            reponse = _lire(f"/repos/{depot}/actions/runs/{run['id']}/jobs?per_page=100", jeton)
            for jr in (reponse or {}).get("jobs", []):
                if jr.get("conclusion") != "success":
                    continue
                job = job_du_nom(jr.get("name", ""), du_fichier)
                duree = _minutes(jr)
                if job and duree is not None:
                    durees[(fichier, job["cle"])].append(duree)
    return durees


# ── Rapport ─────────────────────────────────────────────────────────────────────

_LIBELLES = {
    "ok": "OK",
    "marge": "MARGE FRANCHIE",
    "sans_plafond": "SANS PLAFOND",
    "non_mesure": "non mesuré",
}


def _min(x: float | None) -> str:
    return "—" if x is None else f"{x:.1f}".replace(".", ",")


def tableau(lignes: list[tuple[dict, dict]]) -> str:
    sortie = [
        "| Workflow › job | Plafond | Mesures | Médiane | p95 | Plafond exigé | Verdict |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for job, v in lignes:
        plafond = "—" if job["plafond"] is None else str(job["plafond"])
        sortie.append(
            f"| `{job['fichier']}` › `{job['cle']}` | {plafond} | {v['n']} | "
            f"{_min(v['mediane'])} | {_min(v['p95'])} | {_min(v['seuil'])} | "
            f"{_LIBELLES[v['etat']]} |"
        )
    return "\n".join(sortie)


def _verdict_texte(code: int) -> str:
    return {
        0: "Toutes les marges sont tenues.",
        1: "Au moins un plafond est sous sa marge (ou absent) : le relever, avec la "
        "mesure en commentaire dans le workflow.",
        2: "INCONNU : aucune durée n'a pu être mesurée.",
    }[code]


def rapporter(code: int, corps: str) -> None:
    """Ouvre, commente ou ferme l'issue du contrôle (gh, `GH_TOKEN`)."""
    liste = subprocess.run(
        ["gh", "issue", "list", "--state", "open", "--search", f'in:title "{TITRE_ISSUE}"',
         "--json", "number,title"],
        capture_output=True, text=True, check=True,
    ).stdout
    ouvertes = [i["number"] for i in json.loads(liste or "[]") if i["title"] == TITRE_ISSUE]
    issue = ouvertes[0] if ouvertes else None
    geste = geste_issue(issue, code)
    if geste == "creer":
        subprocess.run(["gh", "issue", "create", "--title", TITRE_ISSUE,
                        "--label", ETIQUETTE_ISSUE, "--body", corps], check=True)
    elif geste == "commenter":
        subprocess.run(["gh", "issue", "comment", str(issue), "--body", corps], check=True)
    elif geste == "fermer":
        subprocess.run(["gh", "issue", "comment", str(issue), "--body",
                        corps + "\n\nToutes les marges sont revenues : fermée par le contrôle."],
                       check=True)
        subprocess.run(["gh", "issue", "close", str(issue), "--reason", "completed"], check=True)


def principal(rapport: bool) -> int:
    jobs = [
        j
        for f in sorted(WORKFLOWS.glob("*.yml"))
        for j in lire_jobs(f.read_text(encoding="utf-8"), f.name)
    ]
    jeton = os.environ.get("GITHUB_TOKEN", "")
    try:
        if not jobs:
            raise Inconnu(f"aucun job lu dans {WORKFLOWS}")
        if not jeton:
            raise Inconnu("GITHUB_TOKEN absent")
        durees = mesurer(jobs, jeton)
    except Inconnu as e:
        code, corps = 2, f"**INCONNU** — {e}"
    else:
        lignes = [(j, juger(j["plafond"], durees[(j["fichier"], j["cle"])])) for j in jobs]
        code = code_global([v["etat"] for _, v in lignes])
        facteur = f"{1 + MARGE_RELATIVE:.2f}".replace(".", ",")
        corps = (
            f"{_verdict_texte(code)}\n\nMarge déclarée : plafond ≥ p95 × "
            f"{facteur} et ≥ p95 + {MARGE_MINIMALE_MIN:g} min ; "
            f"{EXECUTIONS_PAR_WORKFLOW} dernières exécutions réussies par workflow, "
            f"{MIN_MESURES} mesures au moins. Durées en minutes.\n\n{tableau(lignes)}"
        )
    print(corps)
    if rapport:
        rapporter(code, corps + "\n\n— `scripts/ci/plafonds_jobs.py` (#2576)")
    return code


# ── Autotest ────────────────────────────────────────────────────────────────────


def _selftest() -> int:
    workflow = (
        "name: X\non:\n  push:\n    branches: [main]\njobs:\n"
        "  lint:\n    name: Lint Python (Ruff)\n    runs-on: ubuntu-latest\n"
        "    timeout-minutes: 15  # commentaire\n    steps:\n      - run: echo\n"
        "  e2e:\n    name: \"Tests de navigateur (Playwright)\"\n    timeout-minutes: 40\n"
        "  construire:\n    name: Construire ${{ matrix.service.nom }} (${{ matrix.plateforme }})\n"
        "    timeout-minutes: 30\n"
        "  publier:\n    name: Publier ${{ matrix.service }}\n    timeout-minutes: 10\n"
        "  publier-version:\n    name: Publier la version (release et archive)\n"
        "    timeout-minutes: 10\n"
        "  nu:\n    runs-on: ubuntu-latest\n"
        "  pendu:\n    name: Sans plafond\n"
        "env:\n  A: 1\n"
    )
    jobs = lire_jobs(workflow, "x.yml")
    cas: list[tuple[str, object, object]] = [
        ("sept jobs lus, rien après `env:`", [j["cle"] for j in jobs],
         ["lint", "e2e", "construire", "publier", "publier-version", "nu", "pendu"]),
        ("plafond lu malgré le commentaire", jobs[0]["plafond"], 15),
        ("guillemets retirés du nom", jobs[1]["nom"], "Tests de navigateur (Playwright)"),
        ("job sans plafond", jobs[6]["plafond"], None),
        ("matrice : variante reconnue",
         (job_du_nom("Construire api (linux/arm64)", jobs) or {}).get("cle"), "construire"),
        ("le nom littéral prime sur le modèle",
         (job_du_nom("Publier la version (release et archive)", jobs) or {}).get("cle"),
         "publier-version"),
        ("le modèle sert les autres", (job_du_nom("Publier front", jobs) or {}).get("cle"),
         "publier"),
        ("sans nom : la clé, matrice comprise",
         (job_du_nom("nu (3.11, x)", jobs) or {}).get("cle"), "nu"),
        ("nom inconnu : aucun job", job_du_nom("Autre chose", jobs), None),
        ("p95 au rang le plus proche", centile([float(i) for i in range(1, 21)], 0.95), 19.0),
        #  #2576 : p95 24,1 min — 25 min de plafond étaient sous la marge, 40 la tiennent.
        ("Playwright à 25 min : marge franchie", juger(25, [19.4] * 10 + [24.1])["etat"], "marge"),
        ("Playwright à 40 min : tenu", juger(40, [19.4] * 10 + [24.1])["etat"], "ok"),
        ("petit job : 3 min de marge au moins", juger(3, [0.5] * 10)["etat"], "marge"),
        ("trop peu de mesures : non mesuré", juger(10, [9.5] * 4)["etat"], "non_mesure"),
        ("sans plafond, même sans mesure", juger(None, [])["etat"], "sans_plafond"),
        ("code : une marge franchie", code_global(["ok", "marge", "non_mesure"]), 1),
        ("code : un job sans plafond", code_global(["ok", "sans_plafond"]), 1),
        ("code : tout tenu", code_global(["ok", "non_mesure"]), 0),
        ("cas zéro : rien de mesuré = INCONNU", code_global(["non_mesure"]), 2),
        ("cas zéro : aucun job = INCONNU", code_global([]), 2),
        ("issue : premier écart", geste_issue(None, 1), "creer"),
        ("issue : INCONNU se dit aussi", geste_issue(None, 2), "creer"),
        ("issue : l'écart dure", geste_issue(42, 1), "commenter"),
        ("issue : retour au vert", geste_issue(42, 0), "fermer"),
        ("issue : vert sans issue", geste_issue(None, 0), "rien"),
    ]
    #  Les workflows du dépôt eux-mêmes : chacun lu, chaque job avec son plafond.
    reels = [j for f in sorted(WORKFLOWS.glob("*.yml"))
             for j in lire_jobs(f.read_text(encoding="utf-8"), f.name)]
    cas.append(("les workflows du dépôt se lisent (cas zéro)", len(reels) >= 10, True))
    cas.append(("chaque job du dépôt porte un plafond",
                [f"{j['fichier']}:{j['cle']}" for j in reels if j["plafond"] is None], []))
    echecs = 0
    for nom, obtenu, attendu in cas:
        if obtenu != attendu:
            print(f"ÉCHEC {nom} : {obtenu!r} au lieu de {attendu!r}")
            echecs += 1
    print(f"selftest plafonds_jobs : {len(cas) - echecs}/{len(cas)} OK")
    return 1 if echecs else 0


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if arguments == ["--selftest"]:
        sys.exit(_selftest())
    if arguments not in ([], ["--rapport"]):
        print(__doc__.split("Usage :")[1].split("Codes")[0].strip(), file=sys.stderr)
        sys.exit(2)
    sys.exit(principal(rapport=arguments == ["--rapport"]))
