"""Génération dynamique de la fiche d'accueil (fiche arrivant) en HTML."""

from __future__ import annotations

from collections import defaultdict
from html import escape
from typing import Optional

from app.seed.consignes_arrivant import ACCUEIL_GABARIT
from app.utils.consignes_arrivant import texte_en_html
from app.utils.dates_fr import date_longue
from app.utils.fiche_arrivant_css import CSS
from app.utils.liens import adresse_lisible
from app.utils.pdf_theme import (
    icone_svg,
    image_data_uri as _photo_data_uri,
    logo_html,
    qr_data_uri as _qr_data_uri,
)
from app.utils.perimetres import perimetre_du_batiment, perimetre_label_un
from app.utils.etages import etage_label


# ── Helpers ──────────────────────────────────────────────────────────────────


def _initials(prenom: str, nom: str) -> str:
    p = prenom.strip()[0].upper() if prenom and prenom.strip() else "?"
    n = nom.strip()[0].upper() if nom and nom.strip() else "?"
    return p + n


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


# ── Builders ─────────────────────────────────────────────────────────────────


def _build_cs_card(m: dict) -> str:
    """Carte d'un membre CS."""
    is_president = m.get("est_president", False)
    is_gestionnaire = m.get("est_gestionnaire_site", False)
    photo_uri = _photo_data_uri(m.get("photo_url"))

    card_class = "contact-card"
    if is_president:
        card_class += " president"
    elif is_gestionnaire:
        card_class += '" style="border-left-color:var(--navy);background:#F5F7FA;'

    initials = _initials(m.get("prenom", ""), m.get("nom", ""))
    avatar_color = "green" if is_president else ("gold" if is_gestionnaire else "navy")

    if photo_uri and is_gestionnaire:
        avatar_html = f'<img class="contact-photo" src="{photo_uri}" alt="{initials}">'
    else:
        avatar_html = f'<div class="contact-avatar {avatar_color}">{initials}</div>'

    role_html = ""
    if is_gestionnaire:
        role_html = '<div class="contact-role">🏢 Gestionnaire du site</div>'
    elif is_president:
        role_html = '<div class="contact-role">Président</div>'

    #  🔴 `is not None`, jamais un test de vérité : `0` est le rez-de-chaussée,
    #  et il était faux en Python. Un conseiller du RDC n'avait donc AUCUN
    #  étage sur cette fiche — pas un étage faux, un étage absent.
    etage = m.get("etage")
    etage_html = f"Étage {etage_label(etage)}" if etage is not None else ""

    return (
        f'<div class="{card_class}">'
        f"  {avatar_html}"
        f'  <div class="contact-body">'
        f"    {role_html}"
        f'    <div class="contact-name">{escape(m["genre"])} {escape(m["prenom"])} {escape(m["nom"].upper())}</div>'
        f'    <div class="contact-info">{escape(etage_html)}</div>'
        f"  </div>"
        f"</div>"
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
    """Section Conseil Syndical groupée par bâtiment."""
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

    html = '<div class="annuaire-section">\n'
    html += "  <h3>📇 Conseil Syndical</h3>\n"
    if ag_annee:
        html += (
            f'  <p class="muted" style="margin-bottom:8px;font-size:11.5px">Voté en AG {ag_annee}'
        )
        if ag_date:
            from datetime import date as dt_date

            try:
                html += f" — {date_longue(dt_date.fromisoformat(ag_date))}"
            except Exception:
                html += f" — {ag_date}"
        html += "</p>\n"

    for _, entete, bat_membres in sorted(
        (_batiment_entete(bid, ms) for bid, ms in by_bat.items()),
        key=lambda t: t[0],
    ):
        html += '  <div class="bat-section">\n'
        html += f'    <div class="bat-label">{entete}</div>\n'
        html += '    <div class="bat-grid">\n'
        for m in bat_membres:
            html += f"      {_build_cs_card(m)}\n"
        html += "    </div>\n"
        html += "  </div>\n"

    html += "</div>\n"
    return html


def _build_syndic_section(syndic_data: dict) -> str:
    """Section Syndic."""
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

    html = f"<h3>🏛 Syndic — {escape(nom)}</h3>\n"
    html += '<div class="syndic-header" style="display:flex;align-items:center;gap:10px;">\n'
    html += '  <div style="flex:1;">\n'
    html += '    <div style="display:flex;align-items:baseline;gap:6px;flex-wrap:wrap;">\n'
    html += f'      <span class="syndic-name">{escape(nom)}</span>\n'
    html += f'      <span class="syndic-detail">📍 {escape(adresse)}</span>\n'
    html += "    </div>\n"
    html += "  </div>\n"
    html += f"  {qr_html}\n"
    html += "</div>\n"

    if membres:
        html += '<div class="syndic-contacts">\n'
        for m in membres:
            is_principal = m.get("est_principal", False)
            card_class = "contact-card principal" if is_principal else "contact-card syndic"
            avatar_color = "gold" if is_principal else "purple"
            initials = _initials(m.get("prenom", ""), m.get("nom", ""))

            role_label = (
                "★ " + (m.get("fonction") or "Gestionnaire")
                if is_principal
                else (m.get("fonction") or "")
            )

            info_parts = []
            if m.get("email"):
                info_parts.append(f"✉ {escape(m['email'])}")
            if m.get("telephone"):
                for tel in m["telephone"].split(","):
                    tel = tel.strip()
                    if tel:
                        info_parts.append(f"☎ {escape(tel)}")
            info_html = "<br>".join(info_parts)

            html += f'  <div class="{card_class}">\n'
            html += f'    <div class="contact-avatar {avatar_color}">{initials}</div>\n'
            html += f'    <div class="contact-body">\n'
            if role_label:
                html += f'      <div class="contact-role">{escape(role_label)}</div>\n'
            html += f'      <div class="contact-name">{escape(m.get("genre", ""))} {escape(m.get("prenom", ""))} {escape(m.get("nom", "").upper())}</div>\n'
            html += f'      <div class="contact-info">{info_html}</div>\n'
            html += f"    </div>\n"
            html += f"  </div>\n"
        html += "</div>\n"

    return html


def _build_consignes_section(adresse: str, consignes: list[tuple[str, str]]) -> str:
    html = "<h3>📋 Consignes de la copropriété</h3>\n"
    html += '<div class="consignes-intro">\n'
    html += (
        "  <p>À la demande du Conseil syndical, il est rappelé à Mesdames et Messieurs "
        "les résidents que les dispositions du règlement de copropriété relatives aux "
        "parties communes et à la vie collective doivent être respectées par tous et "
        "notamment ce qui suit.</p>\n"
    )
    html += "</div>\n"

    for titre, contenu in consignes:
        html += '<div class="regle">\n'
        html += f'  <div class="regle-titre">{titre}</div>\n'
        html += f'  <div class="regle-contenu">{contenu}</div>\n'
        html += "</div>\n"

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
) -> str:
    """Génère le HTML complet de la fiche arrivant à partir des données annuaire.

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

    # ── Dual CTA ──
    wa_cta = ""
    if whatsapp_url and wa_qr:
        wa_cta = (
            '<div class="whatsapp-cta">\n'
            '  <div class="wa-text">\n'
            f'    <div class="wa-title">{wa_svg}WhatsApp de la Copro</div>\n'
            '    <div class="wa-desc">Infos résidence en temps réel.<br>Demandez le lien au CS de votre bâtiment.</div>\n'
            "  </div>\n"
            f'  <img class="qr-code" src="{wa_qr}" alt="QR WhatsApp">\n'
            "</div>\n"
        )
    else:
        wa_cta = (
            '<div class="whatsapp-cta">\n'
            '  <div class="wa-text">\n'
            f'    <div class="wa-title">{wa_svg}WhatsApp de la Copro</div>\n'
            '    <div class="wa-desc">Infos résidence en temps réel.<br>Demandez le lien au CS de votre bâtiment.</div>\n'
            "  </div>\n"
            "</div>\n"
        )

    return f"""\
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bienvenue — {nom}</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="page">
  <div class="header">
    {logo_html(logo_png, sombre=True)}
    <div class="header-text">
      <div class="header-title">Bienvenue dans votre résidence !</div>
      <div class="header-sub">Consignes de la copropriété</div>
    </div>
  </div>
  <div class="accent-bar"></div>
  <div class="content">
    <h2>Bonjour et bienvenue&nbsp;!</h2>
    <p class="accueil">{accueil_html}</p>
    <div class="dual-cta">
      <div class="cta-banner">
        <div class="cta-banner-text">
          <div class="label">Votre espace en ligne</div>
          <div class="url">{globe_svg}{escape(adresse)}</div>
          <div class="hint">Inscription → Validation par le CS → C'est prêt !</div>
        </div>
        <img class="qr-code" src="{site_qr}" alt="QR {escape(adresse)}">
      </div>
      {wa_cta}
    </div>
    <hr class="sep">
    {_build_cs_section(cs_data)}
    <hr class="sep">
    {_build_syndic_section(syndic_data)}
    <hr class="sep">
    {_build_consignes_section(adresse, consignes)}
  </div>
  <div class="footer">
    <p>© {annee} • {nom} • <strong>{escape(adresse)}</strong></p>
  </div>
</div>
</body>
</html>"""
