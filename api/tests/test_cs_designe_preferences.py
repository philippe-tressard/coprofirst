"""Le conseil désigné par la Diffusion reçoit, et l'aperçu nomme qui ne recevra rien (#2006).

## Le constat du 15/10/2026

Un commentaire sur une affaire, envoyé avec la case « Conseil syndical » cochée,
n'a pas atteint deux membres du CS : leurs deux cases « courriel » étaient
décochées — par une migration, pas par leur profil —, et `send_email_group`
appliquait la préférence à chacun. L'aperçu, lui, les annonçait.

## L'arbitrage

La préférence règle ce qu'un RÉSIDENT reçoit ; un courriel adressé au conseil
s'adresse à son mandat. Les cases syndic / CS désignent (`Designe`, posé par
`syndic_puis`, leur seule source) ; les notifications automatiques gardent la
préférence. Et l'aperçu trie par la fonction même de l'envoi.

Ces tests sont de **comportement** : ils font partir l'envoi groupé jusqu'à la
liste des adresses qu'il remet au transport.
"""

from __future__ import annotations

import asyncio
import json

import pytest

import app.utils.email as module_email
from app.models.core import MembreCS
from app.utils.apercu_diffusion import apercu_email
from app.utils.destinataires import (
    MOTIF_DESACTIVE,
    MOTIF_SANS_ADRESSE,
    MOTIF_SANS_COMPTE,
    cs_du_perimetre_ecartes,
    destinataires_syndic_cs,
    ecartes_syndic_cs,
)
from app.utils.preferences_mail import MOTIF_PREFERENCE, Designe
from tests.aides_base import compte

TOUT_COUPE = json.dumps({"mon_batiment_mail": False, "autres_batiments_mail": False})


def _conseiller(session, **champs):
    return compte(session, roles_json="résident,conseil_syndical", **champs)


@pytest.fixture()
def remis(monkeypatch):
    """Les adresses que l'envoi groupé remet au transport — rien ne part vraiment."""
    adresses: list[str] = []

    async def _transport(code, context, session, *, to, cc=None, **_):
        adresses.extend([*to, *(cc or [])])
        return True

    monkeypatch.setattr(module_email, "envoi_actif", lambda _s: True)
    monkeypatch.setattr(module_email, "_envoyer_modele", _transport)
    return adresses


def _envoyer(session, destinataires, **kw):
    asyncio.run(
        module_email.send_email_group(
            code="ticket_syndic", to_recipients=destinataires, context={}, session=session, **kw
        )
    )


def test_le_cs_coche_recoit_malgre_ses_cases_decochees(session, remis):
    """Le cas du 15/10/2026 : la case « Conseil syndical » atteint TOUT le conseil."""
    coupe = _conseiller(session, nom="DURAND", preferences_notifications=TOUT_COUPE)
    abonne = _conseiller(session, nom="MARTIN")

    destinataires = destinataires_syndic_cs(session, syndic=False, cs=True)
    assert all(isinstance(d, Designe) for d in destinataires)
    #  Même avec un périmètre — une actualité ciblée écartait le CS des autres bâtiments.
    _envoyer(session, destinataires, batiments_concernes={99})

    assert sorted(remis) == sorted([coupe.email, abonne.email])


def test_une_notification_automatique_garde_la_preference(session, remis):
    """Témoin : sans désignation, la préférence du résident tient toujours."""
    coupe = _conseiller(session, preferences_notifications=TOUT_COUPE)
    abonne = _conseiller(session)

    _envoyer(session, [(coupe.id, coupe.email), (abonne.id, abonne.email)])

    assert remis == [abonne.email]


def test_l_apercu_trie_comme_l_envoi(session):
    """Ce que l'envoi écarterait, l'aperçu le nomme — avec le motif."""
    coupe = compte(session, prenom="Jean", nom="DURAND", preferences_notifications=TOUT_COUPE)

    canal = apercu_email(
        session,
        code_modele="ticket_syndic",
        contexte={},
        destinataires=[(coupe.id, coupe.email)],
        lecteur=coupe,
    )

    assert not canal.actif
    assert [(e.qui, e.motif) for e in canal.ecartes] == [("Jean DURAND", MOTIF_PREFERENCE)]


def test_les_ecartes_du_conseil_sont_nommes(session):
    """Sans adresse, compte désactivé : nommés. Cases décochées : RETENU, donc tu."""
    _conseiller(session, prenom="Paul", nom="MARTIN", email="")
    _conseiller(session, prenom="Anne", nom="DURAND", actif=False)
    _conseiller(session, prenom="Luc", nom="BERNARD", preferences_notifications=TOUT_COUPE)

    ecartes = ecartes_syndic_cs(session, syndic=True, cs=True)

    assert ("Paul MARTIN", MOTIF_SANS_ADRESSE) in ecartes
    assert ("Anne DURAND", MOTIF_DESACTIVE) in ecartes
    assert not any("BERNARD" in qui for qui, _ in ecartes)
    #  Aucun gestionnaire principal : le syndic coché ne partira pas, et cela se dit.
    assert any(qui == "Syndic" for qui, _ in ecartes)


def test_le_cs_du_perimetre_nomme_le_membre_sans_compte(session):
    """L'annonce de hall choisit le CS par le périmètre : un membre sans compte y est nommé."""
    from app.models.core import GenreCivilite

    session.add(MembreCS(genre=GenreCivilite.mr, prenom="Marc", nom="DURAND"))
    session.commit()

    assert cs_du_perimetre_ecartes(session) == [("Marc DURAND", MOTIF_SANS_COMPTE)]
