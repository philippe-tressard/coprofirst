"""La 0329 pose dans la politique servie ce que deviennent les notifications (#2495, #2535).

Le texte servi existe sous la forme du gabarit et sous celle de l'éditeur
d'Admin › Pages légales (0327) : l'essai pose chacune, vérifie que les deux puces
neuves arrivent à leur place et sous la forme de leur voisinage, qu'une seconde passe
n'écrit pas deux fois, l'aller-retour, et qu'un texte reformulé ne bouge pas.

À retirer après la MEP qui applique la 0329 (`feedback_tests_migrations_appliquees`).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlmodel import Session

from app.models.core import ConfigSite
from app.seed.contenus_legaux import CONSERVATION_RELEVES, FONCTIONS_TIERS, RECEPTION_COURRIELS
from app.seed.contenus_legaux_notifications import (
    CONSERVATION_NOTIFICATIONS,
    NOTIFICATIONS_PUSH,
)
from app.utils.textes_livres import forme_editeur
from tests.aides_migrations import charger_migration

MIGRATION = charger_migration("0329")
CLE = "politique_confidentialite"
SANS_FORME = lambda puce: puce  # noqa: E731 - la forme du gabarit, telle quelle


def _texte(forme) -> str:
    return (
        "<p>"
        + MIGRATION.FONCTIONS_TIERS_QUATRE
        + " — elles le sont au cas par cas</p><h2>4. Destinataires</h2><ul>"
        + forme(RECEPTION_COURRIELS)
        + "</ul><h2>5. Durée de conservation</h2><ul>"
        + forme(CONSERVATION_RELEVES)
        + "</ul><h2>6. Vos droits</h2>"
    )


def _poser(session: Session, texte: str) -> None:
    session.add(ConfigSite(cle=CLE, valeur=texte))
    session.commit()


def _jouer(session: Session, sens: str) -> str:
    MIGRATION.op = SimpleNamespace(get_bind=session.connection)
    getattr(MIGRATION, sens)()
    session.commit()
    session.expire_all()
    return session.get(ConfigSite, CLE).valeur


@pytest.mark.parametrize("forme", [SANS_FORME, forme_editeur], ids=["gabarit", "editeur"])
def test_les_deux_puces_arrivent_a_leur_place(session: Session, forme):
    avant = _texte(forme)
    _poser(session, avant)
    apres = _jouer(session, "upgrade")
    assert FONCTIONS_TIERS in apres and MIGRATION.FONCTIONS_TIERS_QUATRE not in apres
    assert forme(RECEPTION_COURRIELS) + forme(NOTIFICATIONS_PUSH) in apres
    assert forme(CONSERVATION_RELEVES) + forme(CONSERVATION_NOTIFICATIONS) in apres
    assert _jouer(session, "upgrade") == apres, "une seconde passe écrit deux fois"
    assert _jouer(session, "downgrade") == avant


def test_un_texte_reformule_ne_bouge_pas(session: Session):
    retouche = "<ul><li><p>Réception reformulée.</p></li><li><p>Journal reformulé.</p></li></ul>"
    _poser(session, retouche)
    assert _jouer(session, "upgrade") == retouche


def test_le_gabarit_porte_deja_les_deux_puces():
    """Une installation NEUVE reçoit le gabarit : il doit dire la même chose."""
    from app.seed.contenus_legaux import AJOUTS_1034, DEFAULT_LEGAL

    gabarit = DEFAULT_LEGAL[CLE]
    assert RECEPTION_COURRIELS + NOTIFICATIONS_PUSH in gabarit
    assert CONSERVATION_RELEVES + CONSERVATION_NOTIFICATIONS in gabarit
    ajouts = "".join(paragraphe for _, paragraphe in AJOUTS_1034)
    assert NOTIFICATIONS_PUSH in ajouts and CONSERVATION_NOTIFICATIONS in ajouts
