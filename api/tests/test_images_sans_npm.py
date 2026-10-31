"""Une image Node d'EXÉCUTION n'emporte pas le gestionnaire de paquets (#2377, 31/10/2026).

## Le défaut

La veille nocturne (Trivy, `scripts/ci/veille-securite.sh`) trouvait six HIGH dans
l'image du front et autant dans celle du bridge — `undici` et `brace-expansion` —
alors que `npm audit` était vert : ils ne venaient pas de nos verrous, mais du
**npm livré avec `node:26-alpine`**, qui embarque ses propres dépendances. Aucun
des deux conteneurs ne s'en sert : le front lance `node build`, le bridge
`node index.js`. npm n'y sert qu'à installer, et l'installation est finie.

## Ce que ce test vérifie

Pour chaque service CONSTRUIT (`docker-compose.yml`) dont l'étape finale part de
`node:` :

1. l'étape finale retire npm par la commande canonique `RETRAIT_NPM`, et la fait
   suivre de la preuve qui casse la construction si npm restait
   (`PREUVE`, dans un shell NEUF : celui du `RUN` qui vient de lancer `npm ci`
   garde son chemin en cache et le trouve encore) — le fait, dans l'image ;
2. rien ne l'appelle ensuite : ni une instruction de l'étape, ni `CMD` ou
   `ENTRYPOINT`, ni `command:` ou `healthcheck:` du compose — sinon le conteneur
   ne démarrerait plus.

La commande est recopiée dans deux Dockerfile, et c'est contraint : leurs
contextes de construction (`./front`, `./whatsapp-bridge`) n'ont rien en commun
qu'un fichier partagé puisse servir. Ce test est donc son lieu unique : les deux
copies doivent être la sienne, au caractère près.
"""

from __future__ import annotations

import re

import pytest

from tests.aides_compose import COMPOSE, RACINE, lire_yaml, services_construits

RETRAIT_NPM = (
    "rm -rf /usr/local/lib/node_modules /usr/local/bin/npm /usr/local/bin/npx "
    "/usr/local/bin/corepack /usr/local/bin/yarn /usr/local/bin/yarnpkg /opt/yarn-*"
)
PREUVE = "! sh -c 'command -v npm || command -v npx'"
_APPEL = re.compile(r"(?<![\w/.-])(npm|npx|corepack|yarn)(?![\w-])")


def _instructions(source: str) -> list[tuple[str, str]]:
    """Les instructions d'un Dockerfile, continuations jointes et commentaires ôtés."""
    lignes, courante = [], ""
    for brute in source.replace("\r\n", "\n").split("\n"):
        if brute.lstrip().startswith("#"):
            continue
        if brute.rstrip().endswith("\\"):
            courante += brute.rstrip()[:-1] + " "
            continue
        courante += brute
        if courante.strip():
            lignes.append(courante.strip())
        courante = ""
    return [
        (m.group(1).upper(), m.group(2)) for m in (re.match(r"(\S+)\s*(.*)", x) for x in lignes)
    ]


def _etape_finale(source: str) -> list[tuple[str, str]]:
    instructions = _instructions(source)
    debuts = [i for i, (mot, _) in enumerate(instructions) if mot == "FROM"]
    return instructions[debuts[-1] :] if debuts else []


def _ecarts(source: str, compose: dict | None = None) -> list[str]:
    """Ce qui manque ou ce qui rappelle npm dans l'étape finale (vide : conforme)."""
    etape = _etape_finale(source)
    retrait = next(
        (i for i, (mot, arg) in enumerate(etape) if mot == "RUN" and RETRAIT_NPM in arg), None
    )
    if retrait is None:
        return ["l'étape finale ne retire pas npm (commande RETRAIT_NPM absente)"]
    ecarts = []
    if PREUVE not in etape[retrait][1].split(RETRAIT_NPM, 1)[1]:
        ecarts.append(f"le retrait n'est pas suivi de sa preuve « {PREUVE} »")
    for mot, arg in etape[retrait + 1 :]:
        if mot in ("RUN", "CMD", "ENTRYPOINT", "HEALTHCHECK") and _APPEL.search(arg):
            ecarts.append(f"{mot} {arg} — appelle un gestionnaire de paquets retiré")
    for cle in ("command", "entrypoint", "healthcheck"):
        if compose and compose.get(cle) and _APPEL.search(str(compose[cle])):
            ecarts.append(f"compose `{cle}` : {compose[cle]} — appelle npm, retiré de l'image")
    return ecarts


def _services_node() -> dict[str, str]:
    """Service → Dockerfile, pour chaque image construite dont l'étape finale part de node:."""
    retenus = {}
    for nom, (_, fichier) in services_construits().items():
        source = (RACINE / fichier).read_text(encoding="utf-8")
        etape = _etape_finale(source)
        image = (
            next((t for t in etape[0][1].split() if not t.startswith("--")), "") if etape else ""
        )
        if image.startswith("node:"):
            retenus[nom] = fichier
    return retenus


def test_les_images_node_sont_trouvees():
    """Cas zéro : un contrôle qui ne trouve aucune image Node n'a rien jugé."""
    assert {"front", "whatsapp-bridge"} <= set(_services_node()), _services_node()


@pytest.mark.parametrize("service", sorted(_services_node()))
def test_l_image_d_execution_n_emporte_pas_npm(service):
    fichier = _services_node()[service]
    compose = lire_yaml(COMPOSE)["services"][service]
    ecarts = _ecarts((RACINE / fichier).read_text(encoding="utf-8"), compose)
    assert not ecarts, f"{fichier} : " + " ; ".join(ecarts)


def test_le_controle_refuse_les_cas_fautifs():
    """Le contrôle lui-même : chaque cas fautif est vu, le cas conforme passe."""
    base = "FROM node:26-alpine AS builder\nRUN npm ci\nFROM node:26-alpine\n"
    conforme = (
        base
        + f'RUN apk add x \\\r\n    && {RETRAIT_NPM} \\\n    && {PREUVE}\nCMD ["node", "build"]\n'
    )
    assert _ecarts(conforme) == []
    assert _ecarts(base + 'CMD ["node", "build"]\n'), "étape finale sans retrait"
    assert _ecarts(base + f"RUN {RETRAIT_NPM}\n"), "retrait sans preuve"
    assert _ecarts(conforme + "RUN npm run migrer\n"), "npm rappelé après le retrait"
    assert _ecarts(conforme.replace('CMD ["node", "build"]', 'CMD ["npm", "start"]'))
    assert _ecarts(conforme, {"healthcheck": {"test": ["CMD", "npx", "x"]}})
    #  Le retrait dans l'étape `builder` seule ne compte pas.
    assert _ecarts(
        f"FROM node:26-alpine AS b\nRUN {RETRAIT_NPM} && {PREUVE}\nFROM node:26-alpine\n"
    )
