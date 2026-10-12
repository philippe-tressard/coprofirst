"""Les endpoints DELETE tiennent-ils sous `foreign_keys=ON` ? (#546, étape 3)

## Pourquoi ce fichier

Le 30/08/2026, l'instruction de l'étape 3 a mesuré ceci :

    62 lignes `session.delete(...)` dans app/  →   2 exécutées par la suite
    32 endpoints DELETE exposés                →   0 testés

🔴 **Aucun endpoint de suppression n'avait de test.** Les 880 tests verts sous
les clés (étape 2, 29/08) ne prouvaient donc rien sur l'activation en
production : ils établissaient que les *fixtures* sont propres, pas que les
*suppressions* passent.

C'est `standards/04` §2 appliqué au ticket lui-même — un vert qu'on peut obtenir
sans exercer ce qu'on croit exercer.

## Ce que ces tests sont, et pourquoi ils SONT l'étape 3

Le ticket demandait de « décider l'`ON DELETE` par relation ». Cette décision n'a
pas à être devinée : elle se **constate**. La suite tourne déjà sous
`foreign_keys=ON` ; il suffit donc d'appeler la suppression avec ses enfants en
place.

  • le test passe   ⇒ la suppression est sûre, la question est close ;
  • le test échoue  ⇒ SQLite **nomme la contrainte**, c'est-à-dire précisément la
    relation dont il fallait décider.

⚠️ Chaque cas monte **tous** les enfants que les métadonnées déclarent, y compris
ceux que le code de suppression pourrait avoir oubliés. Un test qui ne monterait
que les enfants déjà gérés confirmerait le code au lieu de l'éprouver.

## Les fonctions sont appelées DIRECTEMENT, pas par HTTP

Ce qu'on éprouve ici est le comportement transactionnel sous les clés, pas
l'authentification — laquelle a ses propres tests (`test_autorisation.py`,
`test_droits_editer_commenter.py`). Passer par un client HTTP ajouterait un
montage de session et de cookies sans rien mesurer de plus sur la question posée.
"""

from datetime import date

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models.core import (
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.models.documents import Document

EMAIL = "suppression-546@test.fr"


def _purger(session: Session) -> None:
    """Nettoyage à l'ENTRÉE comme à la sortie, par le code de production.

    🔴 **`purger()` plutôt qu'une énumération à la main.** Ce module lit les
    MÉTADONNÉES : il découvre tout ce qui dépend de l'utilisateur de test, y
    compris les tables qu'un cas ajoutera demain. Une purge écrite à la main ici
    aurait dû énumérer tickets, documents, publications, télécommandes, vigiks,
    idées, sondages… et elle aurait manqué la suivante — c'est exactement le
    défaut que `purge_referentielle` a corrigé pour les fixtures (#546).

    ⚠️ Le `rollback()` d'abord : une session laissée en erreur par un test qui
    échoue refuse toute requête suivante. Ce fichier PROVOQUE des échecs — sans
    lui, le premier cas rouge empoisonnerait tous les suivants, et on lirait des
    erreurs de montage à la place des vrais verdicts.
    """
    from app.utils.purge_referentielle import purger

    session.rollback()
    for u in session.exec(select(Utilisateur).where(Utilisateur.email == EMAIL)).all():
        purger(session, "utilisateur", u.id)
    session.commit()


@pytest.fixture()
def contexte():
    """Un administrateur — les suppressions les plus larges lui sont réservées."""
    from sqlmodel import SQLModel

    from app.models.core import RoleUtilisateur

    #  Ce fichier ne dépend d'aucune autre fixture : il doit donc créer le schéma
    #  lui-même, sinon il ne passe que lorsqu'un test qui le fait a trié avant —
    #  et un test dont le résultat dépend de l'ordre alphabétique n'est pas un
    #  test (leçon de `conftest.py`, 15/08/2026).
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _purger(session)
        admin = Utilisateur(
            email=EMAIL,
            hashed_password="x",
            prenom="Adèle",
            nom="Admin",
            role=RoleUtilisateur.admin,
            actif=True,
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        yield session, admin
        _purger(session)


def _ticket(session: Session, admin: Utilisateur, suffixe: str) -> Ticket:
    t = Ticket(
        numero=f"TK-546-{suffixe}",
        titre="T",
        description="d",
        categorie="panne",
        auteur_id=admin.id,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def test_supprimer_un_ticket_qui_porte_une_evolution(contexte):
    """Le cas nominal : `delete_ticket` retire les évolutions avant le ticket."""
    from app.routers.tickets.crud import delete_ticket

    session, admin = contexte
    t = _ticket(session, admin, "evol")
    session.add(
        TicketEvolution(ticket_id=t.id, auteur_id=admin.id, type="commentaire", contenu="c")
    )
    session.commit()

    delete_ticket(t.id, session, admin)
    assert session.get(Ticket, t.id) is None


def test_supprimer_un_ticket_qui_porte_un_document(contexte):
    """🔴 LE CAS QUE LE CODE N'A PAS PRÉVU.

    `document.ticket_id` référence `ticket`, et `delete_ticket` retire les
    évolutions et les messages — **pas les documents**. Sous les clés, la
    suppression doit donc échouer.

    Ce test est écrit pour ÉCHOUER tant que le code n'a pas décidé du sort de
    cette relation. C'est ce que #546 appelle « décider par relation » : ici, un
    document attaché à un ticket supprimé n'a plus d'objet — il part avec lui.
    """
    from app.routers.tickets.crud import delete_ticket

    session, admin = contexte
    t = _ticket(session, admin, "doc")
    session.add(
        Document(
            titre="Devis",
            fichier_nom="devis.pdf",
            ticket_id=t.id,
            publie_par_id=admin.id,
        )
    )
    session.commit()

    delete_ticket(t.id, session, admin)
    assert session.get(Ticket, t.id) is None, "le ticket doit être supprimé"
    restants = session.exec(select(Document).where(Document.ticket_id == t.id)).all()
    assert restants == [], "les documents du ticket doivent partir avec lui"


# ── Les autres entités à risque ──────────────────────────────────────────────
#
#  🔴 CE QUE LE PREMIER CAS A APPRIS, et qui vaut pour tous les suivants :
#  SQLAlchemy n'ordonne les DELETE d'un même `commit()` que selon les
#  `Relationship` DÉCLARÉES. Une clé étrangère seule ne suffit pas — l'unité de
#  travail émet alors le DELETE du parent en premier, et la contrainte échoue
#  bien que l'enfant soit marqué pour suppression.
#
#  Relevé automatique des relations dans ce cas (30/08/2026) : **13**, dont
#  celles éprouvées ci-dessous. Les autres attendent leur test.


def _sondage(session: Session, admin: Utilisateur):
    from app.models.communaute import CommentaireSondage, OptionSondage, Sondage, VoteSondage

    s = Sondage(question="Q ?", auteur_id=admin.id)
    session.add(s)
    session.commit()
    session.refresh(s)
    o = OptionSondage(sondage_id=s.id, libelle="Oui")
    session.add(o)
    session.commit()
    session.refresh(o)
    session.add(VoteSondage(sondage_id=s.id, option_id=o.id, user_id=admin.id))
    session.add(CommentaireSondage(sondage_id=s.id, auteur_id=admin.id, contenu="c"))
    session.commit()
    return s


def test_supprimer_un_sondage_avec_ses_options_votes_et_commentaires(contexte):
    """Trois références entrantes, **toutes NOT NULL** — l'échec y serait certain.

    `commentaire_sondage` n'a pas de `Relationship` vers `Sondage` : c'est le
    même montage que `document` → `ticket`, donc le même piège d'ordre.
    """
    from app.models.communaute import Sondage
    from app.routers.sondages.crud import supprimer_sondage

    session, admin = contexte
    s = _sondage(session, admin)
    supprimer_sondage(s.id, session, admin)
    assert session.get(Sondage, s.id) is None


def test_supprimer_une_idee_avec_ses_votes(contexte):
    """`vote_idee.idee_id` est NOT NULL et sans `Relationship` vers `Idee`."""
    from app.models.communaute import Idee, VoteIdee
    from app.routers.idees import delete_idee

    session, admin = contexte
    idee = Idee(titre="T", description="d", auteur_id=admin.id)
    session.add(idee)
    session.commit()
    session.refresh(idee)
    session.add(VoteIdee(idee_id=idee.id, user_id=admin.id))
    session.commit()

    delete_idee(idee.id, session, admin)
    assert session.get(Idee, idee.id) is None


#  La suppression d'une PUBLICATION n'a plus de porte depuis le 23/09/2026 : une
#  actualité est une affaire (#1091), elle se supprime par `delete_ticket`, que
#  les deux cas du haut de ce fichier gardent — évolutions et documents compris.


#  🔴 LES DEUX SUPPRESSIONS D'ACCÈS ONT CHANGÉ DE PORTE le 15/09/2026.
#
#  Elles passaient par `routers/acces/resident` — un porteur retirait son propre
#  badge. Ces deux routes ont été **retirées** sur demande : *« un résident ne
#  peut pas supprimer un accès, il peut juste signaler qu'il a perdu »*. Le geste
#  n'a pas disparu : il vit chez l'administrateur, sur l'écran du parc.
#
#  ⚠️ Le test SUIT le geste, il ne disparaît pas avec la route. La question
#  qu'il pose — *`user_vigik.vigik_id` est NOT NULL et sans `Relationship` :
#  la suppression tient-elle sous `foreign_keys=ON` ?* — ne dépend pas de qui
#  appuie sur le bouton. La supprimer aurait rendu au relevé de l'étape 3 deux
#  lignes non couvertes, sans que rien ne le dise.


def test_supprimer_une_telecommande_resolue_par_un_import(contexte):
    """La ligne d'import qui pointe la télécommande se DÉLIE, elle ne part pas.

    (Ce cas éprouvait `user_telecommande`, NOT NULL et sans `Relationship` —
    table retirée le 23/09/2026, #1194. Le satellite qui reste est l'import.)
    """
    from app.models.core import StatutImport, Telecommande, TelecommandeImport
    from app.routers.acces.parc import supprimer_acces_admin
    from app.utils.types_acces import TELECOMMANDE

    session, admin = contexte
    tc = Telecommande(code="TC-546", user_id=admin.id)
    session.add(tc)
    session.commit()
    session.refresh(tc)
    ligne = TelecommandeImport(
        nom_proprietaire="X", reference="TC-546", statut=StatutImport.resolu, telecommande_id=tc.id
    )
    session.add(ligne)
    session.commit()

    supprimer_acces_admin(
        objet_id=tc.id,
        type_acces=TELECOMMANDE,
        session=session,
        user=admin,
    )
    assert session.get(Telecommande, tc.id) is None
    session.refresh(ligne)
    assert ligne.telecommande_id is None and ligne.statut == StatutImport.en_attente


def test_supprimer_un_vigik_resolu_par_un_import(contexte):
    """Même règle que la télécommande — les deux jumeaux, éprouvés tous deux."""
    from app.models.core import StatutImport, Vigik, VigikImport
    from app.routers.acces.parc import supprimer_acces_admin
    from app.utils.types_acces import VIGIK

    session, admin = contexte
    v = Vigik(code="VG-546", user_id=admin.id)
    session.add(v)
    session.commit()
    session.refresh(v)
    ligne = VigikImport(
        nom_proprietaire="X", code="VG-546", statut=StatutImport.resolu, vigik_id=v.id
    )
    session.add(ligne)
    session.commit()

    supprimer_acces_admin(
        objet_id=v.id,
        type_acces=VIGIK,
        session=session,
        user=admin,
    )
    assert session.get(Vigik, v.id) is None
    session.refresh(ligne)
    assert ligne.vigik_id is None and ligne.statut == StatutImport.en_attente


# ── Les deux dernières tables du relevé ──────────────────────────────────────
#
#  ⚠️ `option_sondage` n'apparaît pas ici, et ce n'est pas un oubli : elle n'a
#  aucun endpoint DELETE propre. Sa seule suppression a lieu dans
#  `supprimer_sondage`, déjà éprouvé plus haut — et vert. Une entrée du relevé
#  qui se referme sans écrire une ligne reste un résultat.


def test_supprimer_un_bail_avec_ses_objets_remis_et_ses_acces(contexte, batiments):
    """`remise_objet.bail_id` est NOT NULL ; vigik et télécommande se DÉLIENT.

    Le code traitait déjà les trois — ce test dit s'il le fait dans le bon ORDRE,
    ce que la lecture ne montre pas : aucune de ces tables n'a de `Relationship`
    vers `LocationBail`.
    """
    from app.models.copropriete import Lot
    from app.models.core import LocationBail, RemiseObjet, Telecommande, Vigik

    #  `bailleur.py` est devenu un paquet le 06/09/2026 (#806) : la suppression
    #  d'un bail vit dans le module qui porte son cycle de vie.
    from app.routers.bailleur.baux import supprimer_bail

    session, admin = contexte
    lot = Lot(batiment_id=batiments[0], numero="546")
    session.add(lot)
    session.commit()
    session.refresh(lot)
    bail = LocationBail(lot_id=lot.id, bailleur_id=admin.id, date_entree=date(2026, 1, 1))
    session.add(bail)
    session.commit()
    session.refresh(bail)
    session.add(RemiseObjet(bail_id=bail.id, libelle="Clé"))
    session.add(Vigik(code="VG-BAIL", user_id=admin.id, bail_id=bail.id))
    session.add(Telecommande(code="TC-BAIL", user_id=admin.id, bail_id=bail.id))
    session.commit()

    supprimer_bail(bail.id, admin, session)
    assert session.get(LocationBail, bail.id) is None
    #  Les accès ne partent PAS : ils appartiennent à la copropriété, pas au bail.
    #  Ils reviennent seulement « non confiés au locataire ».
    for modele, code in ((Vigik, "VG-BAIL"), (Telecommande, "TC-BAIL")):
        objet = session.exec(select(modele).where(modele.code == code)).first()
        assert objet is not None, f"{modele.__name__} ne doit pas être supprimé avec le bail"
        assert objet.bail_id is None and objet.chez_locataire is False
    session.delete(lot)
    session.commit()


def test_supprimer_un_document_cite_par_un_contrat(contexte):
    """🔴 `contrat_entretien.document_id` référence le document, et rien ne le délie.

    Le contrat, lui, doit SURVIVRE : un contrat d'entretien existe indépendamment
    du fichier scanné qu'on lui a joint. C'est l'inverse du document d'un ticket,
    qui n'existe que par son porteur — la décision dépend de ce que la ligne
    raconte, pas de la nullabilité de sa colonne.
    """
    from sqlmodel import Session as S  # noqa: F401  (lisibilité du montage)

    from app.models.copropriete import Copropriete
    from app.models.core import ContratEntretien, Prestataire
    from app.routers.documents import delete_document

    session, admin = contexte
    #  Ce test monte SA copropriété plutôt que d'emprunter celle de `batiments` :
    #  cette fixture-là vide le patrimoine à l'entrée comme à la sortie, et
    #  dépendre de son cycle de vie ferait échouer le montage selon l'ordre des
    #  tests — un test dont le résultat dépend de l'ordre n'est pas un test.
    copro = Copropriete(nom="Copro 546", adresse="1 rue du Test")
    session.add(copro)
    session.commit()
    session.refresh(copro)
    prest = Prestataire(nom="Ascenseurs 546", specialite="ascenseur")
    session.add(prest)
    session.commit()
    session.refresh(prest)
    doc = Document(
        titre="Contrat scanné",
        fichier_nom="c.pdf",
        publie_par_id=admin.id,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    contrat = ContratEntretien(
        copropriete_id=copro.id,
        prestataire_id=prest.id,
        libelle="Entretien ascenseur",
        document_id=doc.id,
    )
    session.add(contrat)
    session.commit()
    session.refresh(contrat)

    delete_document(doc.id, session, admin)
    assert session.get(Document, doc.id) is None
    survivant = session.get(ContratEntretien, contrat.id)
    assert survivant is not None, "le contrat ne part pas avec son fichier joint"
    assert survivant.document_id is None, "sa référence au document doit être déliée"
    session.delete(survivant)
    session.delete(prest)
    session.delete(copro)
    session.commit()
