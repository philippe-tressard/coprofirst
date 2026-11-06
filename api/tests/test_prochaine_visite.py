"""La prochaine visite d'un contrat suit ses affaires d'Entretien (#1092, lot 5b2 ; #1445).

Quand un Entretien est résolu, `app/utils/prochaine_visite` recalcule la
prochaine visite du contrat que l'affaire DÉSIGNE (`contrat_id`) — la règle de
l'ancien calendrier, qui suit désormais l'affaire. Une intervention hors contrat
n'y touche jamais, même si son titre cite le libellé du contrat.

La redirection des anciens liens `/calendrier#ev-N`, qui vivait dans ce fichier
sous le nom `test_redirection_evenements.py`, est éprouvée avec celle des
actualités dans `test_redirection_publications.py`.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlmodel import Session

from app.models.core import RoleUtilisateur, Ticket, Utilisateur
from app.models.prestataires import ContratEntretien, Prestataire
from app.utils.prochaine_visite import apres_cloture, date_prochaine_visite
from tests.aides_base import compte


@pytest.fixture(name="lecteur")
def lecteur_fixture(session: Session) -> Utilisateur:
    return compte(
        session, prefixe="r", nom="R", prenom="R", roles_json=RoleUtilisateur.résident.value
    )


@pytest.mark.parametrize(
    "unite, nombre, attendu",
    [
        ("semaines", 2, date(2026, 10, 7)),
        ("mois", 1, date(2026, 10, 23)),
        ("fois_par_an", 4, date(2026, 12, 23)),
        ("ans", 1, date(2027, 9, 23)),
    ],
)
def test_la_date_suit_la_frequence_du_contrat(unite, nombre, attendu):
    contrat = ContratEntretien(
        prestataire_id=1,
        libelle="x",
        type_equipement="autre",
        date_debut=date(2020, 1, 1),
        frequence_type=unite,
        frequence_valeur=nombre,
    )
    assert date_prochaine_visite(contrat, date(2026, 9, 23)) == attendu


@pytest.mark.parametrize(
    "unite, nombre, depuis, attendu",
    [
        #  Le jour se garde : une visite du 30 ou du 31 ne glisse plus au 28 (#2561).
        ("mois", 1, date(2026, 3, 30), date(2026, 4, 30)),
        ("mois", 2, date(2026, 3, 31), date(2026, 5, 31)),
        ("ans", 1, date(2026, 1, 30), date(2027, 1, 30)),
        ("fois_par_an", 4, date(2026, 8, 31), date(2026, 11, 30)),
        #  …et ne déborde que vers le dernier jour du mois d'arrivée.
        ("mois", 1, date(2027, 1, 31), date(2027, 2, 28)),
        ("mois", 1, date(2028, 1, 30), date(2028, 2, 29)),
    ],
)
def test_une_visite_du_30_ou_du_31_garde_son_jour(unite, nombre, depuis, attendu):
    contrat = ContratEntretien(
        prestataire_id=1,
        libelle="x",
        type_equipement="autre",
        date_debut=date(2020, 1, 1),
        frequence_type=unite,
        frequence_valeur=nombre,
    )
    assert date_prochaine_visite(contrat, depuis) == attendu


def test_un_entretien_sous_contrat_resolu_avance_la_visite_du_contrat(
    session: Session, lecteur: Utilisateur
):
    """Le contrat est celui que l'affaire DÉSIGNE (#1445), plus un rapprochement par le titre."""
    p = Prestataire(nom="Otis", specialite="ascenseur")
    session.add(p)
    session.commit()
    session.refresh(p)
    contrat = ContratEntretien(
        copropriete_id=1,
        prestataire_id=p.id,
        libelle="Ascenseur",
        type_equipement="ascenseur",
        date_debut=date(2020, 1, 1),
        frequence_type="mois",
        frequence_valeur=3,
        actif=True,
    )
    session.add(contrat)
    session.commit()
    session.refresh(contrat)
    t = Ticket(
        numero="TK-1",
        titre="Visite trimestrielle",
        description="x",
        categorie="entretien",
        statut="résolu",
        auteur_id=lecteur.id,
        prestataire_id=p.id,
        contrat_id=contrat.id,
        debut=datetime(2026, 9, 23, 10, 0),
    )
    session.add(t)
    session.commit()
    apres_cloture(t, session)
    assert contrat.prochaine_visite == date(2026, 12, 23)


def test_une_intervention_hors_contrat_ne_touche_pas_au_contrat(
    session: Session, lecteur: Utilisateur
):
    """🔴 Le cas que le rapprochement par le titre ratait (#1445) : un dépannage
    hors contrat, dont le titre cite le libellé du contrat et qui porte une
    fréquence, avançait la visite d'entretien."""
    p = Prestataire(nom="Sicli", specialite="incendie")
    session.add(p)
    session.commit()
    session.refresh(p)
    contrat = ContratEntretien(
        copropriete_id=1,
        prestataire_id=p.id,
        libelle="Extincteurs",
        type_equipement="autre",
        date_debut=date(2020, 1, 1),
        frequence_type="ans",
        frequence_valeur=1,
        actif=True,
    )
    session.add(contrat)
    t = Ticket(
        numero="TK-2",
        titre="Extincteurs — remplacement",
        description="x",
        categorie="entretien",
        statut="résolu",
        auteur_id=lecteur.id,
        prestataire_id=p.id,
        frequence_type="ans",
        frequence_valeur=1,
    )
    session.add(t)
    session.commit()
    apres_cloture(t, session)
    assert contrat.prochaine_visite is None
