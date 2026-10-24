"""Les photos d'une affiche de hall — sous le texte, ou seules (24/10/2026).

Trois affiches, décidées par ce que le conseil syndical a saisi :

| Saisi | Ce qui sort |
|---|---|
| texte | l'affiche ordinaire, au plus petit format qui accueille le texte |
| texte + photo(s) | une galerie de hauteur `galerie_max` (gabarit) en pied de contenu |
| photo(s), sans texte | la galerie occupe TOUTE la zone sous le titre, entre l'en-tête et le pied |

Demandé à l'écran : *« si image seule, adapte au plus petit format l'affichette »*,
puis *« elle doit être ajustée dans la zone affichée »* — pas sur toute la feuille.

🔴 **La photo n'est jamais rognée.** Une hauteur FIXE avec `object-fit: cover`
coupait une capture d'écran à sa bande du milieu (signalé le 24/10/2026). Elle
garde ses proportions et RÉDUIT pour tenir : dimensions `auto`, bornes `max-*`.

⚠️ **Les bornes s'écrivent en millimètres, jamais en pourcentage.** Éprouvé au
rendu WeasyPrint réel : la zone flexible prend bien sa hauteur (64 mm en A6), mais
un `max-height: 100%` y est ignoré, et une photo carrée ou en portrait sortait de
la feuille. La hauteur se calcule donc ici, depuis le format et le titre.
"""

from __future__ import annotations

import math

# En dessous de l'A6, une affiche avec photo devient illisible : on ne descend pas.
# C'était l'A5 jusqu'au 24/10/2026 — une annonce de 150 caractères et une capture
# d'écran sortait sur un A5 à moitié blanc.
FORMAT_MIN_AVEC_PHOTOS = "a6"

# Les seuils de `SEUILS_FORMAT` quand l'affiche porte des photos ET du texte : la
# galerie prend la place d'une partie du texte. Relevés le 24/10/2026 au rendu
# WeasyPrint RÉEL (image de l'API), photo carrée, une ou deux, marge de −10 % :
#
#     format   galerie   dernier poids qui tient   seuil retenu
#     a6        38 mm              580                  520
#     a5        50 mm              960                  860
#     a4        70 mm            1 500                1 350
#
# ⚠️ « Tient » se lit au TEXTE RENDU, jamais au nombre de pages : un `.corps` en
# flex ne se fragmente pas, WeasyPrint TRONQUE le message qui dépasse — une page,
# et la fin du texte perdue sans un mot.
#
# Une affiche SANS texte n'a que son titre pour poids : elle sort au premier format.
SEUILS_FORMAT_AVEC_PHOTOS: tuple[tuple[str, int], ...] = (
    ("a6", 520),
    ("a5", 860),
    ("a4", 1350),
)

# Hauteur laissée à la photo sous un titre d'UNE ligne, quand il n'y a pas de
# texte. Relevé au rendu réel (24/10/2026) : la place entre le bas du titre et le
# bas du corps (a6 78,7 · a5 128,1 · a4 193,1 mm), moins le filet (3,4), le retrait
# de la galerie (3), le bas du corps (5 · 7 · 10) et 4 mm de réserve pour une
# ligne de méta qui passerait à la ligne (un périmètre au long nom).
ZONE_IMAGE_SEULE_MM = {"a6": 63, "a5": 110, "a4": 172}

# Caractères d'une ligne de titre — sous-estimés exprès : relevé, une ligne en
# porte 28 à 30 dans les trois formats. Compter une ligne de trop rétrécit la
# photo d'une ligne ; en compter une de moins la ferait sortir du feuillet.
TITRE_CARACTERES_PAR_LIGNE = 22

# Interligne du titre (`.titre`, `line-height: 1.15`), en millimètres par point.
_LIGNE_TITRE_MM_PAR_PT = 1.15 * 25.4 / 72

# En deçà, la photo serait illisible : un titre de cette longueur est une erreur
# de saisie, et l'affiche reste sur une page.
HAUTEUR_IMAGE_MIN_MM = 25


def hauteur_image_seule(fmt: str, titre: str, taille_titre: str) -> float:
    """Hauteur maximale (mm) de la photo d'une affiche sans texte, sous ce titre."""
    lignes = max(1, math.ceil(len(titre.strip()) / TITRE_CARACTERES_PAR_LIGNE))
    ligne = float(taille_titre.removesuffix("pt")) * _LIGNE_TITRE_MM_PAR_PT
    return max(HAUTEUR_IMAGE_MIN_MM, ZONE_IMAGE_SEULE_MM[fmt] - (lignes - 1) * ligne)


def html_galerie(vignettes: list[str], alt: str, *, hauteur_mm: float | None = None) -> str:
    """La galerie : `hauteur_mm` borne chaque photo quand elle est seule (sans texte)."""
    if not vignettes:
        return ""
    borne = f' style="max-height: {hauteur_mm:.1f}mm"' if hauteur_mm else ""
    balises = "".join(f'<img src="{uri}" alt="{alt}"{borne}>' for uri in vignettes)
    return f'<div class="galerie galerie-{len(vignettes)}">{balises}</div>'
