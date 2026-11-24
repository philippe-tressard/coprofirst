"""La 0352 ajoute `prix_centimes` et REPREND chaque prix posé (#3011).

La base est celle de la production d'avant : sans la colonne. 19,99 € devient
1 999 centimes (pas 1 998 : la reprise passe par `numeric`), un prix absent reste
absent. Rejouée, la migration n'écrit rien de plus ; défaite, la colonne part.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlmodel import Session

from app.models.communaute import PetiteAnnonce

from tests import aides_migrations
from tests.aides_base import moteur_de_test


def _prix(moteur) -> list[tuple]:
    with moteur.connect() as conn:
        return list(
            conn.execute(
                sa.text("SELECT titre, prix, prix_centimes FROM petite_annonce ORDER BY titre")
            ).all()
        )


def test_la_reprise_arrondit_au_centime_et_se_rejoue_sans_effet():
    moteur = moteur_de_test()
    with Session(moteur) as s:
        for titre, prix in (("a", 19.99), ("b", 180.0), ("c", None), ("d", 0.1 + 0.2)):
            #  Écrites comme l'ancien code les écrivait : `prix` seule.
            s.add(PetiteAnnonce(titre=titre, description="d", auteur_id=1, prix=prix))
        s.commit()
    with moteur.begin() as conn:
        conn.execute(sa.text("ALTER TABLE petite_annonce DROP COLUMN prix_centimes"))
    colonnes = {c["name"] for c in sa.inspect(moteur).get_columns("petite_annonce")}
    assert "prix_centimes" not in colonnes, "cas zéro"

    migration = aides_migrations.charger_migration("0352")
    aides_migrations.jouer_pas(moteur, migration.upgrade)
    attendu = [("a", 19.99, 1999), ("b", 180.0, 18000), ("c", None, None), ("d", 0.1 + 0.2, 30)]
    assert _prix(moteur) == attendu
    aides_migrations.jouer_pas(moteur, migration.upgrade)  # un redémarrage la rejoue : rien de plus
    assert _prix(moteur) == attendu

    aides_migrations.jouer_pas(moteur, migration.downgrade)
    assert "prix_centimes" not in {
        c["name"] for c in sa.inspect(moteur).get_columns("petite_annonce")
    }
    moteur.dispose()
