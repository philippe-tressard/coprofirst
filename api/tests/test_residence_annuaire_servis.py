"""Ma résidence et l'Annuaire : les règles d'affichage que l'API SERT (#2505).

L'app iOS ne parle qu'au contrat publié et ne recopie aucune règle du front
(`standards/09` §8, règle 1). Ce que le site calculait dans ses écrans — l'exercice
en clair, « Prénom NOM », l'étage, les numéros d'un champ téléphone, le lieu d'un
document, l'ordre des listes, le regroupement du carnet, le ton d'un verdict — se
calcule donc au serveur, et les deux clients le LISENT.

Un test par règle, le cas fautif d'abord : celui que le front tenait et que le
serveur rendait autrement (ou ne rendait pas).
"""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest
from sqlmodel import Session

from app.models.copropriete import Batiment, Copropriete
from app.models.core import Document, MembreCS, MembreSyndic, RoleUtilisateur
from app.models.gouvernance import GenreCivilite
from app.routers.documents_schemas import DocumentRead
from app.routers.reglement import QuestionReglementRead
from app.utils.carnet_affichage import (
    SANS_EQUIPEMENT,
    annees_du_carnet,
    entrees_de_l_annee,
    groupes_par_equipement,
)
from app.utils.dates_fr import libelle_exercice
from app.utils.etages import etage_label
from app.utils.noms import cle_de_classement
from app.utils.ordre_documents import ordonner
from app.utils.perimetres import perimetre_badge
from app.utils.question_reglement.format import TONS_VERDICT, VERDICTS, ton_verdict
from app.utils.telephones import telephones_de
from tests.aides_http import base_http, client_http


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


# ── L'exercice comptable (`libelleExercice`) ────────────────────────────────


def test_un_exercice_decale_se_nomme_par_ses_deux_mois():
    assert libelle_exercice(7) == "de juillet à juin"
    assert libelle_exercice(2) == "de février à janvier"
    assert libelle_exercice(12) == "de décembre à novembre"


@pytest.mark.parametrize("mois", [None, 1, 0, 13])
def test_sans_mois_ou_hors_bornes_l_exercice_est_l_annee_civile(mois):
    assert libelle_exercice(mois) == "année civile"


def test_la_fiche_de_la_residence_sert_l_exercice(moteur):
    with Session(moteur) as s:
        s.add(Copropriete(nom="Témoin", adresse="1 rue Témoin", mois_debut_exercice=7))
        s.commit()
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    r = http.get("/copropriete")
    assert r.status_code == 200, r.text
    assert r.json()["exercice_libelle"] == "de juillet à juin"


# ── L'étage, les numéros, le classement des noms ────────────────────────────


def test_l_etage_d_une_ligne_de_texte_porte_le_mot_etage():
    assert etage_label(2, suffixe=True) == "2ème étage"
    assert etage_label(1, suffixe=True) == "1er étage"
    #  Le rez-de-chaussée et le sous-sol se disent sans « étage », et sans
    #  suffixe rien ne change pour les appelants d'avant.
    assert etage_label(0, suffixe=True) == "RDC"
    assert etage_label(-1, suffixe=True) == "SS 1"
    assert etage_label(None, suffixe=True) == ""
    assert etage_label(2) == "2ème"


def test_un_champ_telephone_se_decoupe_sans_doublon_ni_vide():
    champ = "01 23 45 67 89, 06 12 34 56 78 ,01 23 45 67 89,, "
    assert telephones_de(champ) == ["01 23 45 67 89", "06 12 34 56 78"]
    assert telephones_de(None) == [] and telephones_de("") == []


def test_le_classement_ignore_la_casse_et_les_accents():
    noms = ["Faure", "Élodie", "durand", ""]
    ranges = sorted(noms, key=lambda n: cle_de_classement(None, n))
    assert ranges == ["durand", "Élodie", "Faure", ""]
    assert cle_de_classement("Paul", "MOREL") == cle_de_classement("paul", "Morel")


# ── L'annuaire (`GET /admin/annuaire`) ──────────────────────────────────────


def _annuaire_seme(moteur) -> None:
    """Le bâtiment D créé AVANT le A : l'ordre des identifiants n'est pas celui des noms."""
    with Session(moteur) as s:
        copro = Copropriete(nom="Témoin", adresse="1 rue Témoin")
        s.add(copro)
        s.flush()
        bat_d = Batiment(copropriete_id=copro.id, numero="D")
        bat_a = Batiment(copropriete_id=copro.id, numero="A")
        s.add_all([bat_d, bat_a])
        s.flush()
        s.add_all(
            [
                MembreCS(
                    genre=GenreCivilite.mr,
                    prenom="Paul",
                    nom="martin",
                    batiment_id=bat_d.id,
                    etage=2,
                ),
                MembreCS(
                    genre=GenreCivilite.mr,
                    prenom="Luc",
                    nom="Bernard",
                    batiment_id=bat_a.id,
                    etage=0,
                ),
                MembreCS(
                    genre=GenreCivilite.mlle, prenom="Claire", nom="Zeller", batiment_id=bat_a.id
                ),
                MembreCS(
                    genre=GenreCivilite.mme,
                    prenom="Anne",
                    nom="Robin",
                    batiment_id=bat_a.id,
                    etage=-1,
                ),
                MembreCS(genre=GenreCivilite.mme, prenom="Alice", nom="Durand"),
                MembreSyndic(
                    genre=GenreCivilite.mme,
                    prenom="Sophie",
                    nom="Lambert",
                    email="gestion@syndic.invalid",
                    telephone="01 23 45 67 89, 06 12 34 56 78, 01 23 45 67 89",
                ),
            ]
        )
        s.commit()


def test_le_conseil_se_classe_par_batiment_nomme_puis_civilite_puis_nom(moteur):
    """Le cas fautif : le serveur rangeait par IDENTIFIANT de bâtiment (D avant A)
    et mettait Mme et Mlle à égalité — l'écran les reclassait, l'app ne pouvait pas."""
    _annuaire_seme(moteur)
    http, _ = client_http(moteur, RoleUtilisateur.résident)
    membres = http.get("/admin/annuaire").json()["cs"]["membres"]
    assert [m["nom"] for m in membres] == ["Robin", "Zeller", "Bernard", "martin", "Durand"]


def test_chaque_personne_porte_son_nom_affiche_son_etage_et_ses_numeros(moteur):
    _annuaire_seme(moteur)
    http, _ = client_http(moteur, RoleUtilisateur.résident)
    annuaire = http.get("/admin/annuaire").json()
    cs = {m["nom"]: m for m in annuaire["cs"]["membres"]}
    assert cs["martin"]["nom_affiche"] == "Paul MARTIN"
    assert cs["martin"]["etage_libelle"] == "2ème étage"
    assert cs["Bernard"]["etage_libelle"] == "RDC"
    assert cs["Robin"]["etage_libelle"] == "SS 1"
    assert cs["Zeller"]["etage_libelle"] == ""
    (syndic,) = annuaire["syndic"]["membres"]
    assert syndic["nom_affiche"] == "Sophie LAMBERT"
    assert syndic["telephones"] == ["01 23 45 67 89", "06 12 34 56 78"]


def test_l_annuaire_ne_rend_aucune_donnee_de_plus_que_l_ecran(moteur):
    """Données personnelles : les champs servis sont ceux d'avant #2505, plus les
    règles calculées depuis eux — ni compte rattaché, ni ordre de gestion."""
    _annuaire_seme(moteur)
    http, _ = client_http(moteur, RoleUtilisateur.résident)
    annuaire = http.get("/admin/annuaire").json()
    assert set(annuaire["cs"]["membres"][0]) == {
        "id", "genre", "prenom", "nom", "batiment_id", "batiment_nom", "etage",
        "est_gestionnaire_site", "est_president", "photo_url",
        "nom_affiche", "etage_libelle",
    }  # fmt: skip
    assert set(annuaire["syndic"]["membres"][0]) == {
        "id", "genre", "prenom", "nom", "fonction", "email", "telephone",
        "est_principal", "photo_url",
        "nom_affiche", "telephones",
    }  # fmt: skip


def test_l_annuaire_reste_ferme_a_l_anonyme(moteur):
    http, _ = client_http(moteur, None)
    assert http.get("/admin/annuaire").status_code == 401


# ── Le lieu d'un document et l'ordre des rubriques ──────────────────────────


def _document(**champs) -> Document:
    return Document(**{"titre": "Doc", "fichier_nom": "d.pdf", **champs})


def test_le_perimetre_par_defaut_se_tait_un_autre_se_nomme(batiments):
    """Le cas fautif : le badge de la copropriété entière ne s'affiche pas."""
    assert perimetre_badge(["résidence"]) == ""
    assert perimetre_badge([]) == "" and perimetre_badge(None) == ""
    lu = DocumentRead.model_validate(
        _document(
            id=1,
            perimetre_cible=json.dumps([f"bat:{batiments[0]}"]),
            publie_le=datetime(2026, 1, 1),
        )
    )
    assert lu.perimetre_libelle and lu.perimetre_libelle == perimetre_badge(lu.perimetre_cible)
    assert lu.model_dump()["perimetre_libelle"] == lu.perimetre_libelle


def test_les_plans_se_rangent_copropriete_d_abord_puis_par_numero(moteur):
    """Le cas fautif : le bâtiment D (identifiant le plus petit) ne passe pas avant A."""
    with Session(moteur) as s:
        copro = Copropriete(nom="Témoin", adresse="1 rue Témoin")
        s.add(copro)
        s.flush()
        bat_d = Batiment(copropriete_id=copro.id, numero="D")
        bat_a = Batiment(copropriete_id=copro.id, numero="A")
        s.add_all([bat_d, bat_a])
        s.flush()
        docs = [
            _document(titre="D", batiment_id=bat_d.id),
            _document(titre="A", batiment_id=bat_a.id),
            _document(titre="Copro"),
        ]
        assert [d.titre for d in ordonner(s, "plan_residence", docs)] == ["Copro", "A", "D"]


def test_les_comptes_rendus_se_rangent_par_annee_puis_date_d_ag():
    jour = datetime(2026, 1, 10)
    docs = [
        _document(titre="2024", annee=2024, date_ag=date(2024, 6, 1), publie_le=jour),
        _document(titre="sans année", publie_le=jour),
        _document(titre="2025-mars", annee=2025, date_ag=date(2025, 3, 1), publie_le=jour),
        _document(titre="2025-juin", annee=2025, date_ag=date(2025, 6, 1), publie_le=jour),
        #  Sans date d'AG, celle du dépôt.
        _document(titre="2025-dépôt", annee=2025, publie_le=datetime(2025, 9, 1)),
    ]
    assert [d.titre for d in ordonner(None, "pv_ag", docs)] == [
        "2025-dépôt",
        "2025-juin",
        "2025-mars",
        "2024",
        "sans année",
    ]


def test_une_autre_categorie_garde_l_ordre_de_la_requete():
    docs = [_document(titre="b"), _document(titre="a")]
    assert ordonner(None, "reglement_copropriete", docs) == docs
    assert ordonner(None, None, docs) == docs


# ── Le carnet d'entretien ───────────────────────────────────────────────────


def _entree(date_: str, origine: str = "affaire", equipement: str | None = None) -> dict:
    return {"date": date_, "origine": origine, "equipement": equipement}


CARNET = [
    _entree("2026-05-02", equipement="ascenseur"),
    _entree("2025-11-20", equipement="toiture"),
    _entree("2025-03-01", equipement="ascenseur"),
    _entree("2019-01-01", origine="contrat", equipement="ascenseur"),
    _entree("2024-07-07"),
]


def test_le_filtre_par_annee_garde_les_contrats_en_vigueur():
    """Le cas fautif : un contrat signé en 2019 vaut en 2025 (décret n° 2001-477)."""
    de_2025 = entrees_de_l_annee(CARNET, "2025")
    assert [e["date"] for e in de_2025] == ["2025-11-20", "2025-03-01", "2019-01-01"]
    assert entrees_de_l_annee(CARNET, None) == CARNET == entrees_de_l_annee(CARNET, "")


def test_les_annees_proposees_sont_celles_des_faits_dates_sans_les_contrats():
    assert annees_du_carnet(CARNET) == ["2026", "2025", "2024"]
    assert annees_du_carnet([]) == []


def test_les_groupes_se_rangent_par_leur_fait_le_plus_recent():
    groupes = groupes_par_equipement(CARNET, {"ascenseur": "Ascenseur", "toiture": "Toiture"})
    assert [g["equipement_libelle"] for g in groupes] == ["Ascenseur", "Toiture", SANS_EQUIPEMENT]
    assert [e["date"] for e in groupes[0]["entrees"]] == ["2026-05-02", "2025-03-01", "2019-01-01"]
    assert groupes[2]["equipement"] is None


def test_le_carnet_est_type_et_refuse_une_annee_illisible(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    assert http.get("/carnet-entretien", params={"annee": "25"}).status_code == 422
    r = http.get("/carnet-entretien", params={"annee": "2025"})
    assert r.status_code == 200, r.text
    assert r.json() == {"entrees": [], "total": 0, "groupes": [], "annees": []}


def test_une_entree_du_carnet_porte_le_libelle_de_sa_categorie(arbre_vide):
    from app.utils.carnet_entretien import EntreeCarnet

    lue = EntreeCarnet(
        date_fait=date(2025, 3, 1), libelle="x", origine="affaire", categorie="panne"
    ).en_dict()
    assert lue["categorie_libelle"] == "Panne"
    assert lue["perimetre_libelle"] == ""
    contrat = EntreeCarnet(date_fait=date(2025, 3, 1), libelle="x", origine="contrat").en_dict()
    assert contrat["categorie_libelle"] == ""


# ── Le ton d'un verdict du règlement ────────────────────────────────────────


def test_chaque_verdict_a_son_ton_et_l_inconnu_se_lit_incertain():
    """Le cas fautif : l'app montrait une capsule neutre pour « Non »."""
    assert ton_verdict("non") == "danger"
    assert ton_verdict("oui") == "succes"
    assert ton_verdict("sous_conditions") == "alerte"
    assert ton_verdict("non_prevu") == "neutre"
    assert ton_verdict("quelque_chose") == "incertain"
    #  Un verdict neuf sans ton se verrait ici, pas sur l'écran.
    assert set(TONS_VERDICT) == set(VERDICTS)


def test_la_question_sert_le_ton_de_son_verdict():
    lue = QuestionReglementRead(
        id=1,
        question="q",
        verdict="non",
        verdict_libelle="Non",
        reponse="r",
        extraits=[],
        texte_id=1,
        texte_en_vigueur=True,
        cree_le=datetime(2026, 1, 1),
    )
    assert lue.model_dump()["verdict_ton"] == "danger"
