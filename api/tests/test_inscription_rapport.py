"""Le rapport nocturne d'une installation, de bout en bout (R3 #1879, spec §4.11).

- il se construit depuis le CONTRAT et ne porte aucune donnée de résident (D5) :
  la base de la copropriété est semée de résidents témoins, et aucune de leurs
  données ne doit se retrouver dans ce qui part ;
- la référence le range s'il est signé par la clé qu'elle connaît pour cet
  identifiant, et seulement alors ; elle ne garde que `rapports.CONSERVATION`.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app import contexte
from app.inscription import client, depot, rapport
from app.inscription.depot import Contact
from app.models.copropriete import Lot
from app.registre import rapports, signature
from app.registre.contrat import Rapport
from app.registre.modeles import Installation, RapportInstallation
from app.utils import horloge
from tests.aides_base import compte, moteur_de_test
from tests.aides_registre import installation_branchee

TEMOINS = ("Alix", "Durand", "temoin-rapport")


@pytest.fixture
def copropriete(monkeypatch, disque_jetable):
    """La base de LA copropriété servie, semée de résidents témoins et de deux lots."""
    moteur = moteur_de_test()
    with Session(moteur) as s:
        for _ in range(3):
            compte(s, prefixe=TEMOINS[2], prenom=TEMOINS[0], nom=TEMOINS[1])
        compte(s, prefixe=TEMOINS[2], prenom=TEMOINS[0], nom=TEMOINS[1], actif=False)
        s.add(Lot(numero="A1"))
        s.add(Lot(numero="A2"))
        s.commit()
    monkeypatch.setattr(contexte, "moteur", lambda: moteur)
    monkeypatch.setattr(contexte, "nouvelle_session", lambda: Session(moteur))
    (disque_jetable / "prive").mkdir()
    (disque_jetable / "prive" / "plan.pdf").write_bytes(b"x" * 2048)
    return moteur


@pytest.fixture
def registre(monkeypatch, tmp_path, copropriete):
    with installation_branchee(monkeypatch, tmp_path) as moteur:
        yield moteur


def test_le_rapport_compte_sans_rien_dire_des_residents(copropriete):
    construit = rapport.construire()
    Rapport.model_validate(construit.model_dump())  # le contrat, rien de plus
    (copro,) = construit.coproprietes
    assert (copro.lots, copro.utilisateurs_inscrits, copro.utilisateurs_actifs) == (2, 4, 3)
    texte = construit.model_dump_json()
    for temoin in TEMOINS:
        assert temoin not in texte, f"une donnée de résident part chez la référence : {temoin}"


def test_une_mesure_impossible_rend_inconnu_jamais_une_valeur(copropriete, monkeypatch):
    def panne(*_a, **_k):
        raise OSError("disque illisible")

    monkeypatch.setattr(rapport.shutil, "disk_usage", panne)
    h = rapport.hebergement()
    assert h.disque_total_mo is None and h.disque_occupe_mo is None
    #  Aucune sauvegarde réussie : « inconnue », pas une date inventée.
    assert rapport.construire().sauvegarde.derniere_reussie_le is None


def test_la_reference_range_le_rapport_signe(registre):
    client.inscrire(Contact(prenom="Alix", nom="Durand", courriel="alix@example.org"))
    client.envoyer_rapport()
    assert depot.lire().dernier_rapport_le is not None
    with Session(registre) as s:
        (ligne,) = s.exec(select(RapportInstallation)).all()
        assert Rapport.model_validate_json(ligne.corps).identite.identifiant == "CF-000001"
        assert "alix@example.org" not in ligne.corps  # le contact n'est pas dans le rapport


def test_un_rapport_signe_d_une_autre_cle_est_refuse(registre):
    client.inscrire(Contact(prenom="Alix", nom="Durand", courriel="alix@example.org"))
    (depot.dossier() / depot.CLE).unlink()  # une copie de l'état, sans la clé
    with pytest.raises(client.RegistreInjoignable, match="401"):
        client.envoyer_rapport()
    with Session(registre) as s:
        assert s.exec(select(RapportInstallation)).all() == []


def test_sans_inscription_aucun_rapport_ne_part(registre):
    with pytest.raises(client.RegistreInjoignable, match="non inscrite"):
        client.envoyer_rapport()


def test_les_rapports_anciens_sont_retires(registre):
    client.inscrire(Contact(prenom="Alix", nom="Durand", courriel="alix@example.org"))
    with Session(registre) as s:
        inst = s.exec(select(Installation).where(Installation.identifiant == "CF-000001")).one()
        s.add(
            RapportInstallation(
                installation_id=inst.id,
                recu_le=horloge.maintenant() - rapports.CONSERVATION - timedelta(days=1),
                corps="{}",
            )
        )
        s.commit()
    client.envoyer_rapport()
    with Session(registre) as s:
        assert len(s.exec(select(RapportInstallation)).all()) == 1


def test_la_cle_publique_de_l_installation_n_est_pas_dans_le_rapport(registre):
    """Le rapport se rattache par son IDENTIFIANT ; la clé se vérifie, elle ne voyage pas."""
    client.inscrire(Contact(prenom="Alix", nom="Durand", courriel="alix@example.org"))
    cle = signature.publique_de(depot.cle_privee())
    assert cle not in rapport.construire().model_dump_json()
