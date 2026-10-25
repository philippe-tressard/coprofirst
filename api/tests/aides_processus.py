"""La base d'application d'un processus de tests : qui la pose (#2223).

Chaque processus de la suite — la suite seule, ou chaque worker de `pytest -n` —
reçoit un schéma d'application à lui (`conftest.py`). Un worker hérite pourtant
de l'environnement du maître, `DATABASE_URL` compris : il la prenait pour une
base choisie par l'appelant, et les onze workers écrivaient dans le même schéma
— types créés deux fois, bâtiments déliés, numéros d'affaire épuisés (chacun
tire la même suite), 545 erreurs au premier passage parallèle (24/10/2026).

Sans import du projet : `conftest.py` le lit avant d'importer l'application.
"""

from __future__ import annotations

from collections.abc import Mapping

#: La variable où `conftest.py` note l'adresse qu'il a posée lui-même.
MARQUE = "TESTS_DATABASE_URL_POSEE"


def base_a_poser(environ: Mapping[str, str]) -> bool:
    """Ce processus pose-t-il son propre schéma ? PURE.

    Oui sans `DATABASE_URL`, et oui quand elle n'est que celle qu'un autre
    processus de la suite a posée (le maître, pour son worker). Non quand
    l'appelant l'a choisie : on ne la remplace pas.
    """
    url = environ.get("DATABASE_URL")
    return url is None or url == environ.get(MARQUE)


#: L'adresse d'un serveur de base qui n'existe pas, et qui le dit TOUT DE SUITE (#2223).
#: `127.0.0.1:1` était refusé sur l'instant sous Linux, mais restait pendant sous
#: Windows jusqu'au délai du système : 130 s pour le seul témoin d'une base
#: injoignable (`test_installation_commune_aiguillage`), la plus longue queue de la
#: suite parallèle. `0.0.0.0` est refusé sur l'instant des deux côtés.
SERVEUR_INJOIGNABLE = "0.0.0.0:1"
