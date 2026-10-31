"""Autotest des fonctions de décision de `licences_tierces.py` (`--selftest`).

Chaque cas est choisi pour échouer si la ligne qu'il éprouve disparaissait
(`standards/04` §46) : le OR qui offre un choix, le AND qui cumule, l'exception
qui ne couvre qu'une licence PRÉCISE, celle qui ne sert plus, et le cas zéro.
"""

from __future__ import annotations

import json
import pathlib
import tempfile

from licences_image import etapes, juger
from licences_inventaire import Inconnu, decider_hors_poste, paquets_npm
from licences_spdx import admise, identifiants, licence_python

ADMISES = frozenset({"MIT", "Apache-2.0", "BSD-3-Clause"})
EXC = (
    {"source": "bridge", "paquets": ("libsignal",), "licences": ("GPL-3.0",)},
    {"source": "bridge", "paquets": ("@img/sharp-*",), "licences": ("LGPL-3.0-or-later",)},
)


class _Politique:
    """La politique des images, réduite à un cas de chaque règle."""

    BIBLIOTHEQUES_SYSTEME = ({"dockerfile": "D", "paquets": ("libheif1",)},)
    INTERDITS_DANS_LES_IMAGES = {"*x265*": "GPLv2"}
    ROUES_A_COMPILER = {"pillow-heif": {"dockerfile": "D", "exigences": "R", "raison": "-"}}


_DOCKERFILE = (
    "FROM a AS heif\n"
    "RUN apt-get update && apt-get install -y --no-install-recommends \\\n"
    "    libheif-dev && rm -rf x\n"
    "# apt-get install libheif-plugin-x265 (un commentaire ne s'installe pas)\n"
    "RUN pip wheel --no-binary pillow-heif x\n"
    "FROM a\n"
    "RUN apt-get install -y --no-install-recommends curl libheif1\n"
    "RUN PIP_NO_BINARY=pillow-heif pip install -r requirements.txt\n"
)


def _images(t) -> None:
    """`licences_image` : chaque règle refuse son cas fautif, et le conforme passe."""
    regles, ok = _Politique(), {"R": "pillow-heif==1.8.1\n"}
    t(
        "images — étapes lues, commentaire ignoré",
        etapes(_DOCKERFILE),
        [["libheif-dev"], ["curl", "libheif1"]],
    )
    t("images — Dockerfile conforme", juger({"D": _DOCKERFILE}, ok, regles), [])
    fautes = {
        "x265 installé": _DOCKERFILE.replace("curl", "libheif-plugin-x265"),
        "recommandés admis": _DOCKERFILE.replace(" --no-install-recommends curl", " curl"),
        "déclaré non installé": _DOCKERFILE.replace(" libheif1\n", "\n"),
        "roue PyPI admise": _DOCKERFILE.replace("--no-binary pillow-heif", ""),
        "roue revenue par les exigences": _DOCKERFILE.replace("PIP_NO_BINARY=pillow-heif ", ""),
    }
    for nom, texte in fautes.items():
        t(f"images — {nom} : ÉCHOUE", len(juger({"D": texte}, ok, regles)), 1)
    t(
        "images — roue retirée des exigences : l'entrée se retire",
        len(juger({"D": _DOCKERFILE}, {"R": ""}, regles)),
        1,
    )
    t("images — cas zéro : Dockerfile absent", len(juger({}, ok, regles)), 3)


def _hors_poste(t) -> None:
    """`LICENCES_HORS_POSTE` : servir sur le poste, être vérifiée sur Linux, se retirer."""
    table = {"uvloop": {"licence": "MIT", "date": "2026-10-02", "raison": "-"}}
    image, poste = {"uvicorn", "uvloop"}, {"uvicorn"}
    r, n, e, reste = decider_hors_poste(table, image, poste, {"uvicorn": "BSD"}, {"uvloop"})
    t(
        "hors poste — Windows : licence déclarée retenue",
        (r, len(e), reste),
        ({"uvloop": "MIT"}, 0, set()),
    )
    t("hors poste — Windows : la sortie le dit", "vérifiée par la CI" in n[0], True)
    r, n, e, reste = decider_hors_poste({}, image, poste, {}, {"uvloop"})
    t("hors poste — sans entrée : reste absente (INCONNU)", reste, {"uvloop"})
    r, n, e, reste = decider_hors_poste(table, image, poste, {"uvloop": "MIT"}, set())
    t("hors poste — Linux : licence lue conforme", (r, e), ({}, []))
    _, _, e, _ = decider_hors_poste(table, image, poste, {"uvloop": "GPL-3.0"}, set())
    t("hors poste — Linux : déclaration fausse ÉCHOUE", len(e), 1)
    _, _, e, _ = decider_hors_poste(table, {"uvicorn"}, poste, {}, set())
    t("hors poste — paquet sorti de l'image : entrée inutile", len(e), 1)
    _, _, e, reste = decider_hors_poste(table, image, image, {}, {"uvloop"})
    t(
        "hors poste — installable sur le poste : entrée inutile, absence réelle",
        (len(e), reste),
        (1, {"uvloop"}),
    )


def lancer(confronter, exceptions_inutiles) -> int:
    cas: list[tuple[str, object, object]] = []

    def t(nom: str, obtenu, attendu) -> None:
        cas.append((nom, obtenu, attendu))

    t("admise — identifiant simple", admise("MIT", ADMISES), True)
    t("admise — copyleft refusé", admise("GPL-3.0", ADMISES), False)
    t("admise — OR : un choix suffit", admise("(MPL-2.0 OR Apache-2.0)", ADMISES), True)
    t("admise — AND : tout est exigé", admise("Apache-2.0 AND LGPL-3.0-or-later", ADMISES), False)
    t("admise — AND admis", admise("MIT AND BSD-3-Clause", ADMISES), True)
    t("admise — priorité AND sur OR", admise("GPL-3.0 AND MIT OR Apache-2.0", ADMISES), True)
    t("admise — WITH jamais d'office", admise("Apache-2.0 WITH LLVM-exception", ADMISES), False)
    t("admise — illisible refusé", admise("MIT | GPL (classifieurs multiples)", ADMISES), False)
    t("admise — parenthèse ouverte", admise("(MIT OR Apache-2.0", ADMISES), False)
    t("admise — vide refusé", admise("", ADMISES), False)
    t(
        "identifiants — sans opérateur ni WITH",
        sorted(identifiants("(ISC AND MIT) OR Apache-2.0 WITH LLVM-exception")),
        ["Apache-2.0", "ISC", "MIT"],
    )
    t(
        "python — License-Expression prime",
        licence_python("MIT", "BSD", []),
        ("MIT", "License-Expression"),
    )
    t(
        "python — champ court, alias",
        licence_python(None, "Apache License, Version 2.0", [])[0],
        "Apache-2.0",
    )
    t(
        "python — texte intégral ignoré",
        licence_python(
            None,
            "Copyright (c) X\nPermission is hereby granted",
            ["License :: OSI Approved :: MIT License"],
        )[0],
        "MIT",
    )
    t(
        "python — classifieurs multiples jamais admis",
        admise(licence_python(None, "", ["License :: A", "License :: B"])[0], ADMISES),
        False,
    )
    t("python — rien de lisible", licence_python(None, None, [])[0], "NON DÉTERMINÉE")

    gpl = [{"nom": "libsignal", "licence": "GPL-3.0"}, {"nom": "express", "licence": "MIT"}]
    e, tol, s = confronter("bridge", gpl, (), ADMISES)
    t("confronter — copyleft sans exception échoue", len(e), 1)
    e, tol, s = confronter("bridge", gpl, EXC, ADMISES)
    t("confronter — exception nominative couvre", (len(e), len(tol)), (0, 1))
    e, _, _ = confronter("bridge", [{"nom": "libsignal", "licence": "AGPL-3.0"}], EXC, ADMISES)
    t("confronter — licence changée : l'exception ne couvre plus", len(e), 1)
    e, _, _ = confronter("front", gpl, EXC, ADMISES)
    t("confronter — exception d'une autre source ne couvre pas", len(e), 1)
    e, _, s2 = confronter(
        "bridge", [{"nom": "@img/sharp-libvips-x", "licence": "LGPL-3.0-or-later"}], EXC, ADMISES
    )
    t("confronter — motif *", len(e), 0)
    t("inutiles — tout sert", exceptions_inutiles(EXC, s | s2, {"bridge"}), [])
    t(
        "inutiles — une exception qui ne sert plus échoue",
        len(exceptions_inutiles(EXC, s, {"bridge"})),
        1,
    )
    t("inutiles — source INCONNUE : rien conclu", exceptions_inutiles(EXC, set(), set()), [])
    _, _, s0 = confronter("bridge", [], EXC, ADMISES)
    t(
        "cas zéro — inventaire vide : toutes les exceptions sont inutiles",
        len(exceptions_inutiles(EXC, s0, {"bridge"})),
        2,
    )

    with tempfile.TemporaryDirectory() as d:
        verrou = pathlib.Path(d) / "package-lock.json"
        verrou.write_text(
            json.dumps({"lockfileVersion": 3, "packages": {"": {}}}), encoding="utf-8"
        )
        t("cas zéro — verrou sans paquet rend une liste vide", paquets_npm(verrou), [])
        verrou.write_text(json.dumps({"lockfileVersion": 1, "dependencies": {}}), encoding="utf-8")
        try:
            paquets_npm(verrou)
            t("verrou v1 — INCONNU", "aucune exception", "Inconnu")
        except Inconnu:
            t("verrou v1 — INCONNU", "Inconnu", "Inconnu")
        verrou.write_text(
            json.dumps({"lockfileVersion": 3, "packages": {"node_modules/a": {"version": "1"}}}),
            encoding="utf-8",
        )
        t(
            "verrou — licence absente déclarée comme telle",
            paquets_npm(verrou)[0]["licence"],
            "NON DÉCLARÉE",
        )

    _hors_poste(t)
    _images(t)
    ko = [(n, o, a) for n, o, a in cas if o != a]
    for n, o, a in ko:
        print(f"✗ {n} : obtenu {o!r}, attendu {a!r}")
    signe = "✗" if ko else "✓"
    print(f"{signe} autotest des licences tierces — {len(cas) - len(ko)}/{len(cas)} cas.")
    return 1 if ko else 0
