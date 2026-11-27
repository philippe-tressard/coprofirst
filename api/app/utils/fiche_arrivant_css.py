"""Feuille de style de la fiche d'accueil — extraite au fil de l'eau.

`fiche_arrivant.py` atteignait exactement les 500 lignes du plafond de modularité
(rang 1 §4) : le lot suivant l'aurait fait échouer. La feuille de style est ce qui
s'en détache le plus proprement — elle n'a aucune logique, et elle change pour des
raisons qui ne sont pas celles du document (une retouche de charte graphique n'est
pas un changement de contenu).

Elle reste **propre à ce document** : ce qui est commun à tous les imprimables —
palette, logo, icônes, polices, moteur — vit dans `pdf_theme.py`, et ne se
redéfinit pas ici.

## Gros caractères (#2776, 16/11/2026)

Les résidents qui reçoivent cette fiche sont souvent âgés. Les consignes
s'imprimaient en 10,5 px (7,9 pt) et en gris : elles passent à 14 px (10,5 pt) et
en noir, les titres de rubrique à 16,5 px (12,4 pt). La mise en page retenue par
l'auteur est la variante « une page, règles en pleine largeur » : des lignes
longues, donc des rubriques moins hautes, et le document tient toujours sur UNE
feuille A4.

## Cartes à bandeau (#3144, 27/11/2026)

Les noms du conseil et du syndic se perdaient dans le reste : ils passent en gras,
dans la couleur principale, sur des cartes blanches à bandeau — le bâtiment pour le
conseil, la fonction pour le syndic. Variante « E4 » choisie sur maquette, puis
ajustée sur la fiche d'une installation réelle : une couleur unique pour tous les
bandeaux, un nom par ligne, l'étage en toutes lettres, le rôle en vignette.

La taille des noms se DÉCIDE en Python (`fiche_arrivant_noms`), qui mesure chaque
nom dans la place qu'une carte lui laisse : cette place se calcule ici, par
`place_nom`, avec les constantes que la feuille emploie — une seule écriture.

Repères : 1 pt = 1,333 px (96 px par pouce, l'unité du navigateur comme de
WeasyPrint). Les petits libellés ne sont jamais en or : l'or de la charte sur blanc
ne contraste qu'à 2,6:1.

🔴 Le document se lit dans le NAVIGATEUR, qui l'imprime lui-même (le PDF n'existe
que dans les tests) : une retouche se juge à l'impression de Chromium en A4, une
seule page, jamais à l'écran.
"""

from __future__ import annotations

from app.utils.pdf_theme import (
    FONT_LISIBLE,
    FONT_SERIF,
    PALETTE_CSS,
    REMISE_A_ZERO_CSS,
    regle_page,
)

# ── La géométrie, lue par la feuille ET par la mesure des noms ────────────────

_PX_PAR_MM = 96 / 25.4
#: La largeur imprimable : A4 moins les marges latérales de `regle_page` (6 mm).
_LARGEUR_UTILE_PX = (210 - 2 * 6) * _PX_PAR_MM
CONTENU_X_PX = 16  #: le retrait latéral de `.content`
ECART_CARTES_PX = 6  #: l'écart entre deux cartes de bâtiment
ECART_SYNDIC_PX = 7  #: l'écart entre deux contacts du syndic, et avant son QR
BORD_CARTE_PX = 1.5  #: le filet d'une carte
CORPS_CARTE_X_PX = 6  #: le retrait latéral du corps d'une carte
QR_PX = 58  #: un QR code ne rétrécit jamais (voir `.qr-code`)
PHOTO_PX = 20  #: la photo posée devant un nom
PHOTO_ECART_PX = 5


def place_nom(colonnes: int, *, ecart: float, reserve: float = 0.0) -> float:
    """La largeur qu'un nom peut occuper dans une carte d'une grille de `colonnes`. PURE.

    `reserve` : ce que la rangée donne à autre chose (le QR de l'extranet du syndic).
    """
    colonnes = max(1, colonnes)
    rangee = _LARGEUR_UTILE_PX - 2 * CONTENU_X_PX - reserve
    carte = (rangee - ecart * (colonnes - 1)) / colonnes
    return carte - 2 * BORD_CARTE_PX - 2 * CORPS_CARTE_X_PX


def _px(valeur: float) -> str:
    return f"{valeur:g}px"


CSS = (
    #  Marges de 5 mm : au-delà de la zone non imprimable d'une imprimante de
    #  bureau, et 2 mm gagnés de chaque côté pour le corps agrandi.
    regle_page(marges="5mm 6mm", numeroter=False)
    + """
@media print {
  body { background: none !important; }
  .page { box-shadow: none !important; border: none !important; border-radius: 0 !important; }
}
"""
    + PALETTE_CSS
    + REMISE_A_ZERO_CSS
    #  Teintes littérales DÉCLARÉES (#3144). `--clair` est le primaire clair de la
    #  charte : écrit en littéral parce que `recolorer` remplace les littéraux, il
    #  prend la teinte claire de chaque palette. Les trois sarcelle sont celles du
    #  rôle « gestionnaire du site » sur le site (`front/src/styles/socle.css`) ;
    #  `--sur-primaire` est le texte clair posé sur la couleur principale. Aucune
    #  n'est un rôle de la palette : `recolorer` ne les touche pas, et c'est voulu.
    + """\
:root {
  --clair: #EEF2F7; --sur-primaire: #E8E6E1;
  --sarcelle: #0b6470; --sarcelle-fond: #ddf1f4; --sarcelle-bordure: #9dc1c6;
}
body {
  font-family: """
    + FONT_LISIBLE
    + """;
  color: var(--ink); background: var(--bg); line-height: 1.35; font-size: 13px;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.page {
  max-width: 210mm; height: 285mm; margin: 0 auto; background: var(--card);
  border-radius: 12px; overflow: hidden; box-shadow: 0 4px 24px rgba(30,58,95,.12);
  display: flex; flex-direction: column;
}

/* ── En-tête : bandeau de la couleur principale, logo de la résidence, filet or ── */
.header {
  background: var(--navy); color: #fff; position: relative;
  padding: 10px 26px 9px; display: flex; align-items: center; gap: 14px;
}
.header::after {
  content: ""; position: absolute; left: 26px; right: 26px; bottom: 0;
  height: 2px; background: var(--gold);
}
.header img, .header svg { flex-shrink: 0; }
.header-text { flex: 1; min-width: 0; }
.header-title {
  font-family: """
    + FONT_SERIF
    + """;
  font-size: 25px; font-weight: 700; line-height: 1.1;
}
.header-sub {
  font-size: 11.5px; color: var(--sur-primaire); letter-spacing: 1.5px;
  text-transform: uppercase; margin-top: 3px; font-weight: 700;
}
.header-site { font-size: 13.5px; font-weight: 700; white-space: nowrap; }

.content {
  padding: 9px """
    + _px(CONTENU_X_PX)
    + """ 4px; flex: 1; display: flex; flex-direction: column; gap: 5px;
}
h2, h3 {
  font-family: """
    + FONT_SERIF
    + """;
  color: var(--navy); font-weight: 700;
}
h2 { font-size: 19px; margin-bottom: 3px; }
h3 { font-size: 17px; }
.sec-titre {
  display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin-bottom: 3px;
  background: var(--clair); border-radius: 8px; padding: 2px 10px;
}
.muted { color: var(--muted); font-size: 12px; }

/* ── Accueil et accès en ligne ── */
.intro { display: grid; grid-template-columns: 1.25fr 1fr 1fr; gap: 9px; align-items: stretch; }
.accueil { font-size: 14px; white-space: pre-wrap; }
/*  Les QR codes ne rétrécissent JAMAIS : un QR trop petit reste beau et cesse
    d'être scannable, et celui du groupe WhatsApp porte un lien long. */
.qr-code { width: """
    + _px(QR_PX)
    + """; min-width: """
    + _px(QR_PX)
    + """; height: """
    + _px(QR_PX)
    + """; flex-shrink: 0; display: block; }
.cta {
  display: flex; align-items: center; gap: 8px; padding: 6px 8px;
  border: 1.5px solid var(--navy); border-radius: 12px;
}
.cta-texte { flex: 1; min-width: 0; }
.cta-label {
  font-size: 10.5px; color: var(--muted); font-weight: 700;
  text-transform: uppercase; letter-spacing: .6px;
}
.cta-titre { font-size: 15px; font-weight: 700; color: var(--navy); margin: 1px 0; overflow-wrap: anywhere; }
.cta-titre svg { vertical-align: -2px; margin-right: 3px; }
.cta-aide { font-size: 12px; color: var(--muted); line-height: 1.28; }
/*  Teinte littérale DÉCLARÉE (#2780) : le voile du Vert Parc, qui n'est pas un
    rôle de la palette — il est commun à toutes, comme sur le site
    (`front/src/styles/palettes.css`) et dans le filet des affiches et courriels.
    `recolorer` ne le touche pas, et c'est voulu : le bloc dit WhatsApp, pas la
    copropriété. Même raison pour l'ombre de `.page` (le bleu de la charte à
    12 %) : elle n'existe qu'à l'écran, l'impression la retire. */
.cta.whatsapp { background: #E8F0EA; border-color: #E8F0EA; }
.cta.whatsapp .cta-titre { color: var(--green); }

/* ── Les cartes : conseil (un bâtiment par carte) et syndic (un contact par carte) ── */
.bats { display: grid; gap: """
    + _px(ECART_CARTES_PX)
    + """; }
.bat {
  background: var(--card); border: """
    + _px(BORD_CARTE_PX)
    + """ solid var(--navy); border-radius: 10px; overflow: hidden;
}
/*  Pas de `text-transform: uppercase` : le libellé est celui que
    l'administration a saisi dans Périmètres, et le document l'affiche TEL QUEL. */
.bat-label {
  background: var(--navy); color: #fff; font-size: 12.5px; font-weight: 700;
  padding: 2px 9px; letter-spacing: .02em;
}
.bat-label svg { vertical-align: -1px; margin-right: 3px; stroke: #fff; }
.bat-corps { padding: 3px """
    + _px(CORPS_CARTE_X_PX)
    + """ 5px; }
.membre { padding: 2px 0; }
.membre + .membre { border-top: 1px solid var(--border); margin-top: 1px; padding-top: 3px; }
/*  La taille vient du document (`--taille-nom`, `fiche_arrivant_noms`) : la plus
    grande où le plus long nom du bloc tient sur une ligne. `.long` : un nom qui ne
    tient même pas abrégé passe à la ligne plutôt que d'être coupé. */
.membre-nom {
  font-size: var(--taille-nom, 14.5px); font-weight: 700; line-height: 1.2;
  color: var(--navy); white-space: nowrap; letter-spacing: -.01em;
  display: flex; align-items: center; gap: """
    + _px(PHOTO_ECART_PX)
    + """;
}
.membre-nom.long { white-space: normal; }
.membre-photo {
  width: """
    + _px(PHOTO_PX)
    + """; height: """
    + _px(PHOTO_PX)
    + """; border-radius: 50%; object-fit: cover; flex-shrink: 0;
}
.membre-detail { font-size: 11.5px; color: var(--muted); line-height: 1.35; }
/*  La vignette du rôle, discrète par choix (9 px) : SEULE exception déclarée au
    plancher de 10,5 px (`test_fiche_arrivant_lisible.py`, `SOUS_LE_PLANCHER`). */
.vignette-ligne { margin-top: 1px; line-height: 1; }
.vignette {
  display: inline-block; font-size: 9px; font-weight: 700; line-height: 1.35;
  padding: 0 4px; border-radius: 999px; white-space: nowrap; letter-spacing: .01em;
  background: var(--sarcelle-fond); color: var(--sarcelle); border: 1px solid var(--sarcelle-bordure);
}

/* ── Syndic : le cabinet dans le titre, un contact par carte, le QR de l'extranet ── */
.syndic-titre-nom { font-size: 14.5px; font-weight: 700; color: var(--navy); }
.syndic-titre-adresse { font-size: 12px; color: var(--muted); }
.syndic { display: grid; grid-template-columns: 1fr auto; gap: """
    + _px(ECART_SYNDIC_PX)
    + """; align-items: center; }
.syndic-contacts { display: grid; gap: """
    + _px(ECART_SYNDIC_PX)
    + """; align-items: stretch; }
.syndic-contacts .bat { align-self: stretch; }
.syndic .bat-label { font-size: 12px; letter-spacing: 0; }
.syndic .membre-detail { overflow-wrap: anywhere; }
.syndic .vignette-ligne { margin: 1px 0 2px; }

/* ── Consignes : une rubrique par bande, en pleine largeur ── */
.rappel { font-size: 12.5px; color: var(--muted); margin-bottom: 2px; }
.regle {
  display: grid; grid-template-columns: 40px 1fr; gap: 11px;
  padding: 4px 0; border-top: 1.5px solid var(--clair); page-break-inside: avoid;
}
.regle.sans-pictogramme { grid-template-columns: 1fr; }
.regle-pictogramme {
  width: 40px; height: 40px; border-radius: 11px; background: var(--clair);
  font-size: 21px; text-align: center; line-height: 40px;
}
.regle-titre {
  font-size: 16.5px; font-weight: 700; color: var(--navy); margin-bottom: 3px;
  display: flex; align-items: center; gap: 7px;
}
/*  Le numéro en pastille, blanc sur la couleur principale : en or sur blanc il ne
    contrastait qu'à 2,6:1 (#3143). */
.regle-numero {
  display: inline-block; min-width: 22px; height: 22px; border-radius: 11px;
  background: var(--navy); color: #fff; font-size: 13px; line-height: 22px; text-align: center;
}
.regle-contenu li {
  list-style: none; position: relative; padding-left: 14px;
  font-size: 14px; color: var(--ink); line-height: 1.32; margin-bottom: 1px;
}
.regle-contenu li::before {
  content: ""; position: absolute; left: 0; top: 7px;
  width: 6px; height: 6px; border-radius: 50%; background: var(--gold);
}
.consigne-footer-note { text-align: center; font-size: 12px; color: var(--muted); font-style: italic; }

.footer {
  padding: 7px 26px; background: var(--navy); color: var(--sur-primaire); position: relative;
  display: flex; justify-content: space-between; gap: 12px; font-size: 12px;
}
.footer::before {
  content: ""; position: absolute; left: 26px; right: 26px; top: 0;
  height: 2px; background: var(--gold);
}
"""
)
