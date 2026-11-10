"""La signature d'un courriel TRANSFÉRÉ par Mail d'Apple n'est pas une pièce (10/11/2026).

Six images de la signature d'un prestataire sont entrées dans une affaire. Mail
d'Apple ne pose aucun `Content-ID` : il découpe le corps en fragments HTML et
pose chaque image entre deux, en `inline`. Aucune n'était donc lue comme
intégrée au corps, et la règle du bandeau (#2515) ne les voyait pas.
"""

from __future__ import annotations

from email.message import EmailMessage

from app.utils import courriel_pieces_jointes as pj
from tests.aides_courriel import image_png

PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _jointe(octets: bytes) -> EmailMessage:
    m = EmailMessage()
    m["From"], m["Subject"] = "x@exemple.test", "Re: ticket"
    m.set_content("Le plan.")
    m.add_attachment(octets, maintype="image", subtype="png", filename="plan.png")
    return m


def _transfere_par_mail_d_apple(*images, joint=PDF):
    """Le transfert relevé le 10/11/2026 : un `multipart/mixed` où le corps est
    découpé en fragments HTML, chaque image posée entre deux, `inline` et SANS
    `Content-ID` ; le document joint l'est de la même façon."""
    from email.mime.application import MIMEApplication
    from email.mime.image import MIMEImage
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    m = MIMEMultipart("alternative")
    m["From"], m["Subject"] = "x@exemple.test", "Fwd: ticket"
    m.attach(MIMEText("Veuillez trouver ci-joint le devis.", "plain", "utf-8"))
    corps = MIMEMultipart("mixed")
    corps.attach(MIMEText("<p>Veuillez trouver ci-joint le devis.</p>", "html", "utf-8"))
    for i, octets in enumerate(images, start=1):
        image = MIMEImage(octets, "png")
        image.add_header("Content-Disposition", "inline", filename=f"image{i:03}.png")
        corps.attach(image)
        corps.attach(MIMEText("<br>", "html", "utf-8"))
    if joint:
        piece = MIMEApplication(joint, "pdf")
        piece.add_header("Content-Disposition", "inline", filename="devis.pdf")
        corps.attach(piece)
    m.attach(corps)
    return m


def test_la_signature_d_un_transfert_par_mail_d_apple_n_est_pas_une_piece():
    """10/11/2026 : six images de la signature d'un prestataire sont entrées dans
    une affaire — bandeaux de 501 × 146 et 409 × 100 px, quatre pictogrammes de
    367 × 345 px. Sans `Content-ID`, aucune n'était lue comme intégrée au corps.
    Le devis, lui, reste."""
    signature = [image_png(501, 146), image_png(409, 100)] + [
        image_png(367 + i, 345) for i in range(4)
    ]
    tri = pj.retenir(pj.trier(_transfere_par_mail_d_apple(*signature)))
    assert [p.nom for p in tri.pieces] == ["devis.pdf"] and tri.ecarts == []


def test_cas_zero_une_photo_transferee_par_mail_d_apple_reste_une_piece():
    """Mail d'Apple pose AUSSI une vraie photo en `inline` : c'est la taille qui
    tranche, au seuil près."""
    from app.utils.courriel_signature import COTE_MIN_INTEGREE

    photos = [image_png(1600, 1200), image_png(COTE_MIN_INTEGREE, 300)]
    tri = pj.retenir(pj.trier(_transfere_par_mail_d_apple(*photos, joint=None)))
    assert [p.famille for p in tri.pieces] == ["image", "image"]


def test_un_pictogramme_JOINT_au_dessus_du_seuil_du_logo_reste_une_piece():
    """Le seuil d'une image intégrée ne vaut pas pour une image JOINTE : rien ne
    dit qu'elle habille le texte."""
    tri = pj.retenir(pj.trier(_jointe(image_png(367, 345))))
    assert [p.nom for p in tri.pieces] == ["plan.png"]
