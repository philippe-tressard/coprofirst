"""Le nom de la résidence n'a plus qu'une source : `site_nom` (#2056)

Deux champs portaient le libellé « Nom de la résidence » : `config_site.site_nom`
(Paramétrage site), que tout le site affiche, et `copropriete.nom` (Fiche
copropriété), que seule la fiche montrait. Arbitré le 17/10/2026 : un seul nom,
`site_nom`, saisi dans la Fiche copropriété.

Cette migration ne fait qu'une chose : quand le site n'a pas de nom propre — clé
absente, vide ou au repli neutre de l'amorce (« Ma Résidence ») — il reprend celui
de la fiche, qui était alors le seul saisi. Un `site_nom` déjà renseigné n'est
jamais remplacé : c'est lui que les résidents voient.

Données seules : l'image précédente lit `site_nom` comme avant (règle #1757).
Idempotente. Sans retour : le nom reporté reste juste pour l'ancienne image.

⚠️ La colonne `copropriete.nom` n'est plus lue ; elle reste, et partira en second
temps. Les noms de table et de clé sont des CONSTANTES du fichier.

Revision ID: 0296
Revises: 0295
"""

import sqlalchemy as sa

from alembic import op

revision = "0296"
down_revision = "0295"
branch_labels = None
depends_on = None

CONFIG = "config_site"  # identifiants : constantes du fichier
COPROPRIETE = "copropriete"
CLE = "site_nom"
REPLI_NEUTRE = "Ma Résidence"  # `utils/liens.NOM_SITE_PAR_DEFAUT` au 17/10/2026


#  Tables décrites par leurs seules colonnes utiles : aucune requête écrite en texte.
_CONFIG = sa.table(CONFIG, sa.column("cle", sa.String), sa.column("valeur", sa.String))
_FICHE = sa.table(COPROPRIETE, sa.column("id", sa.Integer), sa.column("nom", sa.String))


def upgrade():
    bind = op.get_bind()
    nom_fiche = bind.execute(sa.select(_FICHE.c.nom).order_by(_FICHE.c.id).limit(1)).scalar()
    nom_fiche = (nom_fiche or "").strip()
    if not nom_fiche:
        return
    actuel = bind.execute(sa.select(_CONFIG.c.valeur).where(_CONFIG.c.cle == CLE)).scalar()
    if actuel is None:
        bind.execute(sa.insert(_CONFIG).values(cle=CLE, valeur=nom_fiche))
    elif actuel.strip() in ("", REPLI_NEUTRE):
        bind.execute(sa.update(_CONFIG).where(_CONFIG.c.cle == CLE).values(valeur=nom_fiche))


def downgrade():
    pass
