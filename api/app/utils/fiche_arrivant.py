"""Génération dynamique de la fiche d'accueil (fiche arrivant) en HTML.

Gros caractères depuis #2776 : la mise en page et ses tailles sont dans
`fiche_arrivant_css.py` ; ici, la structure du document et ses données.
"""

from __future__ import annotations

import re
from collections import defaultdict
from html import escape
from typing import Optional

from app.seed.consignes_arrivant import ACCUEIL_GABARIT
from app.utils.consignes_arrivant import texte_en_html
from app.utils.dates_fr import date_longue
from app.utils.fiche_arrivant_css import CSS
from app.utils.liens import adresse_lisible
from app.utils.palettes import recolorer
from app.utils.pdf_theme import (
    icone_svg,
    image_data_uri as _photo_data_uri,
    logo_html,
    police_lisible_css,
    qr_data_uri as _qr_data_uri,
)
from app.utils.perimetres import perimetre_du_batiment, perimetre_label_un
from app.utils.etages import etage_label


# ── Icônes ───────────────────────────────────────────────────────────────────
#
#  Le globe et le logo WhatsApp étaient dessinés ICI, en dur — le second étant
#  précisément celui qu'on avait consolidé côté site le 08/08/2026 parce qu'il
#  existait en six exemplaires et deux tracés. La consolidation s'était arrêtée à
#  la frontière front/api. Les deux viennent maintenant du catalogue commun, et
#  le tracé WhatsApp qui subsistait ici (il différait de celui du site de deux
#  caractères) a disparu avec eux.
#
#  Appel à l'usage et non à l'import : si le catalogue était momentanément
#  illisible, une constante de module figerait le repli (chaîne vide) pour toute
#  la vie du process — même raisonnement que le cache de `utils/perimetres.py`,
#  qui refuse de mémoriser un arbre vide.


# ── CSS ── la feuille de style vit dans `fiche_arrivant_css.py` (plafond de 500 l.)


# ── Consignes ── elles vivent en base, éditables par le CS (#1727) : le texte
#    arrive ÉCHAPPÉ et rendu par `utils/consignes_arrivant`, jamais écrit ici.

#: Le titre d'une rubrique tel que le conseil l'écrit : « 📦 1. Emménagement ».
#: Le pictogramme et le numéro se rendent à part (#2776), sans rien changer à la
#: saisie ; un titre écrit sans eux s'affiche tel quel. Le titre arrive ÉCHAPPÉ :
#: `&` ouvre une entité, jamais un pictogramme.
_TITRE = re.compile(r"(?P<pic>[^\w\s&;]{1,4})\s+(?:(?P<num>\d{1,3})[.)]\s+)?(?P<texte>\S.*)", re.S)
_TITRE_NUMERO = re.compile(r"(?P<num>\d{1,3})[.)]\s+(?P<texte>\S.*)", re.S)


def decouper_titre(titre: str) -> tuple[str, str, str]:
    """(pictogramme, numéro, texte) d'un titre de rubrique déjà échappé. PURE.

    Un pictogramme est un emoji ou un symbole hors du latin de base (au-delà de
    U+2000) : un tiret ou une astérisque en tête restent dans le texte.
    """
    m = _TITRE.fullmatch(titre.strip())
    if m and all(ord(c) > 0x2000 for c in m["pic"]):
        return m["pic"], m["num"] or "", m["texte"]
    m = _TITRE_NUMERO.fullmatch(titre.strip())
    if m:
        return "", m["num"], m["texte"]
    return "", "", titre


# ── Builders ─────────────────────────────────────────────────────────────────


def _nom_complet(m: dict) -> str:
    return f"{escape(m.get('genre', ''))} {escape(m.get('prenom', ''))} {escape(m.get('nom', '').upper())}".strip()


def _build_cs_membre(m: dict) -> str:
    """Un membre du conseil : nom, rôle et étage — sur une ligne lisible."""
    is_president = m.get("est_president", False)
    is_gestionnaire = m.get("est_gestionnaire_site", False)

    #  La photo du gestionnaire du site, comme avant #2776 ; les pastilles
    #  d'initiales des autres membres sont parties : elles ne disaient rien que
    #  le nom ne dise, et prenaient la largeur du corps agrandi.
    photo_uri = _photo_data_uri(m.get("photo_url")) if is_gestionnaire else None
    photo_html = f'<img class="membre-photo" src="{photo_uri}" alt="">' if photo_uri else ""

    role = "Gestionnaire du site" if is_gestionnaire else ("Président" if is_president else "")

    #  🔴 `is not None`, jamais un test de vérité : `0` est le rez-de-chaussée,
    #  et il était faux en Python. Un conseiller du RDC n'avait donc AUCUN
    #  étage sur cette fiche — pas un étage faux, un étage absent.
    etage = m.get("etage")
    details = [f"<b>{role}</b>"] if role else []
    if etage is not None:
        details.append(escape(f"Étage {etage_label(etage)}"))

    return (
        f'<div class="membre">{photo_html}<div>'
        f'<div class="membre-nom">{_nom_complet(m)}</div>'
        f'<div class="membre-detail">{" · ".join(details)}</div>'
        "</div></div>"
    )


def _batiment_entete(batiment_id: Optional[int], membres: list) -> tuple[tuple, str, list]:
    """Clé de tri, en-tête HTML et membres d'un bâtiment.

    L'en-tête vient de l'**arbre des périmètres**, jamais d'un `f"Bât. {n}"`
    écrit ici : une copropriété qui renomme un bâtiment depuis `/admin/patrimoine`
    doit le voir renommé sur le document imprimé, et c'est précisément ce qui ne
    marchait pas — ce document ne passant par aucun écran, la divergence y était
    invisible. Le seed nomme d'ailleurs les nœuds « Bât. {id} » quand la fiche
    écrivait « Bât. {numero} » : les deux ne disaient déjà pas la même chose.

    L'ordre est celui de l'administration (`Noeud.ordre`), pas l'ordre
    alphabétique d'un libellé : « Bât. 10 » se rangeait avant « Bât. 2 ».

    Trois replis, du plus au moins renseigné, aucun qui puisse lever :
    l'arbre connaît le bâtiment → son libellé et son icône ; l'arbre est vide ou
    ne le connaît pas → `perimetre_label_un` rend la convention `bat:{id}` sans
    qu'on la réécrive ici ; aucun identifiant → le nom transmis, ou « ? ».
    """
    noeud = perimetre_du_batiment(batiment_id)
    if noeud is not None:
        libelle, icone, rang = noeud.libelle, noeud.icone, (0, noeud.ordre, noeud.code)
    elif batiment_id is not None:
        libelle, icone, rang = perimetre_label_un(f"bat:{batiment_id}"), None, (1, batiment_id, "")
    else:
        #  Aucun bâtiment rattaché : le membre reste affiché, sous un en-tête
        #  neutre et en dernier. Le faire disparaître serait pire — mais l'en-tête
        #  doit rester lisible : ce document est imprimé et remis à un arrivant,
        #  qui n'a aucun moyen d'interpréter un « ? » ni un « Bât. ? » (ce que
        #  produisait la version précédente).
        libelle, icone, rang = "Bâtiment non précisé", None, (2, 0, "")

    #  Icône hors du texte échappé : c'est du balisage produit par le catalogue,
    #  pas une donnée. Le libellé, lui, vient de la base — donc échappé.
    return rang, f"{icone_svg(icone, taille=11)}{escape(libelle)}", membres


def _build_cs_section(cs_data: dict) -> str:
    """Section Conseil Syndical groupée par bâtiment, un bâtiment par colonne."""
    membres = cs_data.get("membres", [])
    if not membres:
        return ""

    ag_annee = cs_data.get("ag_annee")
    ag_date = cs_data.get("ag_date", "")

    #  Groupé par identifiant de bâtiment, et non par son nom : le nom vient de
    #  l'arbre des périmètres, qui est seul à savoir comment l'administration a
    #  choisi de l'appeler. Grouper sur un libellé reviendrait à fusionner deux
    #  bâtiments qu'une copropriété aurait nommés pareil.
    by_bat: dict[Optional[int], list] = defaultdict(list)
    for m in membres:
        by_bat[m.get("batiment_id")].append(m)

    vote = ""
    if ag_annee:
        vote = f"Voté en AG {ag_annee}"
        if ag_date:
            from datetime import date as dt_date

            try:
                vote += f" — {date_longue(dt_date.fromisoformat(ag_date))}"
            except Exception:
                vote += f" — {ag_date}"

    #  Quatre colonnes au plus : au-delà, les bâtiments passent à la ligne.
    colonnes = min(len(by_bat), 4)
    html = '<section class="annuaire-section">\n'
    html += f'  <div class="sec-titre"><h3>📇 Conseil syndical</h3><span class="muted">{escape(vote)}</span></div>\n'
    html += f'  <div class="bats" style="grid-template-columns: repeat({colonnes}, 1fr)">\n'
    for _, entete, bat_membres in sorted(
        (_batiment_entete(bid, ms) for bid, ms in by_bat.items()),
        key=lambda t: t[0],
    ):
        html += '    <div class="bat">\n'
        html += f'      <div class="bat-label">{entete}</div>\n'
        for m in bat_membres:
            html += f"      {_build_cs_membre(m)}\n"
        html += "    </div>\n"
    html += "  </div>\n</section>\n"
    return html


def _build_syndic_section(syndic_data: dict) -> str:
    """Section Syndic : son identité, ses contacts côte à côte, le QR de son extranet."""
    #  Le nom vient de `nom_du_syndic` en amont (#535) : il n'est plus lu
    #  dans `SyndicInfo`, qui pouvait diverger du contrat désigné.
    nom = syndic_data.get("nom_syndic", "")
    adresse = syndic_data.get("adresse", "")
    site_web = syndic_data.get("site_web")
    membres = syndic_data.get("membres", [])

    qr_html = ""
    if site_web:
        qr_src = _qr_data_uri(site_web)
        if qr_src:
            qr_html = f'<img class="qr-code" src="{qr_src}" alt="QR Extranet">'

    contacts = ""
    for m in membres:
        fonction = m.get("fonction") or ("Gestionnaire" if m.get("est_principal") else "")
        if m.get("est_principal"):
            fonction = "★ " + fonction
        lignes = []
        if m.get("email"):
            lignes.append(f"✉ {escape(m['email'])}")
        for tel in (m.get("telephone") or "").split(","):
            if tel.strip():
                lignes.append(f"☎ {escape(tel.strip())}")
        contacts += (
            '<div class="syndic-contact">'
            + (f'<div class="syndic-fonction">{escape(fonction)}</div>' if fonction else "")
            + f'<div class="syndic-personne">{_nom_complet(m)}</div>'
            + "<br>".join(lignes)
            + "</div>"
        )

    #  Trois contacts par ligne au plus, comme avant #2776.
    colonnes = max(1, min(len(membres), 3))
    adresse_html = f'<div class="syndic-adresse">📍 {escape(adresse)}</div>' if adresse else ""
    return (
        '<section>\n  <div class="sec-titre"><h3>🏛 Syndic</h3></div>\n'
        '  <div class="syndic">'
        f'<div><div class="syndic-nom">{escape(nom)}</div>{adresse_html}</div>'
        f'<div class="syndic-contacts" style="grid-template-columns: repeat({colonnes}, 1fr)">{contacts}</div>'
        f"{qr_html}</div>\n</section>\n"
    )


def _build_regle(titre: str, contenu: str) -> str:
    """Une rubrique : pictogramme, titre, et une puce par ligne saisie."""
    pic, num, texte = decouper_titre(titre)
    #  « Une ligne par consigne », dit l'aide de saisie : chaque ligne devient une
    #  puce. Le contenu arrive échappé ; un saut de ligne n'y coupe aucune balise.
    puces = "".join(f"<li>{ligne}</li>" for ligne in contenu.split("\n") if ligne.strip())
    numero = f'<span class="regle-numero">{num}.</span>' if num else ""
    pictogramme = f'<div class="regle-pictogramme">{pic}</div>' if pic else ""
    classe = "regle" if pic else "regle sans-pictogramme"
    return (
        f'<div class="{classe}">{pictogramme}<div>'
        f'<div class="regle-titre">{numero}{texte}</div>'
        f'<ul class="regle-contenu">{puces}</ul>'
        "</div></div>\n"
    )


def _build_consignes_section(adresse: str, consignes: list[tuple[str, str]]) -> str:
    html = '<section>\n  <div class="sec-titre"><h3>📋 Consignes de la copropriété</h3></div>\n'
    html += (
        '  <p class="rappel">À la demande du Conseil syndical, il est rappelé à Mesdames et '
        "Messieurs les résidents que les dispositions du règlement de copropriété relatives "
        "aux parties communes et à la vie collective doivent être respectées par tous et "
        "notamment ce qui suit.</p>\n"
    )
    html += "".join(_build_regle(titre, contenu) for titre, contenu in consignes)
    html += "</section>\n"
    html += f'<p class="consigne-footer-note">Ce document est un résumé. Le règlement complet est disponible sur <strong>{escape(adresse)}</strong> → Résidence.</p>\n'
    return html


# ── Public API ───────────────────────────────────────────────────────────────


def generer_fiche_arrivant(
    *,
    cs_data: dict,
    syndic_data: dict,
    site_nom: str,
    site_url: str,
    logo_png: bytes | None,
    whatsapp_url: str | None = None,
    consignes: list[tuple[str, str]],
    accueil: str | None = None,
    annee: int = 2026,
    palette: str | None = None,
) -> str:
    """Génère le HTML complet de la fiche arrivant à partir des données annuaire.

    Composée aux couleurs de la charte, puis recolorée à la `palette` de la
    copropriété (#2780), comme l'annonce de hall : là où le document se termine,
    jamais chez un appelant.

    `site_nom` et `site_url` sont ceux de la CONFIGURATION, sans défaut (#1725) :
    le paramètre valait `"5hostachy.fr"` par défaut et le seul appelant ne le
    passait pas — la fiche imprimait donc l'adresse de cette résidence quelle que
    soit la configuration, et le nom « Résidence 5 Hostachy » était écrit en dur.
    """
    site_qr = _qr_data_uri(site_url)
    adresse = adresse_lisible(site_url)
    nom = escape(site_nom)
    #  La phrase d'accueil est du TEXTE saisi par le CS : échappée ici, comme les consignes.
    accueil_html = texte_en_html(accueil or ACCUEIL_GABARIT, "", adresse)
    wa_qr = _qr_data_uri(whatsapp_url) if whatsapp_url else ""
    globe_svg = icone_svg("globe")
    wa_svg = icone_svg("whatsapp")

    wa_qr_html = (
        f'<img class="qr-code" src="{wa_qr}" alt="QR WhatsApp">' if whatsapp_url and wa_qr else ""
    )
    wa_cta = (
        '<div class="cta whatsapp">\n'
        '  <div class="cta-texte">\n'
        '    <div class="cta-label">WhatsApp de la Copro</div>\n'
        f'    <div class="cta-titre">{wa_svg}Infos en temps réel</div>\n'
        '    <div class="cta-aide">Demandez le lien au CS de votre bâtiment.</div>\n'
        "  </div>\n"
        f"  {wa_qr_html}\n"
        "</div>\n"
    )

    html = f"""\
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bienvenue — {nom}</title>
<style>
{police_lisible_css()}{CSS}
</style>
</head>
<body>
<div class="page">
  <div class="header">
    {logo_html(logo_png, size=48, sombre=True)}
    <div class="header-text">
      <div class="header-title">Bienvenue dans votre résidence !</div>
      <div class="header-sub">Consignes de la copropriété</div>
    </div>
    <div class="header-site">{escape(adresse)}</div>
  </div>
  <div class="content">
    <div class="intro">
      <div>
        <h2>Bonjour et bienvenue&nbsp;!</h2>
        <p class="accueil">{accueil_html}</p>
      </div>
      <div class="cta">
        <div class="cta-texte">
          <div class="cta-label">Votre espace en ligne</div>
          <div class="cta-titre">{globe_svg}{escape(adresse)}</div>
          <div class="cta-aide">Inscription → Validation par le CS → C'est prêt !</div>
        </div>
        <img class="qr-code" src="{site_qr}" alt="QR {escape(adresse)}">
      </div>
      {wa_cta}
    </div>
    {_build_cs_section(cs_data)}
    {_build_syndic_section(syndic_data)}
    {_build_consignes_section(adresse, consignes)}
  </div>
  <div class="footer">
    <span>© {annee} • {nom} • <strong>{escape(adresse)}</strong></span>
    <span>Bienvenue chez vous</span>
  </div>
</div>
</body>
</html>"""
    return recolorer(html, palette)
