"""Une base en avance sur le code ne bloque pas le démarrage (#1756).

`start.sh` lit `app.utils.revision_base` avant `alembic upgrade head` : une base
migrée par une version plus récente — le retour à l'image précédente — se sert
sans migrer, au lieu d'arrêter le conteneur en boucle. Les quatre réponses sont
éprouvées ici sur une base jetable, et `start.sh` est lu pour vérifier qu'il les
emploie comme la table du module le dit.
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.utils.revision_base import ALEMBIC_INI, etat_revision
from tests.aides_base import moteur_de_test

START = Path(__file__).resolve().parents[1] / "start.sh"


def _tete() -> str:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


def _base(revision: str | None) -> str:
    moteur = moteur_de_test(schema=False)
    if revision is not None:
        with moteur.begin() as c:
            c.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            c.execute(text("INSERT INTO alembic_version VALUES (:r)"), {"r": revision})
    return moteur.url.render_as_string(hide_password=False)


def test_une_revision_connue():
    assert etat_revision(_base(_tete())) == "connue"


def test_une_revision_inconnue_est_en_avance():
    assert etat_revision(_base("9999_version_suivante")) == "en_avance"


def test_une_base_neuve_est_vide():
    assert etat_revision(_base(None)) == "vide"


def test_une_lecture_impossible_ne_rend_jamais_un_verdict(tmp_path):
    injoignable = "postgresql+psycopg://personne:x@127.0.0.1:9/aucune?connect_timeout=1"
    assert etat_revision(injoignable) == "inconnu"
    assert etat_revision(_base(_tete()), ini=tmp_path / "absent.ini") == "inconnu"


def test_start_sh_ne_saute_les_migrations_que_si_la_base_est_en_avance():
    #  Le code seul : les commentaires de start.sh racontent pourquoi, et citent
    #  la commande qu'ils expliquent.
    texte = "\n".join(
        ligne
        for ligne in START.read_text(encoding="utf-8").splitlines()
        if not ligne.lstrip().startswith("#")
    )
    assert "python -m app.utils.revision_base" in texte
    assert '"$ETAT_BASE" = "en_avance"' in texte
    #  Toute autre réponse — inconnu compris — migre : on ne devine pas.
    assert texte.count("alembic upgrade head") == 1
    assert texte.index('"$ETAT_BASE" = "en_avance"') < texte.index("alembic upgrade head")
