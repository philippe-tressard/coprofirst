"""Une release publiée APRÈS le redémarrage de la référence est connue dans l'heure (#2825).

Constaté le 16/11/2026, deux fois : la MEP redémarre l'API (« Déployé ») AVANT que la
release de la version soit publiée (fin du workflow « Images »). La référence ne
relisait les releases qu'au démarrage et à 03:50 : v3.107.0, déployée à 21:49 et publiée
à 21:50, est restée inconnue du registre jusqu'à 03:50 — la démo, en canal Urgence, a
reçu au bail la version d'avant.

Le correctif : la lecture tourne chaque heure (à :50, donc encore à 03:50, avant les
baux de 04:20), en plus de celle du démarrage. Ce test joue « démarrage avant
publication » avec le vrai déclencheur d'APScheduler.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from apscheduler.triggers.cron import CronTrigger

from app.registre import canaux
from app.registre.modeles import VersionDisponible

PARIS = ZoneInfo("Europe/Paris")


class _Planificateur:
    def __init__(self):
        self.taches: dict[str, tuple] = {}

    def add_job(self, fonction, declencheur, *, id, **options):
        self.taches[id] = (fonction, declencheur, options)


def _declencheur_des_releases() -> CronTrigger:
    p = _Planificateur()
    canaux.enregistrer(p)
    fonction, declencheur, options = p.taches["canaux_registre"]
    assert fonction is canaux.run_canaux_registre and declencheur == "cron"
    assert options.get("next_run_time") is not None, "plus de lecture au démarrage"
    champs = {k: v for k, v in options.items() if k in ("hour", "minute")}
    return CronTrigger(timezone=PARIS, **champs)


@pytest.mark.parametrize(
    "deploye",
    [
        datetime(2026, 11, 16, 21, 49, 10, tzinfo=PARIS),  # v3.107.0 : publiée à 21:50
        datetime(2026, 11, 16, 18, 29, 0, tzinfo=PARIS),  # v3.105.1 : publiée à 18:29:42
        datetime(2026, 11, 17, 3, 51, 0, tzinfo=PARIS),  # juste après la lecture de 03:50
    ],
)
def test_une_release_publiee_apres_le_redemarrage_est_relue_dans_l_heure(deploye):
    publiee = deploye + timedelta(minutes=2)
    suivante = _declencheur_des_releases().get_next_fire_time(None, publiee)
    assert suivante - publiee <= timedelta(hours=1), (
        f"release publiée à {publiee:%H:%M}, relue seulement à {suivante:%d/%m %H:%M}"
    )


def test_la_lecture_de_la_nuit_precede_toujours_les_baux():
    """Les baux de la nuit partent à 04:20 : une lecture tombe entre 03:00 et 04:20."""
    declencheur = _declencheur_des_releases()
    nuit = datetime(2026, 11, 17, 3, 0, tzinfo=PARIS)
    assert declencheur.get_next_fire_time(None, nuit) < nuit.replace(hour=4, minute=20)


class _Session:
    def __init__(self, tenues):
        self.tenues = list(tenues)

    def exec(self, *_a, **_kw):
        return self

    def all(self):
        return list(self.tenues)

    def add(self, ligne):
        if ligne not in self.tenues:
            self.tenues.append(ligne)

    def delete(self, ligne):
        self.tenues.remove(ligne)


def test_demarrage_avant_publication_puis_relecture(monkeypatch):
    """La lecture du démarrage ne voit pas la release ; celle de l'heure suivante, si."""
    avant = datetime(2026, 11, 16, 20, 49)
    s = _Session([VersionDisponible(version="3.106.0", publiee_le=avant)])
    monkeypatch.setattr(canaux, "versions_disponibles", lambda session: session.all())

    canaux.relire_versions(s, [canaux.Publication("3.106.0", avant)], avant)
    assert {v.version for v in s.tenues} == {"3.106.0"}

    publiee = datetime(2026, 11, 16, 20, 50)
    lues = [canaux.Publication("3.106.0", avant), canaux.Publication("3.107.0", publiee)]
    constat = canaux.relire_versions(s, lues, publiee + timedelta(hours=1))
    assert {v.version for v in s.tenues} == {"3.106.0", "3.107.0"}
    assert "dernière 3.107.0" in constat
