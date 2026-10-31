"""Licences tierces — ce que les Dockerfile installent hors de pip et npm (#2389).

L'inventaire de `licences_tierces.py` lit les métadonnées des paquets pip et npm.
Il ne voit ni les paquets Debian d'une image, ni ce qu'une roue EMBARQUE :
`pillow-heif` se lit « BSD-3-Clause », alors que ses roues PyPI portent libx265,
l'encodeur HEVC sous GPLv2. Ce module confronte les Dockerfile à la politique
(`licences_politique.BIBLIOTHEQUES_SYSTEME`, `INTERDITS_DANS_LES_IMAGES`,
`ROUES_A_COMPILER`) :

  - un paquet Debian déclaré que l'étape FINALE n'installe plus fait échouer —
    la déclaration se retire, sinon elle couvrirait demain autre chose ;
  - un paquet interdit, dans n'importe quelle étape, fait échouer ;
  - un `apt-get install` sans `--no-install-recommends` fait échouer :
    `libheif1` RECOMMANDE `libheif-plugin-x265`, et apt l'installerait ;
  - une roue à compiler doit l'être (`--no-binary`, puis `PIP_NO_BINARY` pour
    l'installation des exigences), et son entrée se retire si le paquet quitte
    les exigences.

Ce qu'il ne voit pas — l'image construite : `api/scripts/verifier_heif.py`, lancé
par le Dockerfile, y exige l'absence de x265 sur amd64 comme sur arm64.
"""

from __future__ import annotations

import fnmatch
import pathlib
import re

RACINE = pathlib.Path(__file__).resolve().parents[2]

_SUITE = re.compile(r"\\\r?\n")
_INSTALLATION = re.compile(r"apt-get\s+install\b([^&;|]*)")


def etapes(texte: str) -> list[list[str]]:
    """Les paquets que chaque étape installe par `apt-get install`, dans l'ordre. PURE.

    Une étape commence à chaque `FROM`. Un `apt-get install` sans
    `--no-install-recommends` rend le paquet `!recommends`, que `juger` refuse.
    """
    resultat: list[list[str]] = []
    code = "\n".join(x for x in texte.splitlines() if not x.lstrip().startswith("#"))
    for ligne in _SUITE.sub(" ", code + "\n").splitlines():
        if re.match(r"\s*FROM\s", ligne, re.IGNORECASE):
            resultat.append([])
            continue
        for commande in _INSTALLATION.findall(ligne):
            mots = commande.split()
            if not resultat:
                resultat.append([])
            if "--no-install-recommends" not in mots:
                resultat[-1].append("!recommends")
            resultat[-1] += [m for m in mots if not m.startswith("-")]
    return resultat


def juger(textes: dict[str, str], exigences: dict[str, str], politique) -> list[str]:
    """Les manquements des Dockerfile à la politique ; vide = conforme. PURE.

    `textes` : chemin du Dockerfile → contenu ; `exigences` : chemin d'un
    requirements → contenu.
    """
    echecs = []
    for chemin, texte in sorted(textes.items()):
        toutes = etapes(texte)
        for paquet in sorted({p for e in toutes for p in e}):
            if paquet == "!recommends":
                echecs.append(
                    f"{chemin} — un `apt-get install` sans --no-install-recommends : "
                    "les paquets recommandés entreraient (libheif1 recommande x265)"
                )
                continue
            for motif, raison in politique.INTERDITS_DANS_LES_IMAGES.items():
                if fnmatch.fnmatchcase(paquet, motif):
                    echecs.append(f"{chemin} — paquet interdit {paquet} : {raison}")
    for decl in politique.BIBLIOTHEQUES_SYSTEME:
        texte = textes.get(decl["dockerfile"])
        finale = set(etapes(texte)[-1]) if texte and etapes(texte) else set()
        for paquet in decl["paquets"]:
            if paquet not in finale:
                echecs.append(
                    f"{decl['dockerfile']} — {paquet} est déclaré dans BIBLIOTHEQUES_SYSTEME "
                    "mais l'étape finale ne l'installe pas : retirer la déclaration"
                )
    for paquet, regle in politique.ROUES_A_COMPILER.items():
        motif = re.compile(rf"^{re.escape(paquet)}==", re.IGNORECASE | re.MULTILINE)
        if not motif.search(exigences.get(regle["exigences"], "")):
            echecs.append(
                f"{regle['exigences']} — {paquet} n'y est plus : retirer son entrée de "
                "ROUES_A_COMPILER"
            )
            continue
        texte = textes.get(regle["dockerfile"], "")
        for marque in (f"--no-binary {paquet}", f"PIP_NO_BINARY={paquet}"):
            if marque not in texte:
                echecs.append(
                    f"{regle['dockerfile']} — « {marque} » manque : la roue PyPI de {paquet} "
                    f"entrerait dans l'image ({regle['raison']})"
                )
    return echecs


def verifier(politique) -> list[str]:
    """Les manquements des Dockerfile du dépôt."""
    textes = {
        p.relative_to(RACINE).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(RACINE.glob("**/Dockerfile*"))
        if "node_modules" not in p.parts and ".git" not in p.parts
    }
    if not textes:
        return ["aucun Dockerfile lu : contrôle impossible"]
    exigences = {
        r["exigences"]: (RACINE / r["exigences"]).read_text(encoding="utf-8")
        for r in politique.ROUES_A_COMPILER.values()
        if (RACINE / r["exigences"]).exists()
    }
    return juger(textes, exigences, politique)


def rendre(politique, cellule) -> list[str]:
    """La section du document. PURE."""
    lignes = ["## Bibliothèques système des images", ""]
    lignes += [
        "Installées par un Dockerfile hors de pip et npm, donc absentes de "
        "l'inventaire ci-dessous. Seules y figurent celles qui sont entrées pour "
        "une raison nommée.",
        "",
        "| Image | Paquets Debian | Licence | Motif | Statut |",
        "|---|---|---|---|---|",
    ]
    for d in politique.BIBLIOTHEQUES_SYSTEME:
        paquets = ", ".join(f"`{p}`" for p in d["paquets"])
        licences = "<br>".join(f"`{cellule(x)}`" for x in d["licences"])
        lignes.append(
            f"| `{d['dockerfile']}` | {paquets} | {licences} | {d['motif']} | {d['statut']} |"
        )
    interdits = "; ".join(f"`{m}` : {r}" for m, r in politique.INTERDITS_DANS_LES_IMAGES.items())
    roues = "; ".join(f"`{p}` : {r['raison']}" for p, r in politique.ROUES_A_COMPILER.items())
    lignes += ["", f"Interdits dans toute image — {interdits}.", ""]
    lignes += [f"Compilés dans l'image, jamais pris en roue PyPI — {roues}."]
    return lignes
