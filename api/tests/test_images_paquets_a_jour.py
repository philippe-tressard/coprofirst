"""L'étape d'EXÉCUTION de chaque image construite met à jour les paquets de son système (#2543, 05/11/2026).

## Le défaut

La veille nocturne (Trivy, `scripts/ci/veille-securite.sh`) a trouvé deux HIGH dans
l'image de l'API — CVE-2026-109518, `apt` et `libapt-pkg7.0` en 3.0.3, corrigés en
3.0.4 — alors que les trois images Alpine (front, bridge, Caddy) restaient vertes :
elles font `apk upgrade` à leur étape d'exécution depuis #2377, et l'image Debian
de l'API se contentait d'`apt-get install`. Une image de base officielle retarde
sur les correctifs de sa distribution : l'installation seule n'y prend que ce qui
manque, jamais la version corrigée de ce qui est déjà là.

## Ce que ce test vérifie

Pour chaque service CONSTRUIT (`docker-compose.yml`), l'étape finale contient une
instruction `RUN` qui met à jour les paquets de son système : `apk upgrade` sur
Alpine, `apt-get upgrade` sur Debian. Une étape finale dont le gestionnaire ne se
reconnaît pas est refusée : un contrôle qui ne sait pas juger ne dit pas « OK ».
"""

from __future__ import annotations

import re

import pytest

from tests.aides_compose import RACINE, etape_finale, services_construits

#  Le gestionnaire de paquets d'une étape se reconnaît à ce qu'elle installe déjà.
_GESTIONNAIRES = {
    "apk": (re.compile(r"\bapk\s+(add|upgrade)\b"), re.compile(r"\bapk\s+upgrade\b")),
    "apt": (
        re.compile(r"\bapt(-get)?\s+(install|upgrade)\b"),
        re.compile(r"\bapt(-get)?\s+(-\S+\s+)*upgrade\b"),
    ),
}


def _ecarts(source: str) -> list[str]:
    """Ce qui manque à l'étape finale pour que son système soit à jour (vide : conforme)."""
    runs = [arg for mot, arg in etape_finale(source) if mot == "RUN"]
    connus = [
        nom
        for nom, (installe, _) in _GESTIONNAIRES.items()
        if any(installe.search(r) for r in runs)
    ]
    if not connus:
        return [
            "l'étape finale n'installe rien par apk ni par apt : son gestionnaire ne se juge pas"
        ]
    return [
        f"l'étape finale installe par {nom} sans mettre à jour ses paquets ({nom} upgrade absent)"
        for nom in connus
        if not any(_GESTIONNAIRES[nom][1].search(r) for r in runs)
    ]


def _services() -> dict[str, str]:
    return {nom: fichier for nom, (_, fichier) in services_construits().items()}


def test_les_images_construites_sont_trouvees():
    """Cas zéro : un contrôle qui ne trouve pas les quatre images n'a rien jugé."""
    assert {"api", "front", "whatsapp-bridge", "caddy"} <= set(_services()), _services()


@pytest.mark.parametrize("service", sorted(_services()))
def test_l_image_d_execution_met_a_jour_son_systeme(service):
    fichier = _services()[service]
    ecarts = _ecarts((RACINE / fichier).read_text(encoding="utf-8"))
    assert not ecarts, f"{fichier} : " + " ; ".join(ecarts)


def test_le_controle_refuse_les_cas_fautifs():
    """Le contrôle lui-même : chaque cas fautif est vu, le cas conforme passe."""
    debian = "FROM python:3.12-slim AS b\nRUN apt-get update && apt-get upgrade -y\nFROM python:3.12-slim\n"
    assert (
        _ecarts(
            debian + "RUN apt-get update && apt-get upgrade -y \\\n && apt-get install -y curl\n"
        )
        == []
    )
    assert _ecarts(debian + "RUN apt-get update && apt-get install -y curl\n"), (
        "Debian sans upgrade"
    )
    assert _ecarts("FROM node:26-alpine\nRUN apk upgrade --no-cache && apk add tzdata\n") == []
    assert _ecarts("FROM node:26-alpine\nRUN apk add --no-cache tzdata\n"), "Alpine sans upgrade"
    #  La mise à jour dans l'étape `b` seule ne compte pas, et une étape muette ne se juge pas.
    assert _ecarts(debian + "COPY . /app\n"), "étape finale sans gestionnaire reconnu"
