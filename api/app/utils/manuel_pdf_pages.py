"""Les deux pages que le manuel PDF ajoute au manuel servi : la garde et les mentions.

Extraites de `manuel_pdf` (08/10/2026) quand le sous-titre réglé dans
Admin › Présentation › Connexion et pied de page est entré dans la garde : le module passait les 500 lignes. Elles
ne lisent rien — ni base, ni réseau — et se composent à partir de ce qu'on leur
passe ; `manuel_pdf.identite_du_manuel` dit d'où cela vient.
"""

from __future__ import annotations

from datetime import date
from html import escape

from app.utils.dates_fr import date_longue
from app.utils.pdf_theme import FONT_SERIF, logo_html, qr_data_uri
from app.utils.plateforme import LICENCE_NOM, LICENCE_SPDX, NOM_PLATEFORME


def garde(
    site_nom: str,
    site_url: str,
    edite_le: date,
    logo_png: bytes | None,
    sous_titre: str,
) -> str:
    qr = qr_data_uri(site_url)
    bloc_qr = (
        f'<div class="garde-qr"><img src="{qr}" alt="">'
        f"<p>Ouvrez le site en photographiant ce code<br>"
        f"<strong>{escape(site_url)}</strong></p></div>"
        if qr
        else f'<div class="garde-qr"><p><strong>{escape(site_url)}</strong></p></div>'
    )
    return f"""
<section class="garde">
  <div class="garde-logo"><div class="garde-medaillon">{logo_html(logo_png, 64)}</div></div>
  <p class="garde-surtitre">{escape(site_nom)}</p>
  <h1 class="garde-titre">Manuel<br>utilisateur</h1>
  <p class="garde-sous">{f"{escape(sous_titre)}<br>" if sous_titre else ""}
     Trouver vite ce dont vous avez besoin.</p>
  <div class="garde-filet"></div>
  {bloc_qr}
  <p class="garde-pied">Édition du {date_longue(edite_le)}</p>
</section>
"""


def mentions(site_nom: str, site_url: str, edite_le: date) -> str:
    """Les mentions du feuillet — ce qu'un document imprimé doit porter.

    ⚠️ La LICENCE y figure (04/09/2026, à la demande). Le corps du manuel la
    mentionne déjà, mais un feuillet imprimé se lit par sa fin quand on cherche
    « qui a fait ça, et sous quelles conditions » : c'est là qu'on regarde, pas
    au milieu d'une section « À quoi sert ce site ? ».
    """
    return f"""
<section class="mentions">
  <h2>À propos de ce document</h2>
  <dl>
    <dt>Document</dt>
    <dd>Manuel utilisateur de {escape(site_nom)}.</dd>
    <dt>Édité le</dt><dd>{date_longue(edite_le)}</dd>
    <dt>Éditeur</dt>
    <dd>Le conseil syndical de la copropriété. Mentions légales complètes et
        politique de confidentialité sur {escape(site_url)}/mentions-legales.</dd>
    <dt>Diffusion</dt>
    <dd>Document à usage interne, destiné aux résidents. Il décrit un site dont
        l'accès est réservé aux personnes inscrites.</dd>
    <dt>Licence</dt>
    <dd>Ce site est servi par {NOM_PLATEFORME}, un logiciel libre distribué sous la
        {LICENCE_NOM} (<strong>{LICENCE_SPDX}</strong>) : chacun peut l'utiliser,
        le modifier et le redistribuer, y compris à titre commercial, à condition
        de publier ses modifications sous la même licence. Le présent document et les
        contenus publiés dans l'application restent la propriété de leurs
        auteurs.</dd>
    <dt>Hébergement</dt>
    <dd>Cette instance est <strong>auto-hébergée</strong> : les données restent sur
        une machine de la copropriété, elles ne sont ni vendues ni confiées à un
        prestataire.</dd>
  </dl>
</section>
"""


def css_des_pages_ajoutees() -> str:
    """Le style des pages que le PDF ajoute au manuel : garde, sommaire, mentions.

    Il vit à côté de leur balisage (sorti de `manuel_pdf_css` le 23/10/2026, qui
    passait les 500 lignes) : une classe renommée ici se renomme dans la même vue.
    """
    return f"""
/* ── Page de garde ────────────────────────────────────────────────────── */
.garde {{
  page: garde;
  page-break-after: always;
  height: 297mm;
  position: relative;
  background: var(--navy);
  color: #fff;
  text-align: center;
}}
/*  Le bandeau doré : la seule ligne de couleur chaude de la charte, employée
    ici comme sur les affiches de hall — un rappel, pas une décoration. */
.garde::after {{
  content: "";
  position: absolute; left: 0; right: 0; bottom: 0;
  height: 14mm;
  background: var(--gold);
}}
/*  Un liseré doré en haut répond à celui du pied : la page est tenue par ses
    deux bords, pas posée sur un fond. */
.garde::before {{
  content: "";
  position: absolute; left: 0; right: 0; top: 0;
  height: 4mm;
  background: var(--gold);
}}
.garde-logo {{ padding-top: 34mm; }}
/*  Médaillon : le logo est blanc sur bleu, il se perdrait sans un fond clair. */
.garde-medaillon {{
  width: 30mm; height: 30mm;
  margin: 0 auto;
  border-radius: 50%;
  background: rgba(255, 255, 255, .08);
  border: 1px solid rgba(255, 255, 255, .18);
  display: flex;
  align-items: center;
  justify-content: center;
}}
.garde-surtitre {{
  font-size: 9.5pt;
  letter-spacing: .22em;
  text-transform: uppercase;
  color: var(--gold);
  margin-top: 10mm;
}}
.garde-titre {{
  font-family: {FONT_SERIF};
  font-size: 34pt;
  line-height: 1.1;
  margin: 4mm 22mm 0;
  letter-spacing: .01em;
}}
.garde-sous {{
  font-size: 12pt;
  color: #C7D2E0;
  margin: 6mm 28mm 0;
  line-height: 1.6;
}}
.garde-filet {{
  width: 26mm; height: 2px;
  background: var(--gold);
  margin: 10mm auto;
}}
.garde-qr {{ margin-top: 12mm; }}
.garde-qr img {{
  width: 34mm; height: 34mm;
  background: #fff;
  padding: 3mm;
  border-radius: 3mm;
}}
.garde-qr p {{
  font-size: 9.5pt;
  color: #C7D2E0;
  margin-top: 4mm;
}}
.garde-qr strong {{ color: #fff; }}
.garde-pied {{
  position: absolute;
  left: 0; right: 0; bottom: 20mm;
  font-size: 9pt;
  color: #A8B6C8;
}}

/* ── Sommaire ─────────────────────────────────────────────────────────── */
.sommaire {{ page-break-after: always; }}
.sommaire h2 {{ margin-bottom: 6mm; }}
.sommaire ol {{ list-style: none; padding: 0; counter-reset: som; }}
.sommaire li {{ padding: 1.2mm 0; }}
.sommaire a {{
  display: block;
  color: var(--ink);
  text-decoration: none;
}}
/*  🔴 Le numéro de page est RÉSOLU À LA MISE EN PAGE (`target-counter`), jamais
    écrit : on ne sait pas encore combien de pages fera le document, et un
    numéro saisi serait faux dès la première phrase ajoutée au manuel. */
.sommaire a::after {{
  content: target-counter(attr(href), page);
  float: right;
  color: var(--gold);
  font-weight: 700;
}}
/*  Les points de conduite : c'est ce qui rend une ligne de sommaire lisible
    quand le titre est court et le numéro loin. */
.sommaire a::before {{
  content: "";
  float: right;
  width: 0;
}}
.sommaire .som-n2 {{
  counter-increment: som;
  border-bottom: 1px solid var(--border);
  margin-top: 3mm;
}}
.sommaire .som-n2 a {{
  font-family: {FONT_SERIF};
  font-size: 12pt;
  color: var(--navy);
}}
.sommaire .som-n2 a::before {{
  content: counter(som) ". ";
  float: none;
  color: var(--gold);
  font-weight: 700;
}}
/*  Les quinze écrans sont des sous-entrées : décalées, plus discrètes, mais
    présentes — c'est par elles qu'on cherche « Accès & badges ». */
.sommaire .som-n3 {{
  padding: .8mm 0 .8mm 7mm;
  font-size: 9.5pt;
  border-bottom: 1px dotted var(--border);
}}
.sommaire .som-n3 a {{ color: var(--muted); }}

/* ── Mentions ─────────────────────────────────────────────────────────── */
.mentions {{
  page-break-before: always;
  border-top: 3px solid var(--gold);
  padding-top: 6mm;
  font-size: 9pt;
  color: var(--muted);
}}
.mentions h2 {{ font-size: 13pt; }}
.mentions dt {{ font-weight: 700; color: var(--ink); margin-top: 3mm; }}
.mentions dd {{ margin: 0 0 1mm; }}
.mentions .avert {{
  margin-top: 6mm;
  padding: 3mm 4mm;
  background: var(--bg);
  border-left: 3px solid var(--gold);
}}
"""
