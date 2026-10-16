"""La migration de TÊTE s'exécute : défaite, rejouée, puis rejouée encore (#1496).

## Pourquoi ce test (30/09/2026)

`start.sh` lance `alembic upgrade head` sous `set -e` : une migration qui
explose bloque le conteneur au démarrage. Le test qui l'exécutait était FIGÉ
sur la 0157 — quatre-vingt-cinq migrations plus tard, il rejouait toujours la
même, et son cas zéro passait quoi qu'il arrive : la dernière migration écrite
n'était exécutée par aucun test.

Celui-ci ne nomme aucune révision. Il lit la tête dans le graphe d'Alembic, la
charge, et joue sur une base au schéma courant `downgrade()`, `upgrade()`, puis
`upgrade()` une seconde fois — l'idempotence, puisqu'un redémarrage après une
migration interrompue la rejoue (`CLAUDE.md`, 0117 et 0165).

## Sa limite, écrite (`standards/04` §12)

Il ne couvre que la TÊTE, et sur une base VIDE au schéma de `create_all` : pas
une base réelle à l'état N-1, avec ses lignes et ses écarts de schéma. Une
migration de données y passe sans données à transformer — ce qu'elle fait des
lignes se vérifie dans son propre test (`test_migration_<numéro>_*.py`).
Les migrations antérieures ne sont plus rejouées ici dès qu'une autre les suit.
"""

from __future__ import annotations

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from tests import aides_migrations
from tests.aides_base import moteur_de_test


def _tete() -> str:
    """La révision de tête du graphe — lue à l'appel, pour qu'un test puisse la forger."""
    graphe = ScriptDirectory(str(aides_migrations.VERSIONS.parent))
    tetes = graphe.get_heads()
    assert len(tetes) == 1, f"{len(tetes)} têtes de migration : {tetes}"
    return tetes[0]


def _rejouer(revision: str) -> None:
    """Défait la migration, la rejoue, la rejoue encore — chaque pas dans sa transaction."""
    migration = aides_migrations.charger_migration(revision)
    moteur = moteur_de_test()
    for pas in (migration.downgrade, migration.upgrade, migration.upgrade):
        with moteur.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                pas()
    moteur.dispose()


def test_la_migration_de_tete_se_defait_et_se_rejoue():
    _rejouer(_tete())


def test_la_tete_trouvee_est_la_derniere_migration():
    """Cas zéro : la tête est la plus haute révision numérotée, et son fichier existe.

    Sans lui, un graphe mal lu (dossier déplacé, tête prise pour une autre)
    ferait rejouer une vieille migration — le défaut exact de l'ancien test.
    """
    tete = _tete()
    fichiers = sorted(aides_migrations.VERSIONS.glob("[0-9][0-9][0-9][0-9]_*.py"))
    assert fichiers, "le dossier des migrations ne rend rien"
    assert tete == fichiers[-1].name[:4], (
        f"la tête du graphe ({tete}) n'est pas la dernière migration ({fichiers[-1].name})"
    )
    assert aides_migrations.chemin_migration(tete).is_file()


#: Une tête forgée : son `upgrade()` reçoit l'un des corps ci-dessous.
GABARIT = """\
revision = "9999"
down_revision = None
import sqlalchemy as sa
from alembic import op
def upgrade():
    {corps}
def downgrade():
    pass
"""

#: L'une explose ; l'autre ajoute sa colonne sans garde — sa première exécution
#: passe, la seconde lève, comme au redémarrage après une migration interrompue.
#: Le message dépend de la langue du serveur : « already exists » ou « existe déjà ».
FORGEES = {
    "explose": 'raise RuntimeError("migration forgée")',
    "non idempotente": 'op.add_column("utilisateur", sa.Column("forgee", sa.Integer()))',
}


@pytest.mark.parametrize("corps", FORGEES.values(), ids=FORGEES.keys())
def test_le_controle_sait_ECHOUER(corps, tmp_path, monkeypatch):
    """Le test de tête, pointé sur un graphe forgé, échoue — il n'est pas vert à vide."""
    versions = tmp_path / "versions"
    versions.mkdir()
    (versions / "9999_forgee.py").write_text(GABARIT.format(corps=corps), encoding="utf-8")
    monkeypatch.setattr(aides_migrations, "VERSIONS", versions)

    assert _tete() == "9999", "le graphe forgé n'est pas celui que le test lit"
    with pytest.raises(Exception, match="migration forgée|already exists|existe déjà"):
        test_la_migration_de_tete_se_defait_et_se_rejoue()
