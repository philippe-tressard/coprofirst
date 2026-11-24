#!/usr/bin/env python3
"""Un rouge de `main` ou d'un passage planifié ouvre (ou complète) un ticket (#2988).

POURQUOI — `standards/07` §1 bis : un rouge de la branche de production ou d'un
passage planifié doit laisser une trace qu'on ne peut pas manquer. Le courriel de
GitHub sur un workflow planifié ne part pas toujours, ou ne se lit pas ; un ticket,
lui, compte parmi les issues ouvertes que chaque session trie. Ici, seule la veille
de sécurité ouvrait un ticket, et pour ses constats, pas pour sa propre panne ;
aucun `ci.yml` n'alertait sur un rouge de `main`. Instanciation éprouvée :
`scripts/signaler-echec-ci.py` du dépôt du site, adaptée.

QUAND : un passage planifié, ou un push / un lancement à la main sur `main`. Jamais
sur une PR ni une autre branche : son auteur voit le rouge là où il travaille. Hors
de GitHub Actions (le rejeu du poste, qui ne lit pas les `if:`), rien : code 0.

DÉDOUBLONNAGE : un ticket ouvert par workflow, reconnu à son titre exact ; un échec
suivant y ajoute un commentaire, au plus un toutes les DELAI_HEURES. Le ticket se
ferme à la main, avec le passage revenu au vert qui le prouve.

    python3 scripts/ci/signaler_echec_ci.py --signaler    # pas final `if: failure()`
    python3 scripts/ci/signaler_echec_ci.py --selftest

🔒 `api/tests/test_alerte_echec_ci.py` : chaque job d'un workflow de `main` ou
planifié finit par ce pas, avec le droit `issues: write`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

SCRIPT = "scripts/ci/signaler_echec_ci.py"
ETIQUETTES = ("bug", "priorité haute")
DELAI_HEURES = 12
PRODUCTION = "refs/heads/main"


def titre(workflow: str) -> str:
    return f"CI rouge : {workflow}"


def concerne(env: dict) -> tuple[bool, str]:
    """PURE. Ce passage doit-il alerter ? (oui, raison)."""
    if env.get("GITHUB_ACTIONS") != "true":
        return False, "hors de GitHub Actions"
    evenement, ref = env.get("GITHUB_EVENT_NAME", ""), env.get("GITHUB_REF", "")
    if evenement == "schedule":
        return True, "passage planifié"
    if evenement in ("push", "workflow_dispatch") and ref == PRODUCTION:
        return True, f"{evenement} sur main"
    return (
        False,
        f"{evenement or '?'} sur {ref or '?'} : le rouge se voit là où l'on travaille",
    )


def decider(
    workflow: str, ouverts: list[dict], maintenant: datetime
) -> tuple[str, object]:
    """PURE. ("rien", raison) | ("creer", titre) | ("commenter", numéro)."""
    for ticket in ouverts:
        if ticket.get("title") == titre(workflow):
            vu = datetime.fromisoformat(
                ticket.get("updatedAt", "1970-01-01T00:00:00Z").replace("Z", "+00:00")
            )
            if maintenant - vu < timedelta(hours=DELAI_HEURES):
                return (
                    "rien",
                    f"déjà signalé au ticket {ticket['number']} il y a moins de {DELAI_HEURES} h",
                )
            return "commenter", ticket["number"]
    return "creer", titre(workflow)


def corps(env: dict) -> str:
    """L'exécution courante, et elle seule (`standards/07` §4)."""
    adresse = f"{env.get('GITHUB_SERVER_URL', 'https://github.com')}/{env.get('GITHUB_REPOSITORY', '?')}"
    return (
        f"Le workflow « {env.get('GITHUB_WORKFLOW', '?')} » a échoué "
        f"({env.get('GITHUB_EVENT_NAME', '?')}, job `{env.get('GITHUB_JOB', '?')}`, "
        f"commit {env.get('GITHUB_SHA', '?')[:8]}) : "
        f"{adresse}/actions/runs/{env.get('GITHUB_RUN_ID', '?')}\n\n"
        f"Signalé par `{SCRIPT}`. Un échec suivant du même workflow s'ajoute ici en "
        f"commentaire ; fermer quand il est revenu au vert, avec le passage qui le prouve."
    )


def signaler(env: dict, gh) -> int:
    """gh(arguments) → stdout, ou lève CalledProcessError. Injecté pour l'autotest."""
    oui, raison = concerne(env)
    if not oui:
        print(f"signaler_echec_ci : rien à signaler ({raison})")
        return 0
    depot, workflow = env.get("GITHUB_REPOSITORY", ""), env.get("GITHUB_WORKFLOW", "")
    if not depot or not workflow:
        print(
            "::error::GITHUB_REPOSITORY ou GITHUB_WORKFLOW absent : rien n'a été signalé"
        )
        return 1
    try:
        ouverts = json.loads(
            gh(
                [
                    "issue",
                    "list",
                    "-R",
                    depot,
                    "--state",
                    "open",
                    "--limit",
                    "200",
                    "--json",
                    "number,title,updatedAt",
                ]
            )
        )
        geste, valeur = decider(workflow, ouverts, datetime.now(timezone.utc))
        if geste == "rien":
            print(f"signaler_echec_ci : {valeur}")
            return 0
        if geste == "commenter":
            gh(["issue", "comment", str(valeur), "-R", depot, "--body", corps(env)])
            print(f"signaler_echec_ci : commentaire ajouté au ticket #{valeur}")
            return 0
        base = [
            "issue",
            "create",
            "-R",
            depot,
            "--title",
            str(valeur),
            "--body",
            corps(env),
        ]
        try:
            print(gh(base + [a for e in ETIQUETTES for a in ("--label", e)]).strip())
        except subprocess.CalledProcessError:
            #  Une étiquette renommée ne doit pas taire l'alerte : le ticket part sans elle.
            print(gh(base).strip())
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        print(f"::error::signaler_echec_ci : le ticket n'a pas pu être ouvert ({e})")
        return 1


def _gh_reel(args: list[str]) -> str:
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=True
    ).stdout


def autotest() -> int:
    echecs = 0

    def cas(libelle, obtenu, attendu):
        nonlocal echecs
        ok = obtenu == attendu
        echecs += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {libelle} → {obtenu!r}")

    ga = {"GITHUB_ACTIONS": "true"}
    cas(
        "push sur main",
        concerne({**ga, "GITHUB_EVENT_NAME": "push", "GITHUB_REF": PRODUCTION})[0],
        True,
    )
    cas("passage planifié", concerne({**ga, "GITHUB_EVENT_NAME": "schedule"})[0], True)
    cas(
        "lancé à la main sur main",
        concerne(
            {**ga, "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": PRODUCTION}
        )[0],
        True,
    )
    cas(
        "pull request",
        concerne(
            {
                **ga,
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_REF": "refs/pull/3/merge",
            }
        )[0],
        False,
    )
    cas(
        "lancé à la main sur une branche",
        concerne(
            {
                **ga,
                "GITHUB_EVENT_NAME": "workflow_dispatch",
                "GITHUB_REF": "refs/heads/dev",
            }
        )[0],
        False,
    )
    cas(
        "hors de GitHub Actions (rejeu)",
        concerne({"GITHUB_EVENT_NAME": "push", "GITHUB_REF": PRODUCTION})[0],
        False,
    )

    t = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)
    hier = [
        {"number": 7, "title": titre("CI"), "updatedAt": "2026-11-23T06:00:00Z"},
        {"number": 8, "title": "autre", "updatedAt": "2026-11-24T11:00:00Z"},
    ]
    recent = [{"number": 7, "title": titre("CI"), "updatedAt": "2026-11-24T11:30:00Z"}]
    cas("aucun ticket → créer", decider("CI", [], t)[0], "creer")
    cas("ticket d'hier → commenter", decider("CI", hier, t), ("commenter", 7))
    cas("signalé il y a 30 min → rien", decider("CI", recent, t)[0], "rien")

    env = {
        **ga,
        "GITHUB_REPOSITORY": "o/d",
        "GITHUB_WORKFLOW": "CI",
        "GITHUB_EVENT_NAME": "schedule",
        "GITHUB_REF": PRODUCTION,
        "GITHUB_RUN_ID": "42",
        "GITHUB_SHA": "abcdef0123",
        "GITHUB_JOB": "j",
    }

    def simule(ouverts, refuse_etiquette=False, panne=False, e=env):
        appels = []

        def gh(args):
            appels.append(args)
            if panne:
                raise subprocess.CalledProcessError(1, "gh")
            if args[:2] == ["issue", "list"]:
                return json.dumps(ouverts)
            if refuse_etiquette and "--label" in args:
                raise subprocess.CalledProcessError(1, "gh")
            return "https://github.com/o/d/issues/9\n"

        return signaler(e, gh), appels

    code, appels = simule([])
    cas(
        "création : la commande part, étiquetée",
        (code, appels[-1][:2], "--label" in appels[-1]),
        (0, ["issue", "create"], True),
    )
    cas(
        "création : le corps cite le passage",
        "/o/d/actions/runs/42" in appels[-1][appels[-1].index("--body") + 1],
        True,
    )
    cas("dédoublonnage : commentaire", simule(hier)[1][-1][:2], ["issue", "comment"])
    code, appels = simule([], refuse_etiquette=True)
    cas(
        "étiquette refusée : le ticket part sans elle",
        (code, "--label" in appels[-1]),
        (0, False),
    )
    cas("gh en panne : sortie 1, jamais un faux succès", simule([], panne=True)[0], 1)
    cas(
        "PR : aucun appel à gh",
        simule([], e={**env, "GITHUB_EVENT_NAME": "pull_request"}),
        (0, []),
    )
    cas(
        "dépôt absent : sortie 1",
        signaler({**ga, "GITHUB_EVENT_NAME": "schedule"}, lambda a: "[]"),
        1,
    )
    print("== TOUS OK ==" if not echecs else f"== {echecs} ÉCHEC(S) ==")
    return 1 if echecs else 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--signaler", action="store_true")
    g.add_argument("--selftest", action="store_true")
    args = p.parse_args()
    return autotest() if args.selftest else signaler(dict(os.environ), _gh_reel)


if __name__ == "__main__":
    sys.exit(main())
