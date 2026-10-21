"""Le PDF du rapport « Suivi des affaires » — maquette D2 (16/10/2026).

En tête, le nombre d'affaires non fermées et celles de plus de 90 jours, à côté
des deux répartitions en barres découpées, en couleur (`pdf_barres`, #2082) ; puis le tableau : âge, date
d'ouverture, affaire (titre, périmètre quand ce n'est pas celui par défaut, et
l'aperçu — le résumé de l'assistant, sinon le descriptif — coupé à cinq lignes),
catégorie. Le même ordre qu'à l'écran.

Le thème — logo, palette, page, moteur — vient de `pdf_theme`, jamais d'ici.
Tout texte est ÉCHAPPÉ : titres et descriptifs viennent des résidents, les
résumés d'un modèle. La synthèse d'ensemble de #2034 n'existe plus (#2035).
"""

from __future__ import annotations

from html import escape
from typing import Callable

from app.utils.dates_fr import date_courte
from app.utils.pdf_theme import (
    CSS_ENTETE_RAPPORT,
    FONT_SANS,
    PALETTE_CSS,
    entete_rapport,
    html_to_pdf,
    regle_page,
)
from app.utils.suivi_affaires.pdf_barres import CSS_BARRES, repartition_html
from app.utils.suivi_affaires.releve import AffaireOuverte, Releve

#: Le titre, selon le mode du relevé (#2043).
TITRES = {"affaires": "Suivi des affaires", "entretien": "Suivi des entretiens périodiques"}

#: L'aperçu s'arrête à cinq lignes — `line-clamp`, que WeasyPrint applique (#2035).
LIGNES_APERCU = 5

#: Le style du rapport — tête, répartitions, tableau. Le PDF du point CS / Syndic
#: (`points_conseil_pdf`, maquette B, #2089) est ce rapport augmenté : il le lit ici.
CSS_RAPPORT = f"""
{PALETTE_CSS}
{regle_page()}
body {{ font-family: {FONT_SANS}; font-size: 9.5pt; color: var(--ink); margin: 0; }}
{CSS_ENTETE_RAPPORT}.tete {{ display: flex; gap: 10pt; margin-bottom: 10pt; }}
.chiffres {{ display: flex; flex-direction: column; gap: 4pt; }}
.chiffre {{ border: 1px solid var(--border); border-radius: 5pt; padding: 2pt 9pt; min-width: 90pt; }}
.chiffre.fort {{ border-color: var(--navy); background: #eef2f7; }}
.chiffre .v {{ font-size: 14pt; font-weight: 700; color: var(--navy); line-height: 1.1; }}
.chiffre.alerte .v {{ color: #c0392b; }}
.chiffre .l {{ font-size: 7.5pt; color: var(--muted); }}
{CSS_BARRES}table.affaires {{ width: 100%; border-collapse: collapse; }}
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


def _rien(_a: AffaireOuverte) -> str:
    return ""


def tableau_html(
    affaires: list[AffaireOuverte],
    *,
    sous_titre: Callable[[AffaireOuverte], str] = _rien,
    complement: Callable[[AffaireOuverte], str] = _rien,
    entete: str = "Affaire",
    vide: str = "Aucune affaire ouverte.",
) -> str:
    """PURE. Le tableau du rapport : âge, ouverte le, affaire (titre, périmètre,
    résumé), catégorie. `sous_titre` s'insère sous le titre, `complement` sous le
    résumé — du HTML déjà échappé : le PDF du point y met ses vignettes et le
    compte rendu de chaque affaire (#2089)."""
    if not affaires:
        return f'<p class="vide">{escape(vide)}</p>'
    lignes = "".join(
        "<tr>"
        f'<td><span class="age {a.anciennete}">{a.age_jours} j</span></td>'
        f'<td class="date">{date_courte(a.ouverte_le)}</td>'
        f'<td><span class="titre">{escape(a.titre)}</span>{sous_titre(a)}'
        + (
            f'<span class="perimetre">Périmètre : {escape(a.perimetre)}</span>'
            if a.perimetre
            else ""
        )
        + (f'<div class="descriptif">{escape(a.apercu)}</div>' if a.apercu else "")
        + complement(a)
        + f'</td><td class="categorie">{escape(a.libelle_categorie)}</td>'
        "</tr>"
        for a in affaires
    )
    return (
        '<table class="affaires"><thead><tr><th>Âge</th><th>Ouverte le</th>'
        f"<th>{escape(entete)}</th><th>Catégorie</th></tr></thead><tbody>{lignes}</tbody></table>"
    )


def tete_html(r: Releve, libelle_total: str) -> str:
    """PURE. Les trois chiffres — affaires, de plus de 90 jours, fusionnées (#2083) —
    dans la hauteur où en tenaient deux, et les deux répartitions en couleur."""
    fusion = "s" if r.fusionnees > 1 else ""
    return (
        '<div class="tete"><div class="chiffres">'
        f'<div class="chiffre fort"><div class="v">{r.total}</div>'
        f'<div class="l">{escape(libelle_total)}</div></div>'
        f'<div class="chiffre alerte"><div class="v">{r.anciennes}</div>'
        '<div class="l">de plus de 90 jours</div></div>'
        f'<div class="chiffre"><div class="v">{r.fusionnees}</div>'
        f'<div class="l">affaire{fusion} fusionnée{fusion}</div></div>'
        f"</div>{repartition_html('Par catégorie', r.par_categorie)}"
        f"{repartition_html('Par bâtiment', r.par_batiment)}</div>"
    )


def html_rapport(r: Releve, *, site_nom: str, logo_png: bytes | None) -> str:
    """PURE. Le document HTML autonome du rapport."""
    pluriel = "s" if r.total > 1 else ""
    titre = TITRES.get(r.mode, TITRES["affaires"])
    return (
        f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>{titre}</title>"
        f"<style>{CSS_RAPPORT}</style></head><body>"
        f"{entete_rapport(logo_png, site_nom, f'Édité le {date_courte(r.jour)}')}"
        f"<h1>{titre}</h1>"
        f"{tete_html(r, f'affaire{pluriel} non fermée{pluriel}')}"
        f"{tableau_html(r.affaires)}</body></html>"
    )


def generer_pdf(r: Releve, *, site_nom: str, logo_png: bytes | None) -> bytes:
    return html_to_pdf(html_rapport(r, site_nom=site_nom, logo_png=logo_png))
