"""La fiche d'accueil ne coupe jamais son contenu : elle passe sur la feuille suivante (#3143).

## Pourquoi (27/11/2026)

La page de la fiche était fixée à `height: 285mm` avec `overflow: hidden`. Au-delà de
trois rubriques de la taille du gabarit, le bas de la feuille disparaissait sans un
mot : dernières consignes, note « Ce document est un résumé… » et pied de page. Le
conseil peut en saisir jusqu'à douze. Le PDF comptait toujours une page, si bien
qu'un contrôle qui compte les pages ne voyait rien.

Mesuré à l'impression de Chromium en A4, avec douze rubriques : 616 px coupés, pied
de page invisible. Après correctif : deux feuilles, rien de coupé, chaque rubrique
entière sur sa feuille.

La règle est celle de `standards/11` §11 bis : sur papier rien ne défile, et un cadre
à hauteur fixe tronque.

## Ce que ces tests refusent

- partout : la feuille de style qui fige la hauteur de `.page` ;
- au rendu réel (WeasyPrint, en CI) : un texte de la fiche posé hors de sa feuille,
  avec le nombre maximal de rubriques que l'API admet.
"""

from __future__ import annotations

import re

from app.utils.consignes_arrivant import Consignes
from app.utils.fiche_arrivant import generer_fiche_arrivant
from app.utils.fiche_arrivant_css import CSS
from tests.aides_pdf import besoin_weasyprint

#: Le nombre maximal de rubriques que l'API admet, lu sur le schéma, jamais recopié.
MAX_RUBRIQUES = Consignes.model_json_schema()["properties"]["consignes"]["maxItems"]
#: Ce qui doit se lire en bas de la fiche, quelle que soit sa longueur.
PIED = "Bienvenue chez vous"
NOTE = "Ce document est un résumé."


def _fiche(rubriques: int) -> str:
    consignes = [
        (
            f"🧹 {i + 1}. Rubrique témoin {i + 1}",
            "Première consigne témoin, assez longue pour occuper toute une ligne de la fiche.\n"
            "Deuxième consigne témoin, plus courte.\nTroisième consigne témoin.",
        )
        for i in range(rubriques)
    ]
    return generer_fiche_arrivant(
        cs_data={"membres": []},
        syndic_data={"nom_syndic": "Syndic Témoin", "adresse": "1 rue Témoin", "membres": []},
        site_nom="Résidence Témoin",
        site_url="https://residence.example",
        logo_png=None,
        consignes=consignes,
    )


# ── La feuille de style ───────────────────────────────────────────────────────


def _declarations(css: str, selecteur: str) -> list[str]:
    """Le corps de chaque règle qui vise exactement `selecteur`, commentaires retirés."""
    sans_commentaires = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [
        corps
        for sel, corps in re.findall(r"([^{}]+)\{([^{}]*)\}", sans_commentaires)
        if sel.strip() == selecteur
    ]


def coupe_le_contenu(css: str) -> bool:
    """`.page` a-t-elle une hauteur FIXE, et non minimale ? PURE.

    Une hauteur fixe tronque sur papier, quel que soit `overflow` : masqué, le reste
    disparaît ; visible, il déborde dans la marge, sans saut de feuille."""
    return any(re.search(r"(?<![-\w])height\s*:", corps) for corps in _declarations(css, ".page"))


def test_le_controle_voit_la_hauteur_figee():
    """Témoin : la règle d'avant #3143 est refusée, celle d'après est admise."""
    assert coupe_le_contenu(".page { max-width: 210mm; height: 285mm; overflow: hidden; }")
    assert not coupe_le_contenu(".page { max-width: 210mm; min-height: 285mm; }")


def test_la_page_de_la_fiche_grandit_au_lieu_de_couper():
    assert _declarations(CSS, ".page"), "plus aucune règle `.page` : le contrôle ne voit rien"
    assert not coupe_le_contenu(CSS), (
        "`.page` a retrouvé une hauteur fixe : au-delà d'une feuille, la fiche serait "
        "coupée sans un mot (#3143). Écrire `min-height`, jamais `height`."
    )
    assert any("overflow: visible" in corps for corps in _declarations(CSS, ".page")), (
        "à l'impression, `.page` doit laisser voir ce qui dépasse (`overflow: visible`)"
    )


def test_le_pire_cas_porte_toutes_les_rubriques():
    """Le rendu ci-dessous essaie vraiment le pire cas : toutes les rubriques y sont."""
    fiche = _fiche(MAX_RUBRIQUES)
    assert MAX_RUBRIQUES >= 4, "le pire cas ne dépasse plus une feuille : relire ce test"
    assert f"Rubrique témoin {MAX_RUBRIQUES}" in fiche
    assert PIED in fiche and NOTE in fiche


# ── Le rendu réel ─────────────────────────────────────────────────────────────


def _textes_par_feuille(html: str) -> list[list[tuple[str, bool]]]:
    """Pour chaque feuille rendue : (texte, posé dans la zone imprimable ?)."""
    from weasyprint import HTML
    from weasyprint.formatting_structure.boxes import TextBox

    feuilles = []
    for page in HTML(string=html).render().pages:
        boite = page._page_box
        bas = boite.content_box_y() + boite.height
        feuilles.append(
            [
                (b.text, b.position_y + b.height <= bas + 0.5)
                for b in boite.descendants()
                if isinstance(b, TextBox) and b.text.strip()
            ]
        )
    return feuilles


@besoin_weasyprint
def test_avec_toutes_ses_rubriques_rien_ne_sort_de_la_feuille():
    feuilles = _textes_par_feuille(_fiche(MAX_RUBRIQUES))
    hors = [texte for textes in feuilles for texte, dedans in textes if not dedans]
    assert not hors, f"texte posé hors de la feuille, donc perdu à l'impression : {hors[:5]}"
    tout = " ".join(texte for textes in feuilles for texte, _ in textes)
    for attendu in (f"Rubrique témoin {MAX_RUBRIQUES}", PIED, "résumé"):
        assert attendu in tout, f"« {attendu} » n'est rendu sur aucune feuille"
    assert len(feuilles) >= 2, "toutes les rubriques tiennent sur une feuille : relire ce test"
