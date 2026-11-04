"""Le libellé du logement est servi par l'API, et le front ne le compose plus (#2500).

## Ce qui a mené ici (03/11/2026)

La règle vivait dans `front/src/lib/utils.ts::libelleLogement`. L'app iOS lit la
même API et n'avait pas le libellé : elle aurait dû recopier la règle, et elle
n'affichait rien. La règle est passée côté serveur, à l'identique, et chaque cas
de l'ancienne fonction a ici son test. Qu'elle ne revienne pas dans le front, une
seconde écriture qui divergerait au premier cas limite, est tenu par
`npm run lint:regles-partagees` (#2501), avec les autres règles partagées.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.copropriete import Lot
from app.models.core import Batiment, Copropriete, TypeLien, UserLot
from app.utils.lecture_utilisateur import construire_user_read
from app.utils.logement import libelle_logement
from tests.aides_base import compte


def _lot(type_="appartement", *, batiment=None, type_appartement=None, etage=None):
    return SimpleNamespace(
        type=type_, batiment=batiment, type_appartement=type_appartement, etage=etage
    )


_BAT_D = SimpleNamespace(numero="D")


@pytest.mark.parametrize(
    "lots,batiment_compte,etage_compte,attendu",
    [
        #  Le cas nominal : le lot dit tout.
        (
            [_lot(batiment=_BAT_D, type_appartement="T3", etage=2)],
            "Bât. A",
            None,
            "Bât. D, T3, 2ème",
        ),
        #  Le lot sans bâtiment prend celui du compte.
        ([_lot(type_appartement="T2", etage=1)], "Bât. A", None, "Bât. A, T2, 1er"),
        #  🔴 `0` est le rez-de-chaussée — un test de vérité l'effacerait.
        ([_lot(batiment=_BAT_D, etage=0)], "", None, "Bât. D, RDC"),
        #  Le PREMIER appartement fait le libellé ; une cave ne le dispute pas.
        (
            [
                _lot("cave", batiment=_BAT_D, etage=-1),
                _lot(type_appartement="T4", etage=3),
                _lot(type_appartement="T1", etage=5),
            ],
            "Bât. B",
            None,
            "Bât. B, T4, 3ème",
        ),
        #  Un appartement dont on ne sait rien : rien à dire, sans repli sur le compte.
        ([_lot()], "", 4, ""),
        #  Sans appartement : le repli sur le COMPTE, et son séparateur propre.
        ([], "Bât. C", 2, "Bât. C — sans lot — 2ème"),
        ([_lot("parking", batiment=_BAT_D)], "Bât. C", None, "Bât. C — sans lot"),
        ([], "", 0, "sans lot — RDC"),
        #  Ni bâtiment ni étage : « sans lot » tout seul est un reproche.
        ([], "", None, ""),
    ],
    ids=[
        "lot-complet",
        "batiment-du-compte",
        "rdc",
        "premier-appartement",
        "appartement-muet",
        "sans-lot-complet",
        "parking-seul",
        "sans-lot-rdc",
        "rien",
    ],
)
def test_la_regle(lots, batiment_compte, etage_compte, attendu):
    assert libelle_logement(lots, batiment_compte, etage_compte) == attendu


def _batiment(session, numero: str) -> Batiment:
    copro = Copropriete(nom="Test", adresse="1 rue Test")
    session.add(copro)
    session.flush()
    bat = Batiment(copropriete_id=copro.id, numero=numero)
    session.add(bat)
    session.commit()
    session.refresh(bat)
    return bat


def _rattacher(session, user, lot: Lot, *, actif=True) -> None:
    session.add(lot)
    session.flush()
    session.add(
        UserLot(user_id=user.id, lot_id=lot.id, type_lien=TypeLien.propriétaire, actif=actif)
    )
    session.commit()


def test_la_lecture_de_son_compte_le_rend(session):
    """🔴 Le cas zéro : le champ arrive bien dans la réponse de `/auth/me`."""
    bat = _batiment(session, "A")
    user = compte(session, prefixe="logement")
    _rattacher(
        session,
        user,
        Lot(numero="31", type="appartement", batiment_id=bat.id, type_appartement="T3", etage=2),
    )
    assert construire_user_read(user, session).libelle_logement == "Bât. A, T3, 2ème"


def test_un_lien_INACTIF_ne_fait_pas_le_logement(session):
    """Les lots d'un compte sont ceux de `lots_de` : un lien clos n'en est plus un."""
    bat = _batiment(session, "B")
    user = compte(session, prefixe="logement", batiment_id=bat.id, etage=0)
    _rattacher(session, user, Lot(numero="32", type="appartement", etage=4), actif=False)
    assert construire_user_read(user, session).libelle_logement == "Bât. B — sans lot — RDC"


def test_rien_a_dire_rend_None(session):
    user = compte(session, prefixe="logement")
    assert construire_user_read(user, session).libelle_logement is None
