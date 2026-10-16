"""La relance du syndic dit le RÉSUMÉ de chaque affaire, quand il existe (#2035).

Le Suivi des affaires garde sur chaque affaire le résumé que l'assistant lui a
rédigé (0287), et l'aperçu du courriel de relance le montre avant l'envoi. Le
courriel doit donc dire la même chose : « Point de situation » et le résumé ; à
défaut, la description, comme avant.

Au passage, le badge « Relance n°… » dit enfin le numéro de la relance qui part :
il affichait le nombre de relances PRÉCÉDENTES — « n°1 » pour la deuxième.

## 🔴 Pourquoi une MIGRATION et pas seulement le seed

`_poser_les_absents` ne pose que ce qui manque : modifier `seed/emails/tickets.py`
seul n'aurait rien changé en production (0162, 0203, 0266). L'image précédente ne
fournit pas `item.resume` : le modèle migré rend alors la description, comme avant.

🔒 Le résumé vient d'un modèle et c'est du TEXTE : il passe par `| e`, le moteur
des courriels n'échappant rien de lui-même (`SandboxedEnvironment` sans
`autoescape`). La description, elle, est le HTML assaini de l'affaire.

⚠️ Les CARACTÈRES sont écrits tels quels — l'espace fine insécable avant « : »
comprise : la base stocke le caractère décodé (0162, 0266).

## `REPLACE()` ciblé

Le fragment remplacé va de la fin de la ligne « Catégorie » au début du titre
« Historique » : il disparaît une fois remplacé, et rejouer `upgrade` ne
l'applique pas deux fois (`remplacer_passage`). Un modèle retouché depuis
Admin → E-mails, dont ce passage n'a plus la forme d'origine, n'est PAS touché.

Revision ID: 0288
Revises: 0287
"""

from alembic import op

from app.utils.textes_livres import remplacer_passage

revision = "0288"
down_revision = "0287"
branch_labels = None
depends_on = None

_INTITULE = '<p style="margin:0 0 10px;font-size:13px;font-weight:600;color:#374151">'
_TEXTE = '<div style="font-size:13px;color:#1A1A2E;white-space:pre-line">'
_DESCRIPTION = f"{_INTITULE}Description :</p>{_TEXTE}{{{{ item.description }}}}</div>"
_HISTORIQUE = '<p style="margin:12px 0 6px'

#: (code, avant, après) — la forme de 0266, relue par
#: `test_les_migrations_disent_la_meme_chose_que_le_seed`.
REMPLACEMENTS_CORPS: list[tuple[str, str, str]] = [
    (
        "relance_syndic",
        f"</p>{_DESCRIPTION}{_HISTORIQUE}",
        "</p>{% if item.resume %}"
        f"{_INTITULE}Point de situation :</p>{_TEXTE}{{{{ item.resume | e }}}}</div>"
        f"{{% else %}}{_DESCRIPTION}{{% endif %}}{_HISTORIQUE}",
    ),
    #  Le numéro de la relance qui PART : `relance_count` compte les précédentes,
    #  et le modèle annonçait « Relance n°1 » à la deuxième.
    (
        "relance_syndic",
        "Relance n°{{ item.relance_count }}</span>",
        "Relance n°{{ item.relance_count + 1 }}</span>",
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
