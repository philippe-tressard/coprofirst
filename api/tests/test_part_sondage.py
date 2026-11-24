"""La part d'une option de sondage est SERVIE par l'API, avec l'arrondi de l'écran (#3060).

Le site calculait le pourcentage dans `ResultatsSondage` (`Math.round`), et les apps
l'auraient recalculé chacune de son côté. La fiche le sert maintenant (`part`), par
`utils/pourcentages.part_en_pourcent`, sous la même décision que `nb_votes`
(`test_resultats_sondage.py` le tient).
"""

import pytest

from app.models.communaute import OptionSondage, Sondage, VoteSondage
from app.routers.sondages.crud import get_sondage
from app.utils.pourcentages import part_en_pourcent
from tests.aides_base import compte
from tests.aides_sondage import base  # noqa: F401


@pytest.mark.parametrize(
    "nombre, total, attendu, pourquoi",
    [
        (1, 8, 13, "12,5 : demi au SUPÉRIEUR, comme Math.round (round() de Python dirait 12)"),
        (5, 8, 63, "62,5 : idem (round() dirait 62)"),
        (1, 3, 33, "33,3"),
        (2, 3, 67, "66,7"),
        (3, 3, 100, "tout le monde"),
        (0, 3, 0, "personne pour cette option"),
        (0, 0, 0, "aucun vote : 0, jamais une division par zéro"),
    ],
)
def test_arrondi(nombre, total, attendu, pourquoi):
    assert part_en_pourcent(nombre, total) == attendu, pourquoi


def _fiche_votee(session, *, resultats_publics: bool) -> dict:
    """Un sondage à deux options, deux votes pour la première, un pour la seconde."""
    cs = compte(session, prefixe="cs", roles_json="conseil_syndical")
    sondage = Sondage(auteur_id=cs.id, question="Peinture ?", resultats_publics=resultats_publics)
    session.add(sondage)
    session.commit()
    options = [
        OptionSondage(sondage_id=sondage.id, libelle=libelle, ordre=i)
        for i, libelle in enumerate(("Beige", "Gris"))
    ]
    session.add_all(options)
    session.commit()
    for option in (options[0], options[0], options[1]):
        votant = compte(session, prefixe="votant")
        session.add(VoteSondage(sondage_id=sondage.id, option_id=option.id, user_id=votant.id))
    session.commit()
    return get_sondage(sondage_id=sondage.id, session=session, user=cs)


def test_la_fiche_sert_la_part_de_chaque_option(base):
    fiche = _fiche_votee(base, resultats_publics=True)
    assert [(o["libelle"], o["nb_votes"], o["part"]) for o in fiche["options"]] == [
        ("Beige", 2, 67),
        ("Gris", 1, 33),
    ]


def test_resultats_masques_aucune_part(base):
    """Sondage ouvert, résultats réservés à la clôture : la part ne part pas non plus."""
    fiche = _fiche_votee(base, resultats_publics=False)
    assert fiche["resultats_visibles"] is False
    assert all("part" not in o for o in fiche["options"])
