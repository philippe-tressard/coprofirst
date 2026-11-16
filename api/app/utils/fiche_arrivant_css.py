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
en noir, les titres de rubrique à 16,5 px (12,4 pt), les noms du conseil à 13 px.
La mise en page retenue par l'auteur est la variante « une page, règles en
pleine largeur » : des lignes longues, donc des rubriques moins hautes, et le
document tient toujours sur UNE feuille A4.

Repères : 1 pt = 1,333 px (96 px par pouce, l'unité du navigateur comme de
WeasyPrint). Les petits libellés (fonctions, rôles) sont en bleu et non en or :
l'or de la charte sur blanc ne contraste qu'à 2,6:1, illisible à 11 px.

🔴 Le document se lit dans le NAVIGATEUR, qui l'imprime lui-même (le PDF n'existe
que dans les tests) : une retouche se juge à l'impression de Chromium en A4, une
seule page, jamais à l'écran.
"""

from __future__ import annotations

from app.utils.pdf_theme import FONT_LISIBLE, FONT_SERIF, PALETTE_CSS, regle_page


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
    + """\
* { box-sizing: border-box; margin: 0; padding: 0; }
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

/* ── En-tête : bandeau bleu, logo de la résidence, filet or ── */
.header {
  background: var(--navy); color: #fff; position: relative;
  padding: 13px 26px 12px; display: flex; align-items: center; gap: 14px;
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
  font-size: 11.5px; color: var(--gold); letter-spacing: 1.5px;
  text-transform: uppercase; margin-top: 3px; font-weight: 700;
}
.header-site { font-size: 13.5px; font-weight: 700; white-space: nowrap; }

.content { padding: 11px 22px 4px; flex: 1; display: flex; flex-direction: column; gap: 9px; }
h2, h3 {
  font-family: """
    + FONT_SERIF
    + """;
  color: var(--navy); font-weight: 700;
}
h2 { font-size: 19px; margin-bottom: 3px; }
h3 { font-size: 17px; }
.sec-titre { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin-bottom: 5px; }
.muted { color: var(--muted); font-size: 12px; }

/* ── Accueil et accès en ligne ── */
.intro { display: grid; grid-template-columns: 1.25fr 1fr 1fr; gap: 9px; align-items: stretch; }
.accueil { font-size: 14px; white-space: pre-wrap; }
/*  Les QR codes ne rétrécissent JAMAIS : un QR trop petit reste beau et cesse
    d'être scannable, et celui du groupe WhatsApp porte un lien long. */
.qr-code { width: 58px; min-width: 58px; height: 58px; flex-shrink: 0; display: block; }
.cta {
  display: flex; align-items: center; gap: 8px; padding: 8px 9px;
  border: 1.5px solid var(--border); border-radius: 12px;
}
.cta-texte { flex: 1; min-width: 0; }
.cta-label {
  font-size: 10.5px; color: var(--muted); font-weight: 700;
  text-transform: uppercase; letter-spacing: .6px;
}
.cta-titre { font-size: 15px; font-weight: 700; color: var(--navy); margin: 1px 0; }
.cta-titre svg { vertical-align: -2px; margin-right: 3px; }
.cta-aide { font-size: 12px; color: var(--muted); line-height: 1.28; }
.cta.whatsapp { background: #E8F0EA; border-color: #E8F0EA; }
.cta.whatsapp .cta-titre { color: var(--green); }

/* ── Conseil syndical, par bâtiment (le nombre de colonnes vient du document) ── */
.bats { display: grid; gap: 7px; }
.bat { background: var(--bg); border-radius: 10px; padding: 6px 9px; }
/*  Pas de `text-transform: uppercase` : le libellé est celui que
    l'administration a saisi dans Périmètres, et le document l'affiche TEL QUEL. */
.bat-label { font-size: 13px; font-weight: 700; color: var(--navy); margin-bottom: 2px; }
.bat-label svg { vertical-align: -1px; margin-right: 3px; }
.membre { display: flex; align-items: center; gap: 6px; padding: 1px 0; }
.membre-photo { width: 28px; height: 28px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
.membre-nom { font-size: 13px; font-weight: 700; line-height: 1.2; }
.membre-detail { font-size: 12px; color: var(--muted); }
.membre-detail b { color: var(--navy); }

/* ── Syndic ── */
.syndic {
  display: grid; grid-template-columns: 1.1fr 3fr auto; gap: 10px; align-items: center;
  border: 1.5px solid var(--border); border-radius: 12px; padding: 8px 11px;
}
.syndic-nom { font-size: 14.5px; font-weight: 700; color: var(--navy); }
.syndic-adresse { font-size: 12px; color: var(--muted); }
.syndic-contacts { display: grid; gap: 9px; }
.syndic-contact {
  border-left: 1.5px solid var(--border); padding-left: 8px;
  font-size: 11.5px; color: var(--muted); line-height: 1.32; min-width: 0; overflow-wrap: anywhere;
}
.syndic-fonction {
  font-size: 10.5px; color: var(--navy); font-weight: 700;
  text-transform: uppercase; letter-spacing: .5px;
}
.syndic-personne { font-size: 12.5px; color: var(--ink); font-weight: 700; }

/* ── Consignes : une rubrique par bande, en pleine largeur ── */
.rappel { font-size: 12.5px; color: var(--muted); margin-bottom: 4px; }
.regle {
  display: grid; grid-template-columns: 40px 1fr; gap: 11px;
  padding: 6px 0; border-top: 1.5px solid var(--border); page-break-inside: avoid;
}
.regle.sans-pictogramme { grid-template-columns: 1fr; }
.regle-pictogramme {
  width: 40px; height: 40px; border-radius: 11px; background: var(--bg);
  font-size: 21px; text-align: center; line-height: 40px;
}
.regle-titre { font-size: 16.5px; font-weight: 700; color: var(--navy); margin-bottom: 3px; }
.regle-numero { color: var(--gold); margin-right: 5px; }
.regle-contenu li {
  list-style: none; position: relative; padding-left: 14px;
  font-size: 14px; color: var(--ink); line-height: 1.32; margin-bottom: 2px;
}
.regle-contenu li::before {
  content: ""; position: absolute; left: 0; top: 7px;
  width: 6px; height: 6px; border-radius: 50%; background: var(--gold);
}
.consigne-footer-note { text-align: center; font-size: 12px; color: var(--muted); font-style: italic; }

.footer {
  padding: 6px 26px; border-top: 1px solid var(--border); background: var(--footer-bg);
  display: flex; justify-content: space-between; gap: 12px; font-size: 12px; color: var(--muted);
}
"""
)
