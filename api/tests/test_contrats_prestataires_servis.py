"""Ce qu'un contrat et un prestataire DÉDUISENT est servi par l'API (#2507).

## 🔴 Le défaut

L'onglet Prestataires calculait dans le front la fréquence en clair
(`frequenceLabel`), le retard d'une visite (`minuitDuJour`), l'échéance d'un contrat
(`contratUrgence`), l'équipement effectif (`typeEquipementDuContrat`), la note
moyenne (`moyenneNotes`, et une seconde copie dans le Reporting) et la prochaine
visite d'un prestataire. L'app iOS ne recopie aucune règle du site : elle ne
montrait rien de tout cela. Ces cas tiennent ce que l'API sert désormais.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.core import ContratEntretien, NotationPrestataire, Prestataire
from app.routers.prestataires_lecture import lire_contrats, lister_prestataires
from app.utils import horloge
from app.utils.echeance_contrat import urgence_echeance, visite_en_retard
from app.utils.frequence_contrat import frequence_libelle
from app.utils.notes_prestataires import note_moyenne


#  ── frequenceLabel → `frequence_libelle` ───────────────────────────────────


@pytest.mark.parametrize(
    "type_, valeur, attendu",
    [
        ("semaines", 3, "↺ 3 sem."),
        ("mois", 1, "↺ Mensuel"),
        ("fois_par_an", 4, "↺ 4×/an"),
        ("ans", 1, "↺ tous les 1 an"),
        ("ans", 2, "↺ tous les 2 ans"),
    ],
)
def test_la_frequence_en_clair(type_, valeur, attendu):
    assert frequence_libelle(type_, valeur) == attendu


def test_sans_frequence_rien_plutot_qu_une_pastille_vide():
    """🔴 Le cas que l'app ne savait pas : une chaîne vide, l'écran se tait."""
    assert frequence_libelle(None, None) == ""


#  ── retard d'une visite → `en_retard` ──────────────────────────────────────


def test_le_jour_meme_n_est_pas_un_retard():
    """🔴 Avec l'instant au lieu du jour, une visite d'aujourd'hui était en retard à 00 h 01."""
    jour = date(2026, 11, 4)
    assert visite_en_retard(jour, aujourdhui=jour) is False
    assert visite_en_retard(jour - timedelta(days=1), aujourdhui=jour) is True
    assert visite_en_retard(None, aujourdhui=jour) is False


#  ── contratUrgence → `urgence_echeance` ────────────────────────────────────


def test_l_echeance_dans_son_preavis_est_signalee():
    """🔴 Trois mois avant le terme, le préavis court : c'est la décision à prendre."""
    jour = date(2026, 11, 4)
    assert urgence_echeance(date(2027, 1, 15), aujourdhui=jour) == "preavis"


def test_l_echeance_dans_l_annee_puis_plus_tard_puis_inconnue():
    jour = date(2026, 3, 1)
    assert urgence_echeance(date(2026, 12, 1), aujourdhui=jour) == "annee"
    #  Le terme tombe l'an prochain, mais le préavis commence cette année.
    assert urgence_echeance(date(2027, 2, 1), aujourdhui=jour) == "annee"
    assert urgence_echeance(date(2028, 6, 1), aujourdhui=jour) == "futur"
    assert urgence_echeance(None, aujourdhui=jour) is None


#  ── moyenneNotes → `note_moyenne` ──────────────────────────────────────────


def test_la_moyenne_arrondit_la_moitie_vers_le_haut():
    """🔴 `round(4.25, 1)` rend 4,2 en Python, le site écrivait 4,3 : deux notes."""
    assert note_moyenne(17, 4) == 4.3


def test_sans_avis_pas_de_note_et_jamais_zero():
    assert note_moyenne(0, 0) is None


#  ── la lecture : ce que la liste SERT ──────────────────────────────────────


def _poser(session):
    prest = Prestataire(nom="Ascenseurs Durand", specialite="vmc")
    session.add(prest)
    session.commit()
    hier = horloge.aujourd_hui() - timedelta(days=1)
    plus_tard = horloge.aujourd_hui() + timedelta(days=30)
    contrats = [
        ContratEntretien(
            copropriete_id=1,
            prestataire_id=prest.id,
            libelle="VMC",
            type_equipement="autre",
            date_debut=date(2026, 1, 1),
            frequence_type="mois",
            frequence_valeur=1,
            prochaine_visite=hier,
        ),
        ContratEntretien(
            copropriete_id=1,
            prestataire_id=prest.id,
            libelle="Toiture",
            type_equipement="toiture",
            date_debut=date(2026, 1, 1),
            prochaine_visite=plus_tard,
        ),
    ]
    session.add_all(contrats)
    session.add_all(
        [
            NotationPrestataire(prestataire_id=prest.id, note=n)
            for n in (4, 5, 4, 4)  # 17 / 4 = 4,25
        ]
    )
    session.commit()
    return prest, contrats, hier


def test_la_liste_des_contrats_sert_ce_qui_s_en_deduit(session):
    _, contrats, _ = _poser(session)
    vmc, toiture = lire_contrats(session, contrats)
    #  « autre » laisse parler la spécialité du prestataire ; un choix réel reste.
    assert (vmc.equipement_effectif, toiture.equipement_effectif) == ("vmc", "toiture")
    assert (vmc.en_retard, toiture.en_retard) == (True, False)
    assert (vmc.frequence_libelle, toiture.frequence_libelle) == ("↺ Mensuel", "")
    assert vmc.urgence_echeance in {"preavis", "annee", "futur"}
    assert vmc.date_preavis is not None


def test_la_liste_des_prestataires_sert_sa_note_et_sa_prochaine_visite(session):
    _, _, hier = _poser(session)
    (lu,) = lister_prestataires(session, archivees=False)
    assert (lu.note_moyenne, lu.nb_notations) == (4.3, 4)
    assert lu.prochaine_visite == hier


def test_un_contrat_enregistre_en_autre_prend_la_specialite():
    """Le formulaire le faisait avant d'envoyer : la règle vit au serveur (#2507)."""
    from sqlmodel import Session

    from app.models.core import RoleUtilisateur
    from app.models.equipements import Equipement
    from tests.aides_http import base_http, client_http

    with base_http() as moteur:
        with Session(moteur) as s:
            prest = Prestataire(nom="Ascenseurs Durand", specialite="toiture")
            #  La base des tests est neuve : les équipements proposés s'y posent.
            s.add_all([prest, Equipement(code="autre", libelle="Autre")])
            s.commit()
            pid = prest.id
        http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
        reponse = http.post(
            "/prestataires/contrats",
            json={
                "copropriete_id": 1,
                "prestataire_id": pid,
                "libelle": "Toiture",
                "date_debut": "2026-01-01",
            },
        )
    assert reponse.status_code == 201, reponse.text
    corps = reponse.json()
    assert (corps["type_equipement"], corps["equipement_effectif"]) == ("toiture", "toiture")
    #  La création rend la lecture entière : l'échéance n'y reste pas à sa valeur par défaut.
    assert corps["date_fin"] is not None
