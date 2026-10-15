"""Une exécution, UNE ligne d'historique (#1367, 27/09/2026, signalé à l'écran).

Depuis que le battement de début est enregistré, chaque maintenance laissait
deux lignes : le battement, vide (« en_cours », 0 s, aucun détail), puis le
rapport. L'historique affichait des lignes « sans rien d'écrit », et elles
mangeaient la moitié du quota de conservation (dix lignes par tâche).

Les valeurs sont celles que `maintenance.sh` ENVOIE : la même heure de début
pour le battement et le rapport (`standards/05` §15).
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models.core import HistoriqueMaintenance
from app.routers.admin.rapports_scripts import RapportMaintenance, enregistrer_rapport
from app.utils.sante_taches import sans_battements_remplaces
from tests.aides_base import moteur_de_test

DEBUT = datetime(2026, 9, 27, 3, 0, 1)


def _session() -> Session:
    return Session(moteur_de_test())


def _rapport(**kwargs) -> RapportMaintenance:
    base = dict(tache="maintenance", noeud="rpi2", portee="applicative", cree_le=DEBUT)
    base.update(kwargs)
    return RapportMaintenance(**base)


def test_le_rapport_de_fin_REPREND_la_ligne_du_battement():
    with _session() as s:
        enregistrer_rapport(s, _rapport(statut="en_cours", duree_secondes=0))
        enregistrer_rapport(
            s,
            _rapport(
                statut="succes",
                duree_secondes=11,
                details={"tokens": 0, "emails": 2},
                terminee_le=datetime(2026, 9, 27, 3, 0, 13),
            ),
        )
        lignes = s.exec(select(HistoriqueMaintenance)).all()
        assert len(lignes) == 1, "le battement et son rapport font deux lignes"
        assert lignes[0].statut == "succes" and lignes[0].duree_secondes == 11
        assert '"emails": 2' in (lignes[0].details or "")


def test_deux_noeuds_gardent_chacun_leur_ligne():
    """La clé porte le NŒUD : le rapport de rpi1 ne reprend pas le battement de rpi2."""
    with _session() as s:
        enregistrer_rapport(s, _rapport(statut="en_cours", noeud="rpi2"))
        enregistrer_rapport(s, _rapport(statut="succes", noeud="rpi1", portee="hygiene_locale"))
        assert len(s.exec(select(HistoriqueMaintenance)).all()) == 2


def test_un_rapport_sans_battement_cree_sa_ligne():
    """La bascule et l'export n'ont pas de battement : rien ne change pour eux."""
    with _session() as s:
        enregistrer_rapport(s, _rapport(tache="bascule", statut="succes"))
        assert len(s.exec(select(HistoriqueMaintenance)).all()) == 1


def test_l_historique_ne_montre_pas_les_battements_DEJA_remplaces():
    """Les lignes écrites avant le correctif : le filtre de lecture les tait."""
    battement = HistoriqueMaintenance(
        tache="maintenance", noeud="rpi2", portee="applicative", statut="en_cours", cree_le=DEBUT
    )
    fin = HistoriqueMaintenance(
        tache="maintenance", noeud="rpi2", portee="applicative", statut="succes", cree_le=DEBUT
    )
    seul = HistoriqueMaintenance(
        tache="maintenance", noeud="rpi1", portee="applicative", statut="en_cours", cree_le=DEBUT
    )
    assert sans_battements_remplaces([battement, fin, seul]) == [fin, seul]
