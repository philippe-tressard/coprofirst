"""Supprimer un compte laisse le contenu collectif — l'auteur devient facultatif (#1688, #1821)

Arbitrage du 10/10/2026, qui inverse celui du 28/08 (« le contenu part avec le
compte ») : une affaire, son fil et ses messages sont un contenu COLLECTIF — la
mémoire de la copropriété, le carnet d'entretien. Supprimer le compte de qui les
a écrits (l'administration aujourd'hui, la purge des comptes inactifs demain)
les emportait, réponses des autres comprises. Ils restent désormais, l'auteur
remplacé par « Ancien résident » (`utils/noms.nom_auteur`).

La règle tient dans le SCHÉMA : la purge référentielle supprime une ligne dont
la référence au compte est obligatoire, et délie une référence facultative.
Cette migration rend facultative la référence au compte de chaque contenu GARDÉ
— la liste et la raison de chacun se lisent dans `utils/suppression_compte.
CONTENUS_GARDES`, et `test_references_au_compte_declarees.py` tient la
concordance. Les affaires, leur fil et leurs messages (#1688) ; puis (#1821)
les documents, diagnostics, règles de la résidence, annonces de hall, sondages
et leurs votes, idées et leurs soutiens, réponses de la Communauté, notes des
prestataires, évènements, et qui a créé une délégation. Une liste RECOPIÉE ici,
et non importée : une migration appliquée ne doit pas changer quand le code
évolue.

Et la politique servie le dit (`ANONYMISATION_CONTENUS`, lue dans le seed),
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

#: (table, colonne) — identifiants : constantes du fichier.
COLONNES = (
    ("ticket", "auteur_id"),
    ("message_ticket", "auteur_id"),
    ("ticket_evolution", "auteur_id"),
    ("evenement", "auteur_id"),
    ("evenement_evolution", "auteur_id"),
    ("document", "publie_par_id"),
    ("diagnostic_rapport", "publie_par_id"),
    ("regle_residence", "cree_par_id"),
    ("annonce_hall", "auteur_id"),
    ("sondage", "auteur_id"),
    ("vote_sondage", "user_id"),
    ("commentaire_sondage", "auteur_id"),
    ("idee", "auteur_id"),
    ("vote_idee", "user_id"),
    ("reponse_communaute", "auteur_id"),
    ("notation_prestataire", "auteur_id"),
    ("delegation", "cree_par_id"),
)
POLITIQUE = "politique_confidentialite"


def _facultative(conn, table: str, colonne: str) -> bool | None:
    """`None` si la table ou la colonne manque — rien à faire."""
    if table not in set(sa.inspect(conn).get_table_names()):
        return None
    for c in sa.inspect(conn).get_columns(table):
        if c["name"] == colonne:
            return bool(c["nullable"])
    return None


def _politique(sens: int) -> None:
    from app.seed.contenus_legaux import ANONYMISATION_CONTENUS, CONSERVATION_COMPTES
    from app.utils.textes_livres import remplacer_passage

    conn = op.get_bind()
    if "config_site" not in set(sa.inspect(conn).get_table_names()):
        return
    avant, apres = CONSERVATION_COMPTES, CONSERVATION_COMPTES + ANONYMISATION_CONTENUS
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
    for table, colonne in COLONNES:
        if _facultative(conn, table, colonne) is False:
            with op.batch_alter_table(table) as lot:
                lot.alter_column(colonne, existing_type=sa.Integer(), nullable=True)
    _politique(+1)


def downgrade() -> None:
    _politique(-1)
    conn = op.get_bind()
    for table, colonne in COLONNES:
        if _facultative(conn, table, colonne) is not True:
            continue
        t = sa.table(table, sa.column(colonne))
        orphelines = conn.execute(
            sa.select(sa.func.count()).select_from(t).where(t.c[colonne].is_(None))
        ).scalar()
        if orphelines:
            raise RuntimeError(
                f"{table} : {orphelines} ligne(s) sans auteur (comptes supprimés) — "
                "le retour arrière n'invente pas d'auteur."
            )
        with op.batch_alter_table(table) as lot:
            lot.alter_column(colonne, existing_type=sa.Integer(), nullable=False)
