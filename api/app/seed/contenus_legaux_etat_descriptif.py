"""La phrase du gabarit légal sur la LECTURE DE L'ÉTAT DESCRIPTIF par l'assistant (#2218).

Le texte du règlement, que les questions au règlement transmettent déjà, part aussi
quand le conseil demande à l'assistant de lire l'état descriptif de division pour
remplir l'atelier des lots. Le texte doit le dire — 🔒
`tests/test_politique_confidentialite_couvre_le_code.py` l'exige tant que l'usage
`lecture_etat_descriptif` existe.

Écrite une fois : le gabarit (`contenus_legaux.DEFAULT_LEGAL`) et la migration 0313,
qui l'insère dans le texte servi, la lisent ici.

⚠️ **Projet, à faire relire**, comme les autres rubriques (`standards/14`).

Séparé de `contenus_legaux.py`, qui approche 500 lignes (modularité, rang 1).
"""

#: Elle suit la phrase des questions au règlement, dans la même entrée.
LECTURE_ETAT_DESCRIPTIF = (
    "Le même texte du règlement est transmis lorsque le conseil syndical ou "
    "l'administrateur demande à l'assistant de <strong>lire l'état descriptif de "
    "division</strong> pour remplir l'atelier des lots — sans le nom de qui le demande\xa0; "
    "le tableau rendu (lots, nature, niveau, tantièmes) n'entre dans le patrimoine qu'une "
    "fois relu et appliqué par eux. "
)
