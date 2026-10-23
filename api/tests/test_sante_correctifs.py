"""Les correctifs du système d'une installation standard : lus par le contrôle de 06:00
et par le rapport nocturne au registre (`utils/sante_correctifs`)."""

from __future__ import annotations

from datetime import timedelta

from app.models.core import HistoriqueMaintenance, TachePlanifiee
from app.registre.contrat import ETATS_CORRECTIFS
from app.utils import horloge
from app.utils.sante_correctifs import MUET_APRES, etat_correctifs, problemes_correctifs


def _controle(session, statut: str, il_y_a: timedelta, erreur: str | None = None) -> None:
    session.add(
        HistoriqueMaintenance(
            tache=TachePlanifiee.correctifs_systeme.value,
            statut=statut,
            erreur=erreur,
            cree_le=horloge.maintenant() - il_y_a,
        )
    )
    session.commit()


def test_sans_controle_pose_rien_a_dire(session):
    """La référence (ses nœuds ont C30) ne rend pas ce compte : ni courriel, ni état."""
    assert etat_correctifs(session) is None
    assert problemes_correctifs(session) == []


def test_a_jour(session):
    _controle(session, "succes", timedelta(hours=3))
    assert etat_correctifs(session) == "a_jour"
    assert problemes_correctifs(session) == []


def test_en_defaut_se_dit_avec_sa_cause(session):
    _controle(session, "succes", timedelta(hours=27))
    _controle(session, "erreur", timedelta(hours=3), "des correctifs vus par le dernier passage")
    assert etat_correctifs(session) == "en_defaut"
    (probleme,) = problemes_correctifs(session)
    assert "vus par le dernier passage" in probleme and "--etat" in probleme


def test_un_succes_apres_le_defaut_le_fait_taire(session):
    _controle(session, "erreur", timedelta(hours=27), "x")
    _controle(session, "succes", timedelta(hours=3))
    assert problemes_correctifs(session) == []


def test_un_controle_qui_se_tait_n_est_pas_a_jour(session):
    """Le battement manquant (`standards/04` §4) : un succès ancien ne vaut pas « à jour »."""
    _controle(session, "succes", MUET_APRES + timedelta(hours=1))
    assert etat_correctifs(session) == "muet"
    (probleme,) = problemes_correctifs(session)
    assert "inconnu" in probleme


def test_les_etats_sont_ceux_du_contrat(session):
    for statut, il_y_a in (("succes", 1), ("erreur", 1), ("succes", 100)):
        _controle(session, statut, timedelta(hours=il_y_a))
        assert etat_correctifs(session) in ETATS_CORRECTIFS
