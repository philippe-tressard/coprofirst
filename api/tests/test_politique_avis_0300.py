"""La 0300 insère la mention des avis dans la politique servie, une fois (#2075).

Le texte servi vit en base : l'essai pose celui du gabarit SANS la mention, puis
vérifie qu'elle entre après les e-mails transactionnels, qu'elle n'entre pas deux
fois, et qu'un texte retouché (l'ancre absente) ne bouge pas.

À retirer après la MEP qui applique la 0300 (`feedback_tests_migrations_appliquees`) :
les garde-fous génériques des migrations restent.
"""

from __future__ import annotations

from types import SimpleNamespace

from sqlmodel import Session

from app.models.core import ConfigSite
from app.seed.contenus_legaux import DEFAULT_LEGAL
from app.seed.contenus_legaux_avis import APRES_EMAILS_TRANSACTIONNELS, AVIS_SITE_PRESENTATION
from tests.aides_migrations import charger_migration

MIGRATION = charger_migration("0300")
CLE = "politique_confidentialite"
SANS_MENTION = DEFAULT_LEGAL[CLE].replace(AVIS_SITE_PRESENTATION, "")


def _jouer(session: Session, sens: str) -> str:
    MIGRATION.op = SimpleNamespace(get_bind=session.connection)
    getattr(MIGRATION, sens)()
    session.commit()
    session.expire_all()
    return session.get(ConfigSite, CLE).valeur


def _poser(session: Session, texte: str) -> None:
    session.add(ConfigSite(cle=CLE, valeur=texte))
    session.commit()


def test_le_gabarit_porte_la_mention_et_son_ancre():
    assert APRES_EMAILS_TRANSACTIONNELS + AVIS_SITE_PRESENTATION in DEFAULT_LEGAL[CLE]


def test_la_mention_entre_apres_les_emails_une_seule_fois(session: Session):
    _poser(session, SANS_MENTION)
    apres = _jouer(session, "upgrade")
    assert apres.count(AVIS_SITE_PRESENTATION) == 1
    assert APRES_EMAILS_TRANSACTIONNELS + AVIS_SITE_PRESENTATION in apres
    assert _jouer(session, "upgrade").count(AVIS_SITE_PRESENTATION) == 1
    assert _jouer(session, "downgrade") == SANS_MENTION


def test_un_texte_retouche_ne_bouge_pas(session: Session):
    retouche = SANS_MENTION.replace(APRES_EMAILS_TRANSACTIONNELS, "<li>Reformulé.</li>")
    _poser(session, retouche)
    assert _jouer(session, "upgrade") == retouche
