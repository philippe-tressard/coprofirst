#!/usr/bin/env python3
"""Inventaire des licences tierces — liste blanche et exceptions nominatives (#1542).

## Pourquoi

`standards/14` §6.3 : « la liste des dépendances ET de leurs licences est figée
dans le dépôt et relue à chaque ajout ». Rien ne la tenait : `reuse lint`
couvre les fichiers du projet, pas les bibliothèques qu'il tire. L'audit du
02/10/2026 a trouvé `libsignal` (GPL-3.0) dans le bridge WhatsApp, et personne
ne l'avait vu entrer.

## Ce qu'il mesure

  - `front/` et `whatsapp-bridge/` : le champ `license` de CHAQUE entrée de
    `package-lock.json` — le verrou porte la licence déclarée par le paquet.
    Ni installation, ni registre, ni outil tiers à épingler : la mesure porte
    sur le fichier même qui décide de ce qui est installé ;
  - `api/` : les métadonnées des distributions INSTALLÉES, en suivant le graphe
    depuis `api/requirements.txt` (production seule, extras compris), marqueurs
    évalués pour l'image (Linux, Python 3.12). Le job `test-backend` les a
    installées ; ailleurs, une distribution absente rend INCONNU — sauf si elle
    ne peut PAS s'installer sur le poste (`uvloop` sous Windows) et que sa
    licence est déclarée dans `LICENCES_HORS_POSTE` : retenue alors, et
    confrontée en CI à la licence lue du paquet installé.

Chaque licence est confrontée à `licences_politique.ADMISES`, puis aux
EXCEPTIONS. L'inventaire est rendu dans `docs/licences-tierces.md`, GÉNÉRÉ par
`--ecrire` et comparé ici : un paquet qui entre ou qui change de licence fait
échouer la CI tant que le document — donc la relecture — n'a pas suivi. Sans
les versions, exprès : une montée qui ne change ni le nom ni la licence ne
demande rien.

⚠️ Le document ne fige des dépendances Python que les DIRECTES. Les transitives
ne sont pas épinglées (`requirements.txt` ne porte que les directes) : la CI
installe la dernière version publiée, dont la métadonnée de licence change au
fil des migrations vers PEP 639 — le document passerait au rouge sans qu'un
octet du dépôt bouge, et un contrôle rouge sans cause se contourne
(`standards/04` §25). Elles restent JUGÉES par la liste blanche à chaque
passage : une transitive copyleft fait échouer la CI comme une directe.

Les paquets Debian des images et les roues qui embarquent un interdit (#2389) :
`licences_image.py`, appelé ici, confronte les Dockerfile à la politique.

## Ce qu'il ne voit pas
Les fichiers recopiés d'un projet tiers dans le dépôt : `contenus_tiers.py`.

Usage : python scripts/ci/licences_tierces.py [--ecrire | --selftest]
    0 = tout est admis ou couvert, document à jour
    1 = licence non couverte, exception inutile, ou document à régénérer
    2 = INCONNU (une source n'a pas pu être mesurée)
"""

from __future__ import annotations

import fnmatch
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import licences_politique as politique  # noqa: E402
from licences_document import rendre_document  # noqa: E402
from licences_image import verifier as verifier_images  # noqa: E402
from licences_inventaire import Inconnu, paquets_npm, paquets_python  # noqa: E402
from licences_spdx import admise  # noqa: E402

RACINE = pathlib.Path(__file__).resolve().parents[2]
DOCUMENT = RACINE / "docs" / "licences-tierces.md"
VERROUS = (
    ("front", RACINE / "front" / "package-lock.json"),
    ("whatsapp-bridge", RACINE / "whatsapp-bridge" / "package-lock.json"),
)
EXIGENCES_API = RACINE / "api" / "requirements.txt"


def confronter(source: str, paquets: list[dict], exceptions, admises) -> tuple[list, list, set]:
    """(échecs, tolérés, clés d'exception servies) pour une source. PURE."""
    echecs, tolerees, servies = [], [], set()
    for p in paquets:
        if admise(p["licence"], admises):
            continue
        couverte = False
        for i, exc in enumerate(exceptions):
            if exc["source"] != source or p["licence"] not in exc["licences"]:
                continue
            if any(fnmatch.fnmatchcase(p["nom"], motif) for motif in exc["paquets"]):
                servies.add((i, p["licence"]))
                couverte = True
        if couverte:
            tolerees.append(f"{source} · {p['nom']} — {p['licence']}")
        else:
            echecs.append(
                f"{source} · {p['nom']} — licence « {p['licence']} » ni admise ni déclarée\n"
                "      → retirer la dépendance, ou la déclarer dans "
                "scripts/ci/licences_politique.py (EXCEPTIONS) avec son motif"
            )
    return echecs, tolerees, servies


def exceptions_inutiles(exceptions, servies: set, sources_mesurees: set) -> list[str]:
    """Une exception (ou une de ses licences) qui ne couvre plus rien. PURE."""
    inutiles = []
    for i, exc in enumerate(exceptions):
        if exc["source"] not in sources_mesurees:
            continue  # source INCONNUE ou partielle : on ne conclut rien
        for licence in exc["licences"]:
            if (i, licence) not in servies:
                inutiles.append(
                    f"{exc['source']} · {', '.join(exc['paquets'])} — « {licence} » ne couvre "
                    "plus aucun paquet : retirer cette ligne d'EXCEPTIONS"
                )
    return inutiles


def mesurer() -> tuple[dict, dict, list[str], list[str], list[str], list[str]]:
    """(à juger, à figer, réserves sur le jugement, réserves sur le document,
    échecs de mesure, notes)."""
    juger: dict[str, list[dict]] = {}
    figer: dict[str, list[dict]] = {}
    reserves_jugement: list[str] = []
    reserves_document: list[str] = []
    for source, verrou in VERROUS:
        try:
            paquets = paquets_npm(verrou)
        except Inconnu as e:
            paquets, raison = [], str(e)
        else:
            raison = "aucun paquet lu" if not paquets else ""  # cas zéro
        if raison:
            reserves_jugement.append(f"{source} : {raison}")
            reserves_document.append(f"{source} : {raison}")
            continue
        juger[source] = figer[source] = paquets
    try:
        api = paquets_python(EXIGENCES_API, politique.LICENCES_HORS_POSTE)
    except Inconnu as e:
        api = {"paquets": [], "jugement": [str(e)], "document": [str(e)]}
    paquets, rj, rd = api["paquets"], api["jugement"], api["document"]
    directes = [p for p in paquets if "directe" in p["portee"]]
    if not paquets:
        rj = rj or ["aucun paquet lu"]
    if not directes:
        rd = rd or ["aucune dépendance directe lue"]
    reserves_jugement += [f"api : {r}" for r in rj]
    reserves_document += [f"api : {r}" for r in rd]
    if paquets:
        juger["api"] = paquets
    figer["api"] = directes
    return (
        juger,
        figer,
        reserves_jugement,
        reserves_document,
        api.get("echecs", []),
        api.get("notes", []),
    )


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        from licences_selftest import lancer

        return lancer(confronter, exceptions_inutiles)

    juger, figer, reserves_jugement, reserves_document, echecs, notes = mesurer()
    exceptions, admises = politique.EXCEPTIONS, politique.ADMISES
    echecs += verifier_images(politique)
    tolerees, servies = [], set()
    for source, paquets in juger.items():
        e, t, s = confronter(source, paquets, exceptions, admises)
        echecs += e
        tolerees += t
        servies |= s
    completes = {s for s in juger if not any(r.startswith(f"{s} :") for r in reserves_jugement)}
    echecs += exceptions_inutiles(exceptions, servies, completes)

    total = sum(len(p) for p in juger.values())
    detail = ", ".join(f"{s} {len(p)}" for s, p in juger.items())
    print(f"Licences tierces — {total} paquets jugés ({detail}).")
    for t in tolerees:
        print(f"  ~ exception déclarée : {t}")
    for n in notes:
        print(f"  ~ {n}")

    for r in reserves_jugement:
        print(f"\n⚠️  INCONNU — jugement partiel, {r}", file=sys.stderr)
    if reserves_document:
        for r in reserves_document:
            print(f"\n⚠️  INCONNU — document ni comparé ni écrit, {r}", file=sys.stderr)
    else:
        attendu = rendre_document(figer, exceptions, admises)
        if "--ecrire" in argv:
            DOCUMENT.write_bytes(attendu.encode("utf-8"))
            print(f"  ✎ {DOCUMENT.relative_to(RACINE).as_posix()} régénéré.")
        elif not DOCUMENT.exists() or DOCUMENT.read_bytes().decode("utf-8") != attendu:
            echecs.append(
                "docs/licences-tierces.md n'est plus l'inventaire réel — le relire, puis :\n"
                "      python scripts/ci/licences_tierces.py --ecrire"
            )
        else:
            print("  ✓ docs/licences-tierces.md est l'inventaire réel.")

    for e in echecs:
        print(f"\n✗ {e}", file=sys.stderr)
    if echecs:
        return 1
    if reserves_jugement or reserves_document:
        return 2
    print("✓ Toutes les licences sont admises ou couvertes par une exception qui sert.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
