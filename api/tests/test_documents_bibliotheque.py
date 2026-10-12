"""Une pièce jointe n'entre PAS dans la bibliothèque documentaire (#390).

## Pourquoi ce garde-fou (27/08/2026)

`GET /documents` **sans filtre** rend toutes les lignes de la table, et c'est ce
que l'écran Résidence appelle pour son dépôt de plans et de règlements.

Le découpage d'origine de #390 proposait de créer une ligne `document` au moment
du téléversement, « sans rattachement, rattachée ensuite ». Deux conséquences que
personne n'aurait vues avant la production :

1. chaque photo jointe à un ticket serait apparue dans la bibliothèque, lisible de
   tous ceux qui y ont accès — c'est-à-dire la faille que #390 existe pour fermer,
   retournée contre elle-même ;
2. chaque fichier d'un formulaire **abandonné** y serait resté pour toujours, sans
   porteur, donc sans personne pour le supprimer.

Le rattachement est donc fourni **dès la création** — l'invariant de
`routers/documents.py` s'étend au lieu de se relâcher — et la bibliothèque exclut
explicitement ce qui porte un `ticket_id` ou un `evenement_id`.

⚠️ L'exclusion se fait au niveau de la REQUÊTE, pas du filtrage par visibilité.
`document_visible` répondrait « oui » à l'auteur du ticket, et ce serait juste :
la pièce jointe lui est bien lisible. Elle n'a pas sa place dans la bibliothèque
pour autant. Deux questions différentes, deux mécanismes.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import SQLModel, Session, delete

from app.database import engine
from app.models.core import (
    Document,
    Evenement,
    RoleUtilisateur,
    Ticket,
)
from app.routers.documents import list_documents, upload_document
from app.utils.horloge import maintenant
from tests.aides_base import compte


@pytest.fixture()
def bibliotheque():
    """Trois lignes : un document de dépôt, une pièce jointe de ticket, une d'événement."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.exec(delete(Document))
        admin = compte(
            session,
            prefixe="admin",
            prenom="A",
            nom="D",
            role=RoleUtilisateur.admin,
            roles_json="admin",
        )

        #  🔴 Les PORTEURS sont montés, pas inventés. La fixture écrivait
        #  `ticket_id=11` et `evenement_id=22` — deux identifiants tirés au
        #  hasard, sur des lignes qui n'existaient pas. Tant que SQLite ne
        #  vérifiait pas ses clés, la pièce jointe pointait dans le vide et le
        #  test passait quand même (#546).
        #
        #  ⚠️ Et ce n'est pas qu'une question de propreté : ce fichier éprouve
        #  précisément que la bibliothèque distingue un document de DÉPÔT d'une
        #  pièce JOINTE à un porteur. Faire reposer cette distinction sur un
        #  rattachement fictif, c'était mesurer la règle sur un cas qui ne peut
        #  pas se produire en production.
        #
        #  ⚠️ `ticket.numero` est UNIQUE — et c'est une CHAÎNE, pas un entier :
        #  la fixture tourne une fois par test, un numéro en dur passe au premier
        #  et refuse au second.
        porteur_ticket = Ticket(
            numero=uuid.uuid4().hex[:8],
            titre="Fuite au sous-sol",
            description="…",
            auteur_id=admin.id,
        )
        porteur_evenement = Evenement(
            titre="Visite de l'ascensoriste",
            debut=maintenant(),
            auteur_id=admin.id,
        )
        session.add_all([porteur_ticket, porteur_evenement])
        session.commit()
        session.refresh(porteur_ticket)
        session.refresh(porteur_evenement)

        #  Le document de dépôt porte une catégorie — c'est ce qui en fait un
        #  document de la bibliothèque, et non le fait d'exister.
        depot = Document(
            titre="Règlement de copropriété",
            fichier_nom="reglement.pdf",
            categorie_id=None,
            contrat_id=None,
            publication_id=None,
            publie_par_id=admin.id,
        )
        jointe_ticket = Document(
            titre="Photo de la fuite",
            fichier_nom="fuite.jpg",
            ticket_id=porteur_ticket.id,
            publie_par_id=admin.id,
        )
        jointe_evenement = Document(
            titre="Plan d'accès",
            fichier_nom="plan.pdf",
            evenement_id=porteur_evenement.id,
            publie_par_id=admin.id,
        )
        session.add_all([depot, jointe_ticket, jointe_evenement])
        session.commit()
        #  Les identifiants des PORTEURS sont rendus eux aussi : le test les
        #  écrivait en dur (11 et 22), donc il pariait sur les mêmes valeurs
        #  inventées que la fixture. Deux endroits à corriger ensemble, et rien
        #  ne le disait.
        ids = {
            "depot": depot.id,
            "ticket": jointe_ticket.id,
            "evenement": jointe_evenement.id,
            "porteur_ticket": porteur_ticket.id,
            "porteur_evenement": porteur_evenement.id,
        }
        yield admin, ids
    with Session(engine) as session:
        session.exec(delete(Document))
        session.commit()


def test_la_bibliotheque_ignore_les_pieces_jointes(bibliotheque):
    """Le fait, pas le symptôme : la ligne EXISTE, et n'est pas rendue ici."""
    admin, ids = bibliotheque
    with Session(engine) as session:
        rendus = {d.id for d in list_documents(session=session, user=admin)}

    assert ids["depot"] in rendus, "un document de dépôt doit rester dans la bibliothèque"
    assert ids["ticket"] not in rendus, "une pièce jointe de ticket n'est pas un document de dépôt"
    assert ids["evenement"] not in rendus


def test_les_pieces_jointes_se_lisent_par_leur_porteur(bibliotheque):
    """Exclues de la bibliothèque, mais jamais introuvables : c'est la nuance.

    Les exclure PARTOUT aurait rendu impossible d'afficher les pièces jointes
    d'un ticket — on aurait fermé la porte au lieu de la ranger.
    """
    admin, ids = bibliotheque
    with Session(engine) as session:
        du_ticket = {
            d.id
            for d in list_documents(ticket_id=ids["porteur_ticket"], session=session, user=admin)
        }
        de_l_evenement = {
            d.id
            for d in list_documents(
                evenement_id=ids["porteur_evenement"], session=session, user=admin
            )
        }

    assert du_ticket == {ids["ticket"]}
    assert de_l_evenement == {ids["evenement"]}


def test_une_ligne_sans_aucun_rattachement_est_refusee(bibliotheque):
    """🔴 L'INVARIANT, et c'est lui qui empêche les orphelines.

    Il portait trois rattachements ; il en porte huit (les trois fiches de
    Ma résidence depuis la migration 0276). Le relâcher — ce que le
    découpage d'origine impliquait — aurait autorisé une ligne que rien ne
    supprime et que `document_visible` ne sait pas protéger.
    """
    #  `upload_document` est une coroutine, et `pytest-asyncio` n'est pas installé
    #  dans ce projet : on la pilote par `asyncio.run`. Elle lève AVANT tout
    #  `await`, donc la boucle ne sert qu'à l'appeler.
    import asyncio

    from fastapi import HTTPException

    admin, _ = bibliotheque
    with Session(engine) as session:
        with pytest.raises(HTTPException) as leve:
            #  ⚠️ Les quatre rattachements sont passés EXPLICITEMENT à None : appelée
            #  hors de FastAPI, la fonction reçoit sinon ses objets `Form(None)`,
            #  qui sont VRAIS au sens booléen — la garde ne se déclencherait pas et
            #  le test échouerait plus loin, sur une requête SQL, en faisant croire
            #  à un défaut qui n'existe pas.
            asyncio.run(
                upload_document(
                    titre="Sans porteur",
                    categorie_id=None,
                    contrat_id=None,
                    ticket_id=None,
                    evenement_id=None,
                    document_parent_id=None,
                    diagnostic_rapport_id=None,
                    regle_residence_id=None,
                    file=None,
                    session=session,
                    user=admin,
                )
            )
    assert leve.value.status_code == 400
    assert "obligatoire" in str(leve.value.detail)
