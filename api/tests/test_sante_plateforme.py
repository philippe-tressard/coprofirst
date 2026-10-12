"""Le disque est une donnée de la PLATEFORME, pas d'une copropriété (#1814).

Le contrôle de 06:00 tourne une fois par copropriété : avec N copropriétés,
« disque < 15 % » serait parti N fois, à des gens qui ne gèrent pas le serveur.

Ce fichier tient les deux régimes :
- UNE copropriété (l'installation d'aujourd'hui) : rien ne change — le disque
  reste dans son contrôle, un seul courriel, l'écran Admin le montre ;
- à partir de DEUX : il en sort, la tâche de la plateforme le juge une fois, et
  tant que son destinataire n'est pas décidé, elle le DIT au journal.
"""

from __future__ import annotations

import logging
from collections import namedtuple
from dataclasses import replace

import pytest

from app import contexte
from app.utils import health_monitor, sante_plateforme

ALERTE = "Espace disque faible : 3.0% libre (1.0 Go). Vérifier et nettoyer si nécessaire."


@pytest.fixture()
def disque_plein(monkeypatch):
    monkeypatch.setattr(health_monitor, "probleme_disque", lambda: [ALERTE])
    monkeypatch.setattr(sante_plateforme, "probleme_disque", lambda: [ALERTE])


@pytest.fixture()
def deux_coproprietes(monkeypatch):
    une = contexte.courante()
    monkeypatch.setattr(
        contexte, "coproprietes", lambda: (une, replace(une, identifiant="essai-b"))
    )


def test_une_copropriete_garde_le_disque_dans_son_controle(session, disque_plein, caplog):
    assert not sante_plateforme.disque_par_la_plateforme()
    assert ALERTE in health_monitor.collecter_problemes(session)
    with caplog.at_level(logging.INFO, logger=sante_plateforme.__name__):
        sante_plateforme.run_controle_plateforme()
    assert not caplog.records, "la plateforme ne double pas le contrôle d'une seule copropriété"


def test_deux_coproprietes_le_disque_quitte_leur_controle(session, disque_plein, deux_coproprietes):
    assert sante_plateforme.disque_par_la_plateforme()
    assert ALERTE not in health_monitor.collecter_problemes(session)


def test_sans_destinataire_decide_la_plateforme_le_dit(disque_plein, deux_coproprietes, caplog):
    with caplog.at_level(logging.WARNING, logger=sante_plateforme.__name__):
        sante_plateforme.run_controle_plateforme()
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(messages) == 1
    assert "aucun destinataire décidé (#1814" in messages[0] and ALERTE in messages[0]


def test_un_destinataire_sans_envoi_echoue_bruyamment(monkeypatch):
    """Décider l'adresse sans écrire l'envoi ne doit pas taire l'alerte."""
    monkeypatch.setattr(sante_plateforme, "destinataire_alertes_plateforme", lambda: "op@x.test")
    with pytest.raises(NotImplementedError):
        sante_plateforme.alerter([ALERTE])


Usage = namedtuple("Usage", "total used free")


@pytest.mark.parametrize("libre, alerte", [(14, True), (15, False), (60, False)])
def test_le_seuil_d_espace_libre(monkeypatch, libre, alerte):
    gio = 1024**3
    monkeypatch.setattr(
        sante_plateforme.shutil, "disk_usage", lambda _: Usage(100 * gio, 0, libre * gio)
    )
    assert bool(sante_plateforme.probleme_disque()) is alerte


def test_un_disque_illisible_n_alerte_pas_et_le_journalise(monkeypatch, caplog):
    def refus(_):
        raise OSError("refusé")

    monkeypatch.setattr(sante_plateforme.shutil, "disk_usage", refus)
    with caplog.at_level(logging.WARNING, logger=sante_plateforme.__name__):
        assert sante_plateforme.probleme_disque() == []
    assert "Impossible de vérifier l'espace disque" in caplog.text
