"""Les aides des tests d'affaire — créer, corriger, une Suite, un compte, une session.

Elles vivaient dans `test_intervenant_affaire.py`, et trois autres fichiers les
importaient DEPUIS un fichier de tests (`test_equipement_affaire`,
`test_suite_conseil`, `test_trace_droits`) : fusionner ou découper ce fichier-là
aurait cassé les trois. Elles vivent ici, comme `aides_badges.py`, plutôt que
d'être recopiées. `session` est une fixture : un fichier de tests l'IMPORTE
pour que pytest la trouve.

Elles passent par les VRAIES routes de création, de correction et de Suite.
La Suite était écrite deux fois (`test_suite_conseil`, `test_trace_droits`),
au texte du commentaire près (#1495).
"""

from __future__ import annotations

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, select

from app.database import engine
from app.models.core import StatutUtilisateur
from app.models.prestataires import ContratEntretien
from app.routers.tickets import crud, evolutions, mise_a_jour
from app.schemas import TicketCreate, TicketUpdate
from app.schemas_tickets import TicketEvolutionCreate
from app.seed import equipements_par_defaut
from app.utils.perimetres import arbre
from tests.aides_base import compte


@pytest.fixture()
def session(monkeypatch, batiments):
    monkeypatch.setattr(crud, "_notifier_cs_creation", lambda *a, **k: None, raising=False)
    arbre()
    with Session(engine) as s:
        #  Les équipements de départ, comme le seed les pose en production (#2442) :
        #  une affaire ne désigne qu'un équipement qui existe.
        equipements_par_defaut(s)
        s.commit()
        yield s
        #  Les contrats partent AVANT le patrimoine : la fixture `batiments`
        #  supprime la copropriété, et SQLAlchemy dénouerait alors leur
        #  `copropriete_id` (NOT NULL) — le test suivant tombait au montage.
        for c in s.exec(select(ContratEntretien)).all():
            s.delete(c)
        s.commit()


def _compte(session, *, role=None):
    """Un copropriétaire résident actif ; `role` le fait conseil, admin…"""
    return compte(
        session,
        prefixe="int",
        statut=StatutUtilisateur.copropriétaire_résident,
        roles_json=role.value if role else "résident",
    )


def _creer(session, user, **champs):
    corps = TicketCreate(titre="Visite ascenseur", description="Visite trimestrielle.", **champs)
    return crud.create_ticket(corps, BackgroundTasks(), session=session, user=user)


def _corriger(session, user, ticket_id, **champs):
    return mise_a_jour.update_ticket(
        ticket_id,
        TicketUpdate(**champs),
        BackgroundTasks(),
        session=session,
        user=user,
    )


def _suite(session, user, ticket_id, **champs):
    #  `type` se remplace : une Suite d'ÉTAT passe par la même aide.
    corps = TicketEvolutionCreate(
        **{"type": "commentaire", "contenu": "<p>Point d'étape.</p>", "notifier": False, **champs}
    )
    return evolutions.add_evolution(ticket_id, corps, BackgroundTasks(), session=session, user=user)
