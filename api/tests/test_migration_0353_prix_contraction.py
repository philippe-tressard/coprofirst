"""La 0353 reprend la règle de lecture de la v3.125, puis vide `prix` (#3011).

La base est celle de la production d'avant : `prix` encore là. Une annonce dont
les deux colonnes s'accordent garde ses centimes ; une dont `prix` a été corrigé
seul (un retour arrière) prend ses centimes de `prix` ; une sans centimes les
reçoit. Puis `prix` est vide partout. Rejouée, rien de plus ; défaite, `prix` se
recompose ; sur un schéma neuf (sans `prix`), rien.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlmodel import Session

from app.models.communaute import PetiteAnnonce

from tests import aides_migrations
from tests.aides_base import moteur_de_test

_0353 = aides_migrations.charger_migration("0353")


def _lignes(moteur) -> list[tuple]:
    with moteur.connect() as conn:
        return list(
            conn.execute(
                sa.text("SELECT titre, prix, prix_centimes FROM petite_annonce ORDER BY titre")
            ).all()
        )


def test_la_contraction_reprend_la_derniere_saisie_puis_vide_prix():
    moteur = moteur_de_test()
    with Session(moteur) as s:
        for titre, centimes in (("a", 1999), ("b", 1999), ("c", None), ("d", None)):
            s.add(PetiteAnnonce(titre=titre, description="d", auteur_id=1, prix_centimes=centimes))
        s.commit()
    with moteur.begin() as conn:
        #  La colonne d'avant, telle que la production la porte encore.
        conn.execute(sa.text("ALTER TABLE petite_annonce ADD COLUMN prix double precision"))
        for titre, prix in (("a", 19.99), ("b", 25.0), ("c", 12.5)):
            conn.execute(
                sa.text("UPDATE petite_annonce SET prix = :p WHERE titre = :t"),
                {"p": prix, "t": titre},
            )
    #  a : d'accord ; b : `prix` corrigé seul, il l'emporte ; c : centimes manquants ; d : rien.
    aides_migrations.jouer_pas(moteur, _0353.upgrade)
    attendu = [("a", None, 1999), ("b", None, 2500), ("c", None, 1250), ("d", None, None)]
    assert _lignes(moteur) == attendu
    aides_migrations.jouer_pas(moteur, _0353.upgrade)  # un redémarrage la rejoue : rien de plus
    assert _lignes(moteur) == attendu

    aides_migrations.jouer_pas(moteur, _0353.downgrade)
    assert _lignes(moteur) == [
        ("a", 19.99, 1999),
        ("b", 25.0, 2500),
        ("c", 12.5, 1250),
        ("d", None, None),
    ]
    moteur.dispose()


def test_sur_un_schema_neuf_la_contraction_ne_fait_rien():
    moteur = moteur_de_test()
    with Session(moteur) as s:
        s.add(PetiteAnnonce(titre="a", description="d", auteur_id=1, prix_centimes=500))
        s.commit()
    aides_migrations.jouer_pas(moteur, _0353.upgrade)
    aides_migrations.jouer_pas(moteur, _0353.downgrade)
    with moteur.connect() as conn:
        assert conn.execute(sa.text("SELECT prix_centimes FROM petite_annonce")).scalar() == 500
    moteur.dispose()
