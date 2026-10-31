#!/usr/bin/env python3
"""La libheif de l'image : décoder le HEIC, sans jamais embarquer x265 (#2389).

## Pourquoi

Les roues PyPI de `pillow-heif` embarquent libx265, l'ENCODEUR HEVC, sous GPLv2 ;
l'image de l'API est distribuée publiquement (ghcr.io). Le site ne fait que
décoder : `api/Dockerfile` compile le module contre la libheif de Debian, avec le
seul greffon libde265 (LGPL-3.0+). Les métadonnées du paquet disent
« BSD-3-Clause » dans les deux cas : l'inventaire des licences ne voit pas la
différence, seule l'image construite la montre.

## Ce qu'il exige, sur l'image même (amd64 et arm64, CI ou secours d'un nœud)

  1. aucun paquet Debian ni aucun fichier dont le nom porte « x265 » ;
  2. le module `_pillow_heif` lié à la libheif du système, et aucune
     bibliothèque de roue embarquée (`pillow_heif.libs`) ;
  3. aucun encodeur HEVC annoncé par libheif, et le décodeur libde265 présent ;
  4. la photo HEIC témoin décodée, à sa taille.

Un contrôle qui ne PEUT pas s'exécuter (dpkg muet, `ldd` absent, aucun fichier
parcouru) échoue aussi : une construction verte est une mesure, jamais une absence
de mesure (`standards/04` §2). Sa sortie est la preuve écrite au journal de
construction.

Usage : python -I scripts/verifier_heif.py <photo.heic>   (0 = conforme, 1 = non)
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

#: Taille de `tests/donnees/photo.heic`, la photo témoin (produite sur le poste,
#: hors de l'image, par l'encodeur des roues PyPI).
TAILLE_TEMOIN = (640, 480)

#: Où chercher un fichier qui nommerait x265 : tout ce qu'un paquet ou une roue
#: peut déposer.
RACINES = ("/usr", "/lib", "/opt")

INTERDIT = "x265"

#: `libheif.so.1 => /lib/<triplet>/libheif.so.1` — Debian fusionne /lib et /usr/lib.
#: Une roue PyPI la lierait sous `site-packages`, avec un suffixe d'empreinte.
_LIBHEIF_DU_SYSTEME = re.compile(r"^\s*libheif\.so\.\d+ => (/usr)?/lib/", re.MULTILINE)


def constats(
    paquets: list[str],
    fichiers_interdits: list[str],
    fichiers_parcourus: int,
    ldd: str | None,
    libs_embarquees: bool,
    info: dict,
    taille: tuple[int, int] | None,
) -> list[str]:
    """Les manquements, en clair ; vide = conforme. PURE."""
    echecs = []
    if not paquets:
        echecs.append("dpkg ne liste aucun paquet : contrôle impossible")
    echecs += [f"paquet Debian {p}" for p in paquets if INTERDIT in p.lower()]
    if fichiers_parcourus == 0:
        echecs.append("aucun fichier parcouru : contrôle impossible")
    echecs += [f"fichier {f}" for f in fichiers_interdits]
    if ldd is None:
        echecs.append("ldd n'a pas pu s'exécuter sur le module : contrôle impossible")
    elif not _LIBHEIF_DU_SYSTEME.search(ldd):
        echecs.append("le module n'est pas lié à la libheif du système (/lib, /usr/lib)")
    if libs_embarquees:
        echecs.append("bibliothèques de roue embarquées (pillow_heif.libs) : roue PyPI installée")
    encodeurs = [str(v) for v in (info.get("encoders") or {}).values()]
    hevc = [e for e in [info.get("HEIF"), *encodeurs] if e and ("265" in e or "HEVC" in e)]
    echecs += [f"encodeur HEVC annoncé par libheif : {e}" for e in dict.fromkeys(hevc)]
    if "libde265" not in (info.get("decoders") or {}):
        echecs.append("décodeur libde265 absent : le HEIC ne se lirait pas")
    if taille != TAILLE_TEMOIN:
        echecs.append(f"photo témoin décodée en {taille}, attendue en {TAILLE_TEMOIN}")
    return echecs


def _paquets() -> list[str]:
    try:
        sortie = subprocess.run(
            ["dpkg-query", "-W", "-f", "${Package}\n"], capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [p for p in sortie.splitlines() if p]


def _fichiers() -> tuple[list[str], int]:
    interdits, parcourus = [], 0
    for racine in RACINES:
        for dossier, sous, noms in os.walk(racine):
            for nom in [*sous, *noms]:
                parcourus += 1
                if INTERDIT in nom.lower():
                    interdits.append(os.path.join(dossier, nom))
    return interdits, parcourus


def _ldd(module: str) -> str | None:
    try:
        return subprocess.run(["ldd", module], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 1
    import _pillow_heif  # l'extension C, module de premier niveau
    import pillow_heif
    from PIL import Image

    pillow_heif.register_heif_opener()
    paquets = _paquets()
    interdits, parcourus = _fichiers()
    ldd = _ldd(_pillow_heif.__file__)
    libs = (pathlib.Path(pillow_heif.__file__).parent.parent / "pillow_heif.libs").exists()
    info = pillow_heif.libheif_info()
    try:
        with Image.open(argv[0]) as photo:
            photo.load()
            taille = photo.size
    except Exception as exc:  # noqa: BLE001 — toute erreur de lecture vaut « non décodée »
        print(f"  photo témoin illisible : {exc}", file=sys.stderr)
        taille = None

    print("Vérification HEIC de l'image (#2389)")
    print(f"  {len(paquets)} paquets Debian, {parcourus} fichiers parcourus sous {RACINES}")
    print(f"  libheif {info.get('libheif')} — décodeurs {sorted(info.get('decoders') or {})}")
    print(
        f"  encodeurs {sorted(info.get('encoders') or {})} — HEVC : {info.get('HEIF') or 'aucun'}"
    )
    print(f"  module {_pillow_heif.__file__}")
    for ligne in (ldd or "").splitlines():
        if "heif" in ligne or "de265" in ligne:
            print(f"    {ligne.strip()}")
    print(f"  photo témoin {argv[0]} : {taille}")

    echecs = constats(paquets, interdits, parcourus, ldd, libs, info, taille)
    for e in echecs:
        print(f"✗ {e}", file=sys.stderr)
    if echecs:
        return 1
    print("✓ HEIC décodé par libheif + libde265 (LGPL), aucun x265 dans l'image.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
