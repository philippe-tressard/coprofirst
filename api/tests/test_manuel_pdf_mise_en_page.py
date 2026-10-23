"""La mise en page du manuel PDF : les trois défauts signalés le 23/10/2026.

Des pages presque vides derrière un titre, des mots imprimés les uns sur les
autres, des fiches plus hautes qu'une page. Chacun avait une cause dans la
feuille de style du PDF (`utils/manuel_pdf_css`), et c'est elle qu'on lit ici.

⚠️ Ces tests lisent du CSS, ce qui est un pis-aller assumé : WeasyPrint ne
s'installe pas sur le poste, et le rendu ne se mesure pas en CI. Ils tiennent les
causes connues ; le rendu, lui, a été constaté page par page au moment du
correctif, dans l'image de l'API.
"""

from __future__ import annotations

import re

from app.utils.manuel_pdf_css import css_du_pdf

GRILLES = (".ecran-grid", ".quick-grid", ".persona-grid", ".profils-grid")


def _regle(css: str, selecteur: str) -> str:
    """Le corps de la règle qui commence par `selecteur` (la première)."""
    trouve = re.search(re.escape(selecteur) + r"[^{]*\{([^}]*)\}", css)
    assert trouve, f"la règle `{selecteur}` a disparu de la feuille du PDF"
    return trouve.group(1)


def test_les_accolades_de_la_feuille_sont_EQUILIBREES():
    """🔴 Une accolade orpheline suivait `regle_page()`, et personne ne l'a vue.

    Le moteur jetait alors la règle suivante — `@page garde` : la page de garde,
    une affiche, recevait les marges et le numéro des autres pages. Le journal du
    rendu le disait (« Invalid or unsupported selector »), qu'on ne lit pas.
    """
    css = css_du_pdf("")
    assert css.count("{") == css.count("}"), (
        f"{css.count('{')} accolade(s) ouvrante(s), {css.count('}')} fermante(s)"
    )
    assert "@page garde" in css


def test_les_grilles_sont_des_GRILLES_et_non_des_colonnes():
    """🔴 `column-count` repoussait la grille entière à la page suivante.

    « Pour qui ? », « Mini sommaire par profil », la grille des écrans : chacun
    laissait une page presque vide derrière son titre. Une grille CSS se coupe
    entre deux rangées.
    """
    css = css_du_pdf("")
    corps = _regle(css, ", ".join(GRILLES))
    assert "column-count" not in corps
    assert "display: grid" in corps


def test_un_libelle_de_tableau_se_COUPE_au_lieu_de_deborder():
    """🔴 « Copro-bailleurs, Bailleurs, Locataires… » s'imprimait sur la colonne voisine.

    À l'écran, le premier libellé ne se coupe pas (`white-space: nowrap`) ; dans
    la largeur d'une page, il débordait sur son explication.
    """
    regles = re.findall(r"\.affaire-table td:first-child \{([^}]*)\}", css_du_pdf(""))
    assert any("white-space: normal" in r for r in regles)


def test_un_pictogramme_reste_DANS_sa_phrase():
    """🔴 `inline-flex` se lit comme un bloc : le crayon partait seul sur sa ligne.

    Chaque pictogramme au trait d'une phrase la coupait en trois — le texte, le
    dessin seul, la suite.
    """
    corps = _regle(css_du_pdf(""), ".ic, .pastille-lecture-ex")
    assert "display: inline" in corps
