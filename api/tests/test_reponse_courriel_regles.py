"""Ce qu'une réponse par courriel fait au fil — les règles demandées le 28/09/2026.

- un message du SYNDIC — écrit par lui, ou transféré par un membre du conseil —
  fait passer une affaire encore « Ouvert » à « Chez le syndic » ;
- un transfert du syndic porte le message du SYNDIC, pas la note de qui transfère ;
- un simple merci du conseil n'entre pas (l'assistant le juge sans objet) ;
- une affaire CLOSE ne reçoit plus rien, pas même une alerte ;
- un courriel en HTML SEUL se lit (l'application Mail d'Orange) : il était ignoré.

Les règles vivent dans `utils/reponse_courriel.suite_d_un_message` et
`utils/courriel_decodage` ; la relève (`courriel_boite.traiter`) les applique.
"""

from __future__ import annotations

from datetime import datetime
from email.message import EmailMessage
from types import SimpleNamespace

import pytest

from app.models.tickets import StatutTicket
from app.utils import courriel_transfert, llm
from app.utils.courriel_boite import traiter
from app.utils.courriel_decodage import _corps_lisible, _sans_citation, transfert_dans
from app.utils.courriel_ingestion import ACCEPTE, IGNORE
from tests.aides_courriel import (  # noqa: F401 — `scene` est une fixture
    _AUTH_OK,
    _entetes_reponse,
    _evolutions,
    _notifs,
    scene,
)

_ENVOI = datetime(2026, 9, 28, 14, 37)


@pytest.fixture(autouse=True)
def _domaine_du_site(monkeypatch):
    """Le domaine d'où le site écrit, comme en production : le message du site
    cité au bas d'un transfert n'entre pas dans le fil."""
    monkeypatch.setattr(courriel_transfert, "domaines_du_site", lambda _session: {"5hostachy.fr"})


def _modele(texte):
    async def faux(session, *, usage, message, **_):
        return SimpleNamespace(texte=texte)

    return faux


def _transfert_du_syndic(adresse_syndic: str) -> str:
    return (
        "Mme Verdière,\n\nPS : demain je serai à Lyon.\n\ncdlmt\nC S / 06 00 00 00 00\n\n"
        "Début du message réexpédié :\n\n"
        f"De : G S <{adresse_syndic}>\n"
        "Objet : Affaire #TK-121048 — Porte\n"
        "Date : 28 sept. 2026 à 15 h 47\n\n"
        "Bonjour à tous,\n"
        "La société Artur Services passera ce soir.\n\n"
        "De : 5Hostachy <contact@5hostachy.fr>\n"
        "Envoyé : vendredi 25 septembre 2026 18:01\n"
        "Objet : Affaire #TK-121048\n"
        "Le fil complet du site, avec les adresses des résidents.\n"
    )


# ── Le syndic fait avancer le dossier ─────────────────────────────────────────


def test_une_reponse_du_SYNDIC_passe_l_affaire_ouverte_chez_le_syndic(scene):  # noqa: F811
    session, ticket, syndic, _cs = scene
    assert (
        traiter(
            session,
            _entetes_reponse(ticket.jeton_courriel, de=syndic.email),
            "Nous intervenons jeudi.",
            _ENVOI,
            authentification=_AUTH_OK,
        )
        == ACCEPTE
    )
    (evol,) = _evolutions(session, ticket)
    assert (evol.type, evol.ancien_statut, evol.nouveau_statut) == ("etat", "ouvert", "en_cours")
    session.refresh(ticket)
    assert ticket.statut == StatutTicket.en_cours


def test_une_affaire_deja_AVANCEE_ne_change_pas_d_etat(scene):  # noqa: F811
    """« s'il est encore à l'état initial OUVERT » — une affaire en AG y reste."""
    session, ticket, syndic, _cs = scene
    ticket.statut = StatutTicket.en_ag
    session.add(ticket)
    session.commit()
    traiter(
        session,
        _entetes_reponse(ticket.jeton_courriel, de=syndic.email),
        "Nous intervenons jeudi.",
        _ENVOI,
        authentification=_AUTH_OK,
    )
    (evol,) = _evolutions(session, ticket)
    assert evol.type == "commentaire" and evol.nouveau_statut is None
    session.refresh(ticket)
    assert ticket.statut == StatutTicket.en_ag


def test_une_reponse_du_CONSEIL_ne_change_pas_l_etat(scene):  # noqa: F811
    session, ticket, _syndic, cs = scene
    traiter(
        session,
        _entetes_reponse(ticket.jeton_courriel, de=cs.email),
        "J'ai relancé le prestataire.",
        _ENVOI,
        authentification=_AUTH_OK,
    )
    (evol,) = _evolutions(session, ticket)
    assert evol.type == "commentaire"
    session.refresh(ticket)
    assert ticket.statut == StatutTicket.ouvert


# ── Le transfert d'un message du syndic ───────────────────────────────────────


def test_un_TRANSFERT_du_syndic_par_le_conseil_porte_le_message_du_syndic(scene):  # noqa: F811
    session, ticket, syndic, cs = scene
    entetes = dict(_entetes_reponse(ticket.jeton_courriel, de=cs.email))
    entetes["Subject"] = f"TR : Affaire #{ticket.numero} — Fuite"
    traiter(session, entetes, _transfert_du_syndic(syndic.email), _ENVOI, authentification=_AUTH_OK)
    (evol,) = _evolutions(session, ticket)
    #  Daté du message du SYNDIC (15 h 47), pas du transfert (16:37) : depuis le
    #  29/09/2026 chaque message d'un fil transféré porte sa propre date.
    assert evol.contenu.startswith(
        "<p><em>Mail reçu de G S le 28 septembre 2026 à 15:47, transféré par C S</em></p>"
    ), evol.contenu
    assert "Artur Services passera ce soir" in evol.contenu
    assert "Lyon" not in evol.contenu, "la note de qui transfère n'est pas le suivi"
    assert "06 00" not in evol.contenu
    assert "adresses des résidents" not in evol.contenu, "l'historique cité reste dehors"
    assert (evol.type, evol.nouveau_statut) == ("etat", "en_cours")


def test_le_transfert_d_un_message_d_un_TIERS_verse_le_message_du_tiers(scene):  # noqa: F811
    """🔴 Changé le 29/09/2026 : c'était la NOTE du conseil qui entrait. Le conseil
    transfère désormais les échanges reçus dans sa boîte pour qu'ils rejoignent
    l'affaire — c'est le message du tiers que le fil doit garder."""
    session, ticket, _syndic, cs = scene
    entetes = dict(_entetes_reponse(ticket.jeton_courriel, de=cs.email))
    entetes["Subject"] = f"TR : Affaire #{ticket.numero}"
    traiter(
        session,
        entetes,
        _transfert_du_syndic("quelqu-un@ailleurs.test"),
        _ENVOI,
        authentification=_AUTH_OK,
    )
    (evol,) = _evolutions(session, ticket)
    assert evol.type == "commentaire"
    assert evol.contenu.startswith("<p><em>Mail reçu de G S le 28 septembre 2026 à 15:47, ")
    assert "Artur Services" in evol.contenu and "Lyon" not in evol.contenu


def test_une_REPONSE_a_un_transfert_n_est_pas_un_transfert():
    texte = "Merci.\n\nDébut du message réexpédié :\n\nDe : G S <g@syndic.test>\n\nTexte"
    assert transfert_dans("RE: TR : Affaire #TK-1", texte) is None
    assert transfert_dans("TR : Affaire #TK-1", texte).adresse == "g@syndic.test"


# ── Un merci du conseil n'entre pas ───────────────────────────────────────────


def test_un_simple_MERCI_du_conseil_n_entre_pas(scene, monkeypatch):  # noqa: F811
    session, ticket, _syndic, cs = scene
    monkeypatch.setattr(llm, "demander", _modele(""))
    assert (
        traiter(
            session,
            _entetes_reponse(ticket.jeton_courriel, de=cs.email),
            "Merci beaucoup !",
            _ENVOI,
            authentification=_AUTH_OK,
        )
        == IGNORE
    )
    assert _evolutions(session, ticket) == []


def test_le_SYNDIC_entre_meme_quand_l_assistant_le_juge_vide(scene, monkeypatch):  # noqa: F811
    """Une réponse sollicitée n'est jamais écartée par l'assistant."""
    session, ticket, syndic, _cs = scene
    monkeypatch.setattr(llm, "demander", _modele(""))
    traiter(
        session,
        _entetes_reponse(ticket.jeton_courriel, de=syndic.email),
        "Bien reçu.",
        _ENVOI,
        authentification=_AUTH_OK,
    )
    assert len(_evolutions(session, ticket)) == 1


# ── Une affaire close ne reçoit plus rien ─────────────────────────────────────


def test_une_affaire_CLOSE_ne_recoit_plus_rien_ni_alerte(scene):  # noqa: F811
    session, ticket, syndic, cs = scene
    ticket.statut = StatutTicket.résolu
    session.add(ticket)
    session.commit()
    for auth in (_AUTH_OK, (False, "non signé")):
        assert (
            traiter(
                session,
                _entetes_reponse(ticket.jeton_courriel, de=syndic.email),
                "Facture jointe.",
                _ENVOI,
                authentification=auth,
            )
            == IGNORE
        )
    assert _evolutions(session, ticket) == []
    assert _notifs(session, cs) == []


# ── Le courriel en HTML seul ──────────────────────────────────────────────────


def _html_seul(html: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = "RE: Affaire #TK-1"
    message.set_content(html, subtype="html")
    return message


def test_un_courriel_en_HTML_SEUL_se_lit_et_sa_citation_reste_dehors():
    """🔴 L'application Mail d'Orange n'envoie que du HTML : il était lu vide."""
    html = (
        "<html><head><style>p{color:red}</style></head><body>"
        "<div>Bonsoir&nbsp;<br></div><div>D&eacute;sol&eacute;e, je suis absente.</div>"
        "<div>----------------</div><div><b>De :</b> Philippe &lt;p@exemple.test&gt;</div>"
        "<blockquote type='cite'><div>Texte cité</div></blockquote></body></html>"
    )
    texte = _corps_lisible(_html_seul(html))
    assert "Désolée, je suis absente." in texte
    assert "color" not in texte and "<" not in texte.replace("<p@", "")
    assert _sans_citation(texte) == "Bonsoir\nDésolée, je suis absente."


def test_une_citation_HTML_est_marquee_comme_en_texte_brut():
    texte = _corps_lisible(
        _html_seul("<p>Oui.</p><blockquote><p>Question ?</p><p>Suite</p></blockquote>")
    )
    assert _sans_citation(texte) == "Oui."
