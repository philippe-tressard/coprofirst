"""Les arrivées par notification : l'étiquette des liens, et ce qu'on en lit (#1634).

## Ce que ces tests tiennent

- **une** fonction étiquette un lien (`etiqueter_lien`) : `src=courriel:<modèle>`
  ou `src=whatsapp`, avant l'ancre, à côté d'une requête existante — jamais un
  lien d'un autre site, jamais un lien qui porte un jeton (à usage unique,
  `standards/03` §5 bis), jamais deux fois ;
- elle s'applique là où le message se COMPOSE, une fois pour tous les modèles :
  `composer_email` pour les courriels (le texte des modèles en base ne change
  pas), `construire_message` pour le groupe WhatsApp ;
- les modèles des comptes (mot de passe oublié, vérification d'adresse) ne sont
  jamais étiquetés ;
- la synthèse compte les vues arrivées par une étiquette, par canal et par
  modèle, rapportées aux messages envoyés (`historique_email`, `whatsapp_log`).
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from sqlmodel import Session

from app.models.core import HistoriqueEmail, ModeleEmail, TelemetryEvent
from app.models.whatsapp import WhatsAppLog
from app.utils import horloge
from app.utils.arrivees_notification import (
    MODELES_SANS_ETIQUETTE,
    SOURCE_COURRIEL,
    SOURCE_WHATSAPP,
    etiqueter_courriel,
    etiqueter_lien,
    source_courriel,
    synthese_arrivees,
)
from app.utils.email import composer_email
from app.utils.whatsapp_message import construire_message
from tests.aides_base import compte, moteur_de_test

SITE = "https://residence.exemple"


@pytest.mark.parametrize(
    "lien, attendu",
    [
        (f"{SITE}/tickets/34", f"{SITE}/tickets/34?src=courriel:ticket_nouveau"),
        (f"{SITE}/tickets/34#msg-5", f"{SITE}/tickets/34?src=courriel:ticket_nouveau#msg-5"),
        (
            f"{SITE}/admin?onglet=import_tc",
            f"{SITE}/admin?onglet=import_tc&src=courriel:ticket_nouveau",
        ),
        (SITE, f"{SITE}/?src=courriel:ticket_nouveau"),
        ("/tickets/34", "/tickets/34?src=courriel:ticket_nouveau"),
    ],
)
def test_un_lien_du_site_recoit_l_etiquette_avant_l_ancre(lien, attendu):
    assert etiqueter_lien(lien, source_courriel("ticket_nouveau"), SITE) == attendu


@pytest.mark.parametrize(
    "lien",
    [
        "https://autre.exemple/page",
        "mailto:conseil@residence.exemple",
        "//autre.exemple/page",
        f"{SITE}/auth/reinitialisation-mdp?token=abc123",
        f"{SITE}/auth/verifier-email?token=abc123",
        f"{SITE}/tickets/34?src=whatsapp",
        "",
    ],
)
def test_un_lien_etranger_a_jeton_ou_deja_etiquete_ne_change_pas(lien):
    assert etiqueter_lien(lien, SOURCE_WHATSAPP, SITE) == lien


def test_l_etiquette_ne_porte_qu_un_canal_et_un_code_de_modele():
    assert source_courriel("ticket_nouveau") == "courriel:ticket_nouveau"
    #  Un code hors de la forme d'un slug ne part pas dans l'URL : le canal seul.
    assert source_courriel("Jean Dupont <x@y>") == SOURCE_COURRIEL
    assert source_courriel(None) == SOURCE_COURRIEL


def test_le_html_d_un_courriel_est_etiquete_lien_par_lien():
    html = (
        f'<a href="{SITE}/tickets/3" style="x">Ouvrir</a>'
        f'<a href="mailto:a@b.c">écrire</a>'
        f'<a href="{SITE}/admin?onglet=a&amp;b=1">Admin</a>'
    )
    sortie = etiqueter_courriel(html, SITE, "ticket_nouveau")
    assert f'href="{SITE}/tickets/3?src=courriel:ticket_nouveau" style="x"' in sortie
    assert 'href="mailto:a@b.c"' in sortie
    assert f'href="{SITE}/admin?onglet=a&amp;b=1&amp;src=courriel:ticket_nouveau"' in sortie


@pytest.mark.parametrize("code", sorted(MODELES_SANS_ETIQUETTE))
def test_les_courriels_des_comptes_ne_sont_jamais_etiquetes(code):
    html = f'<a href="{SITE}/tableau-de-bord">Accéder</a>'
    assert etiqueter_courriel(html, SITE, code) == html


def test_composer_email_etiquette_les_liens_de_tout_modele():
    """La SEULE composition du projet (#498) : l'aperçu montre ce qui partira."""
    modele = ModeleEmail(
        code="ticket_nouveau",
        libelle="Nouvelle affaire",
        sujet="Affaire",
        corps_html='<a href="{{ app.url }}/tickets/{{ ticket.id }}">Ouvrir</a>',
    )
    ctx = {"annee": 2026, "app": {"url": SITE}, "ticket": {"id": 7}}
    _, html = composer_email(modele, ctx, site_nom="R", site_url=SITE, email_footer="")
    assert f'href="{SITE}/tickets/7?src=courriel:ticket_nouveau"' in html


def test_composer_email_n_etiquette_pas_le_lien_du_mot_de_passe_oublie():
    from app.seed import EMAIL_TEMPLATES

    code, libelle, sujet, corps, *_ = next(
        t for t in EMAIL_TEMPLATES if t[0] == "reinitialisation_mdp"
    )
    modele = ModeleEmail(code=code, libelle=libelle, sujet=sujet, corps_html=corps)
    lien = f"{SITE}/auth/reinitialisation-mdp?token=abc123"
    ctx = {
        "annee": 2026,
        "app": {"url": SITE},
        "residence": {"nom": "R"},
        "lien": lien,
        "destinataire": {"prenom": "Anne"},
    }
    _, html = composer_email(modele, ctx, site_nom="R", site_url=SITE, email_footer="")
    assert f'href="{lien}"' in html
    #  L'ÉTIQUETTE (`?src=…`, `&src=…`), pas l'attribut `src` : l'en-tête porte
    #  l'image du logo par son adresse publique depuis #1728.
    assert not re.search(r"[?&](amp;)?src=", html)


def test_le_message_whatsapp_etiquette_son_lien():
    config = {"site_url": SITE, "whatsapp_footer": "— CS"}
    message = construire_message(
        "Titre", "<p>Texte</p>", False, None, config, lien=f"{SITE}/tickets/9"
    )
    assert f"{SITE}/tickets/9?src=whatsapp" in message
    #  Le message réservé renvoie à l'accueil : étiqueté aussi.
    restreint = construire_message("Titre", "x", False, None, config, '["copropriétaires"]')
    assert f"{SITE}/?src=whatsapp" in restreint


def test_la_synthese_rapporte_les_arrivees_aux_envois():
    moteur = moteur_de_test()
    maintenant = horloge.maintenant()
    with Session(moteur) as s:
        a, b = compte(s).id, compte(s).id
        s.add(
            ModeleEmail(code="ticket_nouveau", libelle="Nouvelle affaire", sujet="", corps_html="")
        )
        for user_id, detail in [
            (a, "courriel:ticket_nouveau"),
            (a, "courriel:ticket_nouveau"),
            (b, "courriel:ticket_nouveau"),
            (None, "whatsapp"),  # un anonyme : renvoyé à la connexion, compté quand même
            (a, None),  # une vue ordinaire
            (a, "texte libre"),  # pas une étiquette
        ]:
            s.add(TelemetryEvent(user_id=user_id, page="/tickets/3", detail=detail))
        #  Trop vieux : hors période.
        s.add(
            TelemetryEvent(
                user_id=b,
                page="/",
                detail="whatsapp",
                cree_le=maintenant - timedelta(days=40),
            )
        )
        for statut in ("succes", "succes", "erreur"):
            s.add(HistoriqueEmail(code="ticket_nouveau", destinataire="x@y.z", statut=statut))
        s.add(HistoriqueEmail(code="sondage_nouveau", destinataire="x@y.z", statut="succes"))
        s.add(WhatsAppLog(message="m", statut="envoyé"))
        s.commit()
        lignes = synthese_arrivees(s, horloge.aujourd_hui() - timedelta(days=30))
    assert lignes == [
        {
            "canal": "courriel",
            "modele": "ticket_nouveau",
            "libelle": "Nouvelle affaire",
            "arrivees": 3,
            "comptes": 2,
            "envois": 2,
        },
        {
            "canal": "whatsapp",
            "modele": None,
            "libelle": None,
            "arrivees": 1,
            "comptes": 0,
            "envois": 1,
        },
        #  Envoyé, jamais suivi : c'est du bruit, et l'écran doit le montrer.
        {
            "canal": "courriel",
            "modele": "sondage_nouveau",
            "libelle": None,
            "arrivees": 0,
            "comptes": 0,
            "envois": 1,
        },
    ]


def test_la_collecte_garde_l_etiquette_et_le_tableau_la_rend():
    """Le bout à bout : une vue étiquetée arrive, l'administrateur la lit par canal."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.models.core import RoleUtilisateur
    from tests.aides_http import base_http, client_http

    with base_http() as moteur:
        vue = {"page": "/tickets/3", "action": "view", "detail": "courriel:ticket_nouveau"}
        assert TestClient(app).post("/telemetry/collect", json={"events": [vue]}).status_code == 204
        http, _ = client_http(moteur, RoleUtilisateur.admin)
        d = http.get("/telemetry/dashboard", params={"scope": "jour"}).json()
    assert d["arrivees"] == [
        {
            "canal": "courriel",
            "modele": "ticket_nouveau",
            "libelle": None,
            "arrivees": 1,
            "comptes": 0,
            "envois": None,
        }
    ]


def test_le_filtre_de_la_lecture_ecarte_les_arrivees_d_un_compte():
    """« Sans le gestionnaire du site » : ses arrivées sortent, celles des autres restent."""
    from sqlalchemy import or_

    moteur = moteur_de_test()
    with Session(moteur) as s:
        gestionnaire, autre = compte(s).id, compte(s).id
        for user_id in (gestionnaire, autre, None):
            s.add(TelemetryEvent(user_id=user_id, page="/", detail="whatsapp"))
        s.commit()
        filtre = [or_(TelemetryEvent.user_id.is_(None), TelemetryEvent.user_id != gestionnaire)]
        (ligne,) = synthese_arrivees(s, horloge.aujourd_hui(), filtre)
    assert (ligne["arrivees"], ligne["comptes"]) == (2, 1)
