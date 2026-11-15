"""La fiche d'accueil se lit sans loupe (#2776).

## Pourquoi

Elle est remise aux nouveaux arrivants, souvent âgés. Ses consignes
s'imprimaient en 10,5 px (7,9 pt), en gris : on la lisait mal. Elle passe en gros
caractères, dans une police dessinée pour les malvoyants, embarquée dans le
document. Ces tests refusent le retour du petit corps, la perte de la police et la
perte d'une ligne de consigne.

Ce qu'ils ne voient pas : la tenue sur UNE page A4. Elle dépend du rendu, et se
vérifie à l'impression de Chromium (`fiche_arrivant_css.py`, en tête).
"""

from __future__ import annotations

import re

import pytest

from app.utils import pdf_theme
from app.utils.fiche_arrivant import decouper_titre, generer_fiche_arrivant
from app.utils.fiche_arrivant_css import CSS

#: Le plus petit corps admis sur la fiche, en px (≈ 7,9 pt). Avant #2776, les
#: contacts descendaient à 8,5 px et les consignes à 10,5 px.
CORPS_MINIMAL = 10.5
#: Le corps des consignes, en px (10,5 pt).
CORPS_CONSIGNES = 14


def _fiche(consignes: list[tuple[str, str]]) -> str:
    return generer_fiche_arrivant(
        cs_data={"membres": []},
        syndic_data={"nom_syndic": "Syndic Témoin", "adresse": "1 rue Témoin", "membres": []},
        site_nom="Résidence Témoin",
        site_url="https://residence.example",
        logo_png=None,
        consignes=consignes,
    )


def _taille(selecteur: str) -> float:
    regle = re.search(re.escape(selecteur) + r"\s*\{([^}]*)\}", CSS)
    assert regle, f"règle absente de la feuille : {selecteur}"
    taille = re.search(r"font-size:\s*([\d.]+)px", regle.group(1))
    assert taille, f"{selecteur} ne fixe plus sa taille"
    return float(taille.group(1))


# ── Le corps ──────────────────────────────────────────────────────────────────


def test_aucun_texte_de_la_fiche_sous_le_corps_minimal():
    tailles = [float(t) for t in re.findall(r"font-size:\s*([\d.]+)px", CSS)]
    assert tailles, "la feuille ne fixe plus aucune taille : le contrôle ne voit rien"
    trop_petites = sorted({t for t in tailles if t < CORPS_MINIMAL})
    assert not trop_petites, f"corps sous {CORPS_MINIMAL} px sur la fiche : {trop_petites}"


def test_les_consignes_s_impriment_en_gros_et_en_noir():
    assert _taille(".regle-contenu li") >= CORPS_CONSIGNES
    regle = re.search(r"\.regle-contenu li\s*\{([^}]*)\}", CSS).group(1)
    assert "color: var(--ink)" in regle, "les consignes repassent en gris"


def test_la_phrase_d_accueil_et_les_noms_restent_lisibles():
    assert _taille(".accueil") >= CORPS_CONSIGNES
    assert _taille(".membre-nom") >= 13


# ── La police ─────────────────────────────────────────────────────────────────


def test_la_police_lisible_est_embarquee_dans_la_fiche():
    """Embarquée, et non installée : c'est le navigateur du lecteur qui imprime."""
    fiche = _fiche([])
    assert "font-family: 'Atkinson Hyperlegible'" in fiche
    assert fiche.count("src: url(data:font/ttf;base64,") == 2, "normal et gras"
    assert f"font-family: {pdf_theme.FONT_LISIBLE}" in CSS


@pytest.mark.parametrize("_style,_graisse,nom", pdf_theme._POLICE_LISIBLE)
def test_les_fichiers_de_la_police_sont_des_truetype(_style, _graisse, nom):
    entete = (pdf_theme._POLICES / nom).read_bytes()[:4]
    assert entete == b"\x00\x01\x00\x00", f"{nom} n'est pas une police TrueType"


def test_sans_ses_fichiers_la_fiche_se_rend_quand_meme(monkeypatch, tmp_path):
    """Un fichier illisible coûte la police, jamais la fiche — et ne se mémorise pas."""
    monkeypatch.setattr(pdf_theme, "_POLICES", tmp_path)
    monkeypatch.setattr(pdf_theme, "_police_lisible_cache", None)
    assert pdf_theme.police_lisible_css() == ""
    assert "Bienvenue dans votre résidence" in _fiche([])
    assert pdf_theme._police_lisible_cache is None


# ── Les rubriques ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "titre,attendu",
    [
        ("📦 1. Emménagement / déménagement", ("📦", "1", "Emménagement / déménagement")),
        ("🗑 2. Sortie des poubelles et tri", ("🗑", "2", "Sortie des poubelles et tri")),
        ("🏢 Parties communes", ("🏢", "", "Parties communes")),
        ("3. Stationnement", ("", "3", "Stationnement")),
        ("Stationnement", ("", "", "Stationnement")),
        ("- Tiret en tête", ("", "", "- Tiret en tête")),
        ("&lt;b&gt; Titre", ("", "", "&lt;b&gt; Titre")),
        ("2026 en vue", ("", "", "2026 en vue")),
    ],
)
def test_le_titre_se_decoupe_sans_rien_perdre(titre, attendu):
    assert decouper_titre(titre) == attendu


def test_chaque_ligne_saisie_devient_une_puce():
    fiche = _fiche([("📦 1. Arrivée", "Première ligne\n\nDeuxième <strong>ligne</strong>")])
    assert "<li>Première ligne</li><li>Deuxième <strong>ligne</strong></li>" in fiche
    assert '<div class="regle-pictogramme">📦</div>' in fiche
    assert '<span class="regle-numero">1.</span>Arrivée' in fiche


def test_un_titre_sans_pictogramme_n_affiche_pas_de_case_vide():
    fiche = _fiche([("Stationnement", "Une ligne")])
    assert 'class="regle sans-pictogramme"' in fiche
    assert "regle-pictogramme" not in fiche.split("<body>")[1]
