"""La 0330 pose la puce des notifications sur téléphone là où la 0329 n'a pas pu (#2495).

Constaté au post-check de v3.80.0 (10/11/2026) : la référence a renseigné sa puce
« Réception des courriels » (le prestataire nommé) ; la 0329, qui posait la puce après
elle, n'a rien trouvé — alors qu'elle passait l'intitulé à « Cinq fonctions ». La
politique servie annonçait cinq services tiers et en listait quatre.

La 0330 ancre la puce sur la FIN de la liste (`</ul><h2>5. Durée de conservation</h2>`),
qu'aucune reformulation d'une puce ne déplace, et la pose sous la forme de son
voisinage. L'essai rejoue le texte tel que la référence le sert.

À retirer après la MEP qui applique la 0330 (`feedback_tests_migrations_appliquees`).
"""

from __future__ import annotations

from types import SimpleNamespace

from sqlmodel import Session

from app.models.core import ConfigSite
from app.seed.contenus_legaux_notifications import NOTIFICATIONS_PUSH
from app.utils.textes_livres import forme_editeur
from tests.aides_migrations import charger_migration

MIGRATION = charger_migration("0330")
CLE = "politique_confidentialite"
RECEPTION_RENSEIGNEE = (
    "<li><p><strong>Réception des courriels</strong> — les réponses arrivent dans une "
    "boîte hébergée chez un prestataire nommé.</p></li>"
)


def _servi(puce_reception: str, *, avec_push: str = "") -> str:
    return (
        "<p>Cinq fonctions font passer des informations</p><ul>"
        + puce_reception
        + avec_push
        + "</ul><h2>5. Durée de conservation</h2><ul><li><p>Comptes.</p></li></ul>"
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


def test_la_puce_arrive_en_fin_de_liste_sous_la_forme_de_l_editeur(session: Session):
    avant = _servi(RECEPTION_RENSEIGNEE)
    _poser(session, avant)
    apres = _jouer(session, "upgrade")
    assert RECEPTION_RENSEIGNEE + forme_editeur(NOTIFICATIONS_PUSH) + "</ul><h2>5." in apres
    assert _jouer(session, "upgrade") == apres, "une seconde passe écrit deux fois"
    assert _jouer(session, "downgrade") == avant


def test_la_forme_du_gabarit_recoit_la_forme_du_gabarit(session: Session):
    gabarit = _servi("<li><strong>Réception des courriels</strong> — texte.</li>").replace(
        "<li><p>Comptes.</p></li>", "<li>Comptes.</li>"
    )
    _poser(session, gabarit)
    apres = _jouer(session, "upgrade")
    assert NOTIFICATIONS_PUSH + "</ul><h2>5." in apres


def test_une_puce_deja_posee_par_la_0329_ne_double_pas(session: Session):
    deja = _servi(RECEPTION_RENSEIGNEE, avec_push=forme_editeur(NOTIFICATIONS_PUSH))
    _poser(session, deja)
    assert _jouer(session, "upgrade") == deja


def test_un_texte_sans_l_ancre_ne_bouge_pas(session: Session):
    retouche = "<h2>5. Conservation (reformulé)</h2>"
    _poser(session, retouche)
    assert _jouer(session, "upgrade") == retouche
