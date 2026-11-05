"""Le syndic SANS compte écrit au fil de son affaire (#2554).

Constat du 05/11/2026 : les gestionnaires du cabinet sont déclarés dans la fiche
du syndic, et aucun n'a de compte. Même authentifiée, leur réponse était refusée
— « cet expéditeur, pourtant authentifié, n'a pas de compte sur le site » —, et
c'est POUR EUX que la relève existe. Elle entre désormais, signée « Le syndic ».
Un autre tiers sans compte reste refusé (`test_courriel_reponse_ticket_bout_en_bout`).
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from app.models.core import GenreCivilite, MembreSyndic, Utilisateur
from app.models.tickets import StatutTicket
from app.utils import courriel_pieces_jointes as pj
from app.utils.courriel_affaire_du_fil import compte_a_l_adresse
from app.utils.courriel_boite import traiter
from app.utils.courriel_ingestion import ACCEPTE
from app.utils.noms import QUALITE_SYNDIC, nom_auteur
from app.utils.photos import parse_photos
from app.utils.reponse_courriel import suite_mise_en_forme
from tests.aides_base import compte
from tests.aides_courriel import (  # noqa: F401 — `scene` est une fixture
    _AUTH_OK,
    _entetes_reponse,
    _evolutions,
    scene,
)
from tests.aides_purge import purger_ligne

_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture()
def gestionnaire(scene):
    """Un second membre du cabinet, déclaré dans la fiche — et SANS compte."""
    session, ticket, _syndic, cs = scene
    membre = MembreSyndic(
        genre=GenreCivilite.mr,
        prenom="Paul",
        nom="Morel",
        email=f"gestion-{uuid.uuid4().hex[:8]}@cabinet-gestion.fr",
    )
    session.add(membre)
    session.commit()
    session.refresh(membre)
    yield session, ticket, membre, cs
    purger_ligne(session, MembreSyndic, membre.id)
    session.commit()


def _repondre(session, ticket, de: str, texte: str = "Le serrurier passe jeudi.", pieces=None):
    return traiter(
        session,
        {
            "From": de,  # sans nom affiché : l'en-tête prend celui de la fiche du cabinet
            "To": "affaire@5hostachy.fr",
            "Subject": f"RE: 00213 — Affaire #{ticket.numero} — Fuite — 5Hostachy",
        },
        texte,
        datetime(2026, 11, 5, 9, 53),
        authentification=_AUTH_OK,
        pieces=pieces,
    )


def test_la_reponse_du_syndic_sans_compte_entre_au_fil(gestionnaire):
    session, ticket, membre, _cs = gestionnaire
    assert compte_a_l_adresse(session, membre.email) is None, "le cas étudié : aucun compte"
    assert _repondre(session, ticket, membre.email) == ACCEPTE
    (suite,) = _evolutions(session, ticket)
    assert suite.auteur_id is None
    assert suite.auteur_qualite == QUALITE_SYNDIC
    assert nom_auteur(None, suite.auteur_qualite) == "Le syndic"
    assert "Paul MOREL" in suite.contenu, "l'en-tête de la Suite nomme qui a écrit"
    assert "Le serrurier passe jeudi." in suite.contenu


def test_le_syndic_sans_compte_fait_avancer_l_affaire(gestionnaire):
    """La règle du syndic (28/09/2026) vaut sans compte : « Ouvert » → « Chez le syndic »."""
    session, ticket, membre, _cs = gestionnaire
    _repondre(session, ticket, membre.email)
    session.refresh(ticket)
    assert ticket.statut == StatutTicket.en_cours


def test_ses_pieces_jointes_entrent_aussi(gestionnaire, disque_jetable):
    session, ticket, membre, _cs = gestionnaire
    admin = compte(session, prefixe="admin", roles_json="admin")
    try:
        tri = pj.Tri(pieces=[pj.Piece("devis.pdf", "application/pdf", "document", _PDF)])
        assert _repondre(session, ticket, membre.email, "Voici le devis.", tri) == ACCEPTE
        (suite,) = _evolutions(session, ticket)
        assert len(parse_photos(suite.fichiers_urls)) == 1
        assert suite.auteur_qualite == QUALITE_SYNDIC
    finally:
        purger_ligne(session, Utilisateur, admin.id)
        session.commit()


def test_sans_administrateur_les_pieces_restent_dans_la_boite_et_le_texte_entre(
    gestionnaire, disque_jetable, monkeypatch
):
    session, ticket, membre, _cs = gestionnaire
    monkeypatch.setattr(pj, "gestionnaire_ou_premier_admin", lambda _s: None)
    tri = pj.Tri(pieces=[pj.Piece("devis.pdf", "application/pdf", "document", _PDF)])
    assert _repondre(session, ticket, membre.email, "Voici le devis.", tri) == ACCEPTE
    (suite,) = _evolutions(session, ticket)
    assert parse_photos(suite.fichiers_urls) == []
    assert "devis.pdf" in suite.contenu and "aucun administrateur" in suite.contenu


def test_une_suite_sans_signataire_ne_s_ecrit_que_pour_le_syndic(scene):
    session, ticket, _syndic, _cs = scene
    from app.utils.reponse_courriel import Texte

    with pytest.raises(ValueError):
        suite_mise_en_forme(
            session,
            ticket,
            None,
            Texte(contenu="<p>Bonjour</p>", origine=None, assiste=False),
            expediteur="inconnu@ailleurs.fr",
            nom="Inconnu",
            envoye_le=datetime(2026, 11, 5),
        )
