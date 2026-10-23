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
from app.utils.pdf_theme import logo_html, qr_data_uri
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
