"""Les pièces jointes d'un fil TRANSFÉRÉ à l'adresse des affaires (#2515, 04/11/2026).

Constat sur une affaire réelle : le fil transféré était versé, mais ses pièces
allaient dans une Suite à part, « Pièces jointes transmises par courriel »,
signée de qui transfère — et c'était le bandeau de signature du syndic. Le PV
que le premier message joignait n'était pas dans le courriel : une réponse cite
le message d'origine sans ses pièces, et rien ne le disait. Transférer ensuite
le bon message aurait été ignoré : son texte était déjà versé.
"""

from __future__ import annotations

from email.message import EmailMessage

from app.utils import courriel_pieces_jointes as pj
from app.utils.courriel_boite import traiter
from app.utils.courriel_ingestion import ACCEPTE
from app.utils.photos import parse_photos
from tests.aides_courriel import (  # noqa: F401 — `monde` et `scene` sont des fixtures
    _AUTH_OK,
    _RELEVE,
    _affaires,
    _entetes_transfert,
    _evolutions,
    _fil,
    image_png,
    monde,
    scene,
)

_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _transferer(session, cs, objet, corps, *, pdf=False, bandeau=False):
    """Transfère `corps`, avec le PV en pièce jointe et/ou un bandeau intégré."""
    m = EmailMessage()
    m.set_content(corps)
    if bandeau:
        m.add_alternative("<p>Transféré.</p>", subtype="html")
        m.get_payload()[1].add_related(image_png(501, 146), "image", "png", cid="<b@exemple.test>")
    if pdf:
        m.add_attachment(_PDF, maintype="application", subtype="pdf", filename="pv.pdf")
    return traiter(
        session,
        _entetes_transfert(cs.email, f"TR: RE: {objet}"),
        corps,
        _RELEVE,
        authentification=_AUTH_OK,
        pieces=pj.trier(m),
    )


def _suites(session, objet):
    (affaire,) = _affaires(session, objet)
    return sorted(_evolutions(session, affaire), key=lambda e: e.cree_le)


def test_les_pieces_vont_dans_la_suite_du_message_transfere(monde, disque_jetable):
    """Le plus récent du fil — celui que le courriel transfère — et pas une
    Suite à part signée de qui transfère."""
    session, _ticket, syndic, cs, objet = monde
    assert _transferer(session, cs, objet, _fil(syndic.email, objet), pdf=True) == ACCEPTE
    jean, du_syndic = _suites(session, objet)
    assert parse_photos(jean.fichiers_urls) == []
    (url,) = parse_photos(du_syndic.fichiers_urls)
    assert url.endswith(".pdf")
    assert all(pj.PIECES_SEULES not in e.contenu for e in (jean, du_syndic))


def test_le_bandeau_de_signature_d_un_transfert_n_entre_pas(monde, disque_jetable):
    session, _ticket, syndic, cs, objet = monde
    assert _transferer(session, cs, objet, _fil(syndic.email, objet), bandeau=True) == ACCEPTE
    assert all(parse_photos(e.fichiers_urls) == [] for e in _suites(session, objet))


def test_le_message_deja_verse_transfere_avec_sa_piece_la_recoit(monde, disque_jetable):
    """Le rejeu : on transfère le message qui porte le PV, déjà versé sans lui.
    Le PV rejoint sa Suite ; le texte n'est pas doublé."""
    session, _ticket, syndic, cs, objet = monde
    _transferer(session, cs, objet, _fil(syndic.email, objet))
    avant = _suites(session, objet)
    assert _transferer(session, cs, objet, _fil(syndic.email, objet), pdf=True) == ACCEPTE
    apres = _suites(session, objet)
    assert [e.id for e in apres] == [e.id for e in avant], "aucune Suite de plus"
    assert len(parse_photos(apres[-1].fichiers_urls)) == 1


def test_cas_zero_un_rejeu_sans_piece_reste_ignore(monde, disque_jetable):
    session, _ticket, syndic, cs, objet = monde
    _transferer(session, cs, objet, _fil(syndic.email, objet))
    assert _transferer(session, cs, objet, _fil(syndic.email, objet)) != ACCEPTE


def test_une_piece_ANNONCEE_et_absente_se_dit(monde, disque_jetable):
    """Le PV « joint en annexe » du premier message, que la réponse transférée
    ne portait pas : la Suite le dit, et dit quoi faire."""
    session, _ticket, syndic, cs, objet = monde
    corps = _fil(syndic.email, objet).replace(
        "A ce jour l'entreprise", "Le procès-verbal est joint en annexe. A ce jour l'entreprise"
    )
    assert _transferer(session, cs, objet, corps) == ACCEPTE
    jean, du_syndic = _suites(session, objet)
    assert pj.PIECE_ABSENTE in jean.contenu
    assert pj.PIECE_ABSENTE not in du_syndic.contenu, "il n'annonce rien"


def test_cas_zero_une_piece_annoncee_et_versee_ne_dit_rien(monde, disque_jetable):
    session, _ticket, syndic, cs, objet = monde
    corps = _fil(syndic.email, objet).replace(
        "Nous nous chargeons", "Ci-joint le bon de commande. Nous nous chargeons"
    )
    assert _transferer(session, cs, objet, corps, pdf=True) == ACCEPTE
    assert all(pj.PIECE_ABSENTE not in e.contenu for e in _suites(session, objet))
