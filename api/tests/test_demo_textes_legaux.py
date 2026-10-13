"""Les textes légaux de la démo publique (spec `mode-demo.md` §9, lot D7 #1907).

Ils remplacent les gabarits « À RENSEIGNER » du produit, et l'éditeur comme le
contact viennent du `.env` : le dépôt public ne nomme personne.
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.demo import legal

TEXTES = (legal.mentions_legales, legal.politique_confidentialite)


@pytest.fixture
def reglages(monkeypatch):
    def poser(editeur: str = "", contact: str = ""):
        monkeypatch.setattr(get_settings(), "demo_editeur", editeur)
        monkeypatch.setattr(get_settings(), "demo_contact", contact)

    return poser


@pytest.mark.parametrize("texte", TEXTES)
def test_rien_a_renseigner_et_les_hebergeurs_nommes(reglages, texte):
    reglages(contact="contact@exemple.invalid")
    html = texte()
    assert "À RENSEIGNER" not in html
    assert "Oracle" in html and "Cloudflare" in html
    assert 'href="mailto:contact@exemple.invalid"' in html


def test_sans_editeur_la_demo_se_declare_non_professionnelle(reglages):
    reglages(contact="contact@exemple.invalid")
    assert "à titre non professionnel" in legal.mentions_legales()
    assert "6, III, 2" in legal.mentions_legales()


def test_l_editeur_du_env_est_echappe(reglages):
    reglages(editeur="Témoin <b>& fils</b>", contact="contact@exemple.invalid")
    html = legal.mentions_legales()
    assert "Témoin &lt;b&gt;&amp; fils&lt;/b&gt;" in html
    assert "6, III, 2" not in html


def test_un_contact_absent_se_signale(reglages):
    reglages()
    assert legal.manques() == ["DEMO_CONTACT"]
    assert "adresse de contact non renseignée" in legal.politique_confidentialite()
    reglages(contact="contact@exemple.invalid")
    assert legal.manques() == []


def test_la_politique_dit_ce_que_la_demo_fait(reglages):
    reglages(contact="contact@exemple.invalid")
    html = legal.politique_confidentialite()
    for promesse in ("effacées chaque nuit", "jamais sauvegardées", "aucun courriel", "Paris"):
        assert promesse in html
