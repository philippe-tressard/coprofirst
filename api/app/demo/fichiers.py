"""Les fichiers de la démo : logo, illustration et documents — PRODUITS, jamais reçus.

La démo refuse tout téléversement de visiteur (M10) : ses fichiers à elle sont
fabriqués ici, à chaque chargement, et écrits par le stockage de la copropriété.
Ils sont l'œuvre du projet — aucune image ni aucun texte repris d'ailleurs.

- le logo et l'illustration sont dessinés avec Pillow ;
- les documents passent par LE moteur PDF du projet (`pdf_theme.html_to_pdf`) :
  aucun autre rendu PDF n'existe, et celui-ci ne fait pas exception. Il exige
  WeasyPrint, présent dans l'image ; sur un poste qui ne l'a pas, la commande
  s'arrête en le disant plutôt que de charger une démo sans documents.
"""

from __future__ import annotations

import io
from html import escape

from PIL import Image, ImageDraw
from sqlmodel import Session, select

from app.demo.dates import jour
from app.demo.patrimoine import NOM_RESIDENCE
from app.models.core import Ticket, Utilisateur
from app.models.documents import CategorieDocument, Document
from app.utils.config_site import ecrire_cle
from app.utils.logo import CLE_LOGO, DOSSIER
from app.utils.pdf_theme import html_to_pdf, logo_html, regle_page
from app.utils.stockage import DOSSIER_PRIVE, stockage

_GLYCINE = (124, 92, 196)
_FEUILLE = (88, 150, 92)


def _png(image: Image.Image) -> bytes:
    sortie = io.BytesIO()
    image.save(sortie, format="PNG")
    return sortie.getvalue()


def logo_png() -> bytes:
    """Une grappe de glycine stylisée sur fond clair — 512 px, carré."""
    image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((16, 16, 496, 496), radius=96, fill=(246, 242, 252, 255))
    d.ellipse((210, 70, 300, 130), fill=_FEUILLE)
    for rang, largeur in enumerate((5, 4, 4, 3, 2, 1)):
        y = 130 + rang * 55
        for i in range(largeur):
            x = 256 + (i - (largeur - 1) / 2) * 52
            d.ellipse((x - 26, y - 26, x + 26, y + 26), fill=_GLYCINE)
    return _png(image)


def illustration_ascenseur() -> bytes:
    """Une porte d'ascenseur schématique : l'illustration d'une affaire de la démo."""
    image = Image.new("RGB", (800, 600), (232, 234, 238))
    d = ImageDraw.Draw(image)
    d.rectangle((250, 80, 550, 560), fill=(150, 156, 166))
    d.rectangle((262, 92, 396, 548), fill=(196, 200, 208))
    d.rectangle((404, 92, 538, 548), fill=(196, 200, 208))
    d.rectangle((580, 280, 620, 360), fill=(90, 96, 106))
    d.ellipse((590, 295, 610, 315), fill=(230, 80, 60))
    return _png(image)


def poser_images(session: Session, affaires: list[Ticket]) -> None:
    st = stockage()
    nom_logo = "residence-demo.png"
    st.ecrire(f"{DOSSIER}/{nom_logo}", logo_png())
    ecrire_cle(session, CLE_LOGO, nom_logo)

    cle = "tickets/demo-ascenseur.png"
    st.ecrire(cle, illustration_ascenseur())
    ascenseur = next(t for t in affaires if t.titre.startswith("L'ascenseur"))
    ascenseur.photos_urls = f'["{st.url(cle)}"]'
    session.add(ascenseur)


#: (code de catégorie, titre, fichier, paragraphes) — des textes écrits pour la démo.
_DOCUMENTS = (
    (
        "reglement_copropriete",
        "Règlement de copropriété (extrait)",
        "reglement-copropriete-demo.pdf",
        (
            "Ce règlement est fictif : il illustre la résidence de démonstration.",
            "Article 1 — Les parties communes comprennent les halls, escaliers, "
            "ascenseurs, espaces verts et le parking.",
            "Article 2 — Chaque copropriétaire use librement des parties privatives, "
            "sans nuire aux droits des autres ni à la destination de l'immeuble.",
            "Article 3 — Les encombrants se déposent le premier mardi du mois.",
        ),
    ),
    (
        "pv_ag",
        "Procès-verbal de l'assemblée générale",
        "pv-assemblee-generale-demo.pdf",
        (
            "Procès-verbal fictif, établi pour la résidence de démonstration.",
            "Résolution 1 — Approbation des comptes de l'exercice : adoptée.",
            "Résolution 2 — Contrat d'entretien des espaces verts : renouvelé.",
            "Résolution 3 — Étude du ravalement des façades : mandat donné au conseil "
            "syndical pour recueillir trois devis.",
        ),
    ),
)


def _html(titre: str, paragraphes: tuple[str, ...], logo: bytes) -> str:
    corps = "".join(f"<p>{escape(p)}</p>" for p in paragraphes)
    return (
        f"<html><head><meta charset='utf-8'><style>{regle_page()}"
        "body{font-family:sans-serif;font-size:11pt;line-height:1.5}</style></head><body>"
        f"{logo_html(logo, 48)}<h1>{escape(titre)}</h1>"
        f"<p><em>{escape(NOM_RESIDENCE)}</em></p>{corps}</body></html>"
    )


def rendre_documents() -> list[tuple[str, str, str, bytes]]:
    """Les PDF, rendus AVANT toute écriture : un rendu impossible laisse la base vierge."""
    logo = logo_png()
    return [
        (code, titre, nom, html_to_pdf(_html(titre, paragraphes, logo)))
        for code, titre, nom, paragraphes in _DOCUMENTS
    ]


def poser_documents(
    session: Session, auteur: Utilisateur, rendus: list[tuple[str, str, str, bytes]]
) -> int:
    st = stockage()
    for code, titre, nom, octets in rendus:
        cle = f"{DOSSIER_PRIVE}/{nom}"
        st.ecrire(cle, octets)
        categorie = session.exec(
            select(CategorieDocument).where(CategorieDocument.code == code)
        ).one()
        session.add(
            Document(
                **st.colonnes(cle),
                titre=titre,
                fichier_nom=nom,
                taille_octets=len(octets),
                mime_type="application/pdf",
                categorie_id=categorie.id,
                publie_par_id=auteur.id,
                annee=jour(0).year,
                date_document=jour(-60),
            )
        )
    return len(rendus)
