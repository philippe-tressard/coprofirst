"""Ce qu'un badge ouvre quand personne ne l'a dit : la règle `acces_deduit` (#953).

La même décision se prend à la création par le conseil syndical et à la
résolution d'une ligne d'import ; elle s'écrit une fois, et ce fichier l'exerce.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import ProgrammingError

#  ⚠️ L'import des modèles n'est pas décoratif : les relations entre modèles se
#  résolvent par leur NOM, à la première requête. Le fichier qui tournait seul en
#  tête de sa tranche ne chargeait que `Perimetre`, et la fixture ci-dessous
#  échouait sur « name 'ContratEntretien' is not defined ». `app.models.core`
#  charge tous les modules (`test_modeles_enregistres.py`).
import app.models.core  # noqa: F401
from app.utils.acces_perimetre import acces_deduit, code_batiment


@pytest.fixture(autouse=True)
def sans_arbre():
    """🔴 Ces cas portent sur le REPLI, donc sur un arbre vide — et ça se pose.

    Depuis le 15/09/2026, `code_batiment` lit l'arbre avant de fabriquer `bat:3`
    (pour que la déduction et la liste d'accès autorisés parlent des mêmes
    codes). L'arbre est un **état de module**, partagé par toute la suite : un
    fichier exécuté avant celui-ci pouvait le laisser chargé, et ces tests-là
    échouaient alors sans rien avoir à se reprocher — c'est arrivé à l'écriture
    de `test_acces_choix.py`.

    Le vider ici rend la condition visible au lieu de la supposer.
    """
    from app import contexte
    from app.utils.perimetres import invalider_cache
    from tests.aides_purge import vider_perimetres

    invalider_cache()
    try:
        with contexte.nouvelle_session() as s:
            vider_perimetres(s)
    except ProgrammingError:
        pass  # la table n'existe pas encore : l'arbre est vide, c'est l'état voulu
    invalider_cache()
    yield
    invalider_cache()


@pytest.mark.parametrize(
    "batiments,attendu",
    [
        ([2], ["bat:2"]),
        ([2, 2, 2], ["bat:2"]),
        ([7, 7], ["bat:7"]),
        ([2, 3], None),
        ([], None),
        ([None], None),
        ([2, None], ["bat:2"]),
    ],
)
def test_la_regle_en_python(batiments, attendu):
    """Ici les entrées SONT des identifiants : la fonction n'en connaît pas d'autres."""
    assert acces_deduit(batiments) == attendu


def test_le_code_dun_batiment():
    assert code_batiment(4) == "bat:4"
