"""La récidive d'un équipement, dans la synthèse d'une affaire close (#1647).

Ce que le conseil a arbitré (03/10/2026) et que ce fichier tient :

- **le seuil** : deux AUTRES affaires (trois au total) — une seule est un hasard ;
- **même équipement ET même périmètre** ;
- seules comptent les affaires **résolues** (une annulée n'est pas une
  intervention), closes dans les **24 mois** qui précèdent celle-ci, jamais après ;
- **le conseil seul la lit** : la synthèse validée est lue par les copropriétaires,
  et le bloc nomme d'AUTRES affaires dont ils n'ont pas à connaître l'existence ;
- à l'assistant, elle se dit par **numéros et dates**, jamais par les titres.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from app.models.core import RoleUtilisateur, StatutUtilisateur, Ticket
from app.models.synthese import BROUILLON, SyntheseAffaire
from app.utils import horloge
from app.utils.echeance_contrat import ajouter_mois
from app.utils.synthese_affaire.lecture import metriques, synthese_lue
from app.utils.synthese_affaire.rassemblement import construire_message, metriques_de
from app.utils.synthese_affaire.recidive import (
    CLE,
    FENETRE_MOIS,
    SEUIL_AUTRES,
    recidive_de,
)
from tests.aides_base import compte

CLOTURE = datetime(2026, 10, 3, 12, 0)


def _affaire(session, auteur, n, *, ferme_le=CLOTURE, **champs):
    base = dict(
        numero=f"TK-REC{n:03d}",
        titre=f"Ascenseur, épisode {n}",
        description="<p>Bloqué.</p>",
        categorie="panne",
        equipement="ascenseur",
        perimetre_cible='["bat:1"]',
        statut="résolu",
        auteur_id=auteur.id,
        cree_le=ferme_le - timedelta(days=10),
        ferme_le=ferme_le,
    )
    ticket = Ticket(**{**base, **champs})
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


@pytest.fixture()
def auteur(session):
    return compte(session, prefixe="rec", statut=StatutUtilisateur.copropriétaire_résident)


# ── La fenêtre ──────────────────────────────────────────────────────────────────
def test_il_y_a_vingt_quatre_mois():
    assert ajouter_mois(datetime(2026, 10, 3, 12, 0), -24) == datetime(2024, 10, 3, 12, 0)
    assert ajouter_mois(datetime(2026, 1, 15), -2) == datetime(2025, 11, 15)


def test_un_jour_qui_n_existe_pas_retombe_sur_le_dernier_du_mois():
    #  Le 29/02/2028 reculé de 24 mois : février 2026 n'a que 28 jours.
    assert ajouter_mois(datetime(2028, 2, 29), -24) == datetime(2026, 2, 28)
    assert ajouter_mois(datetime(2026, 3, 31), -1) == datetime(2026, 2, 28)


def test_les_valeurs_arbitrees_sont_celles_du_conseil():
    assert (SEUIL_AUTRES, FENETRE_MOIS) == (2, 24)


# ── Le relevé ───────────────────────────────────────────────────────────────────
def test_sous_le_seuil_rien(session, auteur):
    ticket = _affaire(session, auteur, 1)
    _affaire(session, auteur, 2, ferme_le=CLOTURE - timedelta(days=90))
    assert recidive_de(session, ticket, CLOTURE) is None


def test_au_seuil_le_releve_nomme_les_autres_du_plus_recent_au_plus_ancien(session, auteur):
    ticket = _affaire(session, auteur, 1)
    ancienne = _affaire(session, auteur, 2, ferme_le=CLOTURE - timedelta(days=300))
    recente = _affaire(session, auteur, 3, ferme_le=CLOTURE - timedelta(days=30))
    releve = recidive_de(session, ticket, CLOTURE)
    assert releve["equipement"] == "ascenseur" and releve["mois"] == 24
    assert [a["id"] for a in releve["autres"]] == [recente.id, ancienne.id]
    assert releve["autres"][0]["numero"] == "TK-REC003"


def test_ce_qui_ne_compte_pas(session, auteur):
    ticket = _affaire(session, auteur, 1)
    _affaire(session, auteur, 2, ferme_le=CLOTURE - timedelta(days=30))  # la seule qui compte
    #  un autre périmètre : un autre appareil
    _affaire(session, auteur, 3, ferme_le=CLOTURE - timedelta(days=40), perimetre_cible='["bat:2"]')
    #  annulée : pas une intervention
    _affaire(session, auteur, 4, ferme_le=CLOTURE - timedelta(days=50), statut="annulé")
    #  hors fenêtre : il y a plus de 24 mois
    _affaire(session, auteur, 5, ferme_le=ajouter_mois(CLOTURE, -24) - timedelta(days=1))
    #  close APRÈS celle-ci : ce n'est pas du passé
    _affaire(session, auteur, 6, ferme_le=CLOTURE + timedelta(days=5))
    #  un autre équipement
    _affaire(session, auteur, 7, ferme_le=CLOTURE - timedelta(days=60), equipement="chaudiere")
    assert recidive_de(session, ticket, CLOTURE) is None  # une seule autre : sous le seuil


def test_un_equipement_non_pose_n_a_pas_de_recidive(session, auteur):
    ticket = _affaire(session, auteur, 1, equipement=None)
    _affaire(session, auteur, 2, equipement=None, ferme_le=CLOTURE - timedelta(days=10))
    _affaire(session, auteur, 3, equipement=None, ferme_le=CLOTURE - timedelta(days=20))
    assert recidive_de(session, ticket, CLOTURE) is None


def test_l_ordre_des_codes_du_perimetre_ne_change_rien(session, auteur):
    ticket = _affaire(session, auteur, 1, perimetre_cible='["bat:1","bat:2"]')
    _affaire(
        session,
        auteur,
        2,
        perimetre_cible='["bat:2","bat:1"]',
        ferme_le=CLOTURE - timedelta(days=9),
    )
    _affaire(
        session,
        auteur,
        3,
        perimetre_cible='["bat:1","bat:2"]',
        ferme_le=CLOTURE - timedelta(days=8),
    )
    assert len(recidive_de(session, ticket, CLOTURE)["autres"]) == 2


# ── La synthèse ─────────────────────────────────────────────────────────────────
def _trois(session, auteur):
    ticket = _affaire(session, auteur, 1, ferme_le=horloge.maintenant())
    for n in (2, 3):
        _affaire(session, auteur, n, ferme_le=horloge.maintenant() - timedelta(days=20 * n))
    return ticket


def test_les_metriques_figees_portent_la_recidive_et_le_message_la_dit_sans_titres(session, auteur):
    from app.routers.tickets.commun import STATUT_LABELS

    ticket = _trois(session, auteur)
    met = metriques_de(session, ticket, ticket.ferme_le)
    assert [a["numero"] for a in met[CLE]["autres"]] == ["TK-REC002", "TK-REC003"]
    message = construire_message(session, ticket, met, STATUT_LABELS)
    assert "Récidive : 2 autres affaires résolues sur le même équipement" in message
    assert "TK-REC002" in message and "TK-REC003" in message
    #  D'autres affaires : leur numéro suffit, leur titre n'a pas à partir chez l'assistant.
    assert "épisode 2" not in message and "épisode 3" not in message


def test_sans_recidive_la_cle_est_absente_et_le_message_se_tait(session, auteur):
    from app.routers.tickets.commun import STATUT_LABELS

    ticket = _affaire(session, auteur, 1, ferme_le=horloge.maintenant())
    met = metriques_de(session, ticket, ticket.ferme_le)
    assert CLE not in met
    assert "Récidive" not in construire_message(session, ticket, met, STATUT_LABELS)


def test_le_conseil_seul_lit_la_recidive(session, auteur):
    ticket = _trois(session, auteur)
    met = metriques_de(session, ticket, ticket.ferme_le)
    synthese = SyntheseAffaire(
        ticket_id=ticket.id, statut=BROUILLON, metriques_json=json.dumps(met, ensure_ascii=False)
    )
    session.add(synthese)
    session.commit()
    #  Par défaut — le carnet, un oubli de l'appelant — la clé est retirée.
    assert CLE not in metriques(synthese)
    assert CLE not in synthese_lue(session, synthese).metriques
    assert CLE in metriques(synthese, conseil=True)
    assert CLE in synthese_lue(session, synthese, conseil=True).metriques
    #  Et la colonne figée n'a pas été touchée : le retrait est à la lecture.
    assert CLE in json.loads(synthese.metriques_json)


def test_la_route_la_donne_au_conseil_et_pas_au_resident(session, auteur):
    from app.routers.tickets import synthese as routes

    cs = compte(session, prefixe="cs", roles_json=RoleUtilisateur.conseil_syndical.value)
    ticket = _trois(session, auteur)
    met = metriques_de(session, ticket, ticket.ferme_le)
    session.add(
        SyntheseAffaire(
            ticket_id=ticket.id,
            statut="validee",
            synthese="<p>Récit</p>",
            metriques_json=json.dumps(met, ensure_ascii=False),
        )
    )
    session.commit()
    vue_cs = routes.lire_synthese(ticket.id, session=session, user=cs).synthese
    vue_resident = routes.lire_synthese(ticket.id, session=session, user=auteur).synthese
    assert CLE in vue_cs.metriques
    assert vue_resident is not None and CLE not in vue_resident.metriques
