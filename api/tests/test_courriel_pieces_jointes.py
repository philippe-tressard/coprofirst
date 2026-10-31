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
import pathlib
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
    tri = pj.retenir(
        pj.trier(
            _message(
                integrees=[_png(120), _png(48)],
                pieces=[
                    ("logo.png", "image", "png", _png(200)),
                    ("smime.p7s", "application", "pkcs7-signature", b"\x30\x82signature"),
                    ("carte.vcf", "text", "vcard", b"BEGIN:VCARD\nEND:VCARD\n"),
                ],
            )
        )
    )
    assert tri.pieces == [] and tri.ecarts == []


def test_une_grande_photo_integree_au_corps_reste_une_piece():
    """L'iPhone intègre la photo au corps : c'est la taille qui tranche."""
    tri = pj.retenir(pj.trier(_message(integrees=[_png(1200)])))
    assert [p.famille for p in tri.pieces] == ["image"]


def test_un_type_refuse_est_ecarte_et_nomme():
    tri = pj.trier(_message(pieces=[("archive.zip", "application", "zip", b"PK\x03\x04")]))
    assert tri.pieces == []
    assert tri.ecarts == [pj.Ecart("archive.zip", pj.MOTIF_TYPE)]


def test_au_dela_de_dix_les_suivantes_sont_ecartees():
    pieces = [(f"p{i}.txt", "text", "plain", f"texte {i}".encode()) for i in range(12)]
    tri = pj.retenir(pj.trier(_message(pieces=pieces)))
    assert len(tri.pieces) == pj.MAX_PIECES == 10
    assert [e.nom for e in tri.au_dela] == ["p10.txt", "p11.txt"]


def test_les_logos_ne_prennent_pas_la_place_des_pieces():
    """Le plafond se compte APRÈS l'écart de la signature : il se juge donc à
    `retenir`, qui mesure, et non au tri, qui n'ouvre aucune image (#2396)."""
    logos = [(f"logo{i}.png", "image", "png", _png(40 + i)) for i in range(5)]
    textes = [(f"p{i}.txt", "text", "plain", f"texte {i}".encode()) for i in range(10)]
    tri = pj.retenir(pj.trier(_message(pieces=[*logos, *textes])))
    assert [p.nom for p in tri.pieces] == [f"p{i}.txt" for i in range(10)]
    assert tri.ecarts == []


def test_le_tri_n_ouvre_aucune_image(monkeypatch):
    """🔴 Le tri lit TOUT message relevé, avant de savoir qui écrit (#2396)."""
    ouvertures = _espionner_les_decodeurs(monkeypatch)
    tri = pj.trier(_message(pieces=[("photo.png", "image", "png", _png(900))]))
    assert [p.nom for p in tri.pieces] == ["photo.png"]
    assert ouvertures == [], f"le tri a ouvert une image : {ouvertures}"


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


def _espionner_les_decodeurs(monkeypatch) -> list[str]:
    """Note chaque porte vers un décodeur d'image : Pillow dans CE process, et
    l'enfant qui l'exécute ailleurs (`process_isole`, appelé par `images`)."""
    from PIL import Image as Pil

    from app.utils import images as images_api

    vues: list[str] = []
    ouvrir = Pil.open
    isole = images_api.executer_isole

    def _ouvrir(*a, **k):
        vues.append("Image.open")
        return ouvrir(*a, **k)

    def _isole(module, fonction, *a, **k):
        vues.append(f"{module}.{fonction}")
        return isole(module, fonction, *a, **k)

    monkeypatch.setattr(Pil, "open", _ouvrir)
    monkeypatch.setattr(images_api, "executer_isole", _isole)
    return vues


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


def test_un_TIERS_n_atteint_aucun_decodeur_d_image(scene, disque_jetable, monkeypatch):
    """🔴 #2396 : la relève mesurait les images (signature) AU TRI, pour tout
    message — un expéditeur anonyme atteignait l'analyse d'en-tête de Pillow,
    libtiff ou libheif. Le refus d'un tiers se décide désormais avant toute
    ouverture, dans ce process comme dans un enfant."""
    session, ticket, _syndic, _cs = scene
    tiers = compte(session, prefixe="voisin", prenom="V", nom="O", roles_json="résident")
    try:
        ouvertures = _espionner_les_decodeurs(monkeypatch)
        message = _message(
            integrees=[_png(60)],
            pieces=[("photo.png", "image", "png", _png(900)), ("p.heic", "image", "heic", b"x")],
        )
        assert _repondre(session, ticket, tiers.email, message) == REFUSE
        assert ouvertures == [], f"un tiers a atteint un décodeur : {ouvertures}"
    finally:
        purger_ligne(session, Utilisateur, tiers.id)
        session.commit()


def test_cas_zero_le_syndic_atteint_le_decodeur_hors_du_process(scene, disque_jetable, monkeypatch):
    """Sans ce témoin, l'espion ci-dessus pourrait rester muet parce qu'il ne
    voit rien — et non parce que rien n'est ouvert. Un message autorisé, lui,
    passe par l'enfant, et JAMAIS par Pillow dans ce process."""
    session, ticket, syndic, _cs = scene
    ouvertures = _espionner_les_decodeurs(monkeypatch)
    message = _message(pieces=[("photo.png", "image", "png", _png(900))])
    assert _repondre(session, ticket, syndic.email, message) == ACCEPTE
    assert "app.utils.images_moteur.mesurer" in ouvertures, ouvertures
    assert "app.utils.images_moteur.reencoder" in ouvertures, ouvertures
    assert "Image.open" not in ouvertures, "une image s'est ouverte dans le process de l'API"


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


# ── Tous les formats d'image (#2388) ──────────────────────────────────────────

#: Chaque format d'image accepté, tel que Pillow l'écrit — HEIC et HEIF (#2389) se
#: lisent dans la photo témoin, l'image n'ayant aucun encodeur HEVC. Le SVG est refusé.
FORMATS_IMAGE = (
    ("JPEG", "image/jpeg", "jpg"),
    ("PNG", "image/png", "png"),
    ("WEBP", "image/webp", "webp"),
    ("GIF", "image/gif", "gif"),
    ("AVIF", "image/avif", "avif"),
    ("BMP", "image/bmp", "bmp"),
    ("TIFF", "image/tiff", "tiff"),
    ("HEIF", "image/heic", "heic"),
    ("HEIF", "image/heif", "heif"),
)

#: Une photo HEIC d'iPhone, 640 × 480 — la même que décode `scripts/verifier_heif.py`
#: à la construction de l'image.
_PHOTO_HEIC = pathlib.Path(__file__).parent / "donnees" / "photo.heic"

_SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


def _image(format_: str) -> bytes:
    if format_ == "HEIF":
        return _PHOTO_HEIC.read_bytes()
    sortie = io.BytesIO()
    Image.new("RGB", (640, 480), (10, 120, 200)).save(sortie, format=format_)
    return sortie.getvalue()


def test_la_table_des_formats_est_celle_de_la_famille():
    """Un format ajouté à la famille « image » sans test ici échoue."""
    from app.utils.fichiers import FAMILLES

    assert {t for _f, t, _e in FORMATS_IMAGE} == set(FAMILLES["image"].types)


def test_chaque_format_d_image_se_televerse(disque_jetable):
    """🔴 Par la porte réelle, `/uploads/fichier`. Depuis v1.48.6 (cfe5f93ff, #1072),
    le JPEG réencodé était confronté à l'extension d'ORIGINE : toute image non JPEG
    rendait 400 « le contenu ne correspond pas à un fichier .png ». Trouvé le
    31/10/2026. Toute image repart en JPEG."""
    from app.models.core import RoleUtilisateur
    from tests.aides_http import base_http, client_http

    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.résident)
        for format_, type_, ext in FORMATS_IMAGE:
            r = http.post(
                "/uploads/fichier", files={"file": (f"photo.{ext}", _image(format_), type_)}
            )
            assert r.status_code == 200, (format_, r.text)
            assert r.json()["type"] == "image" and r.json()["url"].endswith(".jpg"), r.json()
        refus = http.post("/uploads/fichier", files={"file": ("x.svg", _SVG, "image/svg+xml")})
        assert refus.status_code == 400, "un SVG porte du script : il reste refusé"


def test_chaque_format_d_image_entre_par_courriel(scene, disque_jetable):
    session, ticket, syndic, _cs = scene
    pieces = [(f"photo.{e}", *t.split("/"), _image(f)) for f, t, e in FORMATS_IMAGE]
    message = _message(pieces=[*pieces, ("dessin.svg", "image", "svg+xml", _SVG)])
    assert _repondre(session, ticket, syndic.email, message) == ACCEPTE
    (suite,) = _evolutions(session, ticket)
    urls = parse_photos(suite.fichiers_urls)
    #  `.heic` et `.heif` portent la même photo témoin : une pièce répétée n'entre
    #  qu'une fois (`trier`) — l'extension `.heif` passe par `/uploads/fichier`.
    distinctes = len({p[3] for p in pieces})
    assert len(urls) == distinctes and all(u.endswith(".jpg") for u in urls), urls
    assert "dessin.svg (type de fichier non accepté)" in suite.contenu
