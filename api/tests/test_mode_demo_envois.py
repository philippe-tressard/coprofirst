"""Zéro envoi réel en démo (spec `specs/architecture/mode-demo.md` §4.2 et §4.4, lot D2 #1902).

Chaque PORTE d'appel sortant est éprouvée dans la situation la plus défavorable :
la démo posée, la configuration en base qui allume tout — c'est ce qu'un visiteur
administrateur pourrait écrire —, et un faux réseau qui ÉCHOUE s'il est contacté.
Un test qui passerait parce que le service est éteint en base ne prouverait rien.

Et le contrat du puits : il rend FAUX, jamais un faux succès — la purge des comptes
inactifs n'ouvre son délai que sur un envoi parti (#1580).
"""

from __future__ import annotations

import asyncio

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import select

from app.config import get_settings
from app.models.core import ConfigSite, HistoriqueEmail
from app.utils import demo, email, installation, llm, services, taches, tarif_sources, whatsapp
from app.utils.llm_modeles import modeles_disponibles


@pytest.fixture
def en_demo(monkeypatch):
    monkeypatch.setattr(get_settings(), "mode_demo", "oui")


@pytest.fixture
def reseau_interdit(monkeypatch):
    """Tout client HTTP, IMAP ou SMTP construit pendant le test le fait échouer."""

    def _interdit(*_a, **_k):
        raise AssertionError("un appel réseau est parti de la démo")

    monkeypatch.setattr(whatsapp.httpx, "Client", _interdit)
    monkeypatch.setattr("httpx.AsyncClient", _interdit)
    monkeypatch.setattr("imaplib.IMAP4_SSL", _interdit)
    monkeypatch.setattr("app.utils.email.connexion_smtp", _interdit)


@pytest.fixture
def tout_allume(session):
    """La base qu'un visiteur administrateur aurait réécrite : tout est allumé."""
    for cle, valeur in {
        "smtp_enabled": "1",
        "llm_actif": "1",
        "whatsapp_enabled": "1",
        "imap_enabled": "1",
        "verification_version_active": "1",
        "whatsapp_api_url": "http://whatsapp-bridge:8090",
        "whatsapp_group_jid": "groupe@g.us",
    }.items():
        session.add(ConfigSite(cle=cle, valeur=valeur))
    session.commit()
    return session


# ── Courriels : le moteur ───────────────────────────────────────────────────


def test_en_demo_le_moteur_n_envoie_rien_et_le_dit(en_demo, reseau_interdit, tout_allume):
    session = tout_allume
    assert email.envoi_actif(session) is False
    parti = asyncio.run(email.send_email("verification_email", "x@exemple.invalid", {}, session))
    assert parti is False, "le puits rend faux, jamais un faux succès (#1580)"
    trace = session.exec(select(HistoriqueEmail)).all()
    assert [(t.statut, t.erreur) for t in trace] == [("ignore", "démonstration : non envoyé")]


def test_en_demo_l_envoi_groupe_n_envoie_rien(en_demo, reseau_interdit, tout_allume):
    session = tout_allume
    asyncio.run(email.send_email_group("annonce", [(None, "a@exemple.invalid")], {}, session))
    assert [t.statut for t in session.exec(select(HistoriqueEmail)).all()] == ["ignore"]


def test_hors_demo_le_moteur_obeit_a_la_configuration(tout_allume):
    assert email.envoi_actif(tout_allume) is True


# ── WhatsApp, IA, version, tarifs ───────────────────────────────────────────


def test_en_demo_le_bridge_n_est_jamais_appele(en_demo, reseau_interdit):
    with pytest.raises(demo.FermeEnDemo):
        whatsapp._poster_au_bridge("http://whatsapp-bridge:8090/send", {}, {})
    with pytest.raises(demo.FermeEnDemo):
        whatsapp.get_whatsapp_status({"whatsapp_api_url": "http://whatsapp-bridge:8090"})


def test_en_demo_le_fournisseur_d_ia_n_est_jamais_appele(en_demo, reseau_interdit):
    with pytest.raises(demo.FermeEnDemo):
        asyncio.run(llm._appeler(None, "consigne", "message", 10, ()))


def test_en_demo_la_liste_des_modeles_ne_sort_pas(en_demo, reseau_interdit, session):
    rendu = asyncio.run(modeles_disponibles(session))
    assert rendu == {"listable": False, "motif": demo.MESSAGE, "modeles": []}


def test_en_demo_la_grille_tarifaire_ne_sort_pas(en_demo, reseau_interdit):
    with pytest.raises(tarif_sources.SourceIndisponible):
        asyncio.run(tarif_sources._lire("https://fournisseur.example/prix"))


class _ClientQuiEchoue:
    def get(self, *_a, **_k):
        raise AssertionError("le dépôt GitHub a été interrogé depuis la démo")


def test_en_demo_la_version_n_est_pas_verifiee(en_demo):
    rendu = installation.verifier("7bec36e", "replica", client=_ClientQuiEchoue())
    assert rendu.etat == "non_verifie"


# ── Les services se lisent éteints ──────────────────────────────────────────


@pytest.mark.parametrize("code", sorted(c for c, s in services.SERVICES.items() if s.coupable))
def test_en_demo_aucun_service_ne_s_allume(en_demo, code):
    assert not services.service_actif({services.cle_actif(code): "1"}, code)


@pytest.mark.parametrize("code", sorted(c for c, s in services.SERVICES.items() if s.coupable))
def test_hors_demo_un_service_allume_l_est(code):
    assert services.service_actif({services.cle_actif(code): "1"}, code)


# ── Les tâches planifiées ───────────────────────────────────────────────────


def _planificateur(ids) -> BackgroundScheduler:
    planif = BackgroundScheduler()
    for identifiant in ids:
        planif.add_job(lambda: None, "interval", hours=1, id=identifiant)
    return planif


def test_chaque_tache_hors_demo_est_une_tache_declaree():
    assert set(taches.TACHES_HORS_DEMO) <= set(taches.TACHES_PERMANENTES)


def test_en_demo_les_taches_hors_demo_sont_retirees(en_demo):
    planif = _planificateur([*taches.TACHES_PERMANENTES, "backup_rattrapage"])
    retirees = taches.retirer_hors_demo(planif)
    assert set(retirees) == set(taches.TACHES_HORS_DEMO) | {"backup_rattrapage"}
    restantes = {job.id for job in planif.get_jobs()}
    assert {"bail_installation", "sante_plateforme"} <= restantes, (
        "le registre (M11) et les alertes de plateforme restent voulus en démo"
    )


def test_en_demo_une_tache_retiree_n_est_pas_une_tache_disparue(en_demo, caplog):
    planif = _planificateur(taches.TACHES_PERMANENTES)
    taches.retirer_hors_demo(planif)
    import logging

    assert taches.verifier_taches_enregistrees(planif, logging.getLogger("taches")) == []


def test_hors_demo_rien_n_est_retire():
    planif = _planificateur(taches.TACHES_PERMANENTES)
    assert taches.retirer_hors_demo(planif) == []
    assert len(planif.get_jobs()) == len(taches.TACHES_PERMANENTES)
