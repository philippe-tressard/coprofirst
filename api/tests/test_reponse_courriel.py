"""La réponse du syndic par courriel : mise en forme, original conservé, datée (#1322).

Voir `app/utils/reponse_courriel.py`. Ce qui est vérifié ici :

- la Suite est datée de l'ENVOI du courriel, fuseau converti ;
- sans assistant (coupé, non réglé, en échec, réponse suspecte), le texte
  nettoyé entre quand même : une réponse n'est jamais perdue ;
- avec l'assistant, la Suite porte le texte mis en forme, la marque ✨, et le
  texte reçu est conservé.
"""

from __future__ import annotations

import pathlib
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.utils import llm
from app.utils.courriel_boite import traiter
from app.utils.courriel_ingestion import ACCEPTE
from app.utils.reponse_courriel import (
    date_d_envoi,
    mettre_en_forme,
    moment_de_la_suite,
)
from tests.aides_courriel import (  # noqa: F401 — `scene` est une fixture
    _AUTH_OK,
    _entetes_reponse,
    _evolutions,
    scene,
)

_BOITE = pathlib.Path(__file__).resolve().parents[1] / "app" / "utils" / "courriel_boite.py"

_RECU = (
    "Bonjour,\n\n\nNous intervenons jeudi 2 octobre à 9 h.\n\n\nCordialement,\n"
    "Jean Martin\nCabinet Syndic — 01 02 03 04 05\n"
    "Ce message est confidentiel."
)


def _modele(texte: str | None = None, erreur: Exception | None = None):
    async def faux(session, *, usage, message, **_):
        assert usage == "reponse_courriel"
        if erreur:
            raise erreur
        return SimpleNamespace(texte=texte)

    return faux


# ── La date ───────────────────────────────────────────────────────────────────


def test_la_date_d_envoi_est_convertie_en_utc():
    """🔴 Cas zéro : la relève jetait le fuseau — 18:00 +0200 devenait 18:00 UTC."""
    assert date_d_envoi("Thu, 25 Sep 2026 18:00:00 +0200") == datetime(2026, 9, 25, 16, 0)
    assert date_d_envoi("Thu, 25 Sep 2026 18:00:00 -0000") == datetime(2026, 9, 25, 18, 0)
    assert date_d_envoi("") is None
    assert date_d_envoi("pas une date") is None


def test_la_releve_passe_par_la_conversion_partagee():
    """La relève ne relit plus l'en-tête elle-même : une seule conversion."""
    source = _BOITE.read_text(encoding="utf-8")
    assert "parsedate_to_datetime" not in source, (
        "courriel_boite relit l'en-tête Date lui-même : passer par date_d_envoi"
    )
    assert "date_d_envoi(" in source


def test_une_date_absente_ou_future_date_la_suite_de_la_releve():
    maintenant = datetime(2026, 9, 25, 20, 0)
    envoi = datetime(2026, 9, 25, 16, 0)
    assert moment_de_la_suite(envoi, maintenant) == envoi
    assert moment_de_la_suite(None, maintenant) == maintenant
    assert moment_de_la_suite(maintenant + timedelta(hours=2), maintenant) == maintenant


# ── La mise en forme, et ses replis ───────────────────────────────────────────


def test_l_assistant_met_en_forme_et_le_recu_est_garde(monkeypatch):
    #  Sans base : la porte des courriels lit le prompt réglé (#2369).
    monkeypatch.setattr(llm, "config_llm", lambda session, usage: SimpleNamespace(prompt="…"))
    monkeypatch.setattr(llm, "demander", _modele("Nous intervenons jeudi 2 octobre à 9 h."))
    t = mettre_en_forme(None, "Nous intervenons jeudi 2 octobre à 9 h.\n\n\nCordialement", _RECU)
    assert t.contenu == "Nous intervenons jeudi 2 octobre à 9 h."
    assert t.assiste is True
    assert t.origine == _RECU


@pytest.mark.parametrize(
    "faux",
    [
        _modele(erreur=llm.ErreurLLM("usage non réglé")),
        _modele(erreur=RuntimeError("délai")),
        _modele(""),
        _modele("Nous intervenons jeudi. " * 20),  # plus long : il a ajouté
    ],
    ids=["usage-coupe", "panne", "vide", "invente"],
)
def test_sans_assistant_fiable_le_texte_nettoye_entre_quand_meme(monkeypatch, faux):
    monkeypatch.setattr(llm, "demander", faux)
    t = mettre_en_forme(None, "Nous intervenons jeudi.", _RECU)
    assert t.contenu == "Nous intervenons jeudi."
    assert t.assiste is False
    assert t.origine is None


# ── Ce qui est écrit dans le fil ──────────────────────────────────────────────


def test_la_suite_est_datee_de_l_envoi_sans_assistant(scene):  # noqa: F811
    """🔴 Cas zéro : la Suite était datée de la relève."""
    session, ticket, syndic, _cs = scene
    envoi = datetime(2026, 9, 25, 16, 0)
    assert traiter(
        session,
        _entetes_reponse(ticket.jeton_courriel, de=syndic.email),
        _RECU,
        envoi,
        authentification=_AUTH_OK,
    ) == (ACCEPTE)
    (evol,) = _evolutions(session, ticket)
    assert evol.cree_le == envoi
    assert evol.assiste_ia is False and evol.contenu_origine is None
    assert "Nous intervenons jeudi" in evol.contenu


def test_la_suite_porte_la_mise_en_forme_et_le_texte_recu(scene, monkeypatch):  # noqa: F811
    session, ticket, syndic, _cs = scene
    monkeypatch.setattr(llm, "demander", _modele("Nous intervenons jeudi 2 octobre à 9 h."))
    traiter(
        session,
        _entetes_reponse(ticket.jeton_courriel, de=syndic.email),
        _RECU,
        datetime(2026, 9, 25),
        authentification=_AUTH_OK,
    )
    (evol,) = _evolutions(session, ticket)
    assert evol.contenu.endswith("<p>Nous intervenons jeudi 2 octobre à 9 h.</p>")
    assert evol.assiste_ia is True
    assert evol.contenu_origine == _RECU


# ── La ligne « Mail reçu de … le … », écrite par le code (25/09, libellé du 28/09) ─


def test_la_suite_s_ouvre_sur_qui_a_repondu_et_quand(scene):  # noqa: F811
    """En italique, en tête : le nom du compte (l'adresse seule n'en porte pas), et
    la date d'ENVOI en heure de Paris — 16:00 UTC le 25/09 → 18:00."""
    session, ticket, syndic, _cs = scene
    traiter(
        session,
        _entetes_reponse(ticket.jeton_courriel, de=syndic.email),
        "Nous intervenons jeudi.",
        datetime(2026, 9, 25, 16, 0),
        authentification=_AUTH_OK,
    )
    (evol,) = _evolutions(session, ticket)
    assert evol.contenu.startswith(
        "<p><em>Mail reçu de G S le 25 septembre 2026 à 18:00</em></p>"
    ), evol.contenu


def test_le_nom_affiche_du_courriel_prime_et_le_texte_recu_est_echappe():
    from app.utils.reponse_courriel import contenu_de_la_suite

    html = contenu_de_la_suite(
        "Jean Martin <jm@syndic.fr>",
        "G S",
        datetime(2026, 9, 25, 16, 0),
        "Ligne 1\nLigne <2>\n\nParagraphe & fin",
    )
    assert html == (
        "<p><em>Mail reçu de Jean Martin le 25 septembre 2026 à 18:00</em></p>"
        "<p>Ligne 1<br>Ligne &lt;2&gt;</p><p>Paragraphe &amp; fin</p>"
    )
