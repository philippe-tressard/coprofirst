"""Le PDF du compte rendu d'un point CS / Syndic (#2042, refait par #2082).

## L'ordre du document (arbitré le 20/10/2026)

> « Lorsque le CR est validé : les graphiques en couleur ; le Quand/Qui/Où et les
> validations ; la liste initiale des affaires à traiter ; puis le CR du point. »

1. les deux répartitions des affaires du point, en couleur (`pdf_barres`) ;
2. **le point** — Quand, Où, Qui — et **les validations** de chaque présent ;
3. **les affaires à traiter**, figées à l'ouverture, avec leur vignette Public /
   Privé et leur état ;
4. **le compte rendu** : les affaires abordées, une par bloc — marquées
   « CS et présents », « Modifié en révision N », et l'état décidé —, puis les
   non traitées.

Le même document sert d'APERÇU à tout instant (`projet`) : il porte alors
« Projet — révision N » au lieu de la date de validation.

Le thème — logo, palette, page, moteur — vient de `pdf_theme`, jamais d'ici.
Tout texte est ÉCHAPPÉ ; un CR riche est rendu en texte (`texte_brut`). Ce
module est PUR : `points_conseil_expedition.document` assemble ce qu'il montre.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Optional

from app.models.core import RoleUtilisateur, StatutUtilisateur
from app.models.points_conseil import CompteRenduAffaire
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
from app.utils.points_conseil_ou import ou_du_point
from app.utils.roles_libelles import libelle_role, libelle_statut
from app.utils.suivi_affaires.pdf_barres import CSS_BARRES, repartition_html
from app.utils.suivi_affaires.releve import AffaireOuverte, Releve

TITRE = "Compte rendu du point CS / Syndic"

#: Le libellé de la case « CS et présents » (#2082) — celui de l'écran.
LIBELLE_CS_ET_PRESENTS = "CS et présents"

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
{CSS_ENTETE_RAPPORT}{CSS_BARRES}
h2 {{ font-size: 8pt; text-transform: uppercase; letter-spacing: .05em; color: var(--muted);
  margin: 12pt 0 4pt; }}
p {{ margin: 0 0 3pt; }}
.tete {{ display: flex; gap: 10pt; margin-bottom: 4pt; }}
.groupe {{ font-weight: 700; }}
.precision {{ color: var(--muted); }}
ul.validations {{ margin: 0; padding-left: 12pt; }}
table.liste {{ width: 100%; border-collapse: collapse; font-size: 9pt; }}
.liste td {{ border-bottom: 1px solid var(--border); padding: 3pt 4pt; vertical-align: top; }}
.liste .num, .liste .etat {{ white-space: nowrap; color: var(--muted); }}
.vignette {{ font-size: 7pt; font-weight: 700; border-radius: 3pt; padding: 0 3pt;
  white-space: nowrap; }}
.vignette.prive {{ background: #efeaf8; color: #4a3aa7; }}
.vignette.public {{ background: #e8f4ee; color: #3d6b4f; }}
.abordee {{ border-top: 1px solid var(--border); padding: 5pt 0; break-inside: avoid; }}
.abordee .titre {{ font-weight: 700; color: var(--navy); margin-bottom: 2pt; }}
.abordee .texte {{ white-space: pre-line; }}
.marque {{ font-size: 7.5pt; color: var(--muted); font-weight: 400; }}
.marque.revision {{ color: #7b5815; }}
.vide {{ color: var(--muted); font-style: italic; }}
"""


@dataclass
class DocumentPoint:
    """Ce que le PDF montre — assemblé par `points_conseil_expedition.document`."""

    cr: CrGlobal
    #: Le relevé des affaires du point (les répartitions et la liste à traiter).
    releve: Releve
    #: La révision que le document montre, et les marques de chaque CR.
    revision: int
    marques: dict[int, str] = field(default_factory=dict)
    #: « Prénom NOM — validé le … » pour chaque destinataire, et la ligne du point.
    validations: list[str] = field(default_factory=list)
    validation_du_point: str = ""
    #: L'état décidé à la validation, par affaire, déjà écrit : « État : A → B ».
    etats: dict[int, str] = field(default_factory=dict)
    #: Un aperçu (« Projet — révision N »), pas le document validé.
    projet: bool = False


def _vignette(a: Optional[AffaireOuverte]) -> str:
    if a is None:
        return ""
    if a.prive:
        return '<span class="vignette prive">Privé</span>'
    return '<span class="vignette public">Public</span>'


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


def _validations(doc: DocumentPoint) -> str:
    items = "".join(f"<li>{escape(v)}</li>" for v in doc.validations)
    tete = f"<p>{escape(doc.validation_du_point)}</p>" if doc.validation_du_point else ""
    corps = f'<ul class="validations">{items}</ul>' if items else ""
    return f"<h2>Validations</h2>{tete}{corps}" if (tete or corps) else ""


def _liste_initiale(doc: DocumentPoint) -> str:
    affaires = {a.id: a for a in doc.releve.affaires}
    citees = doc.cr.initiales or [
        *(a for a, _ in doc.cr.abordees),
        *doc.cr.non_traitees,
    ]
    if not citees:
        return '<p class="vide">Aucune affaire à traiter.</p>'
    lignes = "".join(
        f'<tr><td class="num">{escape(c.numero)}</td><td>{escape(c.titre)}</td>'
        f"<td>{_vignette(affaires.get(c.id))}</td>"
        f'<td class="etat">{escape(affaires[c.id].libelle_statut) if c.id in affaires else ""}</td></tr>'
        for c in citees
    )
    return f'<table class="liste">{lignes}</table>'


def _marques(doc: DocumentPoint, ticket_id: int, c: CompteRenduAffaire) -> str:
    marques = []
    if c.conseil_seul:
        marques.append(f'<span class="marque">({LIBELLE_CS_ET_PRESENTS})</span>')
    if ticket_id in doc.marques:
        marques.append(f'<span class="marque revision">{escape(doc.marques[ticket_id])}</span>')
    if ticket_id in doc.etats:
        marques.append(f'<span class="marque">{escape(doc.etats[ticket_id])}</span>')
    return " ".join(marques)


def html_compte_rendu(doc: DocumentPoint, *, site_nom: str, logo_png: bytes | None) -> str:
    """PURE. Le document HTML autonome du compte rendu."""
    cr, point = doc.cr, doc.cr.point
    affaires = {a.id: a for a in doc.releve.affaires}
    abordees = (
        "".join(
            '<div class="abordee">'
            f'<p class="titre">{escape(a.numero)} · {escape(a.titre)} {_vignette(affaires.get(a.id))} '
            f"{_marques(doc, a.id, c)}</p>"
            f'<p class="texte">{escape(texte_brut(c.contenu))}</p></div>'
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
    if doc.projet:
        mention = f"Projet — révision {doc.revision}" if doc.revision else "Projet"
    else:
        mention = f"Validé le {date_courte(point.valide_le)}" if point.valide_le else ""
    nb = len(cr.initiales) or len(cr.abordees) + len(cr.non_traitees)
    return (
        f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>{TITRE}</title>"
        f"<style>{_CSS}</style></head><body>"
        f"{entete_rapport(logo_png, site_nom, mention)}"
        f"<h1>{TITRE}</h1>"
        '<div class="tete">'
        f"{repartition_html('Par catégorie', doc.releve.par_categorie)}"
        f"{repartition_html('Par bâtiment', doc.releve.par_batiment)}</div>"
        "<h2>1 · Le point</h2>"
        f"<p>{escape(datetime_longue(point.debut))} · {escape(ou_du_point(point))}</p>"
        f"{_presents(cr)}{_validations(doc)}"
        f"<h2>2 · Les affaires à traiter · {nb}</h2>{_liste_initiale(doc)}"
        f"<h2>3 · Le compte rendu · {len(cr.abordees)} affaire"
        f"{'s' if len(cr.abordees) > 1 else ''} abordée{'s' if len(cr.abordees) > 1 else ''}</h2>"
        f"{abordees}{non_traitees}</body></html>"
    )


def generer_pdf(doc: DocumentPoint, *, site_nom: str, logo_png: bytes | None) -> bytes:
    return html_to_pdf(html_compte_rendu(doc, site_nom=site_nom, logo_png=logo_png))
