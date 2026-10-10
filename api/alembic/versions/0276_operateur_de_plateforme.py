"""Les administrateurs d'alors deviennent aussi opérateurs de la plateforme (#1750)

Chantier multi-copropriétés, lot P2-8 (spec §4.7). Le rôle `admin` mêlait deux
métiers : administrer la résidence, superviser l'installation. Les écrans de
supervision technique et de base de données passent à l'opérateur seul
(arbitrage du 10/10/2026). Sans cette migration, les administrateurs les
perdraient à la mise en production : chacun reçoit donc aussi le rôle opérateur,
et personne ne perd un écran.

## Compatible avec la version précédente (#1757)

Le rôle n'entre que dans `roles_json`, une chaîne, jamais dans la colonne `role`
(un type énuméré sous PostgreSQL). Le code d'avant lit un rôle qu'il ne connaît
pas sans broncher : `has_role` compare des chaînes, `rang_role` rend 0 et le rôle
principal reste `admin`. Revenir en arrière n'est qu'un changement d'image.

Idempotente : un compte qui porte déjà le rôle n'est pas touché. `downgrade` le
retire de tous les comptes.

⚠️ Le nom de table et la valeur du rôle sont des CONSTANTES du fichier — la
valeur figée ici, et non importée : une migration appliquée ne suit pas le code.

Revision ID: 0276
Revises: 0275
"""

import sqlalchemy as sa

from alembic import op

revision = "0276"
down_revision = "0275"
branch_labels = None
depends_on = None

OPERATEUR = "operateur"  # app.models.roles.ROLE_OPERATEUR, figé au 10/10/2026
ADMIN = "admin"


def _roles(role, roles_json) -> list[str]:
    """La même lecture que `Utilisateur.roles` : la liste, sinon le rôle principal."""
    lus = [r.strip() for r in (roles_json or "").split(",") if r.strip()]
    return lus or ([str(role)] if role else [])


def _reecrire(transformer) -> None:
    conn = op.get_bind()
    for ident, role, roles_json in conn.execute(
        sa.text("SELECT id, role, roles_json FROM utilisateur")
    ).all():
        avant = _roles(role, roles_json)
        apres = transformer(avant)
        if apres != avant:
            conn.execute(
                sa.text("UPDATE utilisateur SET roles_json = :roles WHERE id = :ident").bindparams(
                    roles=",".join(apres), ident=ident
                )
            )


def upgrade() -> None:
    _reecrire(lambda r: r + [OPERATEUR] if ADMIN in r and OPERATEUR not in r else r)


def downgrade() -> None:
    _reecrire(lambda r: [x for x in r if x != OPERATEUR])
