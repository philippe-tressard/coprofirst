"""Le contexte de construction du front n'emporte pas de `node_modules` local (#3032).

Le 23/11/2026, la construction de secours du front a échoué sur un nœud et réussi
sur l'autre : un `front/node_modules` résiduel (ignoré par git, invisible à `git
status`) y était recopié par `COPY . .` APRÈS `npm ci`, par-dessus les dépendances
que l'image venait d'installer. La CI construit depuis un clone propre et ne le
voyait jamais.

Ce test lit `front/.dockerignore` ; le workflow « Contexte du front »
(`.github/workflows/contexte-front.yml`) le prouve sur un vrai `docker build`, le
cas fautif d'abord.
"""

from tests.conftest import racine_depot

RACINE = racine_depot()
#: Ce qui ne doit jamais entrer : dépendances et sorties produites sur la machine.
ECARTES = {"node_modules", ".svelte-kit", "build"}
#: Ce que `npm run build` (`vite build`) lit : jamais écarté.
LUS_PAR_LA_CONSTRUCTION = {"src", "static", "scripts", "vite.config.ts", "package.json"}


def _regles() -> set[str]:
    texte = (RACINE / "front" / ".dockerignore").read_text(encoding="utf-8")
    return {
        ligne.strip().strip("/")
        for ligne in texte.splitlines()
        if ligne.strip() and not ligne.strip().startswith("#")
    }


def test_le_contexte_ecarte_les_dependances_locales():
    assert ECARTES <= _regles(), sorted(ECARTES - _regles())


def test_le_contexte_garde_ce_que_la_construction_lit():
    regles = _regles()
    assert all(not r.startswith("!") for r in regles), "aucune exception attendue ici"
    assert not (regles & LUS_PAR_LA_CONSTRUCTION), sorted(regles & LUS_PAR_LA_CONSTRUCTION)
    assert "*" not in regles and "**" not in regles


def test_le_dockerfile_recopie_bien_le_dossier_apres_npm_ci():
    #  La raison d'être du fichier : si le Dockerfile cessait de faire `COPY . .`
    #  après `npm ci`, ce test le dit, et l'écart se relit.
    dockerfile = (RACINE / "front" / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.index("npm ci") < dockerfile.index("COPY . .")
