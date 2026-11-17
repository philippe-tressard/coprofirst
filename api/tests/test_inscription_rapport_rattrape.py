"""Un rapport nocturne perdu se rattrape au démarrage suivant (#2837).

Constaté le 17/11/2026 : CF-000003 (la démo) n'avait rien rapporté depuis le 14/11.
La tâche du bail et du rapport part entre 04:20 et 04:50 (`client.enregistrer`) ; la
mise à jour de 04:30 recrée l'API, et une tâche tombée après 04:30 mourait avec elle.
Le bail était rattrapé par l'annonce de version (#2750), le rapport ne l'était pas. Or
les alertes de la référence (sauvegarde, disque, certificat, retard) se jugent sur le
DERNIER rapport (`registre/alertes.evaluer`).

Le correctif : au démarrage (`client.run_demarrage`), le rapport repart s'il date de
plus de `RAPPORT_EN_RETARD_APRES` — quelle que soit la cause de la perte (mise à jour,
remise à zéro de la démo, panne). Les deux côtés parlent pour de vrai.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session, func, select

from app.config import get_settings
from app.inscription import client, depot
from app.inscription.depot import Contact
from app.registre.modeles import RapportInstallation
from app.utils import horloge
from tests.aides_registre import installation_branchee

CONTACT = Contact(prenom="Alix", nom="Durand", courriel="alix@example.org")


@pytest.fixture
def registre(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "coprofirst_version", "3.112.1")
    with installation_branchee(monkeypatch, tmp_path) as moteur:
        client.inscrire(CONTACT)
        yield moteur


def _rapports_recus(moteur) -> int:
    with Session(moteur) as s:
        return s.exec(select(func.count()).select_from(RapportInstallation)).one()


def _rapport_date_de(heures: float) -> None:
    etat = depot.lire()
    etat.dernier_rapport_le = (horloge.maintenant() - timedelta(hours=heures)).isoformat(
        timespec="seconds"
    )
    depot.ecrire(etat)


def test_un_rapport_perdu_dans_la_nuit_repart_au_demarrage(registre):
    """Le cas du 17/11 : redémarrage SANS changement de version (remise à zéro de la
    démo), l'annonce n'a rien à dire — le rapport, lui, repart."""
    _rapport_date_de(3 * 24)
    avant = _rapports_recus(registre)

    client.run_demarrage()

    assert _rapports_recus(registre) == avant + 1
    assert (
        depot.lire().dernier_rapport_le >= (horloge.maintenant() - timedelta(minutes=1)).isoformat()
    )


def test_un_rapport_jamais_envoye_part_au_demarrage(registre):
    etat = depot.lire()
    etat.dernier_rapport_le = None
    depot.ecrire(etat)
    avant = _rapports_recus(registre)

    client.run_demarrage()

    assert _rapports_recus(registre) == avant + 1


def test_un_rapport_recent_ne_repart_pas(registre):
    """Deux démarrages dans la nuit (mise à jour à 04:30, remise à zéro à 05:15) :
    un seul rapport, pas un par démarrage."""
    _rapport_date_de(1)
    avant = _rapports_recus(registre)

    client.run_demarrage()

    assert _rapports_recus(registre) == avant


def test_un_registre_injoignable_ne_bloque_pas_le_demarrage(registre, monkeypatch):
    _rapport_date_de(3 * 24)

    def injoignable(*_a, **_kw):
        raise client.httpx.ConnectError("registre injoignable")

    monkeypatch.setattr(client.httpx, "post", injoignable)
    client.run_demarrage()  # ne lève pas : le démarrage n'en dépend pas

    assert (
        depot.lire().dernier_rapport_le < (horloge.maintenant() - timedelta(hours=48)).isoformat()
    )


def test_l_essai_ne_rapporte_rien(registre, monkeypatch):
    _rapport_date_de(3 * 24)
    monkeypatch.setattr(client, "essai_admis", lambda: True)
    avant = _rapports_recus(registre)

    client.run_demarrage()

    assert _rapports_recus(registre) == avant


def test_le_planificateur_pose_le_rattrapage_au_demarrage():
    class Planificateur:
        def __init__(self):
            self.taches = {}

        def add_job(self, fonction, *_a, id, **_kw):
            self.taches[id] = fonction

    p = Planificateur()
    client.enregistrer(p)

    assert p.taches["annonce_version_installation"] is client.run_demarrage
    assert p.taches["bail_installation"] is client.run_renouvellement_bail


@pytest.mark.parametrize(
    "heures, en_retard", [(None, True), (0.5, False), (19.9, False), (20.1, True), (72, True)]
)
def test_rapport_en_retard_est_pure(heures, en_retard):
    maintenant = horloge.maintenant()
    dernier = None if heures is None else (maintenant - timedelta(hours=heures)).isoformat()
    assert client.rapport_en_retard(dernier, maintenant) is en_retard
