"""Le point d'inscription du registre et sa base (R1 #1877, spec §4.11).

La base `plateforme` de chaque test est posée par SA chaîne de migrations
(`registre.migrer`) : le schéma testé est celui que la production recevra, et le
test compare ce schéma aux modèles.
"""

from __future__ import annotations

import json

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.registre import base, conditions, migrer, signature
from app.registre.contrat import VERSION_CONTRAT
from app.registre.modeles import (
    IDENTIFIANT_REFERENCE,
    AcceptationConditions,
    ContactInstallation,
    EtatInscription,
    Installation,
    registre_plateforme,
)
from app.registre.routeur import EN_TETE_SIGNATURE, PLAFOND_EN_ATTENTE, TAILLE_MAX
from tests.aides_registre import HOTE, registre_allume

@pytest.fixture
def plateforme(monkeypatch):
    """Une base `plateforme` migrée, et le registre allumé sous son nom dédié."""
    with registre_allume(monkeypatch) as moteur:
        yield moteur


def _demande(cle: str, **autres) -> dict:
    v = conditions.version_en_vigueur()
    return {
        "version_contrat": VERSION_CONTRAT,
        "conditions_acceptees": v,
        "empreinte_conditions": conditions.empreinte(v),
        "cle_publique": cle,
        "version_logicielle": "2.143.0",
        "administrateur": {"prenom": "Alix", "nom": "Exemple", "courriel": "alix@example.org"},
        **autres,
    }


def _envoyer(corps: dict, privee=None, *, hote=HOTE, signature_fausse=False):
    octets = json.dumps(corps).encode()
    sig = signature.signer(privee, octets) if privee is not None else ""
    if signature_fausse:
        sig = signature.signer(signature.generer_paire()[0], octets)
    return TestClient(app).post(
        "/plateforme/inscriptions",
        content=octets,
        headers={"host": hote, EN_TETE_SIGNATURE: sig, "content-type": "application/json"},
    )


def test_la_chaine_de_la_plateforme_pose_le_schema_des_modeles(plateforme):
    with plateforme.connect() as c:
        ecarts = compare_metadata(MigrationContext.configure(c), registre_plateforme.metadata)
    assert ecarts == [], f"migrations et modèles divergent : {ecarts}"


def test_registre_eteint_hors_de_la_reference(plateforme, monkeypatch):
    monkeypatch.setattr(base, "est_reference", lambda: False)
    privee, cle = signature.generer_paire()
    assert _envoyer(_demande(cle), privee).status_code == 404


def test_un_autre_nom_que_le_nom_dedie_rend_404(plateforme):
    privee, cle = signature.generer_paire()
    assert _envoyer(_demande(cle), privee, hote="5hostachy.example").status_code == 404


def test_inscription_signee_attribue_un_identifiant_et_archive_le_contrat(plateforme):
    privee, cle = signature.generer_paire()
    r = _envoyer(_demande(cle), privee)
    assert r.status_code == 201, r.text
    assert r.json() == {"identifiant": "CF-000001", "etat": "en_attente"}
    with Session(plateforme) as s:
        inst = s.exec(select(Installation).where(Installation.cle_publique == cle)).one()
        assert inst.etat == EtatInscription.en_attente
        assert inst.empreinte_cle == signature.empreinte(cle)
        contact = s.exec(select(ContactInstallation)).one()
        assert (contact.prenom, contact.courriel) == ("Alix", "alix@example.org")
        archive = s.exec(select(AcceptationConditions)).one()
        v = conditions.version_en_vigueur()
        assert archive.installation_id == inst.id and archive.version == v
        assert archive.texte == conditions.texte(v)
        assert archive.empreinte == conditions.EMPREINTES[v]
        assert archive.accepte_par == "Alix EXEMPLE <alix@example.org>"


def test_la_meme_cle_retrouve_la_meme_inscription(plateforme):
    privee, cle = signature.generer_paire()
    assert _envoyer(_demande(cle), privee).status_code == 201
    nouveau = {"prenom": "Alix", "nom": "Exemple", "courriel": "autre@example.org"}
    r = _envoyer(_demande(cle, administrateur=nouveau), privee)
    assert r.status_code == 200 and r.json()["identifiant"] == "CF-000001"
    with Session(plateforme) as s:
        assert s.exec(select(ContactInstallation)).one().courriel == "autre@example.org"
        #  Les mêmes conditions ne s'archivent pas deux fois.
        assert len(s.exec(select(AcceptationConditions)).all()) == 1


@pytest.mark.parametrize(
    "faute,code",
    [
        ("signature_absente", 401),
        ("signature_d_une_autre_cle", 401),
        ("conditions_perimees", 400),
        ("texte_different", 400),
        ("contrat_inconnu", 400),
        ("champ_hors_contrat", 422),
    ],
)
def test_une_demande_fautive_est_refusee_sans_rien_ecrire(plateforme, faute, code):
    privee, cle = signature.generer_paire()
    corps = _demande(cle)
    if faute == "conditions_perimees":
        corps["conditions_acceptees"] = 0
    elif faute == "texte_different":
        corps["empreinte_conditions"] = "0" * 64
    elif faute == "contrat_inconnu":
        corps["version_contrat"] = VERSION_CONTRAT + 1
    elif faute == "champ_hors_contrat":
        corps["mot_de_passe"] = "x"
    r = _envoyer(
        corps,
        None if faute == "signature_absente" else privee,
        signature_fausse=faute == "signature_d_une_autre_cle",
    )
    assert r.status_code == code
    #  Rien de ce que la demande contient ne revient dans le refus.
    assert "alix" not in r.text.lower()
    with Session(plateforme) as s:
        assert s.exec(select(Installation)).all() == []


def test_une_demande_trop_lourde_est_refusee(plateforme):
    privee, cle = signature.generer_paire()
    corps = _demande(cle, remplissage="x" * TAILLE_MAX)
    assert _envoyer(corps, privee).status_code == 413


def test_le_registre_ne_se_remplit_pas_au_dela_du_plafond(plateforme):
    with Session(plateforme) as s:
        for i in range(PLAFOND_EN_ATTENTE):
            s.add(Installation(identifiant=f"CF-9{i:05d}"))
        s.commit()
    privee, cle = signature.generer_paire()
    assert _envoyer(_demande(cle), privee).status_code == 503


def test_le_demarrage_inscrit_la_reference_une_fois(plateforme, monkeypatch):
    monkeypatch.setattr(migrer, "moteur", lambda: plateforme)
    monkeypatch.setattr(migrer, "registre_actif", lambda: True)
    assert migrer.preparer() == "pret"
    assert migrer.preparer() == "pret"
    with Session(plateforme) as s:
        ref = s.exec(select(Installation)).one()
        assert (ref.identifiant, ref.canal, ref.etat) == (
            IDENTIFIANT_REFERENCE,
            "main",
            EtatInscription.active,
        )


def test_le_demarrage_ne_fait_rien_registre_eteint(monkeypatch):
    monkeypatch.setattr(migrer, "registre_actif", lambda: False)
    assert migrer.preparer() == "eteint"


def test_un_registre_en_panne_ne_leve_pas(monkeypatch):
    """Le verdict le dit ; la résidence démarre quand même (`start.sh`)."""
    monkeypatch.setattr(migrer, "registre_actif", lambda: True)

    def _panne():
        raise RuntimeError("base injoignable")

    monkeypatch.setattr(migrer, "moteur", _panne)
    assert migrer.preparer() == "echec: RuntimeError"
