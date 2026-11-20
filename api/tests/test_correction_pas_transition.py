"""Une ÉDITION écrit une correction, jamais une étape de workflow.

## Pourquoi ce garde-fou (#433, 18/08/2026)

Le cadre #430 rouvre le workflow à l'édition : *l'édition corrige — une erreur,
un oubli, un complément — et l'état s'y corrige comme les autres champs*. Cela
n'est tenable qu'à une condition : que le `PATCH` n'écrive pas la même ligne
qu'une vraie transition. Sinon corriger un état mal saisi ferait apparaître dans
l'Historique une étape que l'objet n'a jamais franchie — le ticket aurait « été »
en cours alors qu'il n'y est jamais passé.

Le remède a été posé sur les **tickets** par #431 et **n'était couvert par aucun
test**. Il l'est ici. Ses jumeaux — publications (#433), calendrier (18/08/2026) —
sont partis avec leurs entités, devenues des affaires (#1091, #1092) : la règle
n'a plus qu'un lieu, et c'est ce que le cadre voulait.

⚠️ Ce test vérifie **le fait** (ce qui est écrit dans le fil), pas le symptôme
attendu : il relit les évolutions en base après l'appel, au lieu de se fier au
code de retour de l'endpoint (`standards/04` §14 — observer la chose, pas son
enregistrement).
"""

from __future__ import annotations


import json
import uuid

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    RoleUtilisateur,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.routers.tickets.mise_a_jour import update_ticket
from app.schemas import TicketUpdate
from tests.aides_base import compte

#  🔴 La purge passe par le code de PRODUCTION : supprimer une ligne sans ce
#  qui la référence est ce que les clés étrangères refusent (#546).
from tests.aides_purge import purger_ligne

PREFIXE_CORRECTION = "Correction"


@pytest.fixture()
def cs() -> Utilisateur:
    """Un membre du conseil syndical, seul habilité à corriger l'état."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        membre = compte(
            session,
            prefixe="cs",
            prenom="Camille",
            nom="Sorel",
            role=RoleUtilisateur.conseil_syndical,
        )
        yield membre
        purger_ligne(session, Utilisateur, membre.id)
        session.commit()


# ── Publications — retirées le 23/09/2026 ─────────────────────────────────────
#
#  Une actualité est une affaire de catégorie « Actualité » (#1091, lot 4) :
#  elle se corrige par le PATCH des affaires, que les tests ci-dessous gardent.
#  Elle n'a d'ailleurs plus d'état à corriger — c'est sa catégorie qui en décide.


# ── Tickets — le même remède, posé par #431 et jamais gardé ───────────────────


def test_patch_ticket_ecrit_une_correction_et_pas_une_transition(cs):
    with Session(engine) as session:
        ticket = Ticket(
            numero=f"T-{uuid.uuid4().hex[:6]}",
            titre="Ascenseur en panne",
            description="<p>Bloqué au 3ᵉ.</p>",
            categorie="panne",
            statut="ouvert",
            auteur_id=cs.id,
            perimetre_cible=json.dumps(["résidence"], ensure_ascii=False),
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)

        update_ticket(
            ticket.id,
            TicketUpdate(statut="en_cours"),
            BackgroundTasks(),
            session,
            cs,
        )

        evols = session.exec(
            select(TicketEvolution).where(TicketEvolution.ticket_id == ticket.id)
        ).all()

        assert [e.type for e in evols] == ["commentaire"], (
            f"Une édition ne doit écrire aucune transition : {[e.type for e in evols]}."
        )
        assert (evols[0].contenu or "").startswith(PREFIXE_CORRECTION), evols[0].contenu
        assert "État :" in (evols[0].contenu or ""), evols[0].contenu
        assert session.get(Ticket, ticket.id).statut == "en_cours"

        for e in evols:
            session.delete(e)
        purger_ligne(session, Ticket, ticket.id)
        session.commit()


def test_patch_ticket_corriger_un_champ_ecrit_une_correction_et_rien_d_autre(cs):
    """Corriger la CATÉGORIE (ou tout autre champ) écrit UNE ligne de correction.

    Du 18/08/2026 (« corriger sa catégorie m'a créé un historique ! c'est à
    supprimer ») au 20/11/2026, rien ne s'écrivait sans changement d'état. Le prix :
    un prestataire ajouté sans toucher à l'état restait invisible, et la ligne
    précédente semblait nommer le mauvais (#2886). Décision de Philippe : « une
    correction doit toujours écrire sa ligne ».

    La ligne reste une CORRECTION : préfixée, sans `ancien_statut`/`nouveau_statut`
    (aucun jalon), et elle ne dit que ce qui a changé — les champs renvoyés à
    l'identique par le formulaire n'y figurent pas.
    """
    with Session(engine) as session:
        ticket = Ticket(
            numero=f"T-{uuid.uuid4().hex[:6]}",
            titre="Ascenseur en panne",
            description="<p>Bloqué au 3ᵉ.</p>",
            categorie="panne",
            statut="ouvert",
            auteur_id=cs.id,
            perimetre_cible=json.dumps(["résidence"], ensure_ascii=False),
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)

        #  Le formulaire d'édition renvoie TOUTES les sections à chaque
        #  enregistrement — c'est ce qui permet d'effacer un champ. On reproduit ce
        #  comportement : seule la catégorie diffère de l'existant.
        update_ticket(
            ticket.id,
            TicketUpdate(
                titre="Ascenseur en panne",
                description="<p>Bloqué au 3ᵉ.</p>",
                categorie="sinistre",
                perimetre_cible=["résidence"],
                photos_urls=[],
                fichiers_urls=[],
            ),
            BackgroundTasks(),
            session,
            cs,
        )

        evols = session.exec(
            select(TicketEvolution).where(TicketEvolution.ticket_id == ticket.id)
        ).all()
        assert [e.type for e in evols] == ["commentaire"], [(e.type, e.contenu) for e in evols]
        contenu = evols[0].contenu or ""
        assert contenu.startswith(PREFIXE_CORRECTION), contenu
        assert (evols[0].ancien_statut, evols[0].nouveau_statut) == (None, None)
        assert "catégorie" in contenu, contenu
        for intact in ("Titre", "titre", "Description", "description", "État", "périmètre"):
            assert intact not in contenu, f"« {intact} » n'a pas changé : {contenu}"
        #  Le fait, pas le symptôme : la correction a-t-elle été appliquée ?
        assert session.get(Ticket, ticket.id).categorie == "sinistre"

        purger_ligne(session, Ticket, ticket.id)
        session.commit()


def test_patch_ticket_sans_rien_changer_n_ecrit_rien(cs):
    """Réenregistrer à l'identique n'écrit rien — même quand l'état est renvoyé.

    C'est l'autre moitié du défaut du 18/08/2026 : quatre champs n'étaient PAS
    comparés à l'existant (description, périmètre, pièces jointes, photos) et un
    cinquième ne l'était pas non plus (« Saisi pour »). Leur seule présence dans le
    `PATCH` suffisait à écrire « modifié ». Corriger le seul périmètre inscrivait
    donc cinq mentions dont une seule était vraie.
    """
    with Session(engine) as session:
        ticket = Ticket(
            numero=f"T-{uuid.uuid4().hex[:6]}",
            titre="Porte du hall",
            description="<p>Grince.</p>",
            categorie="panne",
            #  « ouvert » et non « en_cours » : hors admin, le contenu d'un ticket
            #  ne se corrige que tant qu'il est ouvert — une fois le suivi engagé,
            #  réécrire le texte ferait mentir ce que le CS a lu avant d'agir.
            #  C'est une règle voulue, et mon premier jet du test l'ignorait.
            statut="ouvert",
            auteur_id=cs.id,
            perimetre_cible=json.dumps(["résidence"], ensure_ascii=False),
            photos_urls=json.dumps([], ensure_ascii=False),
            fichiers_urls=json.dumps([], ensure_ascii=False),
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)

        update_ticket(
            ticket.id,
            TicketUpdate(
                titre="Porte du hall",
                description="<p>Grince.</p>",
                categorie="panne",
                statut="ouvert",
                perimetre_cible=["résidence"],
                photos_urls=[],
                fichiers_urls=[],
                saisi_pour_user_id=None,
                saisi_pour_nom=None,
                saisi_pour_email=None,
            ),
            BackgroundTasks(),
            session,
            cs,
        )

        evols = session.exec(
            select(TicketEvolution).where(TicketEvolution.ticket_id == ticket.id)
        ).all()
        assert evols == [], (
            "Un enregistrement sans aucun changement ne doit rien écrire : "
            f"{[(e.type, e.contenu) for e in evols]}"
        )

        purger_ligne(session, Ticket, ticket.id)
        session.commit()
