"""Le PDF du rapport « Suivi des affaires » — maquette D2 (16/10/2026).

En tête, le nombre d'affaires non fermées et celles de plus de 90 jours, à côté
de la répartition par catégorie en barres ; puis le tableau : âge, date
d'ouverture, affaire (titre, périmètre quand ce n'est pas celui par défaut, et
l'aperçu — le résumé de l'assistant, sinon le descriptif — coupé à cinq lignes),
catégorie. Le même ordre qu'à l'écran.

Le thème — logo, palette, page, moteur — vient de `pdf_theme`, jamais d'ici.
Tout texte est ÉCHAPPÉ : titres et descriptifs viennent des résidents, les
résumés d'un modèle. La synthèse d'ensemble de #2034 n'existe plus (#2035).
"""

from __future__ import annotations

from html import escape

from app.utils.dates_fr import date_courte
from app.utils.pdf_theme import FONT_SANS, PALETTE_CSS, html_to_pdf, logo_html, regle_page
from app.utils.suivi_affaires.releve import Releve

TITRE = "Suivi des affaires"

#: L'aperçu s'arrête à cinq lignes — `line-clamp`, que WeasyPrint applique (#2035).
LIGNES_APERCU = 5

_CSS = f"""
{PALETTE_CSS}
{regle_page()}
body {{ font-family: {FONT_SANS}; font-size: 9.5pt; color: var(--ink); margin: 0; }}
.entete {{ display: flex; justify-content: space-between; align-items: center;
  border-bottom: 2px solid var(--navy); padding-bottom: 6pt; margin-bottom: 10pt; }}
.marque {{ display: flex; align-items: center; gap: 8pt; font-weight: 700; color: var(--navy); }}
.edite {{ color: var(--muted); font-size: 8.5pt; }}
h1 {{ color: var(--navy); font-size: 15pt; margin: 0 0 8pt; }}
.tete {{ display: flex; gap: 10pt; margin-bottom: 10pt; }}
.chiffres {{ display: flex; flex-direction: column; gap: 6pt; }}
.chiffre {{ border: 1px solid var(--border); border-radius: 5pt; padding: 5pt 9pt; min-width: 90pt; }}
.chiffre.fort {{ border-color: var(--navy); background: #eef2f7; }}
.chiffre .v {{ font-size: 20pt; font-weight: 700; color: var(--navy); line-height: 1.1; }}
.chiffre.alerte .v {{ color: #c0392b; }}
.chiffre .l {{ font-size: 8pt; color: var(--muted); }}
.repartition {{ flex: 1; border: 1px solid var(--border); border-radius: 5pt; padding: 6pt 9pt; }}
.repartition h2 {{ font-size: 7.5pt; text-transform: uppercase; letter-spacing: .05em;
  color: var(--muted); margin: 0 0 5pt; }}
.barres {{ width: 100%; border-collapse: collapse; }}
.barres td {{ padding: 2pt 0; border: 0; vertical-align: middle; font-size: 8.5pt; }}
.barres .nom {{ white-space: nowrap; padding-right: 8pt; width: 1%; }}
.barres .nb {{ text-align: right; font-weight: 700; width: 1%; padding-left: 6pt; }}
.piste {{ background: #f7f8fa; border-radius: 2pt; height: 7pt; }}
.barre {{ background: var(--navy); border-radius: 2pt; height: 7pt; }}
table.affaires {{ width: 100%; border-collapse: collapse; }}
.affaires th {{ text-align: left; font-size: 7.5pt; text-transform: uppercase; letter-spacing: .05em;
  color: var(--muted); border-bottom: 1.5pt solid var(--border); padding: 3pt 4pt; }}
.affaires td {{ border-bottom: 1px solid var(--border); padding: 5pt 4pt; vertical-align: top; }}
.affaires tr {{ break-inside: avoid; }}
.affaires thead {{ display: table-header-group; }}
.titre {{ font-weight: 700; display: block; margin-bottom: 2pt; }}
.perimetre {{ display: block; color: var(--muted); font-size: 8pt; margin-bottom: 2pt; }}
.descriptif {{ color: var(--ink); font-size: 8.5pt; line-clamp: {LIGNES_APERCU}; }}
.date, .categorie {{ white-space: nowrap; color: var(--muted); font-size: 8.5pt; }}
.age {{ font-weight: 700; font-size: 8pt; border-radius: 3pt; padding: 1pt 4pt; white-space: nowrap; }}
.age.ancienne {{ background: #fdedec; color: #c0392b; }}
.age.moyenne {{ background: #fdf3e0; color: #7b5815; }}
.age.recente {{ background: #f7f8fa; color: var(--muted); }}
.vide {{ color: var(--muted); font-style: italic; }}
"""


def _repartition(r: Releve) -> str:
    cats = r.par_categorie
    if not cats:
        return ""
    plus_grand = max(c.nombre for c in cats)
    lignes = "".join(
        f'<tr><td class="nom">{escape(c.libelle)}</td>'
        f'<td><div class="piste"><div class="barre" style="width:{round(100 * c.nombre / plus_grand)}%">'
        f'</div></div></td><td class="nb">{c.nombre}</td></tr>'
        for c in cats
    )
    return f'<div class="repartition"><h2>Par catégorie</h2><table class="barres">{lignes}</table></div>'


def _tableau(r: Releve) -> str:
    if not r.affaires:
        return '<p class="vide">Aucune affaire ouverte.</p>'
    lignes = "".join(
        "<tr>"
        f'<td><span class="age {a.anciennete}">{a.age_jours} j</span></td>'
        f'<td class="date">{date_courte(a.ouverte_le)}</td>'
        f'<td><span class="titre">{escape(a.titre)}</span>'
        + (
            f'<span class="perimetre">Périmètre : {escape(a.perimetre)}</span>'
            if a.perimetre
            else ""
        )
        + (f'<div class="descriptif">{escape(a.apercu)}</div>' if a.apercu else "")
        + f'</td><td class="categorie">{escape(a.libelle_categorie)}</td>'
        "</tr>"
        for a in r.affaires
    )
    return (
        '<table class="affaires"><thead><tr><th>Âge</th><th>Ouverte le</th><th>Affaire</th>'
        f"<th>Catégorie</th></tr></thead><tbody>{lignes}</tbody></table>"
    )


def html_rapport(r: Releve, *, site_nom: str, logo_png: bytes | None) -> str:
    """PURE. Le document HTML autonome du rapport."""
    pluriel = "s" if r.total > 1 else ""
    return (
        f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>{TITRE}</title>"
        f"<style>{_CSS}</style></head><body>"
        f'<div class="entete"><span class="marque">{logo_html(logo_png, 28)}{escape(site_nom)}</span>'
        f'<span class="edite">Édité le {date_courte(r.jour)}</span></div>'
        f"<h1>{TITRE}</h1>"
        '<div class="tete"><div class="chiffres">'
        f'<div class="chiffre fort"><div class="v">{r.total}</div>'
        f'<div class="l">affaire{pluriel} non fermée{pluriel}</div></div>'
        f'<div class="chiffre alerte"><div class="v">{r.anciennes}</div>'
        '<div class="l">de plus de 90 jours</div></div>'
        f"</div>{_repartition(r)}</div>"
        f"{_tableau(r)}</body></html>"
    )


def generer_pdf(r: Releve, *, site_nom: str, logo_png: bytes | None) -> bytes:
    return html_to_pdf(html_rapport(r, site_nom=site_nom, logo_png=logo_png))
