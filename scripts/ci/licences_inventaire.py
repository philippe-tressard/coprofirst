"""Collecte des licences tierces — npm par les verrous, Python par les métadonnées.

Rend des listes de `{"nom", "licence", "portee"}` triées par nom. Une source
qui ne peut pas être lue lève `Inconnu` : le contrôle rend alors INCONNU,
jamais un vert sur ce qu'il n'a pas lu (`standards/04` §1).
"""

from __future__ import annotations

import json
import pathlib

from licences_spdx import licence_python

#  L'environnement de l'IMAGE de l'API (`api/Dockerfile`, python:3.12 sur un
#  Raspberry Pi) — pas celui du poste qui lance le contrôle. Évaluer les
#  marqueurs ici, c'est inventorier ce qui part en production : `uvloop` en
#  fait partie, `colorama` (Windows) non.
ENVIRONNEMENT_IMAGE = {
    "implementation_name": "cpython",
    "os_name": "posix",
    "platform_machine": "aarch64",
    "platform_python_implementation": "CPython",
    "platform_system": "Linux",
    "python_full_version": "3.12.0",
    "python_version": "3.12",
    "sys_platform": "linux",
}


class Inconnu(Exception):
    """La source n'a pas pu être mesurée."""


def _trier(paquets: dict[tuple[str, str], set[str]]) -> list[dict]:
    return [
        {"nom": nom, "licence": licence, "portee": ", ".join(sorted(portees))}
        for (nom, licence), portees in sorted(paquets.items())
    ]


def paquets_npm(verrou: pathlib.Path) -> list[dict]:
    """Chaque entrée de `package-lock.json` (v2+), avec la licence qu'il porte."""
    try:
        donnees = json.loads(verrou.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Inconnu(f"{verrou.name} illisible ({e})") from e
    entrees = donnees.get("packages")
    if donnees.get("lockfileVersion", 0) < 2 or not isinstance(entrees, dict):
        raise Inconnu(f"{verrou.name} : format de verrou sans section `packages`")
    paquets: dict[tuple[str, str], set[str]] = {}
    for cle, entree in entrees.items():
        if not cle or entree.get("link"):
            continue  # la racine du projet, ou un lien vers une entrée déjà listée
        nom = entree.get("name") or cle.rsplit("node_modules/", 1)[-1]
        licence = entree.get("license")
        if not isinstance(licence, str) or not licence.strip():
            licence = "NON DÉCLARÉE"
        portee = "devDependencies" if entree.get("dev") else "dependencies"
        if entree.get("optional") or entree.get("devOptional"):
            portee += " (optionnel)"
        paquets.setdefault((nom, licence.strip()), set()).add(portee)
    return _trier(paquets)


def _exigences(fichier: pathlib.Path) -> list[str]:
    try:
        lignes = fichier.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise Inconnu(f"{fichier.name} illisible ({e})") from e
    exigences = []
    for ligne in lignes:
        ligne = ligne.split("#", 1)[0].strip()
        if not ligne:
            continue
        if ligne.startswith("-"):
            raise Inconnu(f"{fichier.name} : option `{ligne}` non prise en charge")
        exigences.append(ligne)
    return exigences


#  Les POSTES de développement. Servent à une seule question : une dépendance de
#  l'image y est-elle installable ? Si non (`uvloop` sous Windows, `greenlet` sous
#  macOS arm64), son absence ici n'est pas une mesure manquée mais une
#  impossibilité — et seule une déclaration de `LICENCES_HORS_POSTE` peut la rendre
#  mesurable, sous le contrôle de la CI qui, elle, lit le paquet installé.
#  Deux postes depuis le 01/11/2026 (#2419) : le Mac, et le PC gardé en repli. Une
#  dépendance n'est « installable sur le poste » que si elle l'est sur TOUS ; le PC
#  retiré, son entrée se retire, et une déclaration devenue inutile échoue.
ENVIRONNEMENTS_POSTES = {
    "Windows": {
        **ENVIRONNEMENT_IMAGE,
        "os_name": "nt",
        "platform_machine": "AMD64",
        "platform_system": "Windows",
        "sys_platform": "win32",
    },
    "macOS": {
        **ENVIRONNEMENT_IMAGE,
        "platform_machine": "arm64",
        "platform_system": "Darwin",
        "sys_platform": "darwin",
    },
}


def _graphe(directes, env: dict, md, Requirement, canonicalize_name) -> tuple[dict, set]:
    """({nom: extras demandés}, absentes) — le graphe sous un environnement donné."""
    extras_vus: dict[str, set[str]] = {}
    absentes: set[str] = set()
    pile = list(directes)
    while pile:
        exigence = pile.pop()
        nom = canonicalize_name(exigence.name)
        demandes = set(exigence.extras)
        if nom in extras_vus and demandes <= extras_vus[nom]:
            continue
        extras_vus[nom] = extras_vus.get(nom, set()) | demandes
        try:
            dist = md.distribution(exigence.name)
        except md.PackageNotFoundError:
            absentes.add(nom)
            continue
        for texte in dist.requires or []:
            dependance = Requirement(texte)
            contextes = extras_vus[nom] or {""}
            if dependance.marker and not any(
                dependance.marker.evaluate({**env, "extra": x}) for x in contextes
            ):
                continue
            pile.append(dependance)
    return extras_vus, absentes


def decider_hors_poste(table: dict, image: set, poste: set, lues: dict, absentes: set):
    """(licences retenues sur déclaration, notes, échecs, absentes restantes). PURE.

    - entrée dont le paquet n'est plus une dépendance de l'image : ÉCHEC ;
    - entrée dont le paquet s'installe aussi sur le poste : ÉCHEC (inutile) ;
    - paquet installé ici (la CI, Linux) : sa licence LUE doit être la
      licence déclarée, sinon ÉCHEC — c'est ce qui empêche la déclaration de
      mentir ;
    - paquet absent ici et non installable sur le poste : la licence déclarée
      est retenue, et la sortie le dit.
    """
    retenues: dict[str, str] = {}
    notes: list[str] = []
    echecs: list[str] = []
    restantes = set(absentes)
    for nom, decl in sorted(table.items()):
        if nom not in image:
            echecs.append(
                f"LICENCES_HORS_POSTE · {nom} n'est plus une dépendance de l'image — "
                "retirer l'entrée"
            )
        elif nom in poste:
            echecs.append(
                f"LICENCES_HORS_POSTE · {nom} s'installe aussi sur le poste : l'entrée ne "
                "sert plus — la retirer"
            )
        elif nom in lues:
            if lues[nom] != decl["licence"]:
                echecs.append(
                    f"LICENCES_HORS_POSTE · {nom} : licence lue « {lues[nom]} », déclarée "
                    f"« {decl['licence']} » — corriger la déclaration après relecture"
                )
        elif nom in absentes:
            retenues[nom] = decl["licence"]
            restantes.discard(nom)
            notes.append(
                f"api · {nom} — {decl['licence']} : licence déclarée, vérifiée par la CI "
                f"(non installable sur cette plateforme ; vérifiée le {decl['date']})"
            )
    return retenues, notes, echecs, restantes


def _licence_installee(md, nom: str) -> str:
    meta = md.metadata(nom)
    licence, _source = licence_python(
        meta.get("License-Expression"), meta.get("License"), meta.get_all("Classifier") or []
    )
    return licence


def paquets_python(fichier: pathlib.Path, hors_poste: dict) -> dict:
    """Le graphe des distributions installées, depuis les exigences de production.

    Rend `paquets` (`portee` : `directe`, `transitive`, ou `transitive (déclarée)`
    pour une licence tirée de `hors_poste`), `jugement` et `document` (réserves
    qui rendent INCONNU), `echecs` et `notes`.

    Une distribution ABSENTE ne lève pas : les autres restent jugées. Une
    transitive absente ne touche que le jugement — le document ne fige que les
    directes. Une directe absente, ou installée dans une autre version que celle
    épinglée, touche les deux : sa métadonnée ne serait pas celle de l'image.
    """
    try:
        import importlib.metadata as md

        from packaging.requirements import Requirement
        from packaging.utils import canonicalize_name
    except ImportError as e:
        raise Inconnu(f"module `packaging` absent ({e})") from e

    directes = [Requirement(e) for e in _exigences(fichier)]
    noms_directs = {canonicalize_name(r.name) for r in directes}
    document: list[str] = []
    for r in directes:
        try:
            version = md.version(r.name)
        except md.PackageNotFoundError:
            document.append(f"{r.name} (directe) non installée ici")
            continue
        if r.specifier and not r.specifier.contains(version, prereleases=True):
            document.append(f"{r.name} installée en {version}, épinglée {r.specifier}")
    jugement = list(document)

    outils = (md, Requirement, canonicalize_name)
    image, absentes = _graphe(directes, ENVIRONNEMENT_IMAGE, *outils)
    poste = set.intersection(
        *(set(_graphe(directes, env, *outils)[0]) for env in ENVIRONNEMENTS_POSTES.values())
    )
    lues = {nom: _licence_installee(md, nom) for nom in image if nom not in absentes}
    retenues, notes, echecs, restantes = decider_hors_poste(
        hors_poste, set(image), set(poste), lues, absentes
    )
    transitives = sorted(restantes - noms_directs)
    if transitives:
        jugement.append(f"transitive(s) non installée(s) ici : {', '.join(transitives)}")

    paquets: dict[tuple[str, str], set[str]] = {}
    for nom, licence in lues.items():
        portee = "directe" if nom in noms_directs else "transitive"
        paquets.setdefault((nom, licence), set()).add(portee)
    for nom, licence in retenues.items():
        paquets.setdefault((nom, licence), set()).add("transitive (déclarée)")
    return {
        "paquets": _trier(paquets),
        "jugement": jugement,
        "document": document,
        "echecs": echecs,
        "notes": notes,
    }
