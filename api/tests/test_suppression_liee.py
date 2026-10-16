"""Supprimer les enfants d'un objet avant l'objet — `suppression_liee` (#1569, #546).

Le module n'était nommé par aucun test (ses appelants — suppression d'un ticket,
d'un événement — le cachent). Il porte trois gestes, et une garantie : les `DELETE` des
enfants partent AVANT celui du parent (le module documente que SQLAlchemy n'ordonne que selon
les `Relationship` déclarées, et `Document` n'en porte aucune vers `Ticket`).

1. `supprimer_documents_de` — les documents d'UN porteur, fichier compris, sans toucher
   ceux d'un autre ; un fichier déjà absent du disque ne fait pas échouer ;
2. `supprimer_lignes_liees` — toutes les lignes de toutes les collections, comptées ;
3. `flush_si_necessaire` — n'émet les DELETE enfants que si des enfants partent ;
4. aucun des trois ne valide la transaction : l'appelant reste maître d'annuler.
"""

from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlmodel import Session, select

from app.models.core import Ticket, TicketEvolution
from app.models.documents import Document
from app.utils.suppression_liee import (
    flush_si_necessaire,
    supprimer_documents_de,
    supprimer_lignes_liees,
)
from tests.aides_base import compte, moteur_de_test

_numero = [0]


def _ticket(session, auteur) -> Ticket:
    _numero[0] += 1
    t = Ticket(
        numero=f"SL-{_numero[0]:04d}",
        titre="Porteur",
        description="…",
        auteur_id=auteur.id,
        perimetre_cible='["résidence"]',
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _document(session, auteur, disque_jetable, nom, *, ticket=None, ecrire=True) -> Document:
    chemin = disque_jetable / nom
    if ecrire:
        chemin.write_bytes(b"%PDF-1.4")
    doc = Document(
        titre=nom,
        fichier_nom=nom,
        fichier_cle=nom,
        publie_par_id=auteur.id,
        ticket_id=ticket.id if ticket else None,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def _document_en_attente(auteur) -> Document:
    return Document(titre="x", fichier_nom="x", publie_par_id=auteur.id)


@pytest.fixture()
def auteur(session):
    return compte(session, prefixe="sl")


# ── supprimer_documents_de ──────────────────────────────────────────────────


def test_les_documents_du_porteur_partent_avec_leur_fichier(session, auteur, disque_jetable):
    t = _ticket(session, auteur)
    doc = _document(session, auteur, disque_jetable, "constat.pdf", ticket=t)

    supprimes = supprimer_documents_de(session, "ticket_id", t.id)
    session.commit()

    assert supprimes == 1
    assert session.get(Document, doc.id) is None
    assert not (disque_jetable / "constat.pdf").exists(), (
        "un fichier sans ligne serait indestructible"
    )


def test_les_documents_d_un_autre_porteur_restent(session, auteur, disque_jetable):
    t, autre = _ticket(session, auteur), _ticket(session, auteur)
    _document(session, auteur, disque_jetable, "a.pdf", ticket=t)
    reste = _document(session, auteur, disque_jetable, "b.pdf", ticket=autre)
    libre = _document(session, auteur, disque_jetable, "libre.pdf")

    assert supprimer_documents_de(session, "ticket_id", t.id) == 1
    session.commit()

    assert session.get(Document, reste.id) is not None
    assert session.get(Document, libre.id) is not None
    assert (disque_jetable / "b.pdf").exists() and (disque_jetable / "libre.pdf").exists()


def test_un_porteur_sans_document_rend_zero(session, auteur):
    assert supprimer_documents_de(session, "ticket_id", _ticket(session, auteur).id) == 0


def test_un_fichier_deja_absent_du_disque_ne_fait_pas_echouer(session, auteur, disque_jetable):
    t = _ticket(session, auteur)
    doc = _document(session, auteur, disque_jetable, "perdu.pdf", ticket=t, ecrire=False)

    assert supprimer_documents_de(session, "ticket_id", t.id) == 1
    session.commit()

    assert session.get(Document, doc.id) is None


def test_plusieurs_documents_sont_comptes(session, auteur, disque_jetable):
    t = _ticket(session, auteur)
    for nom in ("1.pdf", "2.pdf", "3.pdf"):
        _document(session, auteur, disque_jetable, nom, ticket=t)

    assert supprimer_documents_de(session, "ticket_id", t.id) == 3


def test_la_colonne_porteuse_est_un_nom_de_champ_de_document(session):
    with pytest.raises(AttributeError):
        supprimer_documents_de(session, "colonne_inconnue", 1)


def test_supprimer_les_documents_ne_valide_pas_la_transaction(session, auteur, disque_jetable):
    """L'appelant peut tout annuler si une règle métier échoue ensuite."""
    t = _ticket(session, auteur)
    doc = _document(session, auteur, disque_jetable, "garde.pdf", ticket=t)

    supprimer_documents_de(session, "ticket_id", t.id)
    session.rollback()

    assert session.get(Document, doc.id) is not None


# ── supprimer_lignes_liees ──────────────────────────────────────────────────


def _evolutions(session, ticket, auteur, n: int) -> None:
    for i in range(n):
        session.add(
            TicketEvolution(
                ticket_id=ticket.id, type="commentaire", contenu=str(i), auteur_id=auteur.id
            )
        )
    session.commit()
    session.refresh(ticket)


def test_toutes_les_lignes_de_toutes_les_collections_sont_marquees(session, auteur):
    t = _ticket(session, auteur)
    _evolutions(session, t, auteur, 5)
    autres = [_document_en_attente(auteur) for _ in range(3)]
    session.add_all(autres)
    session.commit()

    total = supprimer_lignes_liees(session, t.evolutions, autres)
    session.commit()

    assert total == 8
    assert session.exec(select(TicketEvolution)).all() == []
    assert session.exec(select(Document)).all() == []


def test_chaque_ligne_est_supprimee_meme_quand_la_collection_se_modifie(session, auteur):
    """Parcourir une collection liée en la supprimant en saute un élément sur deux :
    elle est matérialisée par `list()` avant."""
    t = _ticket(session, auteur)
    _evolutions(session, t, auteur, 7)

    assert supprimer_lignes_liees(session, t.evolutions) == 7
    session.commit()

    assert session.exec(select(TicketEvolution)).all() == []


def test_sans_collection_ou_collections_vides_le_total_est_zero(session, auteur):
    assert supprimer_lignes_liees(session) == 0
    assert supprimer_lignes_liees(session, [], []) == 0
    assert supprimer_lignes_liees(session, _ticket(session, auteur).evolutions) == 0


# ── flush_si_necessaire ─────────────────────────────────────────────────────


def test_sans_enfant_a_supprimer_rien_n_est_emis(session, auteur):
    en_attente = _document_en_attente(auteur)
    session.add(en_attente)

    flush_si_necessaire(session)
    flush_si_necessaire(session, 0, 0)

    assert en_attente.id is None, "aucun flush : la ligne n'a pas encore d'identifiant"


def test_des_enfants_a_supprimer_declenchent_l_emission(session, auteur):
    en_attente = _document_en_attente(auteur)
    session.add(en_attente)

    flush_si_necessaire(session, 0, 2)

    assert en_attente.id is not None


# ── L'ordre, sous clés étrangères actives ───────────────────────────────────


@pytest.fixture()
def session_fk():
    with Session(moteur_de_test(cles_etrangeres=True)) as s:
        yield s


def _ticket_et_son_document(session, disque_jetable):
    auteur = compte(session, prefixe="fk")
    t = _ticket(session, auteur)
    _document(session, auteur, disque_jetable, "fk.pdf", ticket=t)
    return t


def _deletes_emis(session, geste) -> list[str]:
    """Les tables dont une ligne est supprimée, dans l'ORDRE où le SQL part."""
    tables: list[str] = []

    def _noter(conn, cursor, statement, *_):
        if statement.startswith("DELETE FROM"):
            tables.append(statement.split()[2])

    moteur = session.get_bind()
    event.listen(moteur, "before_cursor_execute", _noter)
    try:
        geste()
    finally:
        event.remove(moteur, "before_cursor_execute", _noter)
    return tables


def test_avec_flush_l_enfant_part_avant_le_parent(session_fk, disque_jetable):
    """L'ordre est celui que le module garantit : le document, puis le ticket — et la clé
    étrangère, active ici comme en production, ne refuse rien."""
    t = _ticket_et_son_document(session_fk, disque_jetable)
    ticket_id = t.id

    def _supprimer():
        n = supprimer_documents_de(session_fk, "ticket_id", ticket_id)
        flush_si_necessaire(session_fk, n)
        session_fk.delete(t)
        session_fk.commit()

    ordre = _deletes_emis(session_fk, _supprimer)

    assert ordre.index("document") < ordre.index("ticket"), ordre
    assert session_fk.get(Ticket, ticket_id) is None
    assert session_fk.exec(select(Document)).all() == []
