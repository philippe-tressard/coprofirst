"""La relève vérifie l'authenticité sur les OCTETS reçus, et reporte ce qu'elle
ne peut pas vérifier (28/09/2026).

`test_courriel_authenticite` éprouve la vérification ; ce fichier éprouve son
BRANCHEMENT — le tuyau qui la nourrit. Deux choses ne se voient que d'ici :

- la relève passe à `traiter` le verdict calculé sur le message brut, et non
  un en-tête qu'il aurait pu lire lui-même ;
- un DNS injoignable laisse le message NON LU : il n'est ni refusé (le conseil
  serait prévenu d'une usurpation qui n'en est pas une), ni acquitté (la
  réponse serait perdue).
"""

from __future__ import annotations

import pytest

from app.utils import courriel_boite
from app.utils.courriel_authenticite import VerificationReportee
from tests.aides_courriel import imap_actif, journal  # noqa: F401 — fixtures

_BRUT = (
    b"From: gestion@syndic.fr\r\n"
    b"To: affaire@5hostachy.fr\r\n"
    b"Subject: Re: Affaire #TK-121048\r\n"
    b"Date: Mon, 28 Sep 2026 16:37:00 +0200\r\n"
    b"\r\n"
    b"Nous intervenons jeudi.\r\n"
)


class _BoiteUnMessage:
    """Une boîte qui porte un message non lu, et note ce qu'on en fait."""

    def __init__(self):
        self.acquittes: list[bytes] = []

    def login(self, *_a):
        return ("OK", [b""])

    def select(self, *_a, **_k):
        return ("OK", [b"1"])

    def search(self, *_a):
        return ("OK", [b"1"])

    def fetch(self, numero, _quoi):
        return ("OK", [(b"1 (BODY[] {%d}" % len(_BRUT), _BRUT)])

    def store(self, numero, *_a):
        self.acquittes.append(numero)

    def logout(self):
        return ("BYE", [b""])


@pytest.fixture()
def boite(monkeypatch, imap_actif):  # noqa: F811
    b = _BoiteUnMessage()
    monkeypatch.setattr(courriel_boite.imaplib, "IMAP4_SSL", lambda *_a, **_k: b)
    return b


def test_la_releve_verifie_les_OCTETS_recus_et_transmet_le_verdict(boite, monkeypatch):
    vus: dict = {}

    def verifier(brut, from_):
        vus["brut"], vus["from"] = brut, from_
        return (True, "signé par syndic.fr")

    def traiter(session, entetes, corps, recu_le, plancher, authentification=None, pieces=None):
        vus["authentification"], vus["pieces"] = authentification, pieces
        return courriel_boite.ACCEPTE

    monkeypatch.setattr(courriel_boite, "verifier_expediteur", verifier)
    monkeypatch.setattr(courriel_boite, "traiter", traiter)

    courriel_boite.relever()

    assert vus["brut"] == _BRUT, "la vérification doit porter sur le message tel que reçu"
    assert vus["from"] == "gestion@syndic.fr"
    assert vus["authentification"] == (True, "signé par syndic.fr")
    assert vus["pieces"] is not None, "les pièces jointes sont triées sur le message reçu"
    assert boite.acquittes == [b"1"]


def test_un_DNS_injoignable_laisse_le_message_NON_LU(boite, journal, monkeypatch):  # noqa: F811
    def verifier(_brut, _from):
        raise VerificationReportee("DNS injoignable (Timeout)")

    def traiter(*_a, **_k):
        raise AssertionError("un message invérifié ne doit recevoir aucun verdict")

    monkeypatch.setattr(courriel_boite, "verifier_expediteur", verifier)
    monkeypatch.setattr(courriel_boite, "traiter", traiter)

    comptes = courriel_boite.relever()

    assert boite.acquittes == [], "acquitté, le message ne serait jamais repris"
    assert not any(comptes.values())
    assert any("reportée" in m for m in journal), "le report doit se lire au journal"
