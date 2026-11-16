"""Ce qu'un résident ne fait PAS partir, par une Suite ou un message (#1164).

Pendant COMPORTEMENTAL de `test_canaux_notification.py`, qui lit la forme des
gardes. Ici on poste vraiment, en résident puis en conseil syndical, et on
regarde ce qui part.

## Le défaut du 23/09/2026

La création d'une affaire réservait au conseil le groupe WhatsApp et le courriel
externe. Une Suite et un message, non : l'auteur d'une affaire — n'importe quel
résident — publiait sur le groupe des résidents et écrivait, depuis l'adresse du
site, à qui il voulait. Et `POST …/messages` ne vérifiait même pas que l'on
VOYAIT l'affaire : son `GET` voisin le faisait.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from fastapi import BackgroundTasks, HTTPException

import app.routers.tickets.crud as crud
import app.routers.tickets.evolutions as evolutions
import app.routers.tickets.messages as messages
import app.utils.diffusion as diffusion
from app.models.core import RoleUtilisateur, Ticket
from app.routers.tickets.messages_schemas import MessageCreate
from app.schemas import TicketCreate
from app.schemas_tickets import TicketEvolutionCreate
from app.utils.horloge import maintenant
from tests.aides_base import compte


def _affaire(session, auteur, *, confidentiel=False):
    t = Ticket(
        numero=f"TK-{auteur.id:06d}{int(confidentiel)}",
        titre="Porte du hall",
        description="Elle ne ferme plus.",
        categorie="panne",
        auteur_id=auteur.id,
        confidentiel=confidentiel,
        cree_le=maintenant(),
        mis_a_jour_le=maintenant(),
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


@pytest.fixture()
def envois(monkeypatch):
    """Ce qui PART : courriels externes et messages sur le groupe."""
    parti = {"externe": [], "whatsapp": []}
    externe = lambda ticket, user, adresse, *a, **k: parti["externe"].append(adresse)  # noqa: E731
    monkeypatch.setattr(evolutions, "envoyer_email_externe", externe)
    monkeypatch.setattr(messages, "envoyer_email_externe", externe)
    #  Le canal de la résidence, allumé : la couture est le registre (#1060).
    monkeypatch.setattr(diffusion, "config_diffusion", lambda s, *a: {"site_url": "https://x"})
    return parti


def _suite(session, ticket, user):
    taches = BackgroundTasks()
    corps = TicketEvolutionCreate(
        type="commentaire",
        contenu="Toujours cassée.",
        partager_whatsapp=True,
        email_externe="quiconque@exemple.test",
    )
    evolutions.add_evolution(ticket.id, corps, taches, session=session, user=user)
    return [t.func.__name__ for t in taches.tasks]


def test_une_suite_de_resident_ne_publie_ni_n_ecrit_au_dehors(session, envois):
    resident = compte(session, prefixe="r")
    taches = _suite(session, _affaire(session, resident), resident)
    assert envois["externe"] == [], "un résident a fait partir un courriel vers une adresse libre"
    assert "envoyer_whatsapp_avec_log" not in taches, "un résident a publié sur le groupe"


def test_une_suite_du_conseil_publie_et_ecrit(session, envois):
    """Témoin : sans lui, le test précédent serait vert si plus RIEN ne partait."""
    resident = compte(session, prefixe="r")
    cs = compte(session, prefixe="cs", role=RoleUtilisateur.conseil_syndical)
    taches = _suite(session, _affaire(session, resident), cs)
    assert envois["externe"] == ["quiconque@exemple.test"]
    assert "envoyer_whatsapp_avec_log" in taches


def test_un_message_de_resident_n_ecrit_pas_au_dehors(session, envois):
    resident = compte(session, prefixe="r")
    ticket = _affaire(session, resident)
    corps = MessageCreate(contenu="Relance.", email_externe="quiconque@exemple.test")
    messages.add_message(ticket.id, corps, BackgroundTasks(), session=session, user=resident)
    assert envois["externe"] == []


def test_un_message_du_conseil_ecrit_au_dehors(session, envois):
    resident = compte(session, prefixe="r")
    cs = compte(session, prefixe="cs", role=RoleUtilisateur.conseil_syndical)
    ticket = _affaire(session, resident)
    corps = MessageCreate(contenu="Réponse.", email_externe="syndic@exemple.test")
    messages.add_message(ticket.id, corps, BackgroundTasks(), session=session, user=cs)
    assert envois["externe"] == ["syndic@exemple.test"]


def test_on_n_ecrit_pas_sur_une_affaire_qu_on_ne_voit_pas(session, envois):
    """Le `GET …/messages` refusait déjà ; le `POST` voisin, non."""
    auteur = compte(session, prefixe="auteur")
    voisin = compte(session, prefixe="voisin")
    ticket = _affaire(session, auteur, confidentiel=True)
    with pytest.raises(HTTPException) as refus:
        messages.add_message(
            ticket.id,
            MessageCreate(contenu="Je lis tout."),
            BackgroundTasks(),
            session=session,
            user=voisin,
        )
    assert refus.value.status_code == 403


# ── La CLASSE du défaut : une route d'affaire qui ne contrôle pas l'accès ─────
#
#  `POST …/messages` n'avait aucun contrôle, son `GET` voisin si. Rien ne relevait
#  l'écart : chaque route se relit seule. Toute route qui reçoit un `ticket_id`
#  doit poser UNE question d'accès — un prédicat, ou une dépendance de rôle.

_TICKETS = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "tickets"
_CONTROLES = (
    "ticket_visible",
    "peut_commenter",
    "peut_editer",
    "est_rattache_au_lot",
    "require_cs_or_admin",
    "require_admin",
    "require_proprietaire",
)


def _routes_sans_controle(source: str, fichier: str) -> list[str]:
    fautes = []
    for f in ast.walk(ast.parse(source)):
        if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        est_route = any(
            isinstance(d, ast.Call)
            and isinstance(d.func, ast.Attribute)
            and d.func.attr in {"get", "post", "patch", "put", "delete"}
            for d in f.decorator_list
        )
        if est_route and "ticket_id" in [a.arg for a in f.args.args]:
            if not any(c in ast.unparse(f) for c in _CONTROLES):
                fautes.append(f"{fichier}:{f.lineno} ({f.name})")
    return fautes


def test_toute_route_d_une_affaire_controle_l_acces():
    fautes, routes = [], 0
    for p in sorted(_TICKETS.glob("*.py")):
        source = p.read_text(encoding="utf-8")
        routes += source.count("ticket_id: int")
        fautes += _routes_sans_controle(source, p.name)
    assert routes >= 6, f"Seulement {routes} route(s) à `ticket_id` relevées — portée cassée."
    assert not fautes, "Route d'affaire sans contrôle d'accès (#1164) :\n  " + "\n  ".join(fautes)


def test_le_releve_voit_une_route_sans_controle():
    sans = "@router.post('/{ticket_id}/x')\ndef f(ticket_id: int, user=None):\n    return 1\n"
    avec = "@router.post('/{ticket_id}/x')\ndef f(ticket_id: int, user=None):\n    ticket_visible(t, user)\n"
    assert _routes_sans_controle(sans, "s.py")
    assert not _routes_sans_controle(avec, "a.py")


# ── #1171 : ce qu'on coche à la CRÉATION arrive en base ──────────────────────


@pytest.fixture()
def creation(monkeypatch):
    #  Les envois de la création ont leurs propres tests : ici, ce qui est ÉCRIT.
    monkeypatch.setattr(crud, "_notifier_cs_creation", lambda *a, **k: None)
    monkeypatch.setattr(crud, "adresses_deja_servies", lambda *a, **k: set())


def _creer(session, user, **options):
    corps = TicketCreate(
        titre="Litige", description="Entre voisins.", categorie="nuisance", **options
    )
    lu = crud.create_ticket(corps, BackgroundTasks(), session=session, user=user)
    return session.get(Ticket, lu.id)


def test_reservee_au_conseil_a_la_creation_est_ecrit(session, creation):
    cs = compte(session, prefixe="cs", role=RoleUtilisateur.conseil_syndical)
    assert _creer(session, cs, confidentiel=True).confidentiel is True


def test_un_resident_signale_l_urgence_a_la_creation(session, creation):
    resident = compte(session, prefixe="r")
    assert _creer(session, resident, urgente=True).priorite == "haute"


def test_un_resident_ne_restreint_pas_a_la_creation(session, creation):
    resident = compte(session, prefixe="r")
    assert _creer(session, resident, confidentiel=True).confidentiel is False
