"""La 0354 retire `petite_annonce.prix`, vidée par la 0353 (#3011, second temps).

La base est celle de la production : `prix` encore là, vide. Le retrait l'emporte,
les centimes restent ; rejoué, rien de plus. Défait, `prix` revient, recomposée
depuis les centimes — la v3.125 la lirait.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlmodel import Session

from app.models.communaute import PetiteAnnonce
from app.utils.colonnes_presentes import colonnes_presentes

from tests import aides_migrations
from tests.aides_base import moteur_de_test

_0354 = aides_migrations.charger_migration("0354")


def _colonnes(moteur) -> set[str]:
    with moteur.connect() as conn:
        return set(colonnes_presentes(conn, "petite_annonce"))


def test_le_retrait_garde_les_centimes_et_se_defait():
    moteur = moteur_de_test()
    with Session(moteur) as s:
        for titre, centimes in (("a", 1999), ("b", None)):
            s.add(PetiteAnnonce(titre=titre, description="d", auteur_id=1, prix_centimes=centimes))
        s.commit()
    with moteur.begin() as conn:
        #  La colonne d'avant, vide, telle que la production la porte après la 0353.
        conn.execute(sa.text("ALTER TABLE petite_annonce ADD COLUMN prix double precision"))

    aides_migrations.jouer_pas(moteur, _0354.upgrade)
    assert "prix" not in _colonnes(moteur)
    aides_migrations.jouer_pas(moteur, _0354.upgrade)  # un redémarrage la rejoue : rien de plus
    with moteur.connect() as conn:
        lignes = conn.execute(
            sa.text("SELECT titre, prix_centimes FROM petite_annonce ORDER BY titre")
        ).all()
    assert [tuple(ligne) for ligne in lignes] == [("a", 1999), ("b", None)]

    aides_migrations.jouer_pas(moteur, _0354.downgrade)
    with moteur.connect() as conn:
        lignes = conn.execute(
            sa.text("SELECT titre, prix, prix_centimes FROM petite_annonce ORDER BY titre")
        ).all()
    assert [tuple(ligne) for ligne in lignes] == [("a", 19.99, 1999), ("b", None, None)]
    moteur.dispose()
