"""Le disque est une donnée de la PLATEFORME, pas d'une copropriété (#1814).

Le contrôle de 06:00 tourne une fois par copropriété : avec N copropriétés,
« disque < 15 % » serait parti N fois, à des gens qui ne gèrent pas le serveur.

Ce fichier tient les deux régimes :
- UNE copropriété (l'installation d'aujourd'hui) : rien ne change — le disque
  reste dans son contrôle, un seul courriel, l'écran Admin le montre ;
- à partir de DEUX : il en sort, la tâche de la plateforme le juge une fois, et
  l'alerte va à l'OPÉRATEUR de l'installation (`COURRIEL_OPERATEUR`, arbitré le
  13/10/2026) par le SMTP de l'installation — ou se DIT au journal.
"""

from __future__ import annotations

import logging
from collections import namedtuple
from dataclasses import replace

import pytest

from app import contexte
from app.config import get_settings
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


OPERATEUR = "operateur@example.com"


@pytest.fixture()
def operateur(monkeypatch):
    monkeypatch.setattr(get_settings(), "courriel_operateur", OPERATEUR)
    monkeypatch.setattr(get_settings(), "mail_enabled", True)


def _avertissements(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def test_sans_operateur_la_plateforme_le_dit(disque_plein, deux_coproprietes, caplog, monkeypatch):
    monkeypatch.setattr(get_settings(), "courriel_operateur", "  ")
    with caplog.at_level(logging.WARNING, logger=sante_plateforme.__name__):
        sante_plateforme.run_controle_plateforme()
    messages = _avertissements(caplog)
    assert len(messages) == 1
    assert "COURRIEL_OPERATEUR" in messages[0] and ALERTE in messages[0]


def test_sans_smtp_de_l_installation_la_plateforme_le_dit(operateur, monkeypatch, caplog):
    monkeypatch.setattr(get_settings(), "mail_enabled", False)
    envois = []
    monkeypatch.setattr(sante_plateforme, "_envoyer", lambda *a: envois.append(a))
    with caplog.at_level(logging.WARNING, logger=sante_plateforme.__name__):
        assert sante_plateforme.alerter([ALERTE]) is False
    assert not envois and "MAIL_ENABLED" in _avertissements(caplog)[0]


def test_l_operateur_recoit_l_alerte_et_son_adresse_ne_se_journalise_pas(
    operateur, disque_plein, deux_coproprietes, monkeypatch, caplog
):
    envois = []
    monkeypatch.setattr(sante_plateforme, "_envoyer", lambda *a: envois.append(a))
    with caplog.at_level(logging.INFO, logger=sante_plateforme.__name__):
        sante_plateforme.run_controle_plateforme()
    assert envois == [(OPERATEUR, [ALERTE])]
    assert OPERATEUR not in caplog.text  # jamais une adresse au journal (#777)


def test_un_smtp_en_echec_se_dit_et_ne_leve_pas(operateur, monkeypatch, caplog):
    def panne(*_):
        raise ConnectionRefusedError("smtp")

    monkeypatch.setattr(sante_plateforme, "_envoyer", panne)
    with caplog.at_level(logging.WARNING, logger=sante_plateforme.__name__):
        assert sante_plateforme.alerter([ALERTE]) is False
    assert "ConnectionRefusedError" in _avertissements(caplog)[0]
    assert OPERATEUR not in caplog.text


def test_le_message_part_par_le_smtp_de_l_installation(operateur, monkeypatch):
    """Ni modèle ni SMTP d'une copropriété : le message et la connexion de l'INSTALLATION."""
    import fastapi_mail

    partis = []

    async def capter(self, message, *a, **k):
        partis.append((self.config, message))

    monkeypatch.setattr(get_settings(), "mail_from", "plateforme@example.com")
    monkeypatch.setattr(fastapi_mail.FastMail, "send_message", capter)
    assert sante_plateforme.alerter([ALERTE]) is True
    ((config, message),) = partis
    assert OPERATEUR in str(message.recipients) and ALERTE in message.body
    assert config.MAIL_FROM == "plateforme@example.com"
    assert config.MAIL_FROM_NAME == sante_plateforme.NOM_PLATEFORME


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
