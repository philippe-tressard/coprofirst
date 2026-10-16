"""Le « Point de situation » de la relance, posé sur la forme RÉELLEMENT en base (#2035).

La 0288 devait faire dire au courriel de relance le résumé de chaque affaire. En
production, elle n'a rien changé, et en silence : elle cherchait « Description »
suivi d'une espace FINE insécable avant le deux-points — la forme du seed —, et le
modèle servi porte une espace ORDINAIRE, posée avant que le seed adopte la
typographie fine (constaté le 17/10/2026 après la MEP v2.171.0). Son second
remplacement, le numéro de la relance, avait bien porté.

Celle-ci cherche donc la forme servie et écrit celle du seed, celle que la 0288
aurait écrite. Une base où la 0288 a porté n'a plus ce passage : rien ne change.
Un modèle retouché depuis Admin › E-mails n'est pas touché (`remplacer_passage`).

⚠️ Les CARACTÈRES sont écrits tels quels : l'espace ordinaire dans ce qu'on
cherche, l'espace fine (U+202F) dans ce qu'on écrit (0162, 0266).

Revision ID: 0290
Revises: 0289
"""

from alembic import op

from app.utils.textes_livres import remplacer_passage

revision = "0290"
down_revision = "0289"
branch_labels = None
depends_on = None

_INTITULE = '<p style="margin:0 0 10px;font-size:13px;font-weight:600;color:#374151">'
_TEXTE = '<div style="font-size:13px;color:#1A1A2E;white-space:pre-line">'
_HISTORIQUE = '<p style="margin:12px 0 6px'
_SERVIE = f"{_INTITULE}Description :</p>{_TEXTE}{{{{ item.description }}}}</div>"
_SEED = f"{_INTITULE}Description :</p>{_TEXTE}{{{{ item.description }}}}</div>"

#: (code, avant, après) — relu par `test_les_migrations_disent_la_meme_chose_que_le_seed`.
REMPLACEMENTS_CORPS: list[tuple[str, str, str]] = [
    (
        "relance_syndic",
        f"</p>{_SERVIE}{_HISTORIQUE}",
        "</p>{% if item.resume %}"
        f"{_INTITULE}Point de situation :</p>{_TEXTE}{{{{ item.resume | e }}}}</div>"
        f"{{% else %}}{_SEED}{{% endif %}}{_HISTORIQUE}",
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    for code, ancien, nouveau in REMPLACEMENTS_CORPS:
        remplacer_passage(conn, "modele_email", {"code": code}, "corps_html", ancien, nouveau)


def downgrade() -> None:
    conn = op.get_bind()
    for code, ancien, nouveau in REMPLACEMENTS_CORPS:
        remplacer_passage(conn, "modele_email", {"code": code}, "corps_html", nouveau, ancien)
