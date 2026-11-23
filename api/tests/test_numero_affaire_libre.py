"""Le numéro `TK-` d'une affaire est tiré LIBRE (#1802).

Le défaut, rejoué : `generer_numero()` tirait six chiffres au hasard sans
regarder la base, et la colonne `ticket.numero` est unique. Une collision
faisait échouer la création en `IntegrityError` (500) — en production avec une
chance n/10⁶ par création, et dans la suite de tests, dont les affaires
s'accumulent sur le moteur partagé, assez souvent pour faire tomber une CI
(PR #1801, `test_fusion_affaires`).

Le tirage est FORCÉ ici : un hasard qu'on attend ne prouve rien.
"""

from __future__ import annotations

import pytest

from app.routers.tickets import commun
from tests.aides_affaire import _compte, _creer, session  # noqa: F401


def _tirages(monkeypatch, *suites: str) -> None:
    """`random.choices` rend, dans l'ordre, les chiffres de chaque suite."""
    restantes = iter(suites)
    monkeypatch.setattr(commun.random, "choices", lambda *a, **k: list(next(restantes)))


def test_un_numero_deja_pris_est_ecarte(session, monkeypatch):
    _tirages(monkeypatch, "424242")
    existante = _creer(session, _compte(session), categorie="panne")
    assert existante.numero == "TK-424242"

    _tirages(monkeypatch, "424242", "424242", "123456")
    assert commun.generer_numero(session) == "TK-123456"


def test_la_creation_d_une_affaire_ne_tombe_plus_sur_un_numero_pris(session, monkeypatch):
    """Par la vraie création : le défaut exact de la CI de #1801."""
    auteur = _compte(session)
    _tirages(monkeypatch, "777777")
    _creer(session, auteur, categorie="panne")

    _tirages(monkeypatch, "777777", "888888")
    seconde = _creer(session, auteur, categorie="panne")

    assert seconde.numero == "TK-888888"


def test_l_epuisement_des_essais_le_dit(session, monkeypatch):
    """Jamais une boucle sans fin, ni un numéro pris rendu en silence."""
    _tirages(monkeypatch, "555555")
    _creer(session, _compte(session), categorie="panne")

    _tirages(monkeypatch, *["555555"] * commun.ESSAIS_NUMERO)
    with pytest.raises(RuntimeError, match="numéro"):
        commun.generer_numero(session)
