"""Les colonnes présentes d'une table, pour une migration rejouable (#2950).

Une migration teste l'existence d'une colonne avant `add_column` ou `drop_column`
— un redémarrage après une migration interrompue la rejoue (0312). La lecture
`{c["name"] for c in sa.inspect(conn).get_columns(table)}` était recopiée dans
seize migrations sur soixante et une, sous quatre noms (`_colonnes`, `_presentes`,
`_presente`, `_existe`). Les migrations à venir l'appellent ici, comme
`utils/textes_livres` pour un texte livré.

🔴 **Compatible pour toujours.** Une migration est figée : elle importera cette
fonction tant qu'elle existera. Sa signature et ce qu'elle rend ne changent
jamais ; une variante s'ajoute à côté, sous un autre nom.

🔒 `tests/test_textes_livres.py` : une migration nouvelle qui recopie ce corps, ou
celui de `textes_livres.lire_texte`, échoue.
"""

from __future__ import annotations

import sqlalchemy as sa


def colonnes_presentes(conn, table: str) -> set[str]:
    """Les noms des colonnes de `table`, lus dans la base par la connexion donnée.

    Dans une migration : `colonnes_presentes(op.get_bind(), TABLE)`.
    """
    return {c["name"] for c in sa.inspect(conn).get_columns(table)}
