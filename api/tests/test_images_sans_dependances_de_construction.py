"""Une image Node d'EXÉCUTION n'emporte pas ses dépendances de construction (#3061).

## Le défaut (24/11/2026)

`front/Dockerfile` installait tout par `npm ci` dans `builder`, construisait, puis
copiait le `node_modules` ENTIER dans l'étape finale : vite, lightningcss, svelte,
eslint… partaient dans une image publique (`ghcr.io`), alors que `node build` ne
les charge jamais — adapter-node les a fondues dans `build/`. 336 paquets au lieu
de 24 : une surface que Trivy juge pour rien, et lightningcss (MPL-2.0)
redistribué sans servir (#3058).

## Ce que ce test vérifie

Pour chaque image construite dont l'étape finale part de `node:` (`services_node`),
les `node_modules` qui ARRIVENT dans l'étape finale sont élagués des dépendances de
développement :

- installés dans l'étape finale : son `npm ci` porte `--omit=dev` (le bridge) ;
- copiés d'une autre étape (`COPY --from=<étape> … node_modules`) : dans cette
  étape, la DERNIÈRE commande npm qui touche l'arbre (`ci`, `install`, `prune`)
  porte `--omit=dev`, et vient après `npm run build` (le front).

Une image qui n'a aucun `node_modules` d'où qu'il vienne est un INCONNU, pas un
succès : ce contrôle ne saurait pas ce qu'il juge.
"""

from __future__ import annotations

import re

import pytest

from tests.aides_compose import RACINE, etape_finale, etapes, services_node

_ARBRE = re.compile(r"\bnpm\s+(ci|install|i|prune)\b")
_BUILD = re.compile(r"\bnpm\s+run\s+build\b")
_COPIE = re.compile(r"--from=(\S+)\s.*\bnode_modules\b")


def _elague(instructions: list[tuple[str, str]]) -> str | None:
    """L'écart de l'étape qui PRODUIT node_modules (None : élagué après la construction)."""
    rangs = [i for i, (mot, arg) in enumerate(instructions) if mot == "RUN" and _ARBRE.search(arg)]
    if not rangs:
        return "aucune commande npm n'y installe node_modules"
    dernier = instructions[rangs[-1]][1]
    if "--omit=dev" not in dernier:
        return f"sa dernière commande npm (« {dernier} ») ne porte pas --omit=dev"
    construit = [i for i, (mot, arg) in enumerate(instructions) if _BUILD.search(arg)]
    if construit and construit[-1] > rangs[-1]:
        return "l'élagage précède `npm run build`, qui en a besoin : il serait refait à l'envers"
    return None


def _ecarts(source: str) -> list[str]:
    """Ce qui fait entrer des dépendances de construction dans l'étape finale (vide : conforme)."""
    finale = etape_finale(source)
    par_nom = dict(etapes(source))
    copies = [m.group(1) for mot, arg in finale if mot == "COPY" and (m := _COPIE.search(arg))]
    installe = any(mot == "RUN" and _ARBRE.search(arg) for mot, arg in finale)
    if not copies and not installe:
        return ["INCONNU : l'étape finale ne reçoit node_modules ni par npm ni par une copie"]
    ecarts = []
    if installe and (ecart := _elague(finale)):
        ecarts.append(f"étape finale : {ecart}")
    for origine in copies:
        if origine not in par_nom:
            ecarts.append(f"COPY --from={origine} : étape introuvable")
        elif ecart := _elague(par_nom[origine]):
            ecarts.append(f"node_modules copié de « {origine} » : {ecart}")
    return ecarts


def test_les_images_node_sont_trouvees():
    """Cas zéro : un contrôle qui ne trouve aucune image Node n'a rien jugé."""
    assert {"front", "whatsapp-bridge"} <= set(services_node()), services_node()


@pytest.mark.parametrize("service", sorted(services_node()))
def test_l_image_d_execution_n_emporte_pas_la_construction(service):
    fichier = services_node()[service]
    ecarts = _ecarts((RACINE / fichier).read_text(encoding="utf-8"))
    assert not ecarts, f"{fichier} : " + " ; ".join(ecarts)


def test_le_controle_refuse_les_cas_fautifs():
    """Le contrôle lui-même : chaque cas fautif est vu, les deux formes conformes passent."""
    constructeur = "FROM node:26-alpine AS builder\nRUN npm ci\nCOPY . .\nRUN npm run build\n"
    finale = "FROM node:26-alpine\nCOPY --from=builder /app/node_modules ./node_modules\n"
    conforme = constructeur + "RUN npm prune --omit=dev \\\n    --legacy-peer-deps\n" + finale
    assert _ecarts(conforme) == []
    assert _ecarts("FROM node:26-alpine\nRUN npm ci --omit=dev && rm -rf x\n") == []
    #  Le défaut de #3061 : tout le node_modules du constructeur, tel quel.
    assert _ecarts(constructeur + finale)
    #  Installé dans l'étape finale sans --omit=dev.
    assert _ecarts("FROM node:26-alpine\nRUN npm ci\n")
    #  Élagué AVANT la construction : la construction réinstalle ou casse.
    assert _ecarts(
        "FROM node:26-alpine AS builder\nRUN npm ci --omit=dev\nRUN npm run build\n" + finale
    )
    #  Élagué, puis réinstallé en entier.
    assert _ecarts(conforme.replace(finale, "RUN npm install\n" + finale))
    #  Copié d'une étape qui n'existe pas.
    assert _ecarts(constructeur + finale.replace("builder", "absente"))
    #  Rien ne dit d'où vient node_modules : INCONNU, jamais OK.
    assert _ecarts('FROM node:26-alpine\nCMD ["node", "build"]\n')
