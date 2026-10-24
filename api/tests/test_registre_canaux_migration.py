"""La base `plateforme` 0006 reprend les installations, une fois et sans rien écraser (#2210).

Avant 0006, une installation suivait un canal-branche (`replica`, `special-…`), en
vague 0, 1 ou 2, avec peut-être une version épinglée. La migration les ramène au
nouveau suivi (`registre/canaux.suivi_de`) : branche → Urgence en Standard (2),
épinglée → la version en Fixe (3) ; la référence ne bouge pas. Rejouée, la reprise
ne touche plus rien — le choix de l'opérateur n'est jamais réécrit.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import text

from app.registre import canaux, migrer
from tests.aides_base import moteur_de_test
from tests.aides_migrations import VERSIONS_PLATEFORME, charger_migration

#: (identifiant, canal, vague, version épinglée) avant 0006 → (canal, vague) après.
AVANT_APRES = [
    (("CF-000000", "main", 1, None), ("main", 1)),
    (("CF-000001", "replica", 0, None), ("urgence", canaux.VAGUE_STANDARD)),
    (("CF-000002", "replica", 2, "2.169.4"), ("2.169.4", canaux.VAGUE_FIXE)),
    (("CF-000003", "special-client", 1, None), ("urgence", canaux.VAGUE_STANDARD)),
]


def _lire(connexion):
    return connexion.execute(
        text("SELECT identifiant, canal, vague, version_epinglee FROM installation ORDER BY 1")
    ).all()


def test_la_reprise_des_installations_puis_son_rejeu_a_vide():
    moteur = moteur_de_test(schema=False)
    with moteur.begin() as c:
        command.upgrade(migrer.configuration(c), "0005")
        for (ident, canal, vague, epinglee), _ in AVANT_APRES:
            c.execute(
                text(
                    "INSERT INTO installation (identifiant, etat, canal, vague, version_epinglee, "
                    "services_autorises, cree_le) VALUES (:i, 'active', :c, :v, :e, '[]', now())"
                ),
                {"i": ident, "c": canal, "v": vague, "e": epinglee},
            )
    with moteur.begin() as c:
        command.upgrade(migrer.configuration(c), "head")
    attendu = [(i, canal, vague, None) for (i, *_), (canal, vague) in AVANT_APRES]
    with moteur.begin() as c:
        assert _lire(c) == attendu
        #  L'opérateur choisit ensuite : un rejeu de la reprise n'y touche pas.
        c.execute(text("UPDATE installation SET vague = 0 WHERE identifiant = 'CF-000001'"))
        for reprise in charger_migration("0006", VERSIONS_PLATEFORME).REPRISES:
            c.execute(reprise)
        attendu[1] = ("CF-000001", "urgence", canaux.VAGUE_URGENCE, None)
        assert _lire(c) == attendu
        #  Une inscription neuve suit Standard.
        c.execute(
            text(
                "INSERT INTO installation (identifiant, etat, canal, services_autorises, cree_le) "
                "VALUES ('CF-000009', 'en_attente', 'urgence', '[]', now())"
            )
        )
        vague = c.execute(text("SELECT vague FROM installation WHERE identifiant = 'CF-000009'"))
        assert vague.scalar_one() == canaux.VAGUE_STANDARD
