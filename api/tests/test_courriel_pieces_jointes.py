"""Les pièces jointes d'une réponse par courriel, et qui peut écrire au fil (31/10/2026).

Deux demandes du même jour :

- **seuls l'auteur, le conseil et le syndic écrivent au fil** — un tiers est
  refusé par TOUS les chemins, l'ancienne adresse à jeton comprise, et le conseil
  est prévenu ;
- **les pièces jointes entrent dans l'affaire** — documents et images, dix au
  plus, sans les images ni les fichiers de la signature.
"""

from __future__ import annotations

import io
import json
from datetime import datetime
from email.message import EmailMessage

from PIL import Image

from app.models.core import Utilisateur
from app.utils import courriel_pieces_jointes as pj
from app.utils.courriel_boite import traiter
from app.utils.courriel_ingestion import ACCEPTE, REFUSE
from app.utils.photos import parse_photos
from app.utils.stockage import cle_de_url, stockage
from tests.aides_base import compte
from tests.aides_courriel import (  # noqa: F401 — `scene` est une fixture
    _AUTH_OK,
    _entetes_reponse,
    _evolutions,
    _notifs,
    scene,
)
from tests.aides_purge import purger_ligne

_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
_RECU = datetime(2026, 10, 31, 9, 0)


def _png(cote: int) -> bytes:
    sortie = io.BytesIO()
    Image.new("RGB", (cote, cote), (200, 30, 30)).save(sortie, format="PNG")
    return sortie.getvalue()


def _message(texte: str = "Voici le devis.", *, pieces=(), integrees=()) -> EmailMessage:
    """Un message multipart : `pieces` jointes, `integrees` dans le corps HTML."""
    m = EmailMessage()
    m["From"] = "x@exemple.test"
    m["Subject"] = "Re: ticket"
    m.set_content(texte)
    if integrees:
        m.add_alternative(f"<p>{texte}</p>", subtype="html")
        html = m.get_payload()[1]
        for i, octets in enumerate(integrees):
            html.add_related(octets, "image", "png", cid=f"<sig{i}@exemple.test>")
    for nom, maintype, soustype, octets in pieces:
        m.add_attachment(octets, maintype=maintype, subtype=soustype, filename=nom)
    return m


# ── Le tri : ce qui est une pièce ─────────────────────────────────────────────


def test_documents_et_photos_sont_des_pieces():
    tri = pj.trier(
        _message(
            pieces=[
                ("devis.pdf", "application", "pdf", _PDF),
                ("note.txt", "text", "plain", b"bonjour"),
                ("photo.png", "image", "png", _png(800)),
            ]
        )
    )
    assert [p.nom for p in tri.pieces] == ["devis.pdf", "note.txt", "photo.png"]
    assert [p.famille for p in tri.pieces] == ["document", "document", "image"]
    assert tri.ecarts == []


def test_un_tableur_est_une_piece():
    xlsx = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    tri = pj.trier(_message(pieces=[("budget.xlsx", *xlsx.split("/"), b"PK\x03\x04xx")]))
    assert [(p.nom, p.type) for p in tri.pieces] == [("budget.xlsx", xlsx)]


def test_la_signature_ne_compte_pas():
    """Logo intégré au corps, icône jointe, signature électronique : rien n'est
    gardé, et rien n'est signalé — le dire ferait du bruit à chaque message."""
    tri = pj.trier(
        _message(
            integrees=[_png(120), _png(48)],
            pieces=[
                ("logo.png", "image", "png", _png(200)),
                ("smime.p7s", "application", "pkcs7-signature", b"\x30\x82signature"),
                ("carte.vcf", "text", "vcard", b"BEGIN:VCARD\nEND:VCARD\n"),
            ],
        )
    )
    assert tri.pieces == [] and tri.ecarts == []


def test_une_grande_photo_integree_au_corps_reste_une_piece():
    """L'iPhone intègre la photo au corps : c'est la taille qui tranche."""
    tri = pj.trier(_message(integrees=[_png(1200)]))
    assert [p.famille for p in tri.pieces] == ["image"]


def test_un_type_refuse_est_ecarte_et_nomme():
    tri = pj.trier(_message(pieces=[("archive.zip", "application", "zip", b"PK\x03\x04")]))
    assert tri.pieces == []
    assert tri.ecarts == [pj.Ecart("archive.zip", pj.MOTIF_TYPE)]


def test_au_dela_de_dix_les_suivantes_sont_ecartees():
    pieces = [(f"p{i}.txt", "text", "plain", f"texte {i}".encode()) for i in range(12)]
    tri = pj.trier(_message(pieces=pieces))
    assert len(tri.pieces) == pj.MAX_PIECES == 10
    assert [e.nom for e in tri.au_dela] == ["p10.txt", "p11.txt"]


def test_un_meme_fichier_joint_deux_fois_compte_une_fois():
    tri = pj.trier(
        _message(
            pieces=[("a.pdf", "application", "pdf", _PDF), ("b.pdf", "application", "pdf", _PDF)]
        )
    )
    assert [p.nom for p in tri.pieces] == ["a.pdf"]


def test_un_type_indetermine_se_juge_a_son_extension():
    tri = pj.trier(_message(pieces=[("devis.pdf", "application", "octet-stream", _PDF)]))
    assert [(p.famille, p.type) for p in tri.pieces] == [("document", "application/pdf")]


# ── Le versement : ce qui entre dans le fil ───────────────────────────────────


def _repondre(session, ticket, de, message):
    return traiter(
        session,
        _entetes_reponse(ticket.jeton_courriel, de=de),
        message.get_body(("plain",)).get_content(),
        _RECU,
        authentification=_AUTH_OK,
        pieces=pj.trier(message),
    )


def test_les_pieces_du_syndic_entrent_dans_la_suite(scene, disque_jetable):
    session, ticket, syndic, _cs = scene
    message = _message(
        pieces=[("devis.pdf", "application", "pdf", _PDF), ("photo.png", "image", "png", _png(900))]
    )
    assert _repondre(session, ticket, syndic.email, message) == ACCEPTE
    (suite,) = _evolutions(session, ticket)
    urls = parse_photos(suite.fichiers_urls)
    assert len(urls) == 2
    assert urls[0].endswith(".pdf") and urls[1].endswith(".jpg")
    for url in urls:
        assert stockage().chemin(cle_de_url(url)).exists(), url


def test_une_piece_qui_ment_sur_son_type_est_ecartee_et_dite(scene, disque_jetable):
    """La porte du téléversement juge le CONTENU : un exécutable nommé .pdf ne
    passe pas, et la suite le dit — les autres pièces entrent quand même."""
    session, ticket, syndic, _cs = scene
    message = _message(
        pieces=[
            ("faux.pdf", "application", "pdf", b"MZ\x90\x00executable"),
            ("vrai.pdf", "application", "pdf", _PDF),
            ("<script>.zip", "application", "zip", b"PK\x03\x04"),
        ]
    )
    assert _repondre(session, ticket, syndic.email, message) == ACCEPTE
    (suite,) = _evolutions(session, ticket)
    assert len(parse_photos(suite.fichiers_urls)) == 1
    assert "faux.pdf" in suite.contenu
    assert "&lt;script&gt;.zip (type de fichier non accepté)" in suite.contenu
    assert "<script>" not in suite.contenu


def test_un_message_sans_mot_qui_porte_un_devis_entre_au_fil(scene, disque_jetable):
    session, ticket, syndic, _cs = scene
    message = _message("", pieces=[("devis.pdf", "application", "pdf", _PDF)])
    assert _repondre(session, ticket, syndic.email, message) == ACCEPTE
    (suite,) = _evolutions(session, ticket)
    assert pj.PIECES_SEULES in suite.contenu
    assert len(json.loads(suite.fichiers_urls)) == 1


def test_au_dela_de_dix_le_conseil_est_prevenu(scene, disque_jetable):
    session, ticket, syndic, cs = scene
    pieces = [(f"p{i}.txt", "text", "plain", f"texte {i}".encode()) for i in range(11)]
    assert _repondre(session, ticket, syndic.email, _message(pieces=pieces)) == ACCEPTE
    (suite,) = _evolutions(session, ticket)
    assert len(parse_photos(suite.fichiers_urls)) == 10
    assert any("Pièces jointes non reprises" in n.titre for n in _notifs(session, cs))


# ── Qui écrit au fil ──────────────────────────────────────────────────────────


def test_un_TIERS_qui_detient_l_adresse_a_jeton_n_ecrit_rien(scene, disque_jetable):
    """🔴 Le jeton prouve qu'on a reçu l'ADRESSE, pas qu'on est un correspondant
    du dossier : un courriel transféré à un voisin la lui donne. Rien n'est écrit,
    aucun fichier n'est versé, et le conseil est prévenu."""
    session, ticket, _syndic, cs = scene
    tiers = compte(session, prefixe="voisin", prenom="V", nom="O", roles_json="résident")
    try:
        message = _message(pieces=[("devis.pdf", "application", "pdf", _PDF)])
        assert _repondre(session, ticket, tiers.email, message) == REFUSE
        assert _evolutions(session, ticket) == []
        assert not any(disque_jetable.rglob("*.pdf")), "aucun fichier d'un refus ne s'écrit"
        assert _notifs(session, cs), "le conseil syndical doit savoir qu'un message attend"
    finally:
        purger_ligne(session, Utilisateur, tiers.id)
        session.commit()


def test_l_auteur_de_l_affaire_ecrit_toujours_au_fil(scene, disque_jetable):
    session, ticket, _syndic, _cs = scene
    auteur = compte(session, prefixe="auteur", prenom="A", nom="U", roles_json="résident")
    ticket.auteur_id = auteur.id
    session.add(ticket)
    session.commit()
    try:
        assert _repondre(session, ticket, auteur.email, _message("Merci, c'est noté.")) == ACCEPTE
    finally:
        for evol in _evolutions(session, ticket):
            purger_ligne(session, type(evol), evol.id)
        ticket.auteur_id = _cs.id
        session.add(ticket)
        purger_ligne(session, Utilisateur, auteur.id)
        session.commit()
