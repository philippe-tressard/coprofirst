"""Aucun conteneur ne sert en root — et le contrôle regarde le FAIT, pas le mot.

## Le défaut (#769, audit du 05/09/2026)

`api/Dockerfile` et `front/Dockerfile` ne posaient aucun `USER` : les deux
conteneurs s'exécutaient en **root**. Un défaut d'exécution — rendu PDF,
dépendance compromise, désérialisation — donnait alors root sur le volume de
données. Le confinement Docker ne sépare rien quand le processus est root.

🔴 Le front CRÉAIT DÉJÀ l'utilisateur (`adduser -S app`) et ne s'en servait
jamais. C'est le pire des trois états : un `grep adduser` rassurait, et rien ne
protégeait. Un compte créé mais jamais endossé ne donne que l'air.

## Ce que ce test vérifie, et pourquoi pas simplement « USER est présent »

L'API ne PEUT PAS poser `USER` dans son Dockerfile : ses trois volumes sont
écrits par root sur les deux nœuds, et un conteneur qui démarrerait directement
en `app` ne pourrait plus y écrire. Elle bascule donc dans `start.sh`,
après avoir repris les propriétés.

Exiger le mot `USER` aurait donc refusé la seule solution qui marche, et poussé
à la contourner. Le test demande le FAIT — « ce conteneur finit-il par quitter
root ? » — et accepte les deux formes, en vérifiant pour chacune ce qui la rend
vraie.
"""

from __future__ import annotations

import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]


def _lire(chemin: str) -> str:
    fichier = _RACINE / chemin
    assert fichier.exists(), f"{chemin} introuvable — le contrôle a perdu sa portée"
    return fichier.read_text(encoding="utf-8")


def test_le_front_endosse_l_utilisateur_qu_il_cree():
    """`adduser` sans `USER` : le compte existe, le serveur reste root."""
    source = _lire("front/Dockerfile")
    assert re.search(r"\badduser\b", source), (
        "l'utilisateur applicatif du front a disparu du Dockerfile"
    )
    assert re.search(r"^\s*USER\s+app\s*$", source, re.M), (
        "front/Dockerfile crée un utilisateur `app` mais ne l'endosse pas : "
        "le serveur SSR tourne en root. Ajouter `USER app` avant `CMD`."
    )


def test_l_api_bascule_hors_de_root_avant_d_ecrire():
    """L'API ne peut pas poser `USER` — elle doit donc basculer dans `start.sh`.

    Trois choses sont exigées, et chacune répare une moitié du geste :

    1. l'utilisateur existe (`useradd`) ;
    2. `start.sh` reprend les propriétés des volumes — sans quoi le processus
       non-root ne pourrait pas écrire dans des volumes écrits par root ;
    3. il se relance en `app` **avant** Alembic : ce qui s'exécute ensuite ne
       tourne jamais en root.
    """
    dockerfile = _lire("api/Dockerfile")
    assert re.search(r"\buseradd\b.*\bapp\b", dockerfile), (
        "api/Dockerfile ne crée plus d'utilisateur applicatif"
    )

    start = _lire("api/start.sh")
    assert "chown -R app:app" in start, (
        "start.sh ne reprend plus les propriétés des volumes : un conteneur "
        "non-root ne pourra pas écrire dans ses volumes, écrits par root."
    )
    bascule = re.search(r"^\s*exec setpriv .*--reuid=app\b.*$", start, re.M)
    assert bascule, (
        "start.sh ne bascule plus hors de root : l'API sert en root, ce que #769 corrigeait."
    )
    alembic = re.search(r"^\s*alembic upgrade head\s*$", start, re.M)
    assert alembic, "start.sh ne lance plus les migrations"
    assert bascule.start() < alembic.start(), (
        "les migrations tournent AVANT la bascule : elles s'exécuteraient en root."
    )
