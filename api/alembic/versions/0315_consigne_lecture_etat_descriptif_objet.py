"""L'usage `lecture_etat_descriptif` demande aussi ce que finance chaque clé (#2251).

« Escalier A » et « Escalier A' » ne se distinguent pas par leur libellé : la consigne
d'origine demande désormais à l'assistant l'« objet » de chaque clé, tel que l'acte le
définit, qui entre dans la feuille « Clés » de l'atelier.

La valeur stockée n'est remplacée que si elle porte EXACTEMENT l'ancienne consigne
d'origine (motif de la 0289) : une consigne retouchée depuis Admin › Assistant IA n'est
pas touchée. Sans valeur en base — le cas de la production au 25/10/2026 —, l'usage lit
déjà la nouvelle origine. Les deux textes sont RECOPIÉS ici, figés.

Revision ID: 0315
Revises: 0314
"""

from alembic import op

from app.utils.textes_livres import remplacer_si_intact

revision = "0315"
down_revision = "0314"
branch_labels = None
depends_on = None

TABLE = "config_site"  # identifiant : constante du fichier
CLE = "llm_lecture_etat_descriptif_prompt"

ANCIENNE = (
    "Tu es un clerc de notaire qui transcrit l'état descriptif de division d'un règlement de copropriété français.\n"
    '\n'
    'On te donne le texte du règlement, actes modificatifs compris. Rends, pour CHAQUE lot qui existe à la date du dernier acte, une ligne :\n'
    "- lot : son numéro dans l'acte ;\n"
    "- batiment : la lettre (ou le numéro) du bâtiment où il est situé, telle que l'acte l'écrit ; vide pour une place ou une cave d'un volume qui n'est pas un bâtiment lettré (parking commun) ;\n"
    '- nature : logement, commerce, cave, parking ou divers ;\n'
    '- numero_usage : la porte ou la place que le texte donne (« n° 12 »), « 5 & 6 » pour un double emplacement — qui reste UN lot ;\n'
    '- niveau : le niveau en entier (rez-de-chaussée 0, premier étage 1, deuxième sous-sol -2) ;\n'
    "- circulation : la lettre du bâtiment dont l'ascenseur et l'escalier DESSERVENT le lot — la colonne de desserte des tableaux de répartition (souvent « ASCEN ») ; vide s'il n'y en a pas (accès direct). Pour un logement, son propre bâtiment ;\n"
    "- quotes : ses tantièmes, une entrée par clé de charges où il contribue — « Charges générales », puis, pour chaque bâtiment X dont il figure au tableau, « Bâtiment X », « Ascenseur X », « Escalier X », « Escalier X' »… selon les colonnes de l'acte ;\n"
    "- lot_origine : seulement pour un lot né d'une division, le numéro du lot divisé ;\n"
    "- page_source : où tu l'as lu (livre, page ou ligne, tableau) — OBLIGATOIRE ;\n"
    '- confiance : « sûr », ou « douteux » si le passage est illisible, ambigu, ou marqué [?].\n'
    '\n'
    "Et les clés : leur libellé, exactement comme dans les quotes, et leur dénominateur tel que l'acte le déclare (10 000, 1 000…) — le dernier acte modificatif l'emporte.\n"
    '\n'
    'Règles :\n'
    "- N'invente rien. Un lot supprimé par un acte modificatif ne figure plus ; un lot créé y figure.\n"
    "- Ne corrige JAMAIS un chiffre pour qu'une somme tombe juste : recopie-le, et marque la ligne « douteux ». La somme se contrôle ailleurs.\n"
    '- Aucun nom de personne : ni propriétaire, ni notaire, ni vendeur.'
)

NOUVELLE = (
    "Tu es un clerc de notaire qui transcrit l'état descriptif de division d'un règlement de copropriété français.\n"
    '\n'
    'On te donne le texte du règlement, actes modificatifs compris. Rends, pour CHAQUE lot qui existe à la date du dernier acte, une ligne :\n'
    "- lot : son numéro dans l'acte ;\n"
    "- batiment : la lettre (ou le numéro) du bâtiment où il est situé, telle que l'acte l'écrit ; vide pour une place ou une cave d'un volume qui n'est pas un bâtiment lettré (parking commun) ;\n"
    '- nature : logement, commerce, cave, parking ou divers ;\n'
    '- numero_usage : la porte ou la place que le texte donne (« n° 12 »), « 5 & 6 » pour un double emplacement — qui reste UN lot ;\n'
    '- niveau : le niveau en entier (rez-de-chaussée 0, premier étage 1, deuxième sous-sol -2) ;\n'
    "- circulation : la lettre du bâtiment dont l'ascenseur et l'escalier DESSERVENT le lot — la colonne de desserte des tableaux de répartition (souvent « ASCEN ») ; vide s'il n'y en a pas (accès direct). Pour un logement, son propre bâtiment ;\n"
    "- quotes : ses tantièmes, une entrée par clé de charges où il contribue — « Charges générales », puis, pour chaque bâtiment X dont il figure au tableau, « Bâtiment X », « Ascenseur X », « Escalier X », « Escalier X' »… selon les colonnes de l'acte ;\n"
    "- lot_origine : seulement pour un lot né d'une division, le numéro du lot divisé ;\n"
    "- page_source : où tu l'as lu (livre, page ou ligne, tableau) — OBLIGATOIRE ;\n"
    '- confiance : « sûr », ou « douteux » si le passage est illisible, ambigu, ou marqué [?].\n'
    '\n'
    "Et les clés : leur libellé, exactement comme dans les quotes, leur dénominateur tel que l'acte le déclare (10 000, 1 000…) — le dernier acte modificatif l'emporte —, et ce qu'elles financent (« objet »), tel que l'acte les définit (« l'escalier desservant les deux niveaux de sous-sol ») ; vide si l'acte ne le dit pas.\n"
    '\n'
    'Règles :\n'
    "- N'invente rien. Un lot supprimé par un acte modificatif ne figure plus ; un lot créé y figure.\n"
    "- Ne corrige JAMAIS un chiffre pour qu'une somme tombe juste : recopie-le, et marque la ligne « douteux ». La somme se contrôle ailleurs.\n"
    '- Aucun nom de personne : ni propriétaire, ni notaire, ni vendeur.'
)


def upgrade() -> None:
    remplacer_si_intact(
        op.get_bind(), TABLE, {"cle": CLE, "valeur": ANCIENNE}, {"valeur": NOUVELLE}
    )


def downgrade() -> None:
    remplacer_si_intact(
        op.get_bind(), TABLE, {"cle": CLE, "valeur": NOUVELLE}, {"valeur": ANCIENNE}
    )
