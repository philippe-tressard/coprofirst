"""La 0301 lie le nom du logiciel et son code source dans les mentions légales, et rien d'autre.

À retirer après la MEP qui applique la 0301 (`feedback_tests_migrations_appliquees`) :
les garde-fous génériques des migrations restent.
"""

from __future__ import annotations

from types import SimpleNamespace

from sqlmodel import Session

from app.models.core import ConfigSite
from app.seed.contenus_legaux import DEFAULT_LEGAL, PHRASE_CODE_SOURCE, PHRASE_SERVI_PAR
from app.utils.plateforme import DEPOT_SOURCE, NOM_PLATEFORME, SITE_PLATEFORME
from tests.aides_migrations import charger_migration

MIGRATION = charger_migration("0301")
PROPRE = "<p>Un passage propre à cette instance.</p>"
AVANT = [avant for _cle, avant, _apres in MIGRATION.REMPLACEMENTS]
ANCIEN_TEXTE = PROPRE + "".join(AVANT) + PROPRE
NOUVEAU_TEXTE = PROPRE + PHRASE_SERVI_PAR + PHRASE_CODE_SOURCE + PROPRE


def _jouer(session: Session, sens: str) -> None:
    MIGRATION.op = SimpleNamespace(get_bind=session.connection)
    getattr(MIGRATION, sens)()
    session.commit()


def _poser(session: Session, valeur: str) -> None:
    session.add(ConfigSite(cle="mentions_legales", valeur=valeur))
    session.commit()


def _lire(session: Session) -> str:
    session.expire_all()
    return session.get(ConfigSite, "mentions_legales").valeur


def test_les_phrases_sont_remplacees_quand_elles_figurent_telles_quelles(session: Session):
    _poser(session, ANCIEN_TEXTE)
    _jouer(session, "upgrade")
    texte = _lire(session)
    assert all(avant not in texte for avant in AVANT)
    assert texte == NOUVEAU_TEXTE


def test_le_nom_porte_le_lien_du_site_et_code_source_celui_du_depot():
    """Les adresses viennent de `utils/plateforme`, aucune n'est affichée en clair."""
    assert (
        f'<a href="{SITE_PLATEFORME}" target="_blank" rel="noopener noreferrer">{NOM_PLATEFORME}</a>'
        in PHRASE_SERVI_PAR
    )
    assert (
        f'<a href="{DEPOT_SOURCE}" target="_blank" rel="noopener noreferrer">code source</a>'
        in PHRASE_CODE_SOURCE
    )
    for phrase in (PHRASE_SERVI_PAR, PHRASE_CODE_SOURCE):
        assert "https://" not in phrase.replace(f'href="{SITE_PLATEFORME}"', "").replace(
            f'href="{DEPOT_SOURCE}"', ""
        )
    assert PHRASE_SERVI_PAR in DEFAULT_LEGAL["mentions_legales"]
    assert PHRASE_CODE_SOURCE in DEFAULT_LEGAL["mentions_legales"]


def test_le_nom_n_est_pas_repete_dans_le_paragraphe():
    mentions = DEFAULT_LEGAL["mentions_legales"]
    paragraphe = mentions[mentions.index(PHRASE_SERVI_PAR) :]
    paragraphe = paragraphe[: paragraphe.index("</p>")]
    assert paragraphe.count(NOM_PLATEFORME) == 1


def test_un_texte_sans_ces_phrases_ne_bouge_pas(session: Session):
    retouche = PROPRE + "<p>Mentions retouchées depuis Admin.</p>"
    _poser(session, retouche)
    _jouer(session, "upgrade")
    assert _lire(session) == retouche


def test_le_gabarit_ne_porte_plus_les_anciennes_phrases():
    """Cas zéro : le gabarit du produit est déjà à jour, la migration n'a rien à lui faire."""
    assert all(avant not in DEFAULT_LEGAL["mentions_legales"] for avant in AVANT)


def test_le_retour_arriere_rend_les_anciennes_phrases(session: Session):
    _poser(session, ANCIEN_TEXTE)
    _jouer(session, "upgrade")
    _jouer(session, "downgrade")
    assert _lire(session) == ANCIEN_TEXTE
