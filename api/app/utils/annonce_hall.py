"""Génération des annonces affichées dans le hall des bâtiments (A4 / A5).

Le rendu réutilise le thème imprimable commun (`pdf_theme`) : même palette,
même logo et même moteur PDF que la fiche arrivant.

Format : le PLUS PETIT feuillet qui accueille le texte (cf. `choisir_format`),
parce qu'une affiche prend de la place sur le tableau d'affichage du hall. Le CS
peut forcer un format depuis l'interface.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from app.utils import horloge
from html import escape, unescape

# `date_longue` vit désormais dans `dates_fr` (source unique, partagée avec la
# fiche arrivant et les e-mails) ; réimportée ici car le routeur `annonces_hall`
# l'importe historiquement depuis ce module.
from app.utils.dates_fr import date_longue
from app.utils.annonce_hall_photos import (
    FORMAT_MIN_AVEC_PHOTOS,
    SEUILS_FORMAT_AVEC_PHOTOS,
    hauteur_image_seule,
    html_galerie,
)
from app.utils.html_sur import assainir_html
from app.utils.palettes import recolorer
from app.utils.slug import en_slug
from app.utils.pdf_theme import (
    FONT_SANS,
    FONT_SERIF,
    PALETTE_CSS,
    regle_page,
    html_to_pdf,
    image_data_uri,
    logo_html,
    qr_data_uri,
)

# Formats retenus, du plus grand au plus petit.
#
# 🔴 **L'A8 a été RETIRÉ le 10/09/2026, et c'est une mesure, pas un avis.** Le
# gabarit 52 × 74 mm porte un en-tête, un pied et un QR : il ne reste que 13 mm
# de corps. Mesuré au navigateur sur le vrai gabarit, une annonce de **59
# caractères** — un titre de trois mots et rien d'autre — donne déjà une page de
# 77 mm, soit 3 mm de plus que la feuille. L'A8 débordait donc TOUJOURS, en
# silence : WeasyPrint pousse le débordement sur une deuxième page, et une
# affiche de hall sur deux feuillets n'est pas une affiche.
#
# Il était atteignable dès 70 caractères. Personne ne l'avait vu parce que le
# seuil paraissait prudent — c'est le format lui-même qui ne tenait pas.
FORMATS = ("a4", "a5", "a6", "a7")

# Photos facultatives, placées en pied de contenu. Volontairement limité : au-delà,
# l'affiche déborderait du feuillet et le format ne serait plus tenu.
MAX_PHOTOS = 2

# Poids maximal du contenu (titre + message, en caractères) tenant dans chaque
# format. Au-delà du dernier seuil, on reste en A4.
#
# 🔴 **Recalibrés une SECONDE fois le 11/09/2026**, après le resserrement du
# chrome (voir `_GABARITS`). Demandé à l'écran : « l'affiche la plus petite
# possible, éviter l'espace vide — par contre il faut qu'elle reste visible ».
#
# ⚠️ Le critère de mesure a changé, et c'est le vrai progrès. On relevait le
# **taux de remplissage** et l'on gardait 92 % ; on relève désormais le point où
# la page **DÉBORDE** — sa hauteur rendue dépasse celle du feuillet. Le
# remplissage est une appréciation ; le débordement est un fait, et c'est lui qui
# ruine une affiche en la poussant sur une seconde feuille.
#
#     format   dernier poids SANS débordement   seuil retenu (−10 %)
#     a7                470                            420
#     a6                835                            750
#     a5              1 360                          1 220
#     a4              1 885                          1 700
#
# La marge de 10 % couvre ce que la mesure ne voit pas : elle vient du navigateur,
# et c'est WeasyPrint qui rendra le PDF. Les deux moteurs coupent les lignes un
# peu différemment.
#
# Gain par rapport aux seuils du 10/09 : +88 % de texte sur A7, +46 % sur A6,
# +36 % sur A5. L'annonce de référence (629 caractères) passe d'A5 à **A6** —
# surface divisée par deux sur le tableau d'affichage.
#
# ⚠️ Au-delà de 1 700 caractères on reste en A4 **et le texte déborde** : le
# gabarit n'a pas de format plus grand. Inchangé, et toujours pas traité.
SEUILS_FORMAT: tuple[tuple[str, int], ...] = (
    ("a7", 420),
    ("a6", 750),
    ("a5", 1220),
    ("a4", 1700),
)

# Gabarit par format : dimensions de page et échelle typographique.
#
# 🔴 **LE CHROME A ÉTÉ RESSERRÉ LE 11/09/2026, PAS LE TEXTE.** Demandé à l'écran :
# « obtenir l'affiche la plus petite possible, éviter l'espace vide — par contre il
# faut que l'affiche reste visible ».
#
# Mesuré au navigateur sur le vrai gabarit, la part de la feuille consommée AVANT
# le premier mot — en-tête, filet d'accent, pied, marges du corps, ligne de méta :
#
#     a7   66,1 mm sur 105   63 %
#     a6   80,6 mm sur 148   54 %
#     a5   95,3 mm sur 210   45 %
#     a4  113,4 mm sur 297   38 %
#
# Sur un A6, **plus de la moitié du feuillet servait à l'habillage**. C'est lui
# qu'on réduit : marges, hauteur d'en-tête et de pied, logo, QR, interlignes de
# séparation. Le corps du message et le titre gardent EXACTEMENT leur taille —
# une affiche de hall se lit debout devant le tableau, et rétrécir le texte pour
# gagner du papier serait gagner sur le mauvais poste.
#
# ⚠️ Ce n'est pas cosmétique : chaque millimètre rendu au texte permet à une
# annonce de tenir dans le format INFÉRIEUR, ce qui divise sa surface par deux.
_GABARITS: dict[str, dict[str, str]] = {
    "a4": {
        "page_size": "A4",
        "largeur": "210mm",
        "hauteur": "297mm",
        "padding": "10mm 16mm",
        "logo": "44",
        "surtitre": "10pt",
        "residence": "13pt",
        "titre": "30pt",
        "meta": "10pt",
        "corps": "13pt",
        "galerie_max": "70mm",
        "qr": "26mm",
        "pied": "9pt",
    },
    "a5": {
        "page_size": "A5",
        "largeur": "148mm",
        "hauteur": "210mm",
        "padding": "7mm 12mm",
        "logo": "26",
        "surtitre": "8pt",
        "residence": "10.5pt",
        "titre": "21pt",
        "meta": "8.5pt",
        "corps": "10.5pt",
        "galerie_max": "50mm",
        "qr": "15mm",
        "pied": "7.5pt",
    },
    "a6": {
        "page_size": "A6",
        "largeur": "105mm",
        "hauteur": "148mm",
        "padding": "5mm 8mm",
        "logo": "20",
        "surtitre": "6.5pt",
        "residence": "8.5pt",
        "titre": "15pt",
        "meta": "7pt",
        "corps": "8.5pt",
        "galerie_max": "38mm",
        "qr": "11mm",
        "pied": "6pt",
    },
    "a7": {
        "page_size": "A7",
        "largeur": "74mm",
        "hauteur": "105mm",
        "padding": "3.5mm 5.5mm",
        "logo": "17",
        "surtitre": "5pt",
        "residence": "6.5pt",
        "titre": "11pt",
        "meta": "5.5pt",
        "corps": "7pt",
        "galerie_max": "0mm",  # pas de photo en dessous de l'A6
        "qr": "0mm",  # pied simplifié : plus de QR
        "pied": "5pt",
    },
}

# Formats trop petits pour porter le QR code du pied de page.
_SANS_QR = ("a7",)

# ── Helpers ──────────────────────────────────────────────────────────────────

#: Longueur de l'aperçu du message — dans l'historique comme dans le courriel.
#: Il vivait dans le routeur, qui n'en est qu'un des deux clients (01/09/2026).
APERCU_MAX = 180


def texte_brut(html: str) -> str:
    """HTML riche → texte brut (pendant serveur de `stripHtml` côté front).

    TOUTES les entités se décodent, en une passe : la liste des cinq nommées
    qu'on remplaçait laissait les numériques — l'éditeur écrit l'apostrophe
    `&#x27;`, et « L&#x27;Art des toits » s'affichait au Suivi des entretiens
    (17/10/2026). Une passe unique ne décode pas deux fois (`&amp;lt;` reste
    `&lt;`). Le texte rendu est du TEXTE : chaque rendu l'échappe à nouveau.
    """
    txt = unescape(re.sub(r"<[^>]*>", " ", html or ""))
    return re.sub(r"\s+", " ", txt).strip()


def choisir_format(
    message_html: str,
    format_demande: str = "auto",
    *,
    titre: str = "",
    avec_photos: bool = False,
) -> str:
    """Retourne le format effectif (`a4` … `a7`).

    En mode `auto`, on retient **le plus petit format** qui accueille le
    contenu : une annonce courte occupe ainsi moins de place dans l'afficheur
    du hall. Un choix explicite du CS est prioritaire.

    Une affiche portant des photos se mesure sur ses propres seuils, qui
    commencent à `FORMAT_MIN_AVEC_PHOTOS` : la galerie prend la place du texte.
    """
    demande = (format_demande or "auto").lower()
    if demande in FORMATS:
        return demande

    poids = len(texte_brut(message_html)) + len(texte_brut(titre))
    seuils = SEUILS_FORMAT_AVEC_PHOTOS if avec_photos else SEUILS_FORMAT
    return next((fmt for fmt, seuil in seuils if poids <= seuil), "a4")


def format_libelle(fmt: str) -> str:
    return (fmt or "a4").upper()


#  ⚠️ `perimetre_libelle()` vivait ici — QUATRIÈME table de périmètres écrite en
#  dur, retirée le 27/08/2026. Elle connaissait cinq codes (`résidence`, `parking`,
#  `cave`, `aful`, le préfixe `bat:`) et rendait **le code brut** pour tout le
#  reste : une « Voie d'accès » créée depuis `/admin/patrimoine` s'imprimait
#  `aful/voie-acces` sur l'affiche du hall, en toutes lettres et sur papier.
#
#  C'est très exactement ce que `utils/perimetres.py` a été écrit pour abolir
#  (#316) — trois copies avaient alors été fusionnées, celle-ci n'avait pas été
#  vue parce qu'elle porte un AUTRE NOM. Les appelants passent désormais par
#  `perimetre_label_liste`, qui lit l'arbre.


def nom_fichier(titre: str, cree_le: date | datetime) -> str:
    """Nom de fichier proposé au téléchargement / en pièce jointe.

    Les accents sont translittérés (`août` → `aout`) : le nom traverse SMTP et
    des systèmes de fichiers variés, on le garde en ASCII.
    """
    slug = en_slug(texte_brut(titre))[:60]
    return f"annonce-{horloge.jour_civil(cree_le):%Y%m%d}-{slug or 'hall'}.pdf"


# ── CSS ──────────────────────────────────────────────────────────────────────


def _css(fmt: str) -> str:
    g = _GABARITS[fmt]
    # Sous l'A4, la feuille imprimée est plus grande que l'affiche : on matérialise
    # le trait de coupe.
    coupe = "border: .35mm dashed var(--light-muted);" if fmt != "a4" else ""
    # Très petits formats : on sacrifie la date d'affichage pour préserver le texte.
    meta_allegee = ".date-affichage { display: none; }" if fmt in _SANS_QR else ""
    return f"""\
{regle_page(taille=g["page_size"], marges="0", numeroter=False)}
{PALETTE_CSS}\
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: {FONT_SANS};
  color: var(--ink); background: var(--card); line-height: 1.5;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}}
/* Dimensions physiques du feuillet : le pied de page se cale au bas du {g["page_size"]},
   à l'impression comme à l'aperçu écran (où @page n'est pas appliqué). */
.page {{
  width: {g["largeur"]}; min-height: {g["hauteur"]};
  margin: 0 auto; background: var(--card);
  display: flex; flex-direction: column;
  {coupe}
}}
/* Aperçu écran uniquement — WeasyPrint rend en média « print » et ignore ce bloc. */
@media screen {{
  body {{ background: #DCD8D0; padding: 6mm 0; }}
  .page {{ box-shadow: 0 2mm 6mm rgba(30, 58, 95, .22); }}
}}

/* ── En-tête ── */
.entete {{
  background: linear-gradient(135deg, var(--navy) 0%, var(--navy-dark) 100%);
  padding: {g["padding"]}; padding-top: 5mm; padding-bottom: 4mm;
  display: flex; align-items: center; gap: 4mm;
}}
.entete svg {{ flex-shrink: 0; }}
.entete-texte {{ flex: 1; }}
.surtitre {{
  font-size: {g["surtitre"]}; color: var(--gold); font-weight: 700;
  letter-spacing: 2.2px; text-transform: uppercase;
}}
.residence {{
  font-family: {FONT_SERIF}; font-size: {g["residence"]};
  font-weight: 700; color: #FFFFFF; margin-top: 1mm;
}}
.barre-accent {{
  height: 2.2mm;
  background: linear-gradient(90deg, var(--gold) 0%, var(--navy) 50%, var(--green) 100%);
}}

/* ── Corps ── */
.corps {{ flex: 1; padding: {g["padding"]}; display: flex; flex-direction: column; }}
.meta {{
  display: flex; align-items: center; justify-content: space-between;
  gap: 4mm; margin-bottom: 3mm;
}}
.chip-perimetre {{
  /*  🔴 LE FILET EST UNE BOÎTE, PLUS UN EFFET DE PEINTURE (11/09/2026).

      TROISIÈME signalement du même défaut : « deux barres sur le périmètre, on
      dirait deux boîtes ». Les deux tentatives précédentes réglaient un
      mécanisme que je ne peux pas observer depuis ce poste — WeasyPrint ne s'y
      installe pas, et j'ai corrigé deux fois à l'aveugle :

        18/08  bordure d'un seul côté + rayon  → deux segments, rayon retiré
        10/09  dégradé à deux positions        → déclaration jetée, rien peint
        11/09  dégradé à deux arrêts           → deux barres, encore

      On arrête de régler. Le filet devient un ÉLÉMENT : deux rectangles pleins
      côte à côte, chacun d'une couleur unie. Pas de bordure, pas de dégradé, pas
      de coin à raccorder — le mécanisme le plus élémentaire qu'un moteur
      d'impression puisse rendre, et le seul dont le résultat ne dépende d'aucune
      finesse de spécification.

      ⚠️ `display: flex` est déjà employé par l'en-tête, la méta et le pied de
      cette même affiche, et ils sortent correctement en PDF : la disposition
      n'est pas ce qui manque à WeasyPrint. C'est la seule chose que j'aie pu
      VÉRIFIER — sur la capture de l'affiche. */
  display: flex; align-items: stretch;
  font-size: {g["meta"]}; font-weight: 700; color: var(--navy);
  background: #F0EDE6; border-radius: 0 1mm 1mm 0;
  text-transform: uppercase; letter-spacing: .6px;
}}
.chip-filet {{ flex: 0 0 1.2mm; width: 1.2mm; background: var(--gold); }}
.chip-texte {{ padding: 1.1mm 3mm; }}
.date-affichage {{ font-size: {g["meta"]}; color: var(--muted); white-space: nowrap; }}
{meta_allegee}
.titre {{
  font-family: {FONT_SERIF}; font-size: {g["titre"]}; font-weight: 700;
  color: var(--navy); line-height: 1.15; margin-bottom: 3mm;
}}
.filet {{ height: .4mm; background: var(--border); margin-bottom: 3mm; }}
.message {{ font-size: {g["corps"]}; color: var(--ink); }}
.message p {{ margin-bottom: 2.5mm; }}
.message ul, .message ol {{ margin: 0 0 2.5mm 6mm; }}
.message li {{ margin-bottom: 1.2mm; }}
.message strong {{ color: var(--navy); }}
.message h1, .message h2, .message h3 {{
  font-family: {FONT_SERIF}; color: var(--navy);
  margin: 3mm 0 2mm; line-height: 1.2;
}}
.message a {{ color: var(--navy); text-decoration: underline; }}
.message img {{ max-width: 100%; border-radius: 1.5mm; }}

/* ── Photos : jamais rognées, elles réduisent pour tenir (`annonce_hall_photos`) ── */
.galerie {{ margin-top: auto; padding-top: 3mm; text-align: center; line-height: 0; }}
.galerie img {{
  display: inline-block; vertical-align: top;
  width: auto; height: auto; max-width: 100%; max-height: {g["galerie_max"]};
  border-radius: 2mm; border: .3mm solid var(--border);
}}
.galerie-2 img {{ max-width: 48%; }}
.galerie-2 img + img {{ margin-left: 3mm; }}
/* Sans texte, la galerie occupe la zone et y centre la photo. */
.corps-image .galerie {{
  flex: 1 1 0; min-height: 0; margin-top: 0;
  display: flex; align-items: center; justify-content: center;
}}
/* ── Pied de page ── */
.pied {{
  background: var(--footer-bg); border-top: .3mm solid var(--border);
  padding: {g["padding"]}; padding-top: 3.5mm; padding-bottom: 3.5mm;
  display: flex; align-items: center; gap: 4mm;
}}
.pied-texte {{ flex: 1; font-size: {g["pied"]}; color: var(--muted); line-height: 1.45; }}
.pied-signature {{ font-weight: 700; color: var(--navy); }}
.pied-site {{ color: var(--navy); font-weight: 600; }}
.pied-qr {{ width: {g["qr"]}; height: {g["qr"]}; flex-shrink: 0; }}
"""


# ── Rendu ────────────────────────────────────────────────────────────────────


def construire_html(
    *,
    titre: str,
    message_html: str,
    perimetre_label: str,
    format_effectif: str,
    site_nom: str,
    site_url: str,
    logo_png: bytes | None,
    images: list[str] | None = None,
    date_affichage: date | datetime | None = None,
    palette: str | None = None,
) -> str:
    """Assemble le HTML autonome de l'annonce (images et QR en data-URI), aux
    couleurs de la `palette` de la copropriété (#2379)."""
    g = _GABARITS[format_effectif]
    #  Un instant de la base (UTC) se lit au jour de Paris : à 00:30, l'affiche
    #  portait encore la date de la veille (#1565).
    d = horloge.jour_civil(date_affichage or horloge.maintenant())
    url_complete = site_url if site_url.startswith("http") else f"https://{site_url}"
    site_affiche = re.sub(r"^https?://", "", site_url).rstrip("/")

    alt = escape(titre)

    # Photos facultatives, embarquées comme le reste (data-URI).
    # Ignorées sous l'A6 : le gabarit n'a pas la place de les porter.
    photos_admises = (
        (images or [])[:MAX_PHOTOS]
        if FORMATS.index(format_effectif) <= FORMATS.index(FORMAT_MIN_AVEC_PHOTOS)
        else []
    )
    vignettes = [uri for uri in (image_data_uri(u) for u in photos_admises) if uri]
    #  Sans texte, la photo s'ajuste dans toute la zone sous le titre.
    image_seule = bool(vignettes) and not texte_brut(message_html)
    hauteur = hauteur_image_seule(format_effectif, titre, g["titre"]) if image_seule else None
    galerie = html_galerie(vignettes, alt, hauteur_mm=hauteur)
    classe_corps = "corps corps-image" if image_seule else "corps"

    qr = "" if format_effectif in _SANS_QR else qr_data_uri(url_complete)
    qr_html = f'<img class="pied-qr" src="{qr}" alt="QR {escape(site_affiche)}">' if qr else ""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{escape(titre)} — {escape(site_nom)}</title>
<style>
{_css(format_effectif)}
</style>
</head>
<body>
<div class="page">

  <div class="entete">
    {logo_html(logo_png, int(g["logo"]))}
    <div class="entete-texte">
      <div class="surtitre">Avis aux résidents</div>
      <div class="residence">{escape(site_nom)}</div>
    </div>
  </div>
  <div class="barre-accent"></div>

  <div class="{classe_corps}">
    <div class="meta">
      <span class="chip-perimetre"
        ><span class="chip-filet"></span><span class="chip-texte">{escape(perimetre_label)}</span></span>
      <span class="date-affichage">Affiché le {date_longue(d)}</span>
    </div>
    <h1 class="titre">{escape(titre)}</h1>
    <div class="filet"></div>
    <div class="message">{assainir_html(message_html)}</div>
    {galerie}
  </div>

  <div class="pied">
    <div class="pied-texte">
      <span class="pied-signature">Le Conseil Syndical</span> — {escape(site_nom)}<br>
      Retrouvez toutes les informations de la résidence sur
      <span class="pied-site">{escape(site_affiche)}</span>
    </div>
    {qr_html}
  </div>

</div>
</body>
</html>"""
    return recolorer(html, palette)


def generer_pdf(**kwargs) -> bytes:
    """Construit le HTML de l'annonce puis le rend en PDF."""
    return html_to_pdf(construire_html(**kwargs))
