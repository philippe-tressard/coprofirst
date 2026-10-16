"""L'usage `synthese_affaires_en_cours` résume CHAQUE affaire : sa consigne d'origine suit (#2035).

Le ✨ du Suivi des affaires rédigeait une synthèse d'ENSEMBLE (#2034) ; Philippe
l'a remplacée le 16/10/2026 par le résumé de chaque affaire, en une ou deux
phrases, tiré de toute sa matière. La consigne d'origine change donc (`format.CONSIGNE`).

## 🔴 Pourquoi une MIGRATION

Le prompt d'un usage est SEMÉ : la valeur en base fait foi, et réécrire le code
ne change rien à une installation où l'administrateur l'a enregistré
(`test_prompt_seme_suit_le_code.py`, #1059). La valeur stockée n'est remplacée
que si elle porte EXACTEMENT l'ancienne consigne d'origine : une consigne
retouchée depuis Admin › Assistant IA n'est pas touchée. Sans valeur en base —
le cas de la production au 16/10/2026 —, l'usage lit déjà la nouvelle origine.

Les deux textes sont RECOPIÉS ici, figés : une migration ne lit pas le code,
qui changera encore.

Revision ID: 0289
Revises: 0288
"""

from alembic import op

from app.utils.textes_livres import remplacer_si_intact

revision = "0289"
down_revision = "0288"
branch_labels = None
depends_on = None

TABLE = "config_site"  # identifiant : constante du fichier
CLE = "llm_synthese_affaires_en_cours_prompt"

ANCIENNE = (
    "Tu rédiges, pour le conseil syndical d'une copropriété, la synthèse des affaires "
    "encore ouvertes (ni résolues ni annulées). Elle accompagne la liste détaillée du "
    "rapport « Suivi des affaires », qui peut être transmis au syndic ou présenté en "
    "assemblée générale.\n"
    "- Écris en français, au présent, sur un ton factuel et sobre, 200 mots au plus.\n"
    "- Un résumé de deux ou trois phrases, puis trois à six points : ce qui presse "
    "(pannes, sinistres, ce qui touche la sécurité ou beaucoup de résidents), ce qui "
    "attend une décision (assemblée générale, devis), ce qui traîne et mérite une "
    "relance, les affaires qui semblent liées et gagneraient à être traitées ensemble.\n"
    "- Les dates, anciennetés et nombres te sont DONNÉS : reprends-les tels quels, "
    "n'en calcule et n'en invente aucun.\n"
    "- Ne cite aucun nom de personne, aucune adresse, aucun numéro de téléphone ; "
    "désigne les personnes par leur rôle (le syndic, le conseil syndical, un résident, "
    "le prestataire)."
)

NOUVELLE = (
    "Tu résumes, pour le conseil syndical d'une copropriété, chacune des affaires "
    "encore ouvertes. Chaque résumé s'affiche sous le titre de l'affaire dans le "
    "rapport « Suivi des affaires », et peut partir au syndic dans un courriel de relance.\n"
    "- Pour CHAQUE affaire : une ou deux phrases, en français, au présent, sur un ton "
    "factuel et sobre — où elle en est, ce qu'elle attend et de qui.\n"
    "- Appuie-toi sur toute sa matière : titre, périmètre, description et fil daté. "
    "Le dernier état du fil compte plus que la description d'origine.\n"
    "- Ne répète pas le titre. Les dates et les durées te sont DONNÉES : reprends-les "
    "telles quelles, n'en calcule et n'en invente aucune.\n"
    "- Ne cite aucun nom de personne, aucune adresse, aucun numéro de téléphone ; "
    "désigne les personnes par leur rôle (le syndic, le conseil syndical, l'auteur de "
    "l'affaire, un résident, le prestataire)."
)


def upgrade() -> None:
    remplacer_si_intact(
        op.get_bind(), TABLE, {"cle": CLE, "valeur": ANCIENNE}, {"valeur": NOUVELLE}
    )


def downgrade() -> None:
    remplacer_si_intact(
        op.get_bind(), TABLE, {"cle": CLE, "valeur": NOUVELLE}, {"valeur": ANCIENNE}
    )
