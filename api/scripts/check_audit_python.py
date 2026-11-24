#!/usr/bin/env python3
"""Garde-fou : aucune vulnérabilité connue dans les dépendances Python, sauf
exception écrite, motivée et datée.

## Pourquoi (#537, 20/08/2026)

La passe de sécurité du 20/08 couvrait les dix points de l'OWASP Top 10. **Neuf
ont été mesurés ; le dixième ne l'a pas été** :

    $ python -m pip_audit -r api/requirements.txt
    No module named pip_audit

Le versant Node, lui, était couvert depuis #411 (`front/scripts/check-audit.mjs`).
Ce fichier en est le pendant, et il en reprend **les deux décisions**, parce
qu'elles ne dépendent pas du langage :

1. **Aucun seuil de sévérité.** La sévérité annoncée par un avis ne dit rien de
   l'atteignabilité *ici*. C'est l'instruction qui tranche, pas le chiffre — et
   c'est ce qui est écrit dans le motif de chaque exception.

2. **L'échappatoire est nominative, pas globale.** Un contrôle sans porte de
   sortie finit désactivé la semaine où un avis non corrigeable en amont bloque
   toutes les PR. Chaque exception nomme son avis, son motif, sa condition de
   levée et une date de revue ; **elle expire**, et une exception devenue inutile
   FAIT ÉCHOUER le contrôle pour forcer son retrait.

🔴 Un audit qui ne peut pas s'exécuter rend **INCONNU** et sort en **2** — jamais
OK (`standards/04` §1). C'est le défaut même que ce ticket corrigeait : un
contrôle absent ne dit pas « tout va bien », il ne dit rien.

Usage : `python scripts/check_audit_python.py`
    0 = aucune vulnérabilité hors exception
    1 = vulnérabilité non couverte, ou exception périmée / inutile
    2 = INCONNU (l'audit n'a pas pu être mesuré)
"""

from __future__ import annotations

import datetime
import json
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RACINE = pathlib.Path(__file__).resolve().parents[1]
REQUIREMENTS = RACINE / "requirements.txt"
FICHIER_EXCEPTIONS = RACINE / "audit-exceptions.json"

CHAMPS_REQUIS = ("motif", "leveeSi", "revoirLe")


def inconnu(raison: str, detail: str = "") -> None:
    print(f"\n⚠️  INCONNU — {raison}", file=sys.stderr)
    if detail:
        for ligne in str(detail).strip().split("\n")[:5]:
            print(f"   {ligne}", file=sys.stderr)
    print(
        "   L'audit n'a PAS été mesuré : ce n'est ni un succès ni un échec. Relancer le job.\n",
        file=sys.stderr,
    )
    sys.exit(2)


def mesurer() -> list[dict]:
    """Les dépendances vulnérables, telles que `pip-audit` les rapporte."""
    if not REQUIREMENTS.is_file():
        inconnu(f"{REQUIREMENTS} introuvable")

    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip_audit",
                "-r",
                str(REQUIREMENTS),
                "--format",
                "json",
                "--progress-spinner",
                "off",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    except FileNotFoundError as exc:
        inconnu("`pip-audit` n'a pas pu être lancé", str(exc))
    except subprocess.TimeoutExpired:
        inconnu("`pip-audit` n'a pas rendu la main en 5 min (registre injoignable ?)")

    #  ⚠️ `pip-audit` sort en 1 dès qu'il trouve quelque chose : le code de sortie
    #  ne distingue pas « vulnérabilités trouvées » de « audit impossible ».
    #  C'est la sortie JSON qui fait foi, et son absence qui vaut INCONNU.
    try:
        rapport = json.loads(proc.stdout)
    except json.JSONDecodeError:
        inconnu("sortie de `pip-audit` illisible", proc.stderr or proc.stdout)

    if "dependencies" not in rapport:
        inconnu("sortie de `pip-audit` sans section `dependencies`")

    return rapport["dependencies"]


def lire_exceptions() -> dict:
    if not FICHIER_EXCEPTIONS.is_file():
        return {}
    try:
        return json.loads(FICHIER_EXCEPTIONS.read_text(encoding="utf-8")).get("exceptions", {})
    except (json.JSONDecodeError, OSError) as exc:
        inconnu(f"{FICHIER_EXCEPTIONS} illisible", str(exc))


def principal() -> None:
    dependances = mesurer()
    exceptions = lire_exceptions()
    #  Le jour UTC, celui de l'exécuteur de la CI — pas `date.today()`, le jour du
    #  conteneur (DTZ011, `api/scripts/` lu par Ruff depuis #2951).
    aujourdhui = datetime.datetime.now(datetime.timezone.utc).date().isoformat()

    #  🔴 CAS ZÉRO — un `requirements.txt` vide, ou un audit qui n'aurait lu
    #  aucun paquet, rendrait « aucune vulnérabilité » sans avoir rien examiné.
    if len(dependances) < 5:
        inconnu(
            f"{len(dependances)} dépendance(s) analysée(s) seulement : "
            "l'audit n'a pas lu le fichier attendu"
        )

    trouves: dict[str, dict] = {}
    for dep in dependances:
        for vuln in dep.get("vulns", []):
            trouves[vuln["id"]] = {
                "paquet": dep["name"],
                "version": dep["version"],
                "correctifs": vuln.get("fix_versions") or [],
            }

    defauts: list[str] = []

    #  Une vulnérabilité sans exception écrite fait échouer.
    for avis, info in sorted(trouves.items()):
        exc = exceptions.get(avis)
        if not exc:
            correctif = ", ".join(info["correctifs"]) or "aucun correctif publié"
            defauts.append(
                f"✗ {avis} — {info['paquet']} {info['version']} "
                f"(corrigé en : {correctif})\n"
                f"    Corriger la dépendance, ou déclarer l'avis dans "
                f"{FICHIER_EXCEPTIONS.name} avec motif, leveeSi et revoirLe."
            )
            continue
        manquants = [c for c in CHAMPS_REQUIS if not exc.get(c)]
        if manquants:
            defauts.append(f"✗ {avis} — exception incomplète, il manque : {', '.join(manquants)}")
        elif exc["revoirLe"] < aujourdhui:
            defauts.append(
                f"✗ {avis} — exception à revoir depuis le {exc['revoirLe']}.\n"
                f"    Levée prévue : {exc['leveeSi']}"
            )

    #  ⚠️ Et une exception qui ne sert PLUS fait échouer aussi. Une dérogation
    #  oubliée est une porte qu'on croit fermée : le jour où l'avis disparaît,
    #  c'est le moment de retirer la ligne, pas trois mois plus tard.
    for avis in sorted(set(exceptions) - set(trouves)):
        defauts.append(
            f"✗ {avis} — exception déclarée mais l'avis n'est plus rapporté : "
            "la retirer de " + FICHIER_EXCEPTIONS.name
        )

    if defauts:
        print(f"\n✗ Audit Python : {len(defauts)} point(s) à traiter\n", file=sys.stderr)
        for d in defauts:
            print(f"  {d}", file=sys.stderr)
        print("", file=sys.stderr)
        sys.exit(1)

    couvertes = len(trouves)
    print(
        f"✓ Audit Python : {len(dependances)} dépendance(s) analysée(s), "
        f"{couvertes} avis connu(s), tous déclarés avec leur motif et leur date de revue."
    )


if __name__ == "__main__":
    principal()
