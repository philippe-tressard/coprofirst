#!/usr/bin/env python3
"""Un arbre déjà jugé vert ne se rejoue pas (#2632, 11/11/2026).

POURQUOI — le même arbre était jugé trois fois par GitHub : sur la PR du lot vers
`dev`, sur la PR `dev → main` (le squash dans `dev` donne l'arbre que la PR du lot a
testé, quand `dev` n'a pas bougé entre-temps), puis sur le `push` de `main`. Chaque
fois ~20 min. Le rejeu du poste applique déjà « même arbre = trace valable » (#2245) ;
la CI, non.

CE QUE FAIT LE SCRIPT — chaque job requis de `ci.yml` dépose, à son succès, un
ARTEFACT nommé `arbre-vert-<job>-<arbre>` (l'arbre : `HEAD^{tree}` du commit jugé —
le commit de fusion d'une PR). Au départ de la CI, le job `arbre` cherche ces marques
par l'API et dit, job par job, si l'arbre est déjà vert ; le job concerné est alors
SAUTÉ, ce que GitHub compte comme un succès du check requis. Le résumé de l'exécution
nomme l'exécution qui l'avait jugé.

POURQUOI DES ARTEFACTS, ET PAS LE CACHE D'ACTIONS — le cache est cloisonné par
branche : une PR ne lit que le sien, celui de sa base et celui de la branche par
défaut. La PR `dev → main` ne verrait jamais la marque posée par la PR du lot. Les
artefacts se listent pour tout le dépôt.

CE QUI NE VAUT PAS MARQUE — jamais un vert par absence de mesure (`standards/04` §1) :
- une marque d'un AUTRE arbre (le nom l'exclut : arbre modifié, marque inutile) ;
- une marque expirée ;
- une marque posée par une exécution d'un AUTRE dépôt (une PR d'une fourche joue le
  `ci.yml` de la fourche, qui pourrait déposer n'importe quel nom) : seules comptent
  celles dont le dépôt de tête est ce dépôt-ci ;
- une API muette ou illisible : le job JOUE, et le script le dit.

Ne s'applique ni à CodeQL ni à la suite PostgreSQL (autres workflows, `dev → main`).

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
_ARBRE = re.compile(r"^[0-9a-f]{40}$")
_JOB = re.compile(r"^[a-z0-9-]+$")


def nom_de_marque(job: str, arbre: str) -> str:
    """Le nom de l'artefact qui dit « ce job a jugé cet arbre vert »."""
    return f"{PREFIXE}-{job}-{arbre}"


def marque_valable(artefacts: list[dict], job: str, arbre: str, depot_id: int) -> int | None:
    """L'exécution qui a jugé `arbre` vert pour `job`, ou None. PURE.

    `artefacts` : la liste `artifacts` de l'API, filtrée ou non par nom.
    """
    if not _ARBRE.match(arbre) or not _JOB.match(job):
        return None
    attendu = nom_de_marque(job, arbre)
    for a in artefacts:
        execution = a.get("workflow_run") or {}
        if (
            a.get("name") == attendu
            and a.get("expired") is False
            and execution.get("head_repository_id") == depot_id
            and isinstance(execution.get("id"), int)
        ):
            return execution["id"]
    return None


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


def chercher() -> int:
    env = os.environ
    if env.get("GITHUB_ACTIONS") != "true":
        print("· Hors d'Actions : aucune marque à chercher, chaque job joue (le rejeu du poste).")
        return 0
    arbre = env.get("ARBRE", "")
    jobs = env.get("JOBS", "").split()
    sorties, resume = [f"arbre={arbre}"], ["| Job | Verdict |", "|---|---|"]
    try:
        depot_id = int(env["GITHUB_REPOSITORY_ID"])
        depot, jeton = env["GITHUB_REPOSITORY"], env["GITHUB_TOKEN"]
    except (KeyError, ValueError) as e:
        depot_id, depot, jeton = None, "", ""
        print(f"? Contexte illisible ({e}) : chaque job joue.")
    for job in jobs:
        execution = None
        if depot_id is not None and _ARBRE.match(arbre):
            try:
                reponse = _lire(
                    f"/repos/{depot}/actions/artifacts?name={nom_de_marque(job, arbre)}&per_page=10",
                    jeton,
                )
                execution = marque_valable(reponse.get("artifacts", []), job, arbre, depot_id)
            except (urllib.error.URLError, OSError, ValueError) as e:
                print(f"? {job} : marques illisibles ({e}) — il joue.")
        if execution:
            lien = f"https://github.com/{depot}/actions/runs/{execution}"
            texte = f"arbre déjà jugé vert par l'exécution {execution} — sauté"
            resume.append(
                f"| `{job}` | ✓ {texte.replace(str(execution), f'[{execution}]({lien})')} |"
            )
        else:
            texte = "aucune marque valable — il joue"
            resume.append(f"| `{job}` | {texte} |")
        print(f"{job} : {texte}")
        sorties.append(f"{job}={'oui' if execution else 'non'}")
    with open(env["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write("\n".join(sorties) + "\n")
    if env.get("GITHUB_STEP_SUMMARY"):
        with open(env["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"### Arbre `{arbre[:12]}`\n\n" + "\n".join(resume) + "\n")
    return 0


def _selftest() -> int:
    a, b, depot = "a" * 40, "b" * 40, 42
    bonne = {
        "name": nom_de_marque("lint-backend", a),
        "expired": False,
        "workflow_run": {"id": 7, "head_repository_id": depot},
    }
    cas = [
        ("la marque du même arbre sert", marque_valable([bonne], "lint-backend", a, depot), 7),
        # 🔒 Le cas que le ticket exige : arbre modifié → la marque ne sert pas.
        (
            "arbre modifié : la marque ne sert pas",
            marque_valable([bonne], "lint-backend", b, depot),
            None,
        ),
        (
            "autre job : la marque ne sert pas",
            marque_valable([bonne], "build-frontend", a, depot),
            None,
        ),
        (
            "marque expirée",
            marque_valable([{**bonne, "expired": True}], "lint-backend", a, depot),
            None,
        ),
        (
            "expiration absente : refusée",
            marque_valable(
                [{k: v for k, v in bonne.items() if k != "expired"}], "lint-backend", a, depot
            ),
            None,
        ),
        (
            "posée par une fourche",
            marque_valable(
                [{**bonne, "workflow_run": {"id": 7, "head_repository_id": 99}}],
                "lint-backend",
                a,
                depot,
            ),
            None,
        ),
        (
            "exécution sans identifiant",
            marque_valable(
                [{**bonne, "workflow_run": {"head_repository_id": depot}}], "lint-backend", a, depot
            ),
            None,
        ),
        ("cas zéro : aucune marque", marque_valable([], "lint-backend", a, depot), None),
        (
            "arbre illisible : jamais vert",
            marque_valable(
                [{**bonne, "name": nom_de_marque("lint-backend", "")}], "lint-backend", "", depot
            ),
            None,
        ),
        ("nom de job hors forme", marque_valable([bonne], "lint backend", a, depot), None),
        (
            "la bonne parmi d'autres",
            marque_valable(
                [
                    {**bonne, "expired": True},
                    {**bonne, "workflow_run": {"id": 9, "head_repository_id": depot}},
                ],
                "lint-backend",
                a,
                depot,
            ),
            9,
        ),
    ]
    echecs = [f"ÉCHEC {n} : {o!r} au lieu de {x!r}" for n, o, x in cas if o != x]
    print("\n".join(echecs) or "", end="\n" if echecs else "")
    print(f"selftest arbre_deja_vert : {len(cas) - len(echecs)}/{len(cas)} OK")
    return 1 if echecs else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(_selftest())
    if sys.argv[1:] == ["chercher"]:
        sys.exit(chercher())
    print(__doc__.split("Usage :")[1].strip(), file=sys.stderr)
    sys.exit(2)
