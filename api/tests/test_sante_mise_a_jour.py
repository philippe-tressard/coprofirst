"""L'échec récent d'une mise à jour nocturne remonte au courriel de 06:00 (#1756)."""

from __future__ import annotations

from datetime import timedelta

from app.models.core import HistoriqueMaintenance, TachePlanifiee
from app.utils import horloge
from app.utils.sante_mise_a_jour import FENETRE, problemes_mise_a_jour


def _passage(session, statut: str, il_y_a: timedelta, erreur: str | None = None) -> None:
    session.add(
        HistoriqueMaintenance(
            tache=TachePlanifiee.mise_a_jour.value,
            statut=statut,
            erreur=erreur,
            cree_le=horloge.maintenant() - il_y_a,
        )
    )
    session.commit()


def test_aucun_passage_rien_a_dire(session):
    """La référence ne fait pas de mise à jour nocturne : aucune ligne, aucun problème."""
    assert problemes_mise_a_jour(session) == []


def test_un_echec_recent_se_dit_avec_sa_cause(session):
    _passage(session, "erreur", timedelta(hours=2), "santé KO après la mise à jour vers 2.120.0")
    (probleme,) = problemes_mise_a_jour(session)
    assert "2.120.0" in probleme and "version précédente" in probleme


def test_un_succes_apres_l_echec_le_fait_taire(session):
    _passage(session, "erreur", timedelta(hours=26), "santé KO")
    _passage(session, "succes", timedelta(hours=2))
    assert problemes_mise_a_jour(session) == []


def test_un_echec_ancien_a_deja_ete_dit(session):
    _passage(session, "erreur", FENETRE + timedelta(hours=1), "santé KO")
    assert problemes_mise_a_jour(session) == []
