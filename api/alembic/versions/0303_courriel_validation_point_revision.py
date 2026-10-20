"""Le courriel de validation d'un point CS / Syndic marque les CR modifiés en révision N (#2082)

Le modèle `point_conseil_validation` est LIVRÉ en base : le seed ne pose que les
modèles absents. Le passage du titre de chaque affaire reçoit la marque
« — Modifié en révision N » (`a.marque`), par `remplacer_passage` : un modèle
retouché depuis l'administration n'est pas touché.

`| default('')` : l'image précédente ne fournit pas `a.marque`, et le rendu ne
doit pas échouer sur elle (#1757).

Revision ID: 0303
Revises: 0302
"""

from alembic import op

from app.utils.textes_livres import remplacer_passage

revision = "0303"
down_revision = "0302"
branch_labels = None
depends_on = None

TABLE = "modele_email"  # identifiant : constante du fichier
CODE = "point_conseil_validation"
AVANT = "{{ a.numero }} · {{ a.titre }}</p>"
APRES = "{{ a.numero }} · {{ a.titre }}{{ a.marque | default('') }}</p>"


def upgrade() -> None:
    remplacer_passage(op.get_bind(), TABLE, {"code": CODE}, "corps_html", AVANT, APRES)


def downgrade() -> None:
    remplacer_passage(op.get_bind(), TABLE, {"code": CODE}, "corps_html", APRES, AVANT)
