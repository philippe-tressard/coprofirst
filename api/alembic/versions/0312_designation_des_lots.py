"""La désignation des lots selon le règlement : circulation, clés de charges, périmètres (#2212, #2213)

Un parking ou une cave est rattaché à la circulation qui le dessert, pas au bâtiment
de son propriétaire (spec `specs/architecture/lots-et-perimetres.md`). Cette migration
pose de quoi le dire, sans rien retirer ni renommer :

- `batiment.lettre_rcp` — la lettre que l'acte donne au bâtiment ;
- `lot.nature`, `lot.numero_usage`, `lot.circulation_perimetre_id` ;
- `perimetre.desserte` — ce qu'un nœud dessert (circulation, caves, stationnement) ;
- les tables `cle_de_charges`, `quote_part_lot`, `lot_perimetre` ;
- la table de passage de l'état descriptif (`import_etat_descriptif`,
  `ligne_etat_descriptif`).

Tout est nullable ou neuf : l'image précédente ignore ces colonnes et ces tables,
revenir en arrière reste un changement d'image (#1757).

Données posées, sur les seules lignes encore vides :
- `lot.nature` déduite de `lot.type` (appartement → logement) ;
- `perimetre.desserte` sur les nœuds que le gabarit du seed pose sous chaque bâtiment
  (`escaliers`, `ascenseur` → circulation ; `caves` → caves) et sur le nœud
  `parking` (stationnement). Les suffixes sont ceux du gabarit À CETTE DATE
  (`seed/patrimoine.GABARIT_BATIMENT`) : le seed les pose désormais lui-même sur une
  base neuve, et l'administration les règle ensuite.

Revision ID: 0312
Revises: 0311
"""

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0312"
down_revision = "0311"
branch_labels = None
depends_on = None

NATURE = sa.Enum("logement", "commerce", "cave", "parking", "divers", name="naturelot")
DESSERTE = sa.Enum("circulation", "caves", "stationnement", name="desserteperimetre")
RELATION = sa.Enum("situe_dans", "desservi_par", name="relationlotperimetre")

#: Les colonnes ajoutées : (table, colonne, type).
COLONNES = (
    ("batiment", "lettre_rcp", sa.String()),
    ("lot", "nature", NATURE),
    ("lot", "numero_usage", sa.String()),
    ("perimetre", "desserte", DESSERTE),
)

#: Le gabarit du seed à cette date — suffixe de code → desserte.
DESSERTES_DU_GABARIT = {"escaliers": "circulation", "ascenseur": "circulation", "caves": "caves"}


def _deja_cree(type_enum: sa.Enum) -> postgresql.ENUM:
    """Le même type énuméré, sans le recréer (`create_type` n'existe que sur PostgreSQL)."""
    return postgresql.ENUM(*type_enum.enums, name=type_enum.name, create_type=False)


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    for type_enum in (NATURE, DESSERTE, RELATION):
        type_enum.create(bind, checkfirst=True)

    for table, colonne, type_col in COLONNES:
        if colonne not in _colonnes(table):
            #  Le type est déjà créé ci-dessus : `add_column` ne doit pas le recréer.
            col_type = _deja_cree(type_col) if isinstance(type_col, sa.Enum) else type_col
            op.add_column(table, sa.Column(colonne, col_type, nullable=True))
    if "circulation_perimetre_id" not in _colonnes("lot"):
        op.add_column(
            "lot",
            sa.Column(
                "circulation_perimetre_id",
                sa.Integer(),
                sa.ForeignKey("perimetre.id"),
                nullable=True,
            ),
        )

    tables = _tables()
    if "cle_de_charges" not in tables:
        op.create_table(
            "cle_de_charges",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(), nullable=False),
            sa.Column("libelle", sa.String(), nullable=False),
            sa.Column("denominateur", sa.Integer(), nullable=False),
            sa.Column("perimetre_id", sa.Integer(), sa.ForeignKey("perimetre.id"), nullable=True),
            sa.Column("ordre", sa.Integer(), nullable=False, server_default=sa.text("0")),
        )
        op.create_index("ix_cle_de_charges_code", "cle_de_charges", ["code"], unique=True)
    if "quote_part_lot" not in tables:
        op.create_table(
            "quote_part_lot",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("lot_id", sa.Integer(), sa.ForeignKey("lot.id"), nullable=False),
            sa.Column("cle_id", sa.Integer(), sa.ForeignKey("cle_de_charges.id"), nullable=False),
            sa.Column("numerateur", sa.Integer(), nullable=False),
            sa.UniqueConstraint("lot_id", "cle_id", name="uq_quote_part_lot"),
        )
        op.create_index("ix_quote_part_lot_lot_id", "quote_part_lot", ["lot_id"])
    if "lot_perimetre" not in tables:
        op.create_table(
            "lot_perimetre",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("lot_id", sa.Integer(), sa.ForeignKey("lot.id"), nullable=False),
            sa.Column("perimetre_id", sa.Integer(), sa.ForeignKey("perimetre.id"), nullable=False),
            sa.Column(
                "relation",
                _deja_cree(RELATION),
                nullable=False,
            ),
            sa.Column("derive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint("lot_id", "perimetre_id", "relation", name="uq_lot_perimetre"),
        )
        op.create_index("ix_lot_perimetre_lot_id", "lot_perimetre", ["lot_id"])
    if "import_etat_descriptif" not in tables:
        op.create_table(
            "import_etat_descriptif",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("entete_json", sa.String(), nullable=False, server_default="{}"),
            sa.Column("importe_le", sa.DateTime(), nullable=False),
            sa.Column("applique_le", sa.DateTime(), nullable=True),
        )
    if "ligne_etat_descriptif" not in tables:
        op.create_table(
            "ligne_etat_descriptif",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "import_id",
                sa.Integer(),
                sa.ForeignKey("import_etat_descriptif.id"),
                nullable=False,
            ),
            sa.Column("rang", sa.Integer(), nullable=False),
            sa.Column("lot", sa.String(), nullable=False),
            sa.Column("batiment", sa.String(), nullable=True),
            sa.Column("nature", sa.String(), nullable=True),
            sa.Column("numero_usage", sa.String(), nullable=True),
            sa.Column("niveau", sa.String(), nullable=True),
            sa.Column("circulation", sa.String(), nullable=True),
            sa.Column("quotes_json", sa.String(), nullable=False, server_default="{}"),
            sa.Column("lot_origine", sa.String(), nullable=True),
            sa.Column("source", sa.String(), nullable=True),
        )
        op.create_index(
            "ix_ligne_etat_descriptif_import_id", "ligne_etat_descriptif", ["import_id"]
        )

    #  Les natures déduites du type, sur les seuls lots qui n'en ont pas.
    for type_lot, nature in (("appartement", "logement"), ("cave", "cave"), ("parking", "parking")):
        bind.execute(
            text(
                "UPDATE lot SET nature = CAST(:nature AS naturelot) "
                "WHERE nature IS NULL AND CAST(type AS TEXT) = :type_lot"
            ).bindparams(nature=nature, type_lot=type_lot)
        )
    #  Les dessertes du gabarit, sur les seuls nœuds qui n'en ont pas.
    for suffixe, desserte in DESSERTES_DU_GABARIT.items():
        bind.execute(
            text(
                "UPDATE perimetre SET desserte = CAST(:desserte AS desserteperimetre) "
                "WHERE desserte IS NULL AND batiment_id IS NULL AND code LIKE :motif"
            ).bindparams(desserte=desserte, motif=f"bat:%/{suffixe}")
        )
    bind.execute(
        text(
            "UPDATE perimetre SET desserte = CAST('stationnement' AS desserteperimetre) "
            "WHERE desserte IS NULL AND code = :code"
        ).bindparams(code="parking")
    )


def downgrade() -> None:
    tables = _tables()
    for table in (
        "ligne_etat_descriptif",
        "import_etat_descriptif",
        "lot_perimetre",
        "quote_part_lot",
        "cle_de_charges",
    ):
        if table in tables:
            op.drop_table(table)
    if "circulation_perimetre_id" in _colonnes("lot"):
        op.drop_column("lot", "circulation_perimetre_id")
    for table, colonne, _ in COLONNES:
        if colonne in _colonnes(table):
            op.drop_column(table, colonne)
    bind = op.get_bind()
    for type_enum in (RELATION, DESSERTE, NATURE):
        type_enum.drop(bind, checkfirst=True)
