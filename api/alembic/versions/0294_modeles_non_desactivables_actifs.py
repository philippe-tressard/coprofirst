"""Recocher les modèles d'e-mail qui ne se désactivent pas (#2054)

La case « Actif » d'Admin › Modèles e-mail coupait aussi le mot de passe oublié,
la vérification d'adresse, l'alerte système… — les modèles que le code déclare
`desactivable=False` depuis toujours sans que rien ne le lise. Le correctif fait
partir ces modèles même décochés et refuse de les décocher ; cette migration
remet `actif` à vrai sur ceux qu'on aurait décochés, pour que l'écran ne dise
pas « Non » sur un courriel qui part.

Données seules : l'image précédente lit la même colonne et y trouve une valeur
qu'elle sait lire (règle #1757). Idempotente. Sans retour : décocher un courriel
de sécurité n'est pas un état à restaurer.

⚠️ La liste est FIGÉE ici (une migration ne lit pas le code vivant) : c'est
`seed.emails.NON_DESACTIVABLES` au 17/10/2026. La table est une constante du fichier.

Revision ID: 0294
Revises: 0293
"""

import sqlalchemy as sa

from alembic import op

revision = "0294"
down_revision = "0293"
branch_labels = None
depends_on = None

MODELES = "modele_email"  # identifiant : constante du fichier
NON_DESACTIVABLES = (
    "adresse_changement_avis",
    "alerte_systeme",
    "compte_inactif_avertissement",
    "publication_externe",
    "reinitialisation_mdp",
    "relance_syndic",
    "ticket_externe",
    "verification_email",
)


def upgrade():
    op.execute(
        sa.text(
            f"UPDATE {MODELES} SET actif = TRUE WHERE code IN :codes AND actif IS NOT TRUE"
        ).bindparams(sa.bindparam("codes", value=list(NON_DESACTIVABLES), expanding=True))
    )


def downgrade():
    pass
