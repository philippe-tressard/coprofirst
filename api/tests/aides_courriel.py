"""Les aides des tests de courriel entrant — la scène, les en-têtes, le journal (#1495).

## Pourquoi ce module existe (30/09/2026)

Elles vivaient dans quatre FICHIERS DE TESTS — `test_courriel_reponse_ticket`,
`test_courriel_reponse_ticket_bout_en_bout`, `test_courriel_transfert` et
`test_releve_echec_nest_pas_vide` pour le journal de la relève —, et huit
fichiers les importaient depuis là. Un test qui sert de bibliothèque ne
peut plus être découpé, renommé ni supprimé sans casser ceux qui s'en
servent, et rien ne le signale à celui qui le touche. Elles vivent ici, comme
`aides_affaire.py` et `aides_badges.py`.

⚠️ `scene`, `monde`, `journal` et `imap_actif` sont des FIXTURES : un fichier de
tests les IMPORTE pour que pytest les trouve — et `monde` demande `scene`, que
l'importeur doit donc importer aussi.

Deux fabriques d'en-têtes, qui ne sont pas la même fonction : `_entetes_reponse`
répond à un ticket par son adresse à jeton, `_entetes_transfert` écrit à
l'adresse des affaires un fil transféré. Elles portaient toutes deux le nom
`_entetes`, chacune dans son fichier.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    GenreCivilite,
    MembreSyndic,
    Notification,
    StatutTicket,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.models.courriel import FilCourriel, MessageVerse, VersementCourriel
from app.utils import courriel_boite, courriel_transfert
from app.utils.courriel_boite import traiter
from app.utils.courriel_entrant import nouveau_jeton
from tests.aides_base import compte
from tests.aides_purge import purger_ligne

# ── Répondre à un ticket ──────────────────────────────────────────────────────

#: Le verdict d'authenticité, tel que la relève le calcule sur les octets reçus
#: (`courriel_authenticite.verifier_expediteur`) — jamais un en-tête du message.
_AUTH_OK = (True, "signé par syndic.fr")


def _adresse_a_jeton(jeton: str) -> str:
    """L'adresse d'un ANCIEN courriel (avant #1314) : le site ne la pose plus,
    mais une réponse à un message archivé peut encore la citer."""
    return f"tickets+{jeton}@5hostachy.fr"


def _entetes_reponse(jeton: str, *, de: str = "gestion@syndic.fr") -> dict:
    return {"From": de, "To": _adresse_a_jeton(jeton), "Subject": "Re: ticket"}


# ── Ce qui est écrit en base ──────────────────────────────────────────────────


@pytest.fixture()
def scene():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        syndic = compte(
            session,
            email=f"syndic-{uuid.uuid4().hex[:8]}@syndic.fr",
            prenom="G",
            nom="S",
            roles_json="résident",
        )
        cs = compte(session, prefixe="cs", prenom="C", nom="S", roles_json="conseil_syndical")
        #  Le gestionnaire du cabinet, reconnu à son ADRESSE : c'est ce qui
        #  autorise le repli par le sujet (05/09/2026). Sans cette fiche, le même
        #  message serait refusé — et c'est un des tests de
        #  `test_courriel_reponse_ticket_bout_en_bout`.
        fiche_syndic = MembreSyndic(
            genre=GenreCivilite.mr,
            prenom="G",
            nom="S",
            email=syndic.email,
            est_principal=True,
        )
        session.add(fiche_syndic)
        session.commit()
        session.refresh(fiche_syndic)
        ticket = Ticket(
            numero=f"TK-{uuid.uuid4().hex[:6]}",
            titre="Fuite",
            description="…",
            categorie="panne",
            auteur_id=cs.id,
            statut=StatutTicket.ouvert,
            jeton_courriel=nouveau_jeton(),
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        yield session, ticket, syndic, cs
        for evol in session.exec(
            select(TicketEvolution).where(TicketEvolution.ticket_id == ticket.id)
        ).all():
            purger_ligne(session, TicketEvolution, evol.id)
        for notif in session.exec(
            select(Notification).where(Notification.destinataire_id == cs.id)
        ).all():
            purger_ligne(session, Notification, notif.id)
        purger_ligne(session, MembreSyndic, fiche_syndic.id)
        purger_ligne(session, Ticket, ticket.id)
        purger_ligne(session, Utilisateur, syndic.id)
        purger_ligne(session, Utilisateur, cs.id)
        session.commit()


def _evolutions(session, ticket):
    return session.exec(
        select(TicketEvolution)
        .where(TicketEvolution.ticket_id == ticket.id)
        .order_by(TicketEvolution.id)
    ).all()


def _notifs(session, user):
    return session.exec(
        select(Notification)
        .where(Notification.destinataire_id == user.id)
        .order_by(Notification.id)
    ).all()


# ── Un fil transféré par le conseil ───────────────────────────────────────────

_RELEVE = datetime(2026, 9, 29, 12, 0)


def _fil(syndic: str, objet: str, *, plus_recent: str = "") -> str:
    """Le fil de l'exemple du 29/09/2026 — noms et adresses fictifs."""
    return (
        f"{plus_recent}"
        "Début du message réexpédié :\n\n"
        f"De: Gestion Syndic <{syndic}>\n"
        f"Objet: RE: {objet}\n"
        "Date: 29 septembre 2026 à 10:12:34 UTC+2\n"
        "À: Jean Dupont <jean.dupont@exemple.test>\n\n"
        "Bonjour Monsieur Dupont,\n\n"
        "Nous nous chargeons de lancer un ordre de service à l'électricien.\n\n"
        "Cordialement\n\n"
        "De : Jean Dupont <jean.dupont@exemple.test>\n"
        "Envoyé : mardi 29 septembre 2026 08:43\n"
        f"À : Gestion Syndic <{syndic}>\n"
        f"Objet : Re: {objet}\n\n"
        "Bonjour Madame,\n\n"
        "A ce jour l'entreprise ne répond pas à notre demande d'intervention urgente.\n\n"
        "Le sam. 26 sept. 2026, 08:58, Jean Dupont <\n"
        "jean.dupont@exemple.test> a écrit :\n\n"
        "> Bonjour Monsieur,\n>\n"
        "> Le portillon électrique ne fonctionne plus, les résidents ne peuvent plus rentrer.\n"
    )


def _entetes_transfert(de: str, sujet: str) -> dict:
    return {"From": de, "To": "affaire@5hostachy.fr", "Subject": sujet}


@pytest.fixture()
def monde(scene, monkeypatch):
    """La scène des réponses par courriel, un objet de fil unique, et la purge
    de tout ce que les transferts créent."""
    session, ticket, syndic, cs = scene
    monkeypatch.setattr(courriel_transfert, "domaines_du_site", lambda _session: {"5hostachy.fr"})
    objet = f"Portillon bloqué {uuid.uuid4().hex[:8]}"
    yield session, ticket, syndic, cs, objet
    crees = session.exec(
        select(Ticket).where(Ticket.auteur_id == cs.id, Ticket.id != ticket.id)
    ).all()
    for t in [*crees, ticket]:
        #  Les VERSEMENTS aussi (#1747) : laissés en place, ils pointaient vers un
        #  identifiant d'affaire qu'une base neuve réattribue — une affaire d'un test
        #  suivant en héritait (« 9 versements » au lieu d'un, selon l'ordre).
        for modele in (TicketEvolution, MessageVerse, VersementCourriel, FilCourriel):
            for ligne in session.exec(select(modele).where(modele.ticket_id == t.id)).all():
                purger_ligne(session, modele, ligne.id)
    for t in crees:
        purger_ligne(session, Ticket, t.id)
    session.commit()


def _affaires(session, objet):
    return session.exec(select(Ticket).where(Ticket.titre == objet).order_by(Ticket.id)).all()


def _transferer(session, cs, objet, corps, *, sujet=None, auth=_AUTH_OK):
    return traiter(
        session,
        _entetes_transfert(cs.email, sujet or f"TR: RE: {objet}"),
        corps,
        _RELEVE,
        authentification=auth,
    )


# ── Le journal de la relève ───────────────────────────────────────────────────


@pytest.fixture()
def journal():
    """Ce que le logger de la relève ÉMET — sans passer par `caplog`.

    🔴 `caplog` a rendu les deux tests de `test_releve_echec_nest_pas_vide`
    verts seuls et rouges dans la suite complète : il s'appuie sur la
    configuration globale de `logging`, que `app.main` et d'autres modules
    touchent à l'import. Un garde-fou dont le
    verdict dépend de l'ordre des tests ne mesure pas ce qu'il croit mesurer —
    c'est `standards/04` §1, et il rendait ici un ÉCHEC arbitraire.

    Un handler posé sur le logger visé ne dépend de rien d'autre.
    """
    lignes: list[str] = []

    class _Ecoute(logging.Handler):
        def emit(self, enr):
            lignes.append(enr.getMessage())

    ecoute = _Ecoute(level=logging.DEBUG)
    logger = logging.getLogger("app.utils.courriel_boite")
    niveau, propage, eteint = logger.level, logger.propagate, logger.disabled
    logger.addHandler(ecoute)
    logger.setLevel(logging.DEBUG)
    #  🔴 `disabled = False` — et c'est le cœur de l'affaire.
    #
    #  Alembic appelle `fileConfig(alembic.ini)`, qui vaut
    #  `disable_existing_loggers=True` : à la seconde où un test joue une
    #  migration, TOUS les loggers déjà créés passent à `disabled = True`, pour
    #  le reste de la session pytest. Le nôtre n'émettait alors plus rien, et
    #  ces deux tests rendaient un ÉCHEC selon l'ordre d'exécution — verts
    #  seuls, rouges dans la suite.
    #
    #  ⚠️ Ce n'est pas un défaut de production : `app.main` configure la
    #  journalisation au démarrage et Alembic tourne AVANT, dans `start.sh`.
    #  Mais un garde-fou dont le verdict dépend de l'ordre des tests ne mesure
    #  pas ce qu'il croit mesurer (`standards/04` §1).
    logger.disabled = False
    try:
        yield lignes
    finally:
        logger.removeHandler(ecoute)
        logger.setLevel(niveau)
        logger.propagate = propage
        logger.disabled = eteint


@pytest.fixture()
def imap_actif(monkeypatch):
    """La relève se croit configurée — c'est la connexion qui échouera."""
    monkeypatch.setattr(
        courriel_boite,
        "config_imap",
        lambda _session: {
            "imap_enabled": "1",
            "imap_host": "imap.invalide",
            "imap_port": "993",
            "imap_user": "essai@invalide",
            "imap_password": "x",
            "imap_dossier": "INBOX",
        },
    )
