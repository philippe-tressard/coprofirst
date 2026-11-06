"""La 0327 pose la phrase des messages à classer dans un texte repris par l'éditeur (#2555).

Constaté au post-check de v3.69.0 : la 0326 ne reconnaissait que la forme du gabarit,
et la politique servie — reprise par l'éditeur — n'avait pas changé. L'essai pose la
forme de l'éditeur, vérifie le remplacement, l'aller-retour, et qu'un texte reformulé
ne bouge pas. Le PREMIER test compare l'ancienne phrase de la migration à l'ancienne
phrase du gabarit mise en forme d'éditeur : une faute de frappe dans ANCIEN ferait un
remplacement qui n'a jamais lieu, en silence.

À retirer après la MEP qui applique la 0327 (`feedback_tests_migrations_appliquees`).
"""

from __future__ import annotations

from types import SimpleNamespace

from sqlmodel import Session

from app.models.core import ConfigSite
from app.seed.contenus_legaux import CONSERVATION_RELEVES
from tests.aides_migrations import charger_migration

MIGRATION = charger_migration("0327")
MIGRATION_0326 = charger_migration("0326")
CLE = "politique_confidentialite"
AUTOUR = ("<ul><li><p>Avant.</p></li>", "<li><p>Après.</p></li></ul>")


def _jouer(session: Session, sens: str) -> str:
    MIGRATION.op = SimpleNamespace(get_bind=session.connection)
    getattr(MIGRATION, sens)()
    session.commit()
    session.expire_all()
    return session.get(ConfigSite, CLE).valeur


def _poser(session: Session, texte: str) -> None:
    session.add(ConfigSite(cle=CLE, valeur=texte))
    session.commit()


def test_l_ancienne_phrase_est_celle_du_gabarit_reprise_par_l_editeur():
    assert MIGRATION.ANCIEN == MIGRATION.forme_editeur(MIGRATION_0326.ANCIEN)


def test_la_forme_de_l_editeur_recoit_la_phrase_neuve(session: Session):
    avant = AUTOUR[0] + MIGRATION.ANCIEN + AUTOUR[1]
    _poser(session, avant)
    apres = _jouer(session, "upgrade")
    assert MIGRATION.forme_editeur(CONSERVATION_RELEVES) in apres
    assert MIGRATION.ANCIEN not in apres
    assert _jouer(session, "upgrade") == apres
    assert _jouer(session, "downgrade") == avant


def test_un_texte_reformule_ne_bouge_pas(session: Session):
    retouche = AUTOUR[0] + "<li><p>Journal reformulé.</p></li>" + AUTOUR[1]
    _poser(session, retouche)
    assert _jouer(session, "upgrade") == retouche
