"""Thème commun des documents imprimables (fiche arrivant, annonces hall).

Centralise ce qui était jusqu'ici dupliqué dans `fiche_arrivant.py` : logo,
palette de la charte graphique, **icônes**, helpers data-URI et rendu HTML → PDF.

Tout nouveau document imprimable passe par ce module — ne pas redéfinir de
palette, de logo ni de moteur PDF ailleurs. Cette consigne existait déjà et
n'était pas tenue : `utils/email/gabarit.py` redessinait le logo (14/08/2026).
Elle vaut aussi pour ce qui n'est pas un PDF — un e-mail affiche la même marque.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import mimetypes
import re
from pathlib import Path

logger = logging.getLogger("hostachy.pdf_theme")


# ── Palette (specs/design/charte-graphique.md) ───────────────────────────────

PALETTE_CSS = """\
:root {
  --navy: #1E3A5F; --navy-dark: #16304F; --gold: #C9983A; --green: #3D6B4F;
  --bg: #F2EFE9; --card: #FFFFFF; --ink: #1A1A2E; --muted: #5A6070;
  --light-muted: #8A8FA0; --footer-bg: #FAFAF7; --border: #E5E2DC;
}
"""

FONT_SERIF = "Georgia, 'Palatino Linotype', 'Book Antiqua', Palatino, serif"
FONT_SANS = (
    "'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, 'Helvetica Neue', Arial, sans-serif"
)


# ── La page imprimée ─────────────────────────────────────────────────────────

#: 🔴 LE FORMAT PAR DÉFAUT DE TOUT DOCUMENT IMPRIMABLE (18/09/2026).
#:
#: Demandé par Philippe : « sauf Annonce Hall qui utilise des formats plus
#: petits, il faudrait fixer le format A4 par défaut ». Il l'était en fait
#: partout — mais écrit à la main dans chaque document, donc vrai par répétition
#: et non par règle. Un quatrième document imprimable aurait hérité du format
#: que WeasyPrint choisit, pas de celui de la maison.
FORMAT_PAR_DEFAUT = "A4"

#: Les marges de la maison. Resserrées le 03/09/2026 pour réduire le nombre de
#: pages du manuel : 12 mm reste au-delà de la zone non imprimable d'une
#: imprimante de bureau (5 mm) et laisse le pied respirer.
MARGES_PAR_DEFAUT = "12mm 12mm 14mm"


def regle_page(
    *,
    taille: str = FORMAT_PAR_DEFAUT,
    marges: str = MARGES_PAR_DEFAUT,
    numeroter: bool = True,
) -> str:
    """Le bloc `@page` d'un document imprimable — **A4 par défaut**.

    Les trois documents l'écrivaient chacun de leur côté : le manuel en A4 avec
    son pied numéroté, l'annonce de hall dans le format que son débordement lui
    impose et sans marge, la fiche d'arrivant en A4 avec des marges plus
    serrées. Trois écritures, trois occasions de diverger sur une règle qui n'en
    est qu'une : *sur quel papier ce document sort-il*.

    ⚠️ **L'annonce de hall reste l'exception, et elle le dit** : elle choisit son
    format sur le DÉBORDEMENT (A4 → A5 → A6), parce qu'une annonce qui tient sur
    un demi-feuillet ne doit pas en gaspiller un entier. Elle passe donc sa
    taille, au lieu de la subir — c'est la différence entre une exception
    déclarée et un oubli.

    :param taille: `A4`, `A5`, `A6`… tel que le CSS des médias paginés l'entend.
    :param marges: la valeur CSS `margin` de la page. `"0"` pour une affiche.
    :param numeroter: un pied « page / total ». Faux pour une affiche, qui n'a
        qu'une page et dont le pied porte autre chose.
    """
    saut = chr(10)
    pied = (
        saut
        + "  @bottom-center {"
        + saut
        + '    content: counter(page) " / " counter(pages);'
        + saut
        + f"    font-family: {FONT_SANS};"
        + saut
        + "    font-size: 8pt;"
        + saut
        + "    color: var(--light-muted);"
        + saut
        + "  }"
        if numeroter
        else ""
    )
    return (
        "@page {" + saut + f"  size: {taille};" + saut + f"  margin: {marges};" + pied + saut + "}"
    )


# ── Logo ─────────────────────────────────────────────────────────────────────


#: Le dessin du logo NEUTRE, **copie octet pour octet** de `front/static/favicon.svg`
#: — les contextes de build Docker sont `./api` et `./front`, aucun fichier de la
#: racine n'entre dans les images. `test_logo_neutre.py` tient les deux égaux.
LOGO_NEUTRE_SVG = Path(__file__).with_name("logo-neutre.svg")


def logo_svg(size: int = 36) -> str:
    """Le logo NEUTRE du logiciel en SVG inline, à `size` px de côté.

    C'est le repli quand la résidence n'a pas téléversé le sien (#1728) : un
    logo propre à une résidence ne s'écrit pas dans le code, une autre l'aurait
    porté. Le logo réellement affiché se demande à `utils/logo`
    (`logo_televerse_png`), jamais ici.

    Le commentaire du fichier (provenance, couleurs) ne part pas dans le document.
    """
    svg = re.sub(r"\s*<!--.*?-->", "", LOGO_NEUTRE_SVG.read_text(encoding="utf-8"), flags=re.S)
    return svg.strip().replace("<svg ", f'<svg width="{size}" height="{size}" ', 1)


def logo_html(logo_png: bytes | None, size: int = 36) -> str:
    """Le logo d'un document HTML autonome — **la seule écriture** (#1728).

    `logo_png` est celui que la résidence a téléversé (`utils/logo.logo_televerse_png`),
    ou None : le dessin neutre, en SVG, net à toute taille. Le PNG part en
    data-URI, car un document se rend hors requête, sans rien charger.

    🔴 La taille s'écrit AUSSI en `style` : WeasyPrint ignore les attributs
    `width`/`height` d'un `<img>` (sans `presentational_hints`, que
    `pdf_rendu` ne passe pas). Le PNG téléversé, carré de plusieurs centaines
    de pixels, sortait alors à sa taille native et débordait la page de garde
    du manuel (08/10/2026). Le SVG, lui, porte sa taille dans son élément.
    """
    if logo_png is None:
        return logo_svg(size)
    donnees = base64.b64encode(logo_png).decode()
    return (
        f'<img src="data:image/png;base64,{donnees}" width="{size}" height="{size}" '
        f'style="width:{size}px;height:{size}px" alt="">'
    )


# ── Icônes ───────────────────────────────────────────────────────────────────

#: Catalogue des tracés, **copie octet pour octet** de `front/src/lib/icones-svg.json`.
#:
#: Pourquoi une copie et non un fichier unique : les contextes de build Docker
#: sont `./api` et `./front` (docker-compose.yml). Un fichier posé à la racine du
#: dépôt n'entre dans **aucune** des deux images — « une source lue des deux
#: côtés » supposerait d'élargir les deux contextes, donc de toucher la chaîne de
#: déploiement des deux RPi pour un sujet d'affichage.
#:
#: Ce qui rend la copie sûre, c'est `api/tests/test_icones_svg.py` : il échoue si
#: les deux fichiers diffèrent d'un octet, et si un tracé réapparaît en dur d'un
#: côté ou de l'autre. Sans lui, ce serait la duplication interdite par
#: `standards/02-factorisation.md` ; avec lui, c'est un artefact dérivé dont la
#: divergence est impossible. Même pattern que `docs/manuel-utilisateur.html` →
#: `front/static/`.
_CATALOGUE_ICONES = Path(__file__).with_name("icones-svg.json")

_icones_cache: dict[str, str] | None = None


def _icones() -> dict[str, str]:
    global _icones_cache
    if _icones_cache is None:
        try:
            _icones_cache = json.loads(_CATALOGUE_ICONES.read_text(encoding="utf-8"))
        except Exception as exc:
            #  Un document sans ses icônes reste lisible ; un document qui ne se
            #  génère pas ne l'est pas. On journalise et on continue sans.
            logger.error("Catalogue d'icônes illisible (%s) — documents rendus sans icône", exc)
            _icones_cache = {}
    return _icones_cache


def icone_svg(
    nom: str | None,
    *,
    taille: int = 14,
    couleur: str = "#1E3A5F",
    style_sup: str = "vertical-align:-2px;margin-right:3px",
) -> str:
    """Une icône du catalogue en SVG inline, prête pour WeasyPrint.

    Renvoie une **chaîne vide** si le nom est absent ou inconnu : un périmètre
    sans icône est un état normal (le champ `icone` est facultatif), il ne doit
    produire ni carré vide ni point d'interrogation. C'est pourquoi il n'y a pas
    ici le repli `help-circle` du composant `Icon.svelte` — à l'écran, une icône
    manquante signale une erreur de saisie ; sur un document imprimé, elle
    n'apporterait qu'un pictogramme incompréhensible à côté d'un nom de bâtiment.

    `stroke` **et** `color` portent la couleur explicitement : WeasyPrint n'hérite
    pas `currentColor` de façon fiable, et deux tracés du catalogue s'en servent
    pour leur remplissage.
    """
    trace = _icones().get((nom or "").strip())
    if not trace:
        return ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'width="{taille}" height="{taille}" fill="none" stroke="{couleur}" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
        f'style="color:{couleur};{style_sup}">{trace}</svg>'
    )


# ── Data-URI ─────────────────────────────────────────────────────────────────


def qr_data_uri(url: str) -> str:
    """QR code → `data:image/png;base64,…` (chaîne vide si génération impossible)."""
    if not url:
        return ""
    try:
        import qrcode

        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except Exception:
        return ""


def image_data_uri(image_url: str | None) -> str | None:
    """Image locale (`/uploads/…`) → data-URI, ou None si absente/illisible.

    Les documents sont générés hors requête HTTP (BackgroundTask) : les
    ressources doivent être embarquées, jamais référencées par URL.
    """
    if not image_url:
        return None
    #  Par le stockage de la copropriété (#1748), et borné sous sa racine : la
    #  racine était ici `Path("/app")`, écrite en dur, et `/uploads/../…` sortait
    #  du volume sans que rien ne l'arrête.
    from app.utils.stockage import stockage

    path = stockage().fichier_de_url(image_url)
    if path is None:
        return None
    try:
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
    except Exception:
        return None


# ── Rendu PDF ────────────────────────────────────────────────────────────────


def html_to_pdf(html: str) -> bytes:
    """Rend un document HTML autonome en PDF — **le seul point d'entrée du rendu**.

    Le HTML doit être **autonome** : CSS inline dans une balise `<style>` et
    images en data-URI (cf. `image_data_uri` / `qr_data_uri`). Aucune requête
    réseau n'est effectuée au rendu.

    🔴 Le rendu s'exécute dans un **autre process** depuis le 16/09/2026, pour
    qu'un WeasyPrint qui plante ou épuise la mémoire du RPi n'emporte plus l'API.
    Ce que cela coûte (+1,5 à 2 s par document), ce que cela gagne (mesuré), et
    pourquoi c'est `spawn` et jamais `fork` : `app/utils/pdf_rendu.py`.

    ⚠️ Cette fonction reste le point d'entrée de TOUS les documents — n'appelle
    jamais WeasyPrint ailleurs, et n'appelle pas non plus `rendre_pdf`
    directement : c'est ici que le thème commun et le moteur se rejoignent.
    """
    from app.utils.pdf_rendu import rendre_pdf  # import différé : lib lourde

    return rendre_pdf(html)
