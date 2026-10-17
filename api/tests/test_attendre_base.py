"""`start.sh` attend la base et ne migre jamais une base qu'il n'a pas pu lire (#1759, DI-7).

Le serveur de base peut démarrer après l'API ; la migrer pendant qu'il est
injoignable laissait `alembic upgrade head` atteindre une base vide, une seconde
plus tard, sans schéma posé.
"""

from __future__ import annotations


from app.utils.attendre_base import attendre
from tests.aides_base import url_des_tests


def test_une_base_qui_repond_rend_vrai():
    assert attendre(url_des_tests(), delai=5) is True


def test_une_base_injoignable_rend_faux_au_bout_du_delai():
    url = "postgresql+psycopg://personne:x@127.0.0.1:9/aucune?connect_timeout=1"
    assert attendre(url, delai=0.5, pas=0.1) is False


#  L'ordre que `start.sh` suivait (attendre, en avance, schéma initial, migrer) vit
#  dans `app/utils/preparer_bases` depuis #2053, et s'éprouve sur son COMPORTEMENT :
#  `tests/test_preparer_bases.py`.
