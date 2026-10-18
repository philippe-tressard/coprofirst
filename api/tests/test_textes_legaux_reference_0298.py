"""La 0298 corrige les trois écarts des textes de la référence, et rien d'autre (#2069).

Le texte de la référence vit en base, il n'est pas dans le dépôt : l'essai pose un
texte qui porte chacun des passages fautifs, au milieu d'un contenu propre à
l'instance, et vérifie qu'ils partent — et que le reste demeure. Un texte qui ne
les a jamais eus (une copropriété neuve, le gabarit) ne bouge pas.

À retirer après la MEP qui applique la 0298 (`feedback_tests_migrations_appliquees`) :
les garde-fous génériques des migrations restent.
"""

from __future__ import annotations

from types import SimpleNamespace

from sqlmodel import Session

from app.models.core import ConfigSite
from app.seed.contenus_legaux import DEFAULT_LEGAL
from app.utils.plateforme import LICENCE_URL, NOM_PLATEFORME
from tests.aides_migrations import charger_migration

MIGRATION = charger_migration("0298")
PROPRE = "<p>Un passage propre à cette instance.</p>"


def _jouer(session: Session, sens: str) -> None:
    MIGRATION.op = SimpleNamespace(get_bind=session.connection)
    getattr(MIGRATION, sens)()
    session.commit()


def _poser(session: Session) -> dict[str, str]:
    textes: dict[str, str] = {}
    for cle, avant, _apres in MIGRATION.REMPLACEMENTS:
        textes[cle] = textes.get(cle, PROPRE) + avant + PROPRE
    for cle, valeur in textes.items():
        session.add(ConfigSite(cle=cle, valeur=valeur))
    session.commit()
    return textes


def _lire(session: Session, cle: str) -> str:
    session.expire_all()
    return session.get(ConfigSite, cle).valeur


def test_les_trois_ecarts_partent_et_le_reste_demeure(session: Session):
    _poser(session)
    _jouer(session, "upgrade")
    mentions = _lire(session, "mentions_legales")
    politique = _lire(session, "politique_confidentialite")
    for cle, avant, _apres in MIGRATION.REMPLACEMENTS:
        assert avant not in _lire(session, cle), avant[:60]
    assert "conseil syndical de la copropriété</strong>" not in mentions + politique
    assert "<strong>l'administrateur du site</strong>" in politique
    assert "<strong>L'administrateur du site</strong>" in mentions
    assert "président du conseil syndical" not in mentions
    assert "CoproConnect" not in mentions and f"servi par {NOM_PLATEFORME}," in mentions
    assert LICENCE_URL in mentions
    assert "anonymisées" not in politique
    assert PROPRE in mentions and PROPRE in politique


def test_le_retour_arriere_rend_ce_qui_a_ete_remplace(session: Session):
    textes = _poser(session)
    _jouer(session, "upgrade")
    _jouer(session, "downgrade")
    for cle, avant, apres in MIGRATION.REMPLACEMENTS:
        if apres:
            assert avant in _lire(session, cle), avant[:60]
    #  Les passages retirés ne reviennent pas (sans ancre) : c'est dit dans la migration.
    assert _lire(session, "politique_confidentialite") != textes["politique_confidentialite"]


def test_un_texte_sans_ces_passages_ne_bouge_pas(session: Session):
    for cle in ("mentions_legales", "politique_confidentialite"):
        session.add(ConfigSite(cle=cle, valeur=DEFAULT_LEGAL[cle]))
    session.commit()
    _jouer(session, "upgrade")
    for cle in ("mentions_legales", "politique_confidentialite"):
        assert _lire(session, cle) == DEFAULT_LEGAL[cle]


def test_le_gabarit_ne_porte_aucun_des_passages_fautifs():
    """Cas zéro du sens inverse : le gabarit du produit est déjà juste."""
    gabarit = DEFAULT_LEGAL["mentions_legales"] + DEFAULT_LEGAL["politique_confidentialite"]
    for _cle, avant, _apres in MIGRATION.REMPLACEMENTS:
        assert avant not in gabarit, avant[:60]
