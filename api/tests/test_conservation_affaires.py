"""La conservation des affaires, lot L1 : la règle et le constat (#2014).

`utils/conservation_affaires` dit quand une affaire close échoit — en exercices
complets, selon sa catégorie — et le constat compte ce qui partira. Rien n'est
retiré : la route est en lecture seule, réservée à l'administrateur.
"""

from __future__ import annotations

import itertools
from datetime import date, datetime

import pytest
from sqlmodel import Session

from app.models.copropriete import Copropriete
from app.models.core import MessageTicket, RoleUtilisateur, Ticket, TicketEvolution
from app.models.documents import Document
from app.models.tickets import CategorieTicket
from app.utils import conservation_affaires as ca
from tests.aides_http import base_http, client_http


def test_chaque_categorie_a_sa_duree():
    """Une catégorie sans durée ferait conserver ses affaires sans limite, sans un mot."""
    assert set(ca.DUREES) == set(CategorieTicket)
    assert {t.exercices for t in ca.TYPES} == {10, 5, 2}
    assert {t for t in ca.DUREES.values()} == set(ca.TYPES)


def test_les_categories_du_bati_gardent_dix_exercices():
    assert ca.type_de("etude_travaux").exercices == 10
    assert ca.type_de(CategorieTicket.sinistre).exercices == 10
    assert ca.type_de("nuisance").exercices == 5
    assert ca.type_de("question").exercices == 2


@pytest.mark.parametrize(
    ("cloture", "exercices", "mois_debut", "attendu"),
    [
        #  Année civile : close en 2025, gardée 2 exercices → jusqu'au 31/12/2027.
        (date(2025, 6, 15), 2, None, (date(2028, 1, 1), "2025", "2027")),
        #  Les bornes : le 31/12 et le 1/1 ne tombent pas dans le même exercice.
        (date(2025, 12, 31), 5, None, (date(2031, 1, 1), "2025", "2030")),
        (date(2026, 1, 1), 5, None, (date(2032, 1, 1), "2026", "2031")),
        #  Un exercice qui commence en juillet : juin 2025 est dans 2024-2025.
        (date(2025, 6, 30), 10, 7, (date(2035, 7, 1), "2024-2025", "2034-2035")),
        (date(2025, 7, 1), 10, 7, (date(2036, 7, 1), "2025-2026", "2035-2036")),
    ],
)
def test_l_echeance_se_compte_en_exercices_complets(cloture, exercices, mois_debut, attendu):
    assert ca.echeance(cloture, exercices, mois_debut) == attendu


def test_une_affaire_ouverte_n_echoit_jamais():
    ouverte = Ticket(titre="t", description="d", statut="en_cours", categorie="panne")
    assert ca.jour_de_cloture(ouverte) is None


def test_une_actualite_se_date_de_sa_publication():
    publiee = Ticket(
        titre="t",
        description="d",
        statut="publie",
        categorie="actualite",
        cree_le=datetime(2025, 3, 10, 10),
    )
    assert ca.jour_de_cloture(publiee) == date(2025, 3, 10)


_NUMEROS = itertools.count(1)


def _affaire(session: Session, categorie: str, ferme_le: datetime, **champs) -> Ticket:
    ticket = Ticket(
        numero=f"TK-C{next(_NUMEROS)}",
        titre=f"Affaire {categorie}",
        description="d",
        categorie=categorie,
        statut="résolu",
        ferme_le=ferme_le,
        **champs,
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


def test_le_constat_groupe_et_pese_les_pieces_jointes(session, disque_jetable):
    """Photos, pièces du fil, des évolutions, documents rattachés : tous comptent."""
    (disque_jetable / "photo.jpg").write_bytes(b"x" * 100)
    (disque_jetable / "devis.pdf").write_bytes(b"y" * 50)
    (disque_jetable / "prive").mkdir()
    (disque_jetable / "prive" / "rapport.pdf").write_bytes(b"z" * 25)
    session.add(Copropriete(nom="Essai", adresse="1 rue de l'Essai", mois_debut_exercice=None))
    travaux = _affaire(
        session,
        "etude_travaux",
        datetime(2025, 5, 2, 9),
        photos_urls='["/uploads/photo.jpg"]',
        fichiers_urls='["/uploads/disparu.pdf"]',
    )
    session.add(
        MessageTicket(ticket_id=travaux.id, contenu="m", fichiers_urls='["/uploads/devis.pdf"]')
    )
    session.add(
        TicketEvolution(ticket_id=travaux.id, type="suite", fichiers_urls='["/uploads/photo.jpg"]')
    )
    session.add(
        Document(
            titre="Rapport",
            fichier_nom="rapport.pdf",
            fichier_cle="prive/rapport.pdf",
            ticket_id=travaux.id,
        )
    )
    _affaire(session, "panne", datetime(2025, 11, 3, 9))
    _affaire(session, "panne", datetime(2025, 2, 1, 9))
    absorbee = _affaire(session, "panne", datetime(2025, 2, 1, 9))
    absorbee.fusionnee_dans_id = travaux.id
    session.add(absorbee)
    session.add(
        Ticket(numero="TK-O1", titre="Ouverte", description="d", categorie="panne", statut="ouvert")
    )
    session.commit()

    entretien, bati = ca.constat(session)

    assert (entretien.type, entretien.exercice_cloture, entretien.affaires) == (
        ca.ENTRETIEN,
        "2025",
        2,
    )
    assert entretien.echoit_le == date(2031, 1, 1)
    assert (bati.type, bati.dernier_exercice_garde, bati.echoit_le) == (
        ca.TRAVAUX,
        "2035",
        date(2036, 1, 1),
    )
    #  La même photo, jointe deux fois, ne se compte qu'une fois ; un fichier
    #  absent du disque est dit, pas pesé.
    assert (bati.affaires, bati.fichiers, bati.octets, bati.absents) == (1, 3, 175, 1)


def test_la_route_est_reservee_a_l_administrateur_et_ne_retire_rien():
    with base_http() as moteur:
        with Session(moteur) as s:
            _affaire(s, "question", datetime(2025, 4, 1, 9))
        cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
        assert cs.get("/admin/conservation-affaires").status_code == 403
        admin, _ = client_http(moteur, RoleUtilisateur.admin)
        lu = admin.get("/admin/conservation-affaires").json()
        assert lu["application_active"] is False
        [echeance] = lu["echeances"]
        assert echeance["type"] == "breves" and echeance["echoit_le"] == "2028-01-01"
        assert echeance["affaires"] == 1 and echeance["exercices"] == 2
        assert admin.get("/admin/conservation-affaires").json() == lu
