"""Le PDF du compte rendu d'un point CS / Syndic — maquette C1 (#2042).

Deux parties, comme à l'écran : le point (quand, où, qui), puis les affaires
abordées, une par bloc, et les non traitées. Il n'existe qu'une fois le compte
rendu VALIDÉ (`routers/points_conseil_validation`) ; il porte alors aussi les
CR « Conseil seul » — c'est le document du conseil, qui l'envoie lui-même.

Le thème — logo, palette, page, moteur — vient de `pdf_theme`, jamais d'ici.
Tout texte est ÉCHAPPÉ ; un CR riche est rendu en texte (`texte_brut`).
"""

from __future__ import annotations

from html import escape

from app.models.core import RoleUtilisateur, StatutUtilisateur
from app.utils.annonce_hall import texte_brut
from app.utils.dates_fr import date_courte, datetime_longue
from app.utils.pdf_theme import (
    CSS_ENTETE_RAPPORT,
    FONT_SANS,
    PALETTE_CSS,
    entete_rapport,
    html_to_pdf,
    regle_page,
)
from app.utils.points_conseil import CrGlobal, nom_present
from app.utils.roles_libelles import libelle_role, libelle_statut

TITRE = "Compte rendu du point CS / Syndic"

#: Les trois groupes du Qui, dans l'ordre du CR — le même qu'à l'écran. Les deux
#: premiers se nomment par la table des rôles et des statuts, jamais réécrits.
GROUPES = (
    ("cs", libelle_role(RoleUtilisateur.conseil_syndical)),
    ("syndic", libelle_statut(StatutUtilisateur.syndic)),
    ("invite", "Invités"),
)

_CSS = f"""
{PALETTE_CSS}
{regle_page()}
body {{ font-family: {FONT_SANS}; font-size: 10pt; color: var(--ink); margin: 0; }}
{CSS_ENTETE_RAPPORT}h2 {{ font-size: 8pt; text-transform: uppercase; letter-spacing: .05em; color: var(--muted);
  margin: 12pt 0 4pt; }}
p {{ margin: 0 0 3pt; }}
.groupe {{ font-weight: 700; }}
.precision {{ color: var(--muted); }}
.abordee {{ border-top: 1px solid var(--border); padding: 5pt 0; break-inside: avoid; }}
.abordee .titre {{ font-weight: 700; color: var(--navy); margin-bottom: 2pt; }}
.abordee .texte {{ white-space: pre-line; }}
.marque-cs {{ font-size: 7.5pt; color: var(--muted); font-weight: 400; }}
.vide {{ color: var(--muted); font-style: italic; }}
"""


def _presents(cr: CrGlobal) -> str:
    lignes = []
    for nature, libelle in GROUPES:
        noms = [
            escape(nom_present(p))
            + (
                f' <span class="precision">({escape(", ".join(x for x in (p.fonction, p.entreprise) if x))})</span>'
                if p.fonction or (p.entreprise and (p.prenom or p.nom))
                else ""
            )
            + (
                f' <span class="precision">— {escape(", ".join(x for x in (p.telephone, p.email) if x))}</span>'
                if p.telephone or p.email
                else ""
            )
            for p in cr.presents
            if p.nature == nature
        ]
        if noms:
            lignes.append(f'<p><span class="groupe">{libelle} :</span> {" · ".join(noms)}</p>')
    return "".join(lignes) or '<p class="vide">Aucun présent indiqué.</p>'


def html_compte_rendu(cr: CrGlobal, *, site_nom: str, logo_png: bytes | None) -> str:
    """PURE. Le document HTML autonome du compte rendu."""
    point = cr.point
    ou = ("À distance" if point.a_distance else "Sur place") + (
        f" — {point.lieu}" if point.lieu else ""
    )
    abordees = (
        "".join(
            '<div class="abordee">'
            f'<p class="titre">{escape(a.numero)} · {escape(a.titre)}'
            + (' <span class="marque-cs">(conseil seul)</span>' if c.conseil_seul else "")
            + f'</p><p class="texte">{escape(texte_brut(c.contenu))}</p></div>'
            for a, c in cr.abordees
        )
        or '<p class="vide">Aucune affaire abordée.</p>'
    )
    non_traitees = (
        "<h2>Non traitées</h2><p>"
        + " · ".join(f"{escape(a.numero)} {escape(a.titre)}" for a in cr.non_traitees)
        + "</p>"
        if cr.non_traitees
        else ""
    )
    mention = f"Validé le {date_courte(point.valide_le)}" if point.valide_le else ""
    return (
        f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>{TITRE}</title>"
        f"<style>{_CSS}</style></head><body>"
        f"{entete_rapport(logo_png, site_nom, mention)}"
        f"<h1>{TITRE}</h1>"
        "<h2>1 · Le point</h2>"
        f"<p>{escape(datetime_longue(point.debut))} · {escape(ou)}</p>"
        f"{_presents(cr)}"
        f"<h2>2 · Les affaires abordées · {len(cr.abordees)}</h2>"
        f"{abordees}{non_traitees}</body></html>"
    )


def generer_pdf(cr: CrGlobal, *, site_nom: str, logo_png: bytes | None) -> bytes:
    return html_to_pdf(html_compte_rendu(cr, site_nom=site_nom, logo_png=logo_png))
