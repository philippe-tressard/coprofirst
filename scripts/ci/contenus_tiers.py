#!/usr/bin/env python3
"""Contenus tiers recopiés dans le dépôt — leur attribution REUSE est-elle VRAIE ? (#1543)

## Pourquoi

`reuse lint` vérifie qu'une licence est DÉCLARÉE pour chaque fichier, pas
qu'elle est juste. Les tracés Lucide (ISC, MIT pour la part issue de Feather)
recopiés dans `icones-svg.json` recevaient la licence du motif `**` de
`REUSE.toml` — celle du projet — et le contrôle restait vert : la copie
existait, la notice exigée par la licence ISC non.

## Ce qu'il mesure — deux sens (`standards/05` §9 bis)

1. **Déclaré → attribué.** Pour chaque fichier de
   `licences_politique.CONTENUS_TIERS`, ce que REUSE lui attribue RÉELLEMENT
   (`reuse lint --json`, l'outil lui-même, pas une relecture de REUSE.toml)
   doit nommer toutes les licences et tous les titulaires déclarés. Un fichier
   déclaré qui n'existe plus fait échouer : la déclaration se retire.
2. **Présent → déclaré.** Les tracés du catalogue d'icônes servent
   d'EMPREINTES : tout fichier versionné qui en contient un doit figurer parmi
   les fichiers de son contenu tiers. Une troisième copie du catalogue, une
   icône collée dans un composant, repasseraient sinon sous `**` en silence.

## Ce qu'il ne voit pas
Un contenu tiers qui ne partage AUCUN tracé avec le catalogue (une icône
Lucide jamais ajoutée au catalogue, une image, une police) : celui-là se
déclare dans `CONTENUS_TIERS` à son arrivée.

Usage : python scripts/ci/contenus_tiers.py
    0 = chaque contenu tiers est attribué et déclaré
    1 = attribution fausse ou incomplète, copie non déclarée, déclaration morte
    2 = INCONNU (REUSE ou le catalogue n'ont pas pu être lus)
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import licences_politique as politique  # noqa: E402
from licences_spdx import identifiants  # noqa: E402

RACINE = pathlib.Path(__file__).resolve().parents[2]
#: Un tracé plus court (« M12 5v14 ») se retrouve dans des dessins sans lien.
LONGUEUR_EMPREINTE = 20
_TRACE = re.compile(r'\bd=\\?"([^"\\]+)\\?"')


class Inconnu(Exception):
    pass


def attributions_reuse() -> dict[str, tuple[set[str], list[str]]]:
    """{chemin: (licences, copyrights)} tels que REUSE les attribue."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    sortie = subprocess.run(
        [sys.executable, "-m", "reuse", "lint", "--json"],
        cwd=RACINE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    try:
        rapport = json.loads(sortie.stdout)
    except ValueError as e:
        raise Inconnu(f"`reuse lint --json` illisible : {(sortie.stderr or '')[:300]}") from e
    fichiers = rapport.get("files") or []
    if not fichiers:  # cas zéro : REUSE n'a rien lu
        raise Inconnu("`reuse lint --json` ne rend aucun fichier")
    resultat = {}
    for f in fichiers:
        licences: set[str] = set()
        for e in f.get("spdx_expressions", []):
            licences |= identifiants(e["value"])
        resultat[f["path"].replace("\\", "/")] = (
            licences,
            [c["value"] for c in f.get("copyrights", [])],
        )
    return resultat


def empreintes(catalogue: dict[str, str], icones) -> set[str]:
    """Les tracés assez longs pour désigner leur origine. PURE."""
    traces: set[str] = set()
    for nom, svg in catalogue.items():
        if icones is None and nom in politique.ICONES_HORS_LUCIDE:
            continue
        if icones is not None and nom not in icones:
            continue
        traces |= {d for d in _TRACE.findall(svg) if len(d) >= LONGUEUR_EMPREINTE}
    return traces


def verifier_attribution(contenu: dict, attributions: dict) -> list[str]:
    """Sens 1 — chaque fichier déclaré porte les licences et titulaires déclarés. PURE."""
    echecs = []
    for chemin in contenu["fichiers"]:
        if chemin not in attributions:
            echecs.append(
                f"{contenu['nom']} : {chemin} déclaré mais absent du dépôt (ou ignoré "
                "par REUSE) — retirer la déclaration de CONTENUS_TIERS"
            )
            continue
        licences, copyrights = attributions[chemin]
        manquantes = sorted(set(contenu["licences"]) - licences)
        if manquantes:
            echecs.append(
                f"{contenu['nom']} : REUSE attribue à {chemin} « {' AND '.join(sorted(licences))} »"
                f" — il y manque {', '.join(manquantes)}. Ajouter un bloc [[annotations]] "
                "à REUSE.toml, et le texte de la licence dans LICENSES/"
            )
        for titulaire in contenu["titulaires"]:
            if not any(titulaire in c for c in copyrights):
                echecs.append(
                    f"{contenu['nom']} : aucun SPDX-FileCopyrightText de {chemin} ne nomme "
                    f"« {titulaire} » — la licence exige de conserver sa mention"
                )
    return echecs


def verifier_presence(contenu: dict, traces: set[str], textes: dict[str, str]) -> list[str]:
    """Sens 2 — tout fichier qui porte une empreinte est déclaré. PURE."""
    echecs = []
    for chemin, texte in textes.items():
        if chemin in contenu["fichiers"]:
            continue
        communs = traces & set(_TRACE.findall(texte))
        if communs:
            echecs.append(
                f"{contenu['nom']} : {chemin} recopie {len(communs)} tracé(s) — le déclarer "
                "dans CONTENUS_TIERS (licences_politique.py) et dans REUSE.toml"
            )
    return echecs


def textes_versionnes() -> dict[str, str]:
    sortie = subprocess.run(["git", "ls-files", "-z"], cwd=RACINE, capture_output=True, check=False)
    if sortie.returncode != 0:
        raise Inconnu("`git ls-files` a échoué")
    textes = {}
    for chemin in sortie.stdout.decode("utf-8").split("\0"):
        if not chemin:
            continue
        try:
            textes[chemin] = (RACINE / chemin).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binaire ou illisible : aucun tracé SVG en clair
    if not textes:
        raise Inconnu("aucun fichier versionné lu")
    return textes


def main() -> int:
    echecs: list[str] = []
    try:
        catalogue = json.loads((RACINE / politique.CATALOGUE_ICONES).read_text(encoding="utf-8"))
        manquantes = sorted(set(politique.ICONES_HORS_LUCIDE) - set(catalogue))
        echecs += [
            f"ICONES_HORS_LUCIDE nomme « {n} », absente du catalogue — retirer l'entrée"
            for n in manquantes
        ]
        attributions = attributions_reuse()
        textes = textes_versionnes()
        mesures = []
        for contenu in politique.CONTENUS_TIERS:
            echecs += verifier_attribution(contenu, attributions)
            if contenu.get("sans_empreinte"):
                #  Une image : le sens 1 (attribution) la juge ; le sens 2 n'a rien à retrouver.
                mesures.append(f"{contenu['nom']} {len(contenu['fichiers'])} fichier(s)")
                continue
            traces = empreintes(catalogue, contenu["icones"])
            if not traces:  # cas zéro : sans empreinte, le sens 2 ne verrait rien
                raise Inconnu(f"{contenu['nom']} : aucune empreinte tirée du catalogue")
            echecs += verifier_presence(contenu, traces, textes)
            mesures.append(f"{contenu['nom']} {len(contenu['fichiers'])} fichier(s)")
    except (Inconnu, OSError, ValueError) as e:
        print(f"\n⚠️  INCONNU — {e}", file=sys.stderr)
        return 2

    print(f"Contenus tiers — {', '.join(mesures)} ; {len(textes)} fichiers versionnés balayés.")
    for e in echecs:
        print(f"\n✗ {e}", file=sys.stderr)
    if echecs:
        return 1
    print("✓ Chaque contenu tiers est attribué par REUSE à ses licences et titulaires.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
