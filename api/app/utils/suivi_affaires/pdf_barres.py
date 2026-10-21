"""Les RÉPARTITIONS en barres découpées, sur papier — en couleur (#2082).

Le Suivi des affaires imprimait des barres pleines, d'une seule teinte (#2043 :
« l'écran les découpe, le papier non »). Le PDF du point CS / Syndic validé les
veut **en couleur**, comme à l'écran : les deux PDF les lisent ici, une fois.

La teinte de chaque tranche vient du relevé (`repartition.teinter`) ; ce module
ne fait que la peindre. `TEINTES` recopie les jetons `--serie-*` et `--palier-*`
de `front/src/styles/socle.css` : le papier ne lit pas la feuille de l'écran
(deux images, deux contextes de build). 🔒 `test_teintes_repartition.py` échoue
si les deux divergent.

Les barres sont des TABLEAUX : WeasyPrint les rend à coup sûr, une boîte souple
découpée en parts proportionnelles beaucoup moins.
"""

from __future__ import annotations

from html import escape
from urllib.parse import quote

from app.utils.suivi_affaires.repartition import Barre, CLE_PLUSIEURS

#: Les couleurs des teintes — celles de `socle.css` (écran), recopiées pour le papier.
TEINTES: dict[str, str] = {
    "s1": "#2a78d6",
    "s2": "#eb6834",
    "s3": "#1baf7a",
    "s4": "#eda100",
    "s5": "#e87ba4",
    "s6": "#008300",
    "s7": "#4a3aa7",
    "s8": "#e34948",
    "p1": "#444441",
    "p2": "#888780",
    "p3": "#b4b2a9",
    "p4": "#d3d1c7",
    #  `--color-text-muted` à l'écran.
    "autre": "#5a6070",
}

#: « Plusieurs bâtiments » : hachurée, comme à l'écran. Un MOTIF SVG en data-URI,
#: pas un `repeating-linear-gradient` : WeasyPrint ne rendait pas ce dernier — la
#: barre restait vide et la légende sans carré (constaté sur le PDF du 21/10/2026).
#: Encodé en entier (`quote`) : il vit dans un attribut `style="…"`.
_MOTIF = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4">'
    '<rect width="4" height="4" fill="#f7f8fa"/>'
    '<path d="M-1 1 L1 -1 M0 4 L4 0 M3 5 L5 3" stroke="#888780" stroke-width="1.2"/></svg>'
)
_HACHURE = f"url(data:image/svg+xml;charset=utf-8,{quote(_MOTIF, safe='')})"

CSS_BARRES = """
.repartition { flex: 1; border: 1px solid var(--border); border-radius: 5pt; padding: 6pt 9pt; }
.repartition h2 { font-size: 7.5pt; text-transform: uppercase; letter-spacing: .05em;
  color: var(--muted); margin: 0 0 5pt; }
.barres { width: 100%; border-collapse: collapse; }
.barres td { padding: 2pt 0; border: 0; vertical-align: middle; font-size: 8.5pt; }
.barres .nom { white-space: nowrap; padding-right: 8pt; width: 1%; }
.barres .nb { text-align: right; font-weight: 700; width: 1%; padding-left: 6pt; }
.piste { background: #f7f8fa; border-radius: 2pt; height: 7pt; }
table.tranches { border-collapse: separate; border-spacing: 1pt 0; height: 7pt; }
table.tranches td { padding: 0; height: 7pt; }
.legende { margin: 4pt 0 0; padding: 0; font-size: 7.5pt; color: var(--muted); }
.legende span.item { display: inline-block; margin-right: 8pt; }
.legende span.pastille { display: inline-block; width: 6pt; height: 6pt; border-radius: 1pt;
  margin-right: 2pt; vertical-align: middle; }
"""


def _fond(teinte: str) -> str:
    if teinte == CLE_PLUSIEURS:
        return f"background-color:#b4b2a9;background-image:{_HACHURE};background-size:4px 4px"
    return f"background:{TEINTES.get(teinte, TEINTES['autre'])}"


def _barre(b: Barre, plus_grand: int) -> str:
    parts = "".join(
        f'<td style="width:{round(100 * t.nombre / b.nombre, 2)}%;{_fond(t.teinte)}"'
        f' title="{escape(t.libelle)} : {t.nombre}"></td>'
        for t in b.tranches
    )
    largeur = round(100 * b.nombre / plus_grand, 2)
    return (
        f'<tr><td class="nom">{escape(b.libelle)}</td><td><div class="piste">'
        f'<table class="tranches" style="width:{largeur}%"><tr>{parts}</tr></table>'
        f'</div></td><td class="nb">{b.nombre}</td></tr>'
    )


def _legende(barres: list[Barre]) -> str:
    vues: dict[str, tuple[str, str]] = {}
    for t in (t for b in barres for t in b.tranches):
        vues.setdefault(t.cle, (t.libelle, t.teinte))
    return "".join(
        f'<span class="item"><span class="pastille" style="{_fond(teinte)}"></span>'
        f"{escape(libelle)}</span>"
        for libelle, teinte in vues.values()
    )


def repartition_html(titre: str, barres: list[Barre]) -> str:
    """PURE. Une répartition : chaque barre découpée en tranches colorées, et sa légende."""
    if not barres:
        return ""
    plus_grand = max(b.nombre for b in barres) or 1
    lignes = "".join(_barre(b, plus_grand) for b in barres)
    return (
        f'<div class="repartition"><h2>{escape(titre)}</h2>'
        f'<table class="barres">{lignes}</table>'
        f'<p class="legende">{_legende(barres)}</p></div>'
    )
