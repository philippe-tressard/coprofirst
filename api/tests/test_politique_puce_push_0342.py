"""La 0342 fait nommer Google et FCM à la puce des notifications sur téléphone (#2789).

La production sert la puce sous la forme de l'éditeur d'Admin › Pages légales (constaté
le 16/11/2026 sur `GET /api/config/legal`) ; l'essai rejoue les deux formes, et un texte
reformulé, qui ne change pas.

À retirer après la MEP qui applique la 0342 (`feedback_tests_migrations_appliquees`).
"""

from __future__ import annotations

from types import SimpleNamespace

from sqlmodel import Session

from app.models.core import ConfigSite
from app.seed.contenus_legaux_notifications import NOTIFICATIONS_PUSH
from app.utils.textes_livres import forme_editeur
from tests.aides_migrations import charger_migration

MIGRATION = charger_migration("0342")
CLE = "politique_confidentialite"


def _jouer(session: Session, texte: str, sens: str = "upgrade") -> str:
    ligne = session.get(ConfigSite, CLE)
    if ligne is None:
        ligne = ConfigSite(cle=CLE, valeur=texte)
    ligne.valeur = texte
    session.add(ligne)
    session.commit()
    MIGRATION.op = SimpleNamespace(get_bind=session.connection)
    getattr(MIGRATION, sens)()
    session.commit()
    session.expire_all()
    return session.get(ConfigSite, CLE).valeur


def test_la_puce_de_l_editeur_nomme_google_et_revient_en_arriere(session: Session):
    avant = "<ul>" + forme_editeur(MIGRATION.ANCIENNE) + "</ul>"
    apres = _jouer(session, avant)
    assert apres == "<ul>" + forme_editeur(NOTIFICATIONS_PUSH) + "</ul>"
    assert "Firebase Cloud Messaging" in apres
    assert _jouer(session, apres, "downgrade") == avant


def test_la_puce_du_gabarit_aussi(session: Session):
    assert (
        _jouer(session, "<ul>" + MIGRATION.ANCIENNE + "</ul>") == f"<ul>{NOTIFICATIONS_PUSH}</ul>"
    )


def test_un_texte_reformule_ne_change_pas(session: Session):
    reformule = "<ul><li><p>Notifications : nous ne transmettons rien.</p></li></ul>"
    assert _jouer(session, reformule) == reformule
