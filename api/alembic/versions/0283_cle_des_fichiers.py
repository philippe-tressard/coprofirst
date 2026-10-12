"""Le document, le rapport de diagnostic et l'affiche gardent la CLÉ de leur fichier (#1816)

Chantier multi-copropriétés, suite de P2-6 (#1748, spec §4.4). Trois colonnes
gardaient le chemin ABSOLU écrit sur le disque du conteneur
(`/app/uploads/prive/<nom>`) : un chemin n'a pas de sens dans un stockage objet,
et il change si le volume est monté ailleurs. Chaque table reçoit la clé du
stockage (`prive/<nom>`, `annonces-hall/<nom>`), et les lignes existantes la
reçoivent ici.

Additive : trois colonnes nullables, que l'image précédente ignore (règle #1757,
`test_migrations_compatibles.py`). Le chemin reste écrit le temps d'une version,
pour qu'un retour à l'image précédente le relise ; son retrait est un second
temps (`CONTRACTIONS`).

La clé se DÉDUIT du chemin, sans la racine du volume — une migration ne lit pas
la configuration : ses deux derniers segments, quand l'avant-dernier est l'un
des dossiers où ces fichiers s'écrivent. Relevé en production le 12/10/2026 :
30 documents et 14 rapports sous `…/prive/`, une affiche sous
`…/annonces-hall/`, aucun ailleurs. Une ligne qui n'y répondrait pas garde une
clé vide, et se relit par son chemin, borné (`stockage().cle_de`).

Idempotente : `start.sh` a `set -e`, et un redémarrage après une migration
interrompue la rejoue — une colonne déjà présente est laissée telle quelle, une
clé déjà posée n'est pas recalculée.

⚠️ Les noms de table et de colonne sont des CONSTANTES du fichier ; les
requêtes passent par `sa.table`, sans SQL composé.

Revision ID: 0283
Revises: 0282
"""

from pathlib import PurePosixPath

import sqlalchemy as sa

from alembic import op

revision = "0283"
down_revision = "0282"
branch_labels = None
depends_on = None

#: (table, colonne de la clé, colonne du chemin) — identifiants : constantes du fichier.
COLONNES = (
    ("document", "fichier_cle", "fichier_chemin"),
    ("diagnostic_rapport", "fichier_cle", "fichier_chemin"),
    ("annonce_hall", "pdf_cle", "pdf_chemin"),
)

#: Les dossiers où ces fichiers s'écrivent : `DOSSIER_PRIVE` et `DOSSIER_PDF`,
#: recopiés — une migration appliquée ne suit pas le code qui évolue.
DOSSIERS = frozenset({"prive", "annonces-hall"})


def cle_du_chemin(chemin: object) -> str | None:
    """`/app/uploads/prive/a.pdf` → `prive/a.pdf` ; `None` hors des dossiers connus."""
    if not isinstance(chemin, str) or not chemin:
        return None
    parties = PurePosixPath(chemin.replace("\\", "/")).parts
    if len(parties) < 2 or parties[-2] not in DOSSIERS or parties[-1] in ("", ".", ".."):
        return None
    return "/".join(parties[-2:])


def _colonnes(conn, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(table)}


def upgrade():
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    for table, cle, chemin in COLONNES:
        if table not in tables:
            continue
        if cle not in _colonnes(conn, table):
            op.add_column(table, sa.Column(cle, sa.String, nullable=True))
        t = sa.table(table, sa.column("id"), sa.column(cle), sa.column(chemin))
        lignes = conn.execute(sa.select(t.c.id, t.c[chemin]).where(t.c[cle].is_(None))).fetchall()
        for identifiant, valeur in lignes:
            deduite = cle_du_chemin(valeur)
            if deduite is not None:
                conn.execute(t.update().where(t.c.id == identifiant).values({cle: deduite}))


def downgrade():
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    for table, cle, _chemin in COLONNES:
        if table in tables and cle in _colonnes(conn, table):
            with op.batch_alter_table(table) as batch:
                batch.drop_column(cle)
