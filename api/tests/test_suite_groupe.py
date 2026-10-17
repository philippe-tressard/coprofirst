"""Une Suite part sur le groupe avec SON message, et le lien de l'historique.

## Le défaut du 28/09/2026

Signalé par l'utilisateur : sur la Suite d'une affaire partagée sur WhatsApp,
c'était le message initial qui s'affichait. L'aperçu de diffusion montrait la
description de l'affaire au lieu de la Suite saisie ; la première Suite d'une
affaire partait sans lien ; celle d'une actualité portait le lien deux fois.

On poste de vraies Suites et l'on compose le message comme le canal le fera
(`construire_message`) : c'est le texte reçu qu'on regarde, pas ses morceaux.
"""

from __future__ import annotations

import pytest
from fastapi import BackgroundTasks

import app.routers.tickets.apercu as apercu
import app.routers.tickets.evolutions as evolutions
import app.utils.diffusion as diffusion
from app.models.core import RoleUtilisateur, Ticket
from app.schemas_tickets import TicketEvolutionCreate
from app.utils import horloge
from app.utils.whatsapp_message import construire_message
from tests.aides_adresse import poser_adresse_du_site
from tests.aides_base import compte

SITE = "https://5hostachy.fr"
INITIAL = "Elle ne ferme plus."


@pytest.fixture()
def session(session, monkeypatch):
    #  Le canal de la résidence, allumé : la couture est le registre (#1060).
    monkeypatch.setattr(diffusion, "config_diffusion", lambda s, *a: {})
    poser_adresse_du_site(monkeypatch, SITE)
    return session


@pytest.fixture()
def cs(session):
    return compte(
        session,
        prefixe="cs",
        prenom="C",
        nom="S",
        roles_json=RoleUtilisateur.conseil_syndical.value,
    )


def _affaire(session, auteur, categorie="panne"):
    t = Ticket(
        numero=f"TK-{categorie}",
        titre="Porte du hall",
        description=INITIAL,
        categorie=categorie,
        auteur_id=auteur.id,
        cree_le=horloge.maintenant(),
        mis_a_jour_le=horloge.maintenant(),
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _suite(session, ticket, user, contenu):
    """Poste une Suite partagée sur le groupe ; rend le texte que le groupe reçoit."""
    taches = BackgroundTasks()
    corps = TicketEvolutionCreate(type="commentaire", contenu=contenu, partager_whatsapp=True)
    evolutions.add_evolution(ticket.id, corps, taches, session=session, user=user)
    envois = [t for t in taches.tasks if t.func.__name__ == "envoyer_whatsapp_avec_log"]
    assert len(envois) == 1, "la Suite du conseil doit partir sur le groupe"
    titre, texte, urgente, perimetre, _image, config, public, confidentiel = envois[0].args
    return construire_message(
        titre,
        texte,
        urgente,
        perimetre,
        config,
        public,
        confidentiel,
        lien=envois[0].kwargs["lien"],
    )


@pytest.mark.parametrize("categorie", ["panne", "actualite"])
def test_la_premiere_suite_part_avec_son_message_et_le_lien(session, cs, categorie):
    ticket = _affaire(session, cs, categorie)
    recu = _suite(session, ticket, cs, "Le serrurier passe jeudi.")
    assert "Le serrurier passe jeudi." in recu
    assert INITIAL not in recu, "c'est la Suite qui part, pas le message initial"
    lien = f"{SITE}/tickets/{ticket.id}"
    assert recu.count(lien) == 1, "le lien de l'historique, une fois — ni absent, ni doublé"


def test_la_suite_suivante_compte_le_fil(session, cs):
    ticket = _affaire(session, cs)
    _suite(session, ticket, cs, "Premier passage.")
    recu = _suite(session, ticket, cs, "Réparée.")
    assert "Réparée." in recu and "Premier passage." not in recu
    assert "Déjà 2 message(s)" in recu, "le message initial et la Suite précédente"


def test_l_apercu_d_une_suite_montre_la_suite(session, cs):
    ticket = _affaire(session, cs)
    brouillon = apercu.BrouillonTicket(
        ticket_id=ticket.id, commentaire="Le serrurier passe jeudi.", partager_whatsapp=True
    )
    rendu = apercu.apercu_diffusion(brouillon, session=session, user=cs)
    (wa,) = [c for c in rendu.canaux if c.canal == "whatsapp"]
    assert wa.actif
    assert "Le serrurier passe jeudi." in wa.texte
    assert INITIAL not in wa.texte, "l'aperçu montrait le message initial"
    assert f"{SITE}/tickets/{ticket.id}" in wa.texte
    #  L'aperçu et l'envoi disent la même chose, au mot près.
    assert wa.texte == _suite(session, ticket, cs, "Le serrurier passe jeudi.")


def _image_de_la_suite(session, ticket, user, fichiers_urls):
    taches = BackgroundTasks()
    corps = TicketEvolutionCreate(
        type="commentaire",
        contenu="Voici l'état.",
        partager_whatsapp=True,
        fichiers_urls=fichiers_urls,
    )
    evolutions.add_evolution(ticket.id, corps, taches, session=session, user=user)
    (envoi,) = [t for t in taches.tasks if t.func.__name__ == "envoyer_whatsapp_avec_log"]
    return envoi.args[4]


def test_une_suite_part_avec_sa_premiere_image(session, cs):
    """Les photos d'une Suite voyagent dans `fichiers_urls`, mêlées aux documents.

    Constaté le 06/10/2026 sur la Suite du 29/09 (porte des boîtes aux lettres) :
    la photo jointe n'est jamais partie sur le groupe, seul le texte.
    """
    ticket = _affaire(session, cs)
    image = _image_de_la_suite(
        session,
        ticket,
        cs,
        [
            "/uploads/fichiers/a_devis.pdf",
            "/uploads/fichiers/b_porte.jpg",
            "/uploads/fichiers/c.png",
        ],
    )
    assert image == "/uploads/fichiers/b_porte.jpg", "la première IMAGE, pas le premier fichier"


def test_une_suite_sans_image_part_sans_image(session, cs):
    ticket = _affaire(session, cs)
    assert _image_de_la_suite(session, ticket, cs, ["/uploads/fichiers/a_devis.pdf"]) is None
    assert _image_de_la_suite(session, ticket, cs, []) is None


def test_l_apercu_d_une_suite_montre_son_image(session, cs):
    ticket = _affaire(session, cs)
    brouillon = apercu.BrouillonTicket(
        ticket_id=ticket.id,
        commentaire="Voici l'état.",
        partager_whatsapp=True,
        fichiers_urls=["/uploads/fichiers/b_porte.jpg"],
    )
    rendu = apercu.apercu_diffusion(brouillon, session=session, user=cs)
    (wa,) = [c for c in rendu.canaux if c.canal == "whatsapp"]
    assert wa.avec_photo, "l'aperçu doit annoncer la photo que le groupe recevra"
