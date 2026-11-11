#!/usr/bin/env python3
"""Un arbre déjà jugé vert ne se rejoue pas (#2632, 11/11/2026).

POURQUOI — le même arbre était jugé trois fois par GitHub : sur la PR du lot vers
`dev`, sur la PR `dev → main` (le squash dans `dev` donne l'arbre que la PR du lot a
jugé, quand `dev` n'a pas bougé entre-temps), puis sur le `push` de `main`. Chaque
fois ~20 min. Le rejeu du poste applique déjà « même arbre = trace valable » (#2245) ;
la CI, non.

🔴 UN CHECK REQUIS QUI CONCLUT « SUCCÈS » SANS JOUER EST UNE PORTE DE LA PROTECTION DE
`main`. D'où la règle : rien de ce qu'une exécution DÉPOSE ne fait foi. Chaque job
requis de `ci.yml` dépose bien, à son succès, un artefact `arbre-vert-<job>-<arbre>` —
mais ce n'est qu'un INDEX, qui dit quelle exécution relire. La preuve vient de
l'exécution elle-même, relue par l'API ; un job n'est sauté que si TOUT ceci tient :

1. l'exécution est celle du MÊME fichier de workflow (`.github/workflows/ci.yml`), sur
   CE dépôt, et sa tête aussi (une PR d'une fourche joue le `ci.yml` de la fourche) ;
2. le job correspondant y a conclu `success` — réellement joué : un job SAUTÉ ne
   compte pas, une tranche de Playwright non plus, et « Tests Python » exige que son
   étape pytest ait tourné (elle ne tourne que vers `dev`) ;
3. l'arbre du commit de cette exécution, RECALCULÉ par l'API git (jamais lu dans
   l'artefact), est égal à `HEAD^{tree}` ;
4. pour une exécution de PR — qui a jugé le commit de FUSION, pas sa tête —, la base
   D'ALORS est un ancêtre de la tête : la fusion avait alors l'arbre de la tête. La
   base d'alors se lit dans le journal des mouvements de la branche (API `activity`),
   jamais dans `pull_requests[].base.sha` de l'exécution, qui donne la base ACTUELLE
   (constaté le 11/11 : trois exécutions d'avant la réécriture de `dev` y montraient
   toutes la pointe d'après). La fusion jugée (`GITHUB_SHA`) est fixée à l'ÉVÉNEMENT,
   qui précède la création de l'exécution : toute pointe de la base dans les
   `MARGE_BASE_S` secondes qui la précèdent doit être un ancêtre de la tête ; un
   mouvement postérieur ne la change plus (11/11 : `dev` a bougé 73 s après, et une
   marge symétrique refusait une preuve juste).

Dans le doute — API muette, exécution introuvable, arbre différent, champ absent —, le
job JOUE, et le script dit pourquoi. Jamais un vert par absence de mesure
(`standards/04` §1).

POURQUOI DES ARTEFACTS COMME INDEX, ET PAS LE CACHE D'ACTIONS — le cache est cloisonné
par branche : la PR `dev → main` ne verrait jamais celui de la PR du lot. Les
artefacts se listent pour tout le dépôt.

HORS DE PORTÉE, par construction : seuls les jobs de `ci.yml` passent par ce juge. La
suite PostgreSQL (`postgresql.yml`) et CodeQL (`codeql-avant-dev.yml`) n'en dépendent
pas et jouent toujours.

Usage : arbre_deja_vert.py chercher   (dans Actions : GITHUB_TOKEN, GITHUB_REPOSITORY,
                                       GITHUB_REPOSITORY_ID, ARBRE, JOBS, GITHUB_OUTPUT)
        arbre_deja_vert.py --selftest
Hors d'Actions (le rejeu du poste), `chercher` le dit et ne cherche rien.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
PREFIXE = "arbre-vert"
WORKFLOW = ".github/workflows/ci.yml"
EVENEMENTS = ("pull_request", "push", "workflow_dispatch")
#: Combien d'exécutions indexées relire au plus, par job.
CANDIDATS_MAX = 5
_SHA = re.compile(r"^[0-9a-f]{40}$")
#: La fusion d'une PR est fixée à l'événement, juste AVANT la création de l'exécution :
#: toute pointe de la base dans cette marge (secondes) doit être un ancêtre de la tête.
MARGE_BASE_S = 120

#: Le nom, dans l'exécution, de chaque job requis — confronté à `ci.yml` par
#: `test_ci_arbre_deja_vert.py`. `tranches` : le préfixe des variantes d'une matrice,
#: qui doivent TOUTES avoir réussi ; `etape` : l'étape qui doit avoir tourné.
JOBS_REQUIS: dict[str, dict[str, str]] = {
    "lint-backend": {"nom": "Lint Python (Ruff)"},
    "test-backend": {"nom": "Tests Python (pytest)", "etape": "Run pytest"},
    "test-scripts": {"nom": "Scripts d'infra (syntaxe + self-tests)"},
    "build-frontend": {"nom": "Build SvelteKit"},
    "e2e-frontend": {
        "nom": "Tests de navigateur (Playwright)",
        "tranches": "Tests de navigateur — ",
    },
}


def nom_de_marque(job: str, arbre: str) -> str:
    """Le nom de l'artefact qui INDEXE l'exécution ayant jugé `arbre` pour `job`."""
    return f"{PREFIXE}-{job}-{arbre}"


def _reussi(jobs: list[dict], nom: str, etape: str | None) -> str | None:
    trouves = [j for j in jobs if j.get("name") == nom]
    if len(trouves) != 1:
        return f"job « {nom} » trouvé {len(trouves)} fois"
    if trouves[0].get("conclusion") != "success":
        return f"« {nom} » a conclu {trouves[0].get('conclusion')!r}, pas success"
    if etape:
        etapes = [e for e in trouves[0].get("steps") or [] if e.get("name") == etape]
        if len(etapes) != 1 or etapes[0].get("conclusion") != "success":
            return f"l'étape « {etape} » n'a pas tourné avec succès"
    return None


def _secondes(horodatage: str) -> float | None:
    from datetime import datetime

    try:
        return datetime.fromisoformat(horodatage.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def bases_du_moment(activites: list[dict], instant: str, marge_s: int = MARGE_BASE_S):
    """Les pointes qu'a pu avoir la base pour une fusion fixée juste avant `instant`,
    ou None si on ne peut pas le dire. PURE. `activites` : le journal `activity`.

    La pointe d'avant la marge, puis chaque pointe posée dedans, jusqu'à `instant`
    compris ; ce qui suit ne change plus la fusion. Une branche
    supprimée dans la marge, un journal qui ne remonte pas jusqu'avant elle, un
    horodatage illisible : None — l'ancestralité n'est pas établie.
    """
    t = _secondes(instant)
    if t is None:
        return None
    datees = []
    for a in activites:
        s = _secondes(a.get("timestamp", ""))
        if s is None:
            return None
        datees.append((s, a.get("after", "")))
    datees.sort()
    avant = [apres for s, apres in datees if s <= t - marge_s]
    if not avant:
        return None
    pointes = [avant[-1]] + [apres for s, apres in datees if t - marge_s < s <= t]
    if any(not _SHA.match(x or "") or set(x) == {"0"} for x in pointes):
        return None
    return list(dict.fromkeys(pointes))


def juger(
    job: str,
    execution: dict,
    jobs: list[dict],
    arbre_execution: str | None,
    base_ancetre: bool | None,
    arbre: str,
    depot_id: int,
) -> str | None:
    """Le motif pour lequel `execution` NE prouve PAS que `arbre` est vert pour `job`,
    ou None si elle le prouve. PURE : tout ce qu'elle lit lui est passé.

    `arbre_execution` : l'arbre du commit de tête, recalculé par l'API git.
    `base_ancetre` : pour une PR, la base enregistrée est-elle un ancêtre de la tête.
    """
    regle = JOBS_REQUIS.get(job)
    if regle is None:
        return f"job {job!r} inconnu du juge"
    if not _SHA.match(arbre or ""):
        return "arbre courant illisible"
    if execution.get("path") != WORKFLOW:
        return f"autre workflow ({execution.get('path')!r})"
    if (execution.get("repository") or {}).get("id") != depot_id:
        return "exécution d'un autre dépôt"
    if (execution.get("head_repository") or {}).get("id") != depot_id:
        return "tête venue d'un autre dépôt (fourche)"
    if execution.get("event") not in EVENEMENTS:
        return f"événement {execution.get('event')!r} non retenu"
    if execution.get("event") == "pull_request" and base_ancetre is not True:
        return (
            "PR dont la base n'est pas un ancêtre de la tête : la fusion jugée avait un autre arbre"
        )
    if arbre_execution != arbre:
        return f"arbre différent ({(arbre_execution or 'illisible')[:12]})"
    motif = _reussi(jobs, regle["nom"], regle.get("etape"))
    if motif:
        return motif
    if "tranches" in regle:
        tranches = [j for j in jobs if (j.get("name") or "").startswith(regle["tranches"])]
        if not tranches:
            return "aucune tranche dans l'exécution"
        rouges = [j["name"] for j in tranches if j.get("conclusion") != "success"]
        if rouges:
            return f"tranche(s) non jouée(s) ou non verte(s) : {', '.join(rouges)}"
    return None


# ── Entrées et sorties ──────────────────────────────────────────────────────────


def _lire(chemin: str, jeton: str) -> dict:
    requete = urllib.request.Request(
        f"{API}{chemin}",
        headers={
            "Authorization": f"Bearer {jeton}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(requete, timeout=20) as r:
        return json.load(r)


def _toutes_les_pages(chemin: str, cle: str, jeton: str) -> list[dict]:
    elements: list[dict] = []
    for page in range(1, 6):
        lot = _lire(f"{chemin}&page={page}", jeton).get(cle, [])
        elements += lot
        if len(lot) < 100:
            return elements
    raise ValueError(f"{chemin} : plus de 500 éléments")


def _arbre_du_commit(depot: str, sha: str, jeton: str) -> str | None:
    if not _SHA.match(sha or ""):
        return None
    return (_lire(f"/repos/{depot}/git/commits/{sha}", jeton).get("tree") or {}).get("sha")


def _base_ancetre(depot: str, execution: dict, jeton: str) -> bool | None:
    prs = execution.get("pull_requests") or []
    if len(prs) != 1:
        return None
    #  La BRANCHE de base seulement : sa pointe d'alors se lit dans son journal.
    ref, tete = (prs[0].get("base") or {}).get("ref"), execution.get("head_sha")
    if not ref or not _SHA.match(tete or ""):
        return None
    activites: list[dict] = []
    limite = (_secondes(execution.get("created_at", "")) or 0) - MARGE_BASE_S
    for page in range(1, 6):
        lot = _lire(f"/repos/{depot}/activity?ref=refs/heads/{ref}&per_page=100&page={page}", jeton)
        activites += lot
        if len(lot) < 100 or any((_secondes(a.get("timestamp", "")) or 0) <= limite for a in lot):
            break
    pointes = bases_du_moment(activites, execution.get("created_at", ""))
    if not pointes:
        return None
    for base in pointes:
        statut = _lire(f"/repos/{depot}/compare/{base}...{tete}", jeton).get("status")
        if statut not in ("ahead", "identical"):
            return False
    return True


def prouver(job: str, arbre: str, depot: str, depot_id: int, jeton: str) -> tuple[int | None, str]:
    """(exécution qui prouve, ou None ; ce qui a été constaté)."""
    index = _lire(f"/repos/{depot}/actions/artifacts?name={nom_de_marque(job, arbre)}", jeton)
    candidats: list[int] = []
    for a in index.get("artifacts", []):
        identifiant = (a.get("workflow_run") or {}).get("id")
        if isinstance(identifiant, int) and identifiant not in candidats:
            candidats.append(identifiant)
    if not candidats:
        return None, "aucune exécution indexée pour cet arbre"
    motifs = []
    for identifiant in candidats[:CANDIDATS_MAX]:
        execution = _lire(f"/repos/{depot}/actions/runs/{identifiant}", jeton)
        jobs = _toutes_les_pages(
            f"/repos/{depot}/actions/runs/{identifiant}/jobs?per_page=100", "jobs", jeton
        )
        base = (
            _base_ancetre(depot, execution, jeton)
            if execution.get("event") == "pull_request"
            else None
        )
        arbre_exe = _arbre_du_commit(depot, execution.get("head_sha", ""), jeton)
        motif = juger(job, execution, jobs, arbre_exe, base, arbre, depot_id)
        if motif is None:
            return identifiant, f"arbre déjà jugé vert par l'exécution {identifiant}"
        motifs.append(f"{identifiant} : {motif}")
    return None, "aucune preuve — " + " ; ".join(motifs)


def chercher() -> int:
    env = os.environ
    if env.get("GITHUB_ACTIONS") != "true":
        print("· Hors d'Actions : aucune exécution à relire, chaque job joue (le rejeu du poste).")
        return 0
    arbre = env.get("ARBRE", "")
    sorties, resume = [f"arbre={arbre}"], ["| Job | Verdict |", "|---|---|"]
    try:
        depot_id = int(env["GITHUB_REPOSITORY_ID"])
        depot, jeton = env["GITHUB_REPOSITORY"], env["GITHUB_TOKEN"]
    except (KeyError, ValueError) as e:
        depot_id, depot, jeton = None, "", ""
        print(f"? Contexte illisible ({e}) : chaque job joue.")
    for job in env.get("JOBS", "").split():
        execution, constat = None, "contexte illisible"
        if depot_id is not None:
            try:
                execution, constat = prouver(job, arbre, depot, depot_id, jeton)
            except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as e:
                constat = f"API illisible ({e})"
        verdict = "✓ sauté" if execution else "joue"
        print(f"{job} : {verdict} — {constat}")
        if execution:
            lien = f"https://github.com/{depot}/actions/runs/{execution}"
            constat = constat.replace(str(execution), f"[{execution}]({lien})")
        resume.append(f"| `{job}` | {verdict} — {constat} |")
        sorties.append(f"{job}={'oui' if execution else 'non'}")
    with open(env["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write("\n".join(sorties) + "\n")
    if env.get("GITHUB_STEP_SUMMARY"):
        with open(env["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"### Arbre `{arbre[:12]}`\n\n" + "\n".join(resume) + "\n")
    return 0


# ── Autotest ────────────────────────────────────────────────────────────────────


def _selftest() -> int:
    a, b, depot = "a" * 40, "b" * 40, 42
    exe = {
        "path": WORKFLOW,
        "event": "push",
        "head_sha": "c" * 40,
        "repository": {"id": depot},
        "head_repository": {"id": depot},
    }
    pr = {**exe, "event": "pull_request"}
    ok = {"conclusion": "success"}
    jobs = [
        {**ok, "name": "Lint Python (Ruff)"},
        {**ok, "name": "Tests Python (pytest)", "steps": [{**ok, "name": "Run pytest"}]},
        {**ok, "name": "Tests de navigateur (Playwright)"},
        {**ok, "name": "Tests de navigateur — Chromium 1/4"},
        {**ok, "name": "Tests de navigateur — WebKit, mise en page"},
    ]

    def refus(job, execution=exe, liste=jobs, arbre_exe=a, base=None, arbre=a):
        return juger(job, execution, liste, arbre_exe, base, arbre, depot)

    sans_pytest = [
        {**x, "steps": [{"name": "Run pytest", "conclusion": "skipped"}]}
        if x["name"] == "Tests Python (pytest)"
        else x
        for x in jobs
    ]
    tranche_sautee = jobs[:4] + [{**jobs[4], "conclusion": "skipped"}]
    sans_tete = {k: v for k, v in exe.items() if k != "head_repository"}
    prouve = [
        ("push du même arbre, job vert", refus("lint-backend")),
        ("PR à base ancêtre de la tête", refus("lint-backend", pr, base=True)),
        ("Playwright : agrégat et toutes les tranches verts", refus("e2e-frontend")),
        ("pytest réellement joué", refus("test-backend")),
    ]
    # 🔒 Les cas fautifs exigés par la coordination (11/11/2026). Un artefact FORGÉ ne
    # pèse rien : il ne fait que désigner une exécution, que l'on relit entière.
    refuse = [
        ("artefact forgé vers une exécution d'un autre arbre", refus("lint-backend", arbre_exe=b)),
        ("arbre courant modifié : la marque ne sert pas", refus("lint-backend", arbre=b)),
        ("arbre de l'exécution illisible", refus("lint-backend", arbre_exe=None)),
        (
            "autre fichier de workflow",
            refus("lint-backend", {**exe, "path": ".github/workflows/autre.yml"}),
        ),
        ("exécution d'un autre dépôt", refus("lint-backend", {**exe, "repository": {"id": 99}})),
        ("tête venue d'une fourche", refus("lint-backend", {**exe, "head_repository": {"id": 99}})),
        ("champ du dépôt de tête absent", refus("lint-backend", sans_tete)),
        ("événement non retenu (schedule)", refus("lint-backend", {**exe, "event": "schedule"})),
        (
            "PR à base non ancêtre : la fusion jugée avait un autre arbre",
            refus("lint-backend", pr, base=False),
        ),
        ("PR, ancestralité inconnue", refus("lint-backend", pr, base=None)),
        ("job rouge", refus("lint-backend", liste=[{**jobs[0], "conclusion": "failure"}])),
        (
            "job SAUTÉ : aucune chaîne de sauts",
            refus("lint-backend", liste=[{**jobs[0], "conclusion": "skipped"}]),
        ),
        ("job absent de l'exécution", refus("build-frontend")),
        ("job en double", refus("lint-backend", liste=jobs + [jobs[0]])),
        ("pytest non joué (exécution vers main)", refus("test-backend", liste=sans_pytest)),
        ("une tranche sautée", refus("e2e-frontend", liste=tranche_sautee)),
        ("agrégat vert sans tranche", refus("e2e-frontend", liste=jobs[:3])),
        ("job inconnu du juge (CodeQL)", refus("codeql")),
        ("arbre courant illisible", refus("lint-backend", arbre="", arbre_exe="")),
    ]
    journal = [
        {"timestamp": "2026-11-11T09:00:00Z", "after": "1" * 40},
        {"timestamp": "2026-11-11T09:27:08Z", "after": "2" * 40},
        {"timestamp": "2026-11-11T09:47:01Z", "after": "0" * 40},
        {"timestamp": "2026-11-11T09:47:06Z", "after": "3" * 40},
    ]
    bases = [
        (
            "la pointe d'alors, pas l'actuelle",
            bases_du_moment(journal, "2026-11-11T09:32:20Z"),
            ["2" * 40],
        ),
        (
            "une pointe posée dans la marge compte aussi",
            bases_du_moment(journal, "2026-11-11T09:28:00Z"),
            ["1" * 40, "2" * 40],
        ),
        (
            "branche supprimée dans la marge : inconnu",
            bases_du_moment(journal, "2026-11-11T09:47:03Z"),
            None,
        ),
        (
            "un mouvement APRÈS la création ne change plus la fusion",
            bases_du_moment(journal, "2026-11-11T09:26:00Z"),
            ["1" * 40],
        ),
        ("journal trop court : inconnu", bases_du_moment(journal, "2026-11-11T08:00:00Z"), None),
        ("instant illisible : inconnu", bases_du_moment(journal, ""), None),
        (
            "horodatage illisible : inconnu",
            bases_du_moment(
                journal + [{"timestamp": "x", "after": "4" * 40}], "2026-11-11T09:32:20Z"
            ),
            None,
        ),
    ]
    echecs = [f"ÉCHEC base — {n} : {o!r}" for n, o, x in bases if o != x]
    echecs += [f"ÉCHEC prouvé attendu — {n} : {m}" for n, m in prouve if m is not None]
    echecs += [f"ÉCHEC refus attendu — {n}" for n, m in refuse if m is None]
    for e in echecs:
        print(e)
    total = len(bases) + len(prouve) + len(refuse)
    print(f"selftest arbre_deja_vert : {total - len(echecs)}/{total} OK")
    return 1 if echecs else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(_selftest())
    if sys.argv[1:] == ["chercher"]:
        sys.exit(chercher())
    print(__doc__.split("Usage :")[1].strip(), file=sys.stderr)
    sys.exit(2)
