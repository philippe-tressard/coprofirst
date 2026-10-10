"""Supprimer un compte laisse ses affaires — l'auteur devient facultatif (#1688)

Arbitrage du 10/10/2026, qui inverse celui du 28/08 (« le contenu part avec le
compte ») : une affaire, son fil et ses messages sont un contenu COLLECTIF — la
mémoire de la copropriété, le carnet d'entretien. Supprimer le compte de qui les
a écrits (l'administration aujourd'hui, la purge des comptes inactifs demain)
les emportait, réponses des autres comprises. Ils restent désormais, l'auteur
remplacé par « Ancien résident » (`utils/noms.nom_auteur`).

La règle tient dans le SCHÉMA : la purge référentielle supprime une ligne dont
la référence au compte est obligatoire, et délie une référence facultative.
Cette migration rend facultatif `auteur_id` sur les quatre tables d'un fil :

- `ticket`, `message_ticket` ;
- `ticket_evolution` et `evenement_evolution`, qui partagent `EvolutionMixin`.

Et la politique servie le dit (`ANONYMISATION_AFFAIRES`, lue dans le seed),
posée juste après le passage de conservation des comptes — sauf si
l'administration l'a reformulé : elle y reporte alors la règle elle-même.

## Compatible avec la version précédente (#1757)

Rendre une colonne facultative est un ASSOUPLISSEMENT : l'ancien code écrit
toujours un auteur, et lit les lignes existantes, qui en ont toutes un.

## Comment

`batch_alter_table` : un `ALTER COLUMN … DROP NOT NULL` sous PostgreSQL (la
production), une recopie de la table sous SQLite, qui ne sait pas modifier une
contrainte en place — sans danger ici, le contexte d'Alembic ne pose pas
`foreign_keys=ON` (même geste que la 0213). Idempotente : une colonne déjà
facultative n'est pas touchée. Le retour arrière la rend obligatoire de nouveau
et ÉCHOUE si une ligne n'a plus d'auteur, plutôt que d'en inventer un.

⚠️ Les noms de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0276
Revises: 0275
"""

import sqlalchemy as sa

from alembic import op

revision = "0276"
down_revision = "0275"
branch_labels = None
depends_on = None

TABLES = ("ticket", "message_ticket", "ticket_evolution", "evenement_evolution")
COLONNE = "auteur_id"  # identifiants : constantes du fichier
POLITIQUE = "politique_confidentialite"


def _facultative(conn, table: str) -> bool | None:
    """`None` si la table ou la colonne manque — rien à faire."""
    if table not in set(sa.inspect(conn).get_table_names()):
        return None
    for c in sa.inspect(conn).get_columns(table):
        if c["name"] == COLONNE:
            return bool(c["nullable"])
    return None


def _politique(sens: int) -> None:
    from app.seed.contenus_legaux import ANONYMISATION_AFFAIRES, CONSERVATION_COMPTES
    from app.utils.textes_livres import remplacer_passage

    conn = op.get_bind()
    if "config_site" not in set(sa.inspect(conn).get_table_names()):
        return
    avant, apres = CONSERVATION_COMPTES, CONSERVATION_COMPTES + ANONYMISATION_AFFAIRES
    if sens < 0:
        avant, apres = apres, avant
    elif apres in (
        conn.execute(
            sa.text("SELECT valeur FROM config_site WHERE cle = :cle").bindparams(cle=POLITIQUE)
        ).scalar()
        or ""
    ):
        return  # déjà posée : la rejouer la doublerait
    remplacer_passage(conn, "config_site", {"cle": POLITIQUE}, "valeur", avant, apres)


def upgrade() -> None:
    conn = op.get_bind()
    for table in TABLES:
        if _facultative(conn, table) is False:
            with op.batch_alter_table(table) as lot:
                lot.alter_column(COLONNE, existing_type=sa.Integer(), nullable=True)
    _politique(+1)


def downgrade() -> None:
    _politique(-1)
    conn = op.get_bind()
    for table in TABLES:
        if _facultative(conn, table) is not True:
            continue
        t = sa.table(table, sa.column(COLONNE))
        orphelines = conn.execute(
            sa.select(sa.func.count()).select_from(t).where(t.c[COLONNE].is_(None))
        ).scalar()
        if orphelines:
            raise RuntimeError(
                f"{table} : {orphelines} ligne(s) sans auteur (comptes supprimés) — "
                "le retour arrière n'invente pas d'auteur."
            )
        with op.batch_alter_table(table) as lot:
            lot.alter_column(COLONNE, existing_type=sa.Integer(), nullable=False)
