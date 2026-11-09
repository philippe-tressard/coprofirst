"""Feuille de style de la fiche d'accueil — extraite au fil de l'eau.

`fiche_arrivant.py` atteignait exactement les 500 lignes du plafond de modularité
(rang 1 §4) : le lot suivant l'aurait fait échouer. La feuille de style est ce qui
s'en détache le plus proprement — elle n'a aucune logique, et elle change pour des
raisons qui ne sont pas celles du document (une retouche de charte graphique n'est
pas un changement de contenu).

Elle reste **propre à ce document** : ce qui est commun à tous les imprimables —
palette, logo, icônes, moteur — vit dans `pdf_theme.py`, et ne se redéfinit pas ici.
"""

from __future__ import annotations

from app.utils.pdf_theme import PALETTE_CSS, regle_page


CSS = (
    regle_page(marges="6mm 8mm", numeroter=False)
    + """
@media print {
  body { background: none !important; }
  .page { box-shadow: none !important; border: none !important; }
}
"""
    + PALETTE_CSS
    + """\
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, 'Helvetica Neue', Arial, sans-serif;
  color: var(--ink); background: var(--bg); line-height: 1.4; font-size: 12.5px;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.page {
  max-width: 210mm; height: 281mm; margin: 0 auto; background: var(--card);
  border-radius: 12px; overflow: hidden; box-shadow: 0 4px 24px rgba(30,58,95,.12);
  display: flex; flex-direction: column;
}
.header {
  background: linear-gradient(135deg, var(--navy) 0%, var(--navy-dark) 100%);
  padding: 12px 20px; display: flex; align-items: center; gap: 10px;
}
.header svg { flex-shrink: 0; }
.header-text { flex: 1; }
.header-title {
  font-family: Georgia, 'Palatino Linotype', 'Book Antiqua', Palatino, serif;
  font-size: 18px; font-weight: 700; color: #fff; letter-spacing: .3px;
}
.header-sub {
  font-size: 10px; color: var(--gold); letter-spacing: 1.5px;
  text-transform: uppercase; margin-top: 1px; font-weight: 600;
}
.accent-bar {
  height: 3px;
  background: linear-gradient(90deg, var(--gold) 0%, var(--navy) 50%, var(--green) 100%);
}
.content { padding: 10px 20px; flex: 1; }
.content h2 {
  font-family: Georgia, 'Palatino Linotype', serif;
  font-size: 16px; font-weight: 700; color: var(--navy); margin-bottom: 3px;
}
.content h3 {
  font-size: 12.5px; font-weight: 700; color: var(--navy);
  margin: 8px 0 4px; padding-bottom: 2px;
  border-bottom: 2px solid var(--gold); display: inline-block;
}
.content p { margin-bottom: 4px; font-size: 12px; }
.content .muted { color: var(--muted); font-size: 10.5px; }
/*  Hauteur des blocs à QR code — resserrée le 14/08/2026 pour que le document
    tienne sur UNE page A4 (`.page` est haute de 281 mm, fixe : ce qui dépasse
    part sur une seconde feuille).

    WeasyPrint rend à 96 px par pouce, donc 1 mm = 3.78 px. Le gain est pris sur
    les rembourrages verticaux (7 → 4 px, soit 6 px = 1,6 mm par bloc) et sur les
    marges, JAMAIS sur `.qr-code` : un QR rétréci reste beau et cesse d'être
    scannable, et celui du groupe WhatsApp porte un lien long, donc un motif dense.
    C'est le seul élément de ce document dont la taille a une fonction. */
.dual-cta { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 4px 0; }
.cta-banner {
  display: flex; align-items: center; gap: 8px;
  background: linear-gradient(135deg, #F7F5F0, #F0EDE6);
  border-radius: 6px; padding: 4px 10px; border-left: 4px solid var(--gold);
}
.cta-banner-text { flex: 1; }
.cta-banner-text .label { font-size: 9px; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: .5px; }
.cta-banner-text .url { font-size: 13px; font-weight: 700; color: var(--navy); letter-spacing: .3px; }
.cta-banner-text .hint { font-size: 9px; color: var(--light-muted); margin-top: 1px; }
.bat-section { margin-bottom: 4px; }
/*  Pas de `text-transform: uppercase` : le libellé est celui que
    l'administration a saisi dans Périmètres, et le document l'affiche TEL QUEL.
    Le mettre en capitales, c'était le réécrire — « Bâtiment 1 » devenait
    « BÂTIMENT 1 », et une copropriété qui nommerait ses bâtiments « Le Cèdre »
    n'aurait pas reconnu le sien. */
.bat-label {
  font-size: 10.5px; font-weight: 700; color: var(--navy);
  letter-spacing: .3px;
  padding: 2px 6px; border-left: 3px solid var(--gold);
  margin-bottom: 3px; background: #FAFAF7;
}
.bat-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 3px; }
.annuaire-section { margin-top: 6px; }
.annuaire-section h3 { margin-top: 6px; }
.contact-card {
  background: #F7F5F0; border-radius: 5px; padding: 4px 8px;
  border-left: 3px solid var(--navy); display: flex; align-items: center; gap: 6px;
}
.contact-card.president { border-left-color: var(--green); background: #F2F7F4; }
.contact-card.syndic { border-left-color: #7C3AED; }
.contact-card.principal { border-left-color: var(--gold); background: #FDFAF3; }
.contact-avatar {
  width: 24px; height: 24px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 9px; font-weight: 700; color: #fff; flex-shrink: 0;
}
.contact-avatar.navy { background: var(--navy); }
.contact-avatar.green { background: var(--green); }
.contact-avatar.gold { background: var(--gold); }
.contact-avatar.purple { background: #7C3AED; }
.contact-body { flex: 1; min-width: 0; }
.contact-name { font-size: 11px; font-weight: 600; color: var(--ink); }
.contact-role { font-size: 8.5px; color: var(--gold); font-weight: 600; text-transform: uppercase; letter-spacing: .5px; }
.contact-info { font-size: 9.5px; color: var(--muted); line-height: 1.3; }
.syndic-header {
  background: linear-gradient(135deg, #F7F5F0, #F0EDE6); border-radius: 6px;
  padding: 4px 10px; margin-top: 2px; margin-bottom: 2px; overflow: visible;
}
.syndic-name { font-size: 12px; font-weight: 700; color: var(--navy); }
.syndic-detail { font-size: 10px; color: var(--muted); }
.syndic-contacts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; }
.contact-photo {
  width: 24px; height: 24px; border-radius: 50%;
  object-fit: cover; flex-shrink: 0;
}
.qr-code { width: 52px; min-width: 52px; height: 52px; flex-shrink: 0; display: block; }
.sep { border: none; height: 1px; background: var(--border); margin: 6px 0; }
.footer {
  background: var(--footer-bg); padding: 6px 20px; text-align: center;
  border-top: 1px solid var(--border);
}
.footer p { font-size: 10px; color: var(--light-muted); }
.accueil { white-space: pre-wrap; }
.consignes-intro {
  background: linear-gradient(135deg, #F7F5F0, #F0EDE6);
  border-radius: 6px; padding: 8px 12px; margin-bottom: 6px;
  border-left: 4px solid var(--gold);
}
.consignes-intro p { margin: 0; font-size: 10.5px; color: var(--muted); line-height: 1.35; }
.consignes-intro strong { color: var(--navy); }
.regle {
  margin-bottom: 5px; padding: 6px 10px;
  background: #FAFAF7; border-radius: 5px;
  border-left: 3px solid var(--green); page-break-inside: avoid;
}
.regle-titre { font-size: 12px; font-weight: 700; color: var(--navy); margin-bottom: 2px; }
.regle-contenu { font-size: 10.5px; color: var(--muted); line-height: 1.35; white-space: pre-wrap; }
.regle-contenu strong { color: var(--ink); }
.consigne-footer-note {
  text-align: center; margin-top: 6px;
  font-size: 10px; color: var(--light-muted); font-style: italic;
}
.whatsapp-cta {
  display: flex; align-items: center; gap: 8px; padding: 4px 10px;
  background: linear-gradient(135deg, #E8F5E9, #F1F8E9);
  border-radius: 6px; border-left: 4px solid #25D366;
}
.whatsapp-cta .wa-text { flex: 1; }
.whatsapp-cta .wa-title { font-size: 11px; font-weight: 700; color: var(--navy); margin-bottom: 1px; }
.whatsapp-cta .wa-desc { font-size: 9px; color: var(--muted); line-height: 1.3; }
.whatsapp-cta .wa-desc strong { color: var(--ink); }
"""
)
