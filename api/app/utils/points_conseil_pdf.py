"""Le PDF du point CS / Syndic — la maquette B (#2089, choisie le 20/10/2026 parmi cinq).

> « Reprendre uniquement celui de “Exporter PDF”, qui est chouette ; il faut juste
> rajouter les sections manquantes : Quand / Qui / Où et les validations, et le
> CR du point — fusionner le listing des affaires avec le CR affaire par
> affaire. » — puis : « On retient B, mais bien conserver les résumés initiaux
> de chaque affaire après le titre. »

Le document EST le rapport du Suivi des affaires (`suivi_affaires.pdf` : son
style, sa tête, son tableau), augmenté :

1. **le point en tête** : Quand, Où, Qui, et les **validations** dans un cartouche ;
2. les deux chiffres et les deux **répartitions en couleur** ;
3. **les affaires abordées** : âge, date d'ouverture, titre — sous lui, l'état de
   suivi et « qui la lit » en vignettes —, périmètre, **résumé d'origine**, puis
   le **compte rendu** dans la cellule, marqué « CS et présents », « Modifié en
   révision N », et l'état décidé ;
4. **les non abordées**, à la fin, numéro et titre.

Le même document, validé ou non : un point en cours ou en relecture porte
« Projet — révision N » ; validé, « Validé le … » — c'est lui qui est rangé et
envoyé aux présents. Tout texte est ÉCHAPPÉ ; un CR riche est rendu en texte.
Ce module est PUR : `points_conseil_expedition.document` assemble ce qu'il montre.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

from app.models.core import RoleUtilisateur, StatutUtilisateur
from app.models.points_conseil import CompteRenduAffaire
from app.utils.annonce_hall import texte_brut
from app.utils.dates_fr import date_courte, date_longue, datetime_longue
from app.utils.pdf_theme import entete_rapport, html_to_pdf
from app.utils.points_conseil import CrGlobal, nom_present
from app.utils.points_conseil_ou import ou_du_point
from app.utils.roles_libelles import libelle_role, libelle_statut
from app.utils.suivi_affaires.pdf import CSS_RAPPORT, tableau_html, tete_html
from app.utils.suivi_affaires.releve import AffaireOuverte, Releve

TITRE = "Point CS / Syndic"

#: Le libellé de la case « CS et présents » (#2082) — celui de l'écran.
LIBELLE_CS_ET_PRESENTS = "CS et présents"

#: Les trois groupes du Qui, dans l'ordre du CR — le même qu'à l'écran. Les deux
#: premiers se nomment par la table des rôles et des statuts, jamais réécrits.
GROUPES = (
    ("cs", libelle_role(RoleUtilisateur.conseil_syndical)),
    ("syndic", libelle_statut(StatutUtilisateur.syndic)),
    ("invite", "Invités"),
)

#: La teinte de la vignette d'état — celles des badges d'état de l'écran
#: (`STATUT_TICKET_BADGE`) : orange chez le syndic, violet à l'AG, bleu chez le
#: prestataire, vert clos, gris sinon.
TEINTES_ETAT = {
    "en_cours": ("#fdf3e0", "#7b5815"),
    "en_ag": ("#efeaf8", "#4a3aa7"),
    "chez_prestataire": ("#e6f0fb", "#1d5fa8"),
    "résolu": ("#e8f4ee", "#2e7d4f"),
    "annulé": ("#f3f4f7", "#5a6070"),
}

_CSS = (
    CSS_RAPPORT
    + """
.cote { display: flex; gap: 10pt; margin-bottom: 10pt; }
.point { flex: 1; border: 1px solid var(--border); border-radius: 5pt; padding: 6pt 9pt; }
.point p { margin: 0 0 3pt; }
.groupe { font-weight: 700; }
.precision { color: var(--muted); }
.cartouche { width: 160pt; border: 1px solid var(--navy); border-radius: 5pt; padding: 6pt 9pt;
  font-size: 8.5pt; }
.cartouche h3, .point h3 { margin: 0 0 4pt; font-size: 7.5pt; text-transform: uppercase;
  letter-spacing: .05em; color: var(--navy); }
.cartouche p { margin: 0 0 3pt; }
.cartouche .ok { color: #2e7d4f; }
.cartouche .derog { color: #7b5815; }
h2 { font-size: 7.5pt; text-transform: uppercase; letter-spacing: .05em; color: var(--muted);
  margin: 12pt 0 4pt; }
.caps { display: block; margin: 0 0 2pt; }
.cap { display: inline-block; font-size: 7pt; font-weight: 700; border-radius: 6pt;
  padding: 0 5pt; margin-right: 3pt; border: 1px solid transparent; }
.cap.lecture { background: #eef2f7; color: var(--navy); }
.cap.decide { background: #fff; color: var(--navy); border-color: var(--navy); }
.crb { background: #f6f8fb; border-left: 2.5pt solid var(--navy); padding: 4pt 7pt;
  margin-top: 4pt; font-size: 8.5pt; white-space: pre-line; }
.crb .lbl { font-size: 7pt; text-transform: uppercase; letter-spacing: .05em; color: var(--navy);
  font-weight: 700; margin-right: 4pt; }
.marque { font-size: 7pt; color: var(--muted); }
.marque.revision { color: #7b5815; font-weight: 700; }
.nt { color: var(--muted); font-size: 8.5pt; }
"""
)


@dataclass
class DocumentPoint:
    """Ce que le PDF montre — assemblé par `points_conseil_expedition.document`."""

    cr: CrGlobal
    #: Le relevé des affaires du point (les répartitions et les lignes).
    releve: Releve
    #: La révision que le document montre, et les marques de chaque CR.
    revision: int
    marques: dict[int, str] = field(default_factory=dict)
    #: « Prénom NOM — validé le … » pour chaque destinataire, et la ligne du point.
    validations: list[str] = field(default_factory=list)
    validation_du_point: str = ""
    #: L'état décidé à la validation, par affaire, déjà écrit : « État : A → B ».
    etats: dict[int, str] = field(default_factory=dict)
    #: Un projet (« Projet — révision N »), pas le document validé.
    projet: bool = False


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


def _cartouche(doc: DocumentPoint) -> str:
    lignes = (
        "".join(
            f'<p class="{"derog" if "dérogation" in v else "ok" if "validé" in v else ""}">'
            f"{escape(v)}</p>"
            for v in doc.validations
        )
        or '<p class="precision">Aucun destinataire.</p>'
    )
    pied = (
        f'<p class="precision">{escape(doc.validation_du_point)}</p>'
        if doc.validation_du_point
        else ""
    )
    return f'<div class="cartouche"><h3>Validations</h3>{lignes}{pied}</div>'


def _vignette_etat(a: AffaireOuverte) -> str:
    fond, encre = TEINTES_ETAT.get(a.statut, ("#f3f4f7", "#5a6070"))
    return (
        f'<span class="cap" style="background:{fond};color:{encre}">'
        f"{escape(a.libelle_statut)}</span>"
    )


def _sous_titre(a: AffaireOuverte) -> str:
    """L'état de suivi et « qui la lit », sous le titre — comme la page Affaires."""
    lecture = f'<span class="cap lecture">{escape(a.lecture)}</span>' if a.lecture else ""
    fusions = (
        f'<span class="marque">Fusionne : {escape(" · ".join(a.fusionnees))}</span>'
        if a.fusionnees
        else ""
    )
    return f'<span class="caps">{_vignette_etat(a)}{lecture}{fusions}</span>'


def _compte_rendu(doc: DocumentPoint, ticket_id: int, c: CompteRenduAffaire) -> str:
    marques = []
    if c.conseil_seul:
        marques.append(f'<span class="marque">({LIBELLE_CS_ET_PRESENTS})</span>')
    if ticket_id in doc.marques:
        marques.append(f'<span class="marque revision">{escape(doc.marques[ticket_id])}</span>')
    if ticket_id in doc.etats:
        marques.append(f'<span class="cap decide">{escape(doc.etats[ticket_id])}</span>')
    return (
        f'<div class="crb"><span class="lbl">CR</span>{escape(texte_brut(c.contenu))}'
        + (f" {' '.join(marques)}" if marques else "")
        + "</div>"
    )


def html_compte_rendu(doc: DocumentPoint, *, site_nom: str, logo_png: bytes | None) -> str:
    """PURE. Le document HTML autonome du point (maquette B)."""
    cr, point = doc.cr, doc.cr.point
    crs = {a.id: c for a, c in cr.abordees}
    abordees = [a for a in doc.releve.affaires if a.id in crs]
    if doc.projet:
        mention = f"Projet — révision {doc.revision}" if doc.revision else "Projet"
    else:
        mention = f"Validé le {date_courte(point.valide_le)}" if point.valide_le else ""
    fin = f" → {point.fin:%H:%M}" if point.fin else ""
    nb = len(cr.abordees) + len(cr.non_traitees)
    non_traitees = (
        f'<h2>Non abordées · {len(cr.non_traitees)}</h2><p class="nt">'
        + " · ".join(f"{escape(a.numero)} {escape(a.titre)}" for a in cr.non_traitees)
        + "</p>"
        if cr.non_traitees
        else ""
    )
    return (
        f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>{TITRE}</title>"
        f"<style>{_CSS}</style></head><body>"
        f"{entete_rapport(logo_png, site_nom, mention)}"
        f"<h1>{TITRE} du {escape(date_longue(point.debut))}</h1>"
        '<div class="cote"><div class="point"><h3>Le point</h3>'
        f"<p>{escape(datetime_longue(point.debut))}{fin} · {escape(ou_du_point(point))}</p>"
        f"{_presents(cr)}</div>{_cartouche(doc)}</div>"
        f"{tete_html(doc.releve, 'affaires à traiter')}"
        f"<h2>Les affaires · {nb} — abordées {len(cr.abordees)}, "
        f"non abordées {len(cr.non_traitees)}</h2>"
        + tableau_html(
            abordees,
            sous_titre=_sous_titre,
            complement=lambda a: _compte_rendu(doc, a.id, crs[a.id]),
            entete="Affaire et compte rendu",
            vide="Aucune affaire abordée.",
        )
        + f"{non_traitees}</body></html>"
    )


def generer_pdf(doc: DocumentPoint, *, site_nom: str, logo_png: bytes | None) -> bytes:
    return html_to_pdf(html_compte_rendu(doc, site_nom=site_nom, logo_png=logo_png))
