"""Un courriel qu'aucune affaire ne désigne attend d'être classé (#2555).

Le cas d'origine, le 05/11/2026 : « Re: Portillon Hostachy », d'un membre du
conseil, refusé — « rien ne permet de dire à quel ticket » — alors que l'affaire
du portillon était ouverte. Le message était perdu pour le site.
"""

from __future__ import annotations

from datetime import datetime
from email.message import EmailMessage

import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.models.core import Ticket, TicketEvolution
from app.models.courriel import CourrielAClasser, CourrielReleve
from app.models.tickets import StatutTicket
from app.routers import courriels_affaires as route
from app.utils import courriel_a_classer as a_classer
from app.utils.courriel_boite import traiter
from app.utils.courriel_ingestion import A_CLASSER, IGNORE, REFUSE
from tests.aides_courriel import (  # noqa: F401 — `scene` est une fixture
    _AUTH_OK,
    _evolutions,
    _notifs,
    scene,
)
from tests.aides_purge import purger_ligne

_RECU = datetime(2026, 11, 5, 11, 29)


def _brut(de: str, sujet: str, texte: str, *, en_reponse_a: str | None = None) -> bytes:
    m = EmailMessage()
    m["From"] = de
    m["To"] = "affaire@5hostachy.fr"
    m["Subject"] = sujet
    if en_reponse_a:
        m["In-Reply-To"] = en_reponse_a
    m.set_content(texte)
    return m.as_bytes()


def _recevoir(session, de, sujet="Re: Portillon bd Hostachy", texte="Il est encore bloqué.", **k):
    brut = _brut(de, sujet, texte, **k)
    entetes = {"From": de, "To": "affaire@5hostachy.fr", "Subject": sujet}
    if k.get("en_reponse_a"):
        entetes["In-Reply-To"] = k["en_reponse_a"]
    return traiter(session, entetes, texte, _RECU, authentification=_AUTH_OK, brut=brut)


@pytest.fixture()
def file(scene):
    """La scène, et ce que la file y laisse — purgé à la fin."""
    session, ticket, syndic, cs = scene
    ticket.titre = "Portillon bd Hostachy bloqué fermé"
    session.add(ticket)
    session.commit()
    yield session, ticket, syndic, cs
    for item in session.exec(select(CourrielAClasser)).all():
        purger_ligne(session, CourrielAClasser, item.id)
    for ligne in session.exec(select(CourrielReleve)).all():
        purger_ligne(session, CourrielReleve, ligne.id)
    session.commit()


def _item(session) -> CourrielAClasser:
    (item,) = session.exec(select(CourrielAClasser)).all()
    return item


# ── Ce qui entre dans la file ─────────────────────────────────────────────────


def test_le_cas_d_origine_attend_d_etre_classe_et_le_conseil_est_prevenu(file):
    session, _ticket, _syndic, cs = file
    decision = _recevoir(session, cs.email, en_reponse_a="<perso@icloud.test>")
    assert decision == A_CLASSER
    item = _item(session)
    assert item.statut == a_classer.A_CLASSER and item.brut
    assert any("classé" in n.titre for n in _notifs(session, cs))


def test_un_message_d_un_connu_qui_ne_cite_rien_attend_aussi(file):
    """Sans `In-Reply-To` ni numéro : il était IGNORÉ sans un mot."""
    session, _ticket, syndic, _cs = file
    assert _recevoir(session, syndic.email, sujet="Portillon") == A_CLASSER


def test_un_inconnu_n_entre_pas_dans_la_file(file):
    session, *_ = file
    assert _recevoir(session, "promo@ailleurs.test", sujet="Offre") == IGNORE
    decision = _recevoir(session, "x@ailleurs.test", en_reponse_a="<a@b.test>")
    assert decision == REFUSE
    assert session.exec(select(CourrielAClasser)).all() == []


def test_un_message_non_authentifie_n_entre_pas_dans_la_file(file):
    session, _t, _s, cs = file
    entetes = {"From": cs.email, "To": "affaire@5hostachy.fr", "Subject": "Portillon"}
    decision = traiter(session, entetes, "x", _RECU, authentification=(False, "non signé"))
    assert decision == IGNORE
    assert session.exec(select(CourrielAClasser)).all() == []


# ── Les suggestions ───────────────────────────────────────────────────────────


def test_l_affaire_ouverte_du_meme_sujet_est_suggeree(file):
    session, ticket, _syndic, cs = file
    _recevoir(session, cs.email, sujet="Re: Portillon Hostachy")
    assert [t.id for t in a_classer.suggestions(session, _item(session))][:1] == [ticket.id]


def test_une_affaire_close_n_est_pas_suggeree(file):
    session, ticket, _syndic, cs = file
    ticket.statut = StatutTicket.résolu
    session.add(ticket)
    session.commit()
    _recevoir(session, cs.email, sujet="Re: Portillon Hostachy")
    assert ticket.id not in [t.id for t in a_classer.suggestions(session, _item(session))]


# ── Les trois gestes ──────────────────────────────────────────────────────────


def test_rattacher_verse_le_message_au_fil_et_efface_son_contenu(file):
    session, ticket, _syndic, cs = file
    _recevoir(session, cs.email, texte="Toujours bloqué ce matin.")
    item = _item(session)
    reponse = route.rattacher(item.id, route.Rattachement(numero=f"#{ticket.numero}"), cs, session)
    assert reponse.ticket_id == ticket.id
    (suite,) = _evolutions(session, ticket)
    assert "Toujours bloqué ce matin." in suite.contenu
    assert "transféré par" in suite.contenu
    session.refresh(item)
    assert item.statut == a_classer.RATTACHE and item.brut is None
    releve = session.get(CourrielReleve, item.releve_id)
    assert releve.ticket_id == ticket.id and "rattaché" in releve.motif


def test_creer_ouvre_une_affaire_du_conseil(file):
    session, _ticket, syndic, cs = file
    _recevoir(session, syndic.email, sujet="Fuite au 3e", texte="Une fuite au plafond.")
    reponse = route.creer(_item(session).id, cs, session)
    neuve = session.get(Ticket, reponse.ticket_id)
    assert neuve.titre == "Fuite au 3e"
    assert "Une fuite au plafond." in neuve.description
    for evol in session.exec(
        select(TicketEvolution).where(TicketEvolution.ticket_id == neuve.id)
    ).all():
        purger_ligne(session, TicketEvolution, evol.id)
    purger_ligne(session, Ticket, neuve.id)
    session.commit()


def test_ecarter_n_ecrit_rien(file):
    session, ticket, _syndic, cs = file
    _recevoir(session, cs.email)
    item = _item(session)
    route.ecarter(item.id, cs, session)
    assert _evolutions(session, ticket) == []
    session.refresh(item)
    assert item.statut == a_classer.ECARTE and item.brut is None


def test_un_message_deja_classe_ne_se_classe_pas_deux_fois(file):
    session, _ticket, _syndic, cs = file
    _recevoir(session, cs.email)
    item = _item(session)
    route.ecarter(item.id, cs, session)
    with pytest.raises(HTTPException) as refus:
        route.creer(item.id, cs, session)
    assert refus.value.status_code == 409


def test_on_ne_rattache_pas_a_une_affaire_close_ni_inconnue(file):
    session, ticket, _syndic, cs = file
    _recevoir(session, cs.email)
    item = _item(session)
    with pytest.raises(HTTPException) as inconnue:
        route.rattacher(item.id, route.Rattachement(numero="TK-000000"), cs, session)
    assert inconnue.value.status_code == 404
    ticket.statut = StatutTicket.résolu
    session.add(ticket)
    session.commit()
    with pytest.raises(HTTPException) as close:
        route.rattacher(item.id, route.Rattachement(numero=ticket.numero), cs, session)
    assert close.value.status_code == 409


def test_le_journal_porte_l_apercu_et_les_suggestions(file):
    session, ticket, _syndic, cs = file
    _recevoir(session, cs.email, sujet="Re: Portillon Hostachy", texte="Bloqué depuis hier.")
    journal = route.courriels_affaires(cs, session)
    (ligne,) = [m for m in journal.messages if m.a_classer]
    assert ligne.decision == A_CLASSER
    assert ligne.a_classer.apercu == "Bloqué depuis hier."
    assert ligne.a_classer.suggestions[0].numero == ticket.numero
