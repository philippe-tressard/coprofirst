"""Les annexes des fiches de « Ma résidence » (migration 0276, `utils/annexes`).

Ce que ces tests tiennent — chaque point est une règle de `utils/annexes` :

1. une annexe se lit EXACTEMENT comme sa fiche, et pas autrement ;
2. elle n'entre pas dans la bibliothèque — la règle de #390, étendue ;
3. elle n'a qu'un porteur, jamais une annexe, jamais plus de `MAX_ANNEXES` ;
4. une fiche supprimée emporte ses annexes, fichiers compris ;
5. le fichier PRINCIPAL se remplace, et l'ancien s'efface après l'écriture.

Le disque n'est pas touché : la porte de téléversement et le stockage sont
remplacés par des doublures qui écrivent dans `tmp_path` et notent ce qu'on
efface. Ce qu'on éprouve ici est la règle, pas l'écriture — celle-là a ses
propres tests (`test_signature_fichiers.py`, `test_stockage_source_unique.py`).
"""

from __future__ import annotations

import asyncio
import io
import json

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.models.core import (
    CategorieDocument,
    DiagnosticRapport,
    DiagnosticType,
    Document,
    ProfilAccesDocument,
    RegleResidence,
    RoleUtilisateur,
    StatutUtilisateur,
)
from app.routers import diagnostics, documents, regles_residence
from app.utils import annexes
from app.utils.visibility import document_visible
from tests.aides_base import compte


class _Stockage:
    """Note les chemins effacés au lieu d'effacer."""

    def __init__(self):
        self.effaces: list[str] = []

    def supprimer_chemin(self, chemin):
        self.effaces.append(chemin)


@pytest.fixture()
def disque(tmp_path, monkeypatch):
    stockage = _Stockage()

    def televerser(file, raw_name, user=None):
        dest = tmp_path / f"{len(list(tmp_path.iterdir()))}-{raw_name}"
        dest.write_bytes(file.file.read())
        return str(dest)

    for module in (annexes, documents, diagnostics):
        monkeypatch.setattr(module, "stockage", lambda: stockage, raising=False)
    monkeypatch.setattr(annexes, "enregistrer_televersement", televerser)
    monkeypatch.setattr(documents, "enregistrer_televersement", televerser)
    return stockage


def _fichier(nom: str = "annexe.pdf") -> UploadFile:
    return UploadFile(
        file=io.BytesIO(b"%PDF-1.4 essai"),
        filename=nom,
        headers=Headers({"content-type": "application/pdf"}),
    )


def _deposer(session, user, **rattachement) -> Document:
    """`upload_document` hors de FastAPI : chaque `Form(None)` passé à None.

    ⚠️ Appelée sans eux, la fonction recevrait ses objets `Form(None)`, VRAIS au
    sens booléen — la garde des rattachements se tromperait de cas.
    """
    champs = dict.fromkeys(
        (
            "categorie_id",
            "contrat_id",
            "ticket_id",
            "evenement_id",
            "document_parent_id",
            "diagnostic_rapport_id",
            "regle_residence_id",
            "batiment_id",
            "lot_id",
            "annee",
            "date_ag",
            "batiments_ids_json",
            "perimetre_cible",
        )
    )
    champs.update(rattachement)
    return asyncio.run(
        documents.upload_document(
            titre="Annexe",
            description="",
            perimetre="résidence",
            file=_fichier(),
            background_tasks=None,
            session=session,
            user=user,
            **champs,
        )
    )


def _lister(session, user, **filtres):
    champs = dict.fromkeys(
        (
            "categorie_id",
            "contrat_id",
            "ticket_id",
            "evenement_id",
            "document_parent_id",
            "diagnostic_rapport_id",
            "regle_residence_id",
            "annexes_de",
        )
    )
    champs.update(filtres)
    return documents.list_documents(session=session, user=user, **champs)


@pytest.fixture()
def residence(session):
    """Un CS, un propriétaire, un locataire ; un plan lisible des seuls propriétaires."""
    cs = compte(session, prefixe="cs", role=RoleUtilisateur.admin, roles_json="admin")
    proprio = compte(
        session,
        prefixe="proprio",
        roles_json="propriétaire",
        statut=StatutUtilisateur.copropriétaire_résident,
    )
    locataire = compte(
        session,
        prefixe="locataire",
        roles_json="résident",
        statut=StatutUtilisateur.locataire,
    )
    profil = ProfilAccesDocument(
        code="proprietaires", libelle="Propriétaires", roles_autorises=json.dumps(["propriétaire"])
    )
    session.add(profil)
    session.commit()
    categorie = CategorieDocument(code="plan_residence", libelle="Plans", profil_acces_id=profil.id)
    session.add(categorie)
    session.commit()
    plan = Document(
        titre="Plan de masse",
        fichier_nom="plan.pdf",
        fichier_chemin="/tmp/plan.pdf",
        categorie_id=categorie.id,
        publie_par_id=cs.id,
    )
    regle = RegleResidence(titre="Couleur des volets", cree_par_id=cs.id)
    type_diag = DiagnosticType(code="dpe", nom="Essai", texte_legislatif="…")
    session.add_all([plan, regle, type_diag])
    session.commit()
    rapport = DiagnosticRapport(
        diagnostic_type_id=type_diag.id,
        titre="DPE 2025",
        fichier_nom="dpe.pdf",
        fichier_chemin="/tmp/dpe.pdf",
        publie_par_id=cs.id,
    )
    session.add(rapport)
    session.commit()
    return {
        "cs": cs,
        "proprio": proprio,
        "locataire": locataire,
        "plan": plan,
        "regle": regle,
        "rapport": rapport,
    }


# ── 1. Une annexe se lit comme sa fiche ──────────────────────────────────────


def test_l_annexe_d_un_plan_suit_la_lecture_du_plan(session, residence, disque):
    r = residence
    annexe = _deposer(session, r["cs"], document_parent_id=r["plan"].id)
    assert annexe.categorie_id is None
    assert document_visible(r["proprio"], r["plan"], session)
    assert document_visible(r["proprio"], annexe, session)
    #  🔴 Le locataire ne lit pas le plan : il ne lit pas davantage son annexe.
    assert not document_visible(r["locataire"], r["plan"], session)
    assert not document_visible(r["locataire"], annexe, session)


def test_une_annexe_de_regle_ou_de_rapport_se_lit_par_tout_compte(session, residence, disque):
    r = residence
    pour_regle = _deposer(session, r["cs"], regle_residence_id=r["regle"].id)
    pour_rapport = _deposer(session, r["cs"], diagnostic_rapport_id=r["rapport"].id)
    assert document_visible(r["locataire"], pour_regle, session)
    assert document_visible(r["locataire"], pour_rapport, session)


def test_une_annexe_dont_la_fiche_a_disparu_ne_se_lit_plus(session, residence, disque):
    r = residence
    orpheline = Document(
        titre="Orpheline",
        fichier_nom="o.pdf",
        fichier_chemin="/tmp/o.pdf",
        regle_residence_id=987654,
        publie_par_id=r["cs"].id,
    )
    assert not document_visible(r["locataire"], orpheline, session)


# ── 2. Hors de la bibliothèque ────────────────────────────────────────────────


def test_l_annexe_n_entre_pas_dans_la_bibliotheque(session, residence, disque):
    r = residence
    annexe = _deposer(session, r["cs"], document_parent_id=r["plan"].id)
    sans_filtre = {d.id for d in _lister(session, r["cs"])}
    assert r["plan"].id in sans_filtre
    assert annexe.id not in sans_filtre
    assert [d.id for d in _lister(session, r["cs"], document_parent_id=r["plan"].id)] == [annexe.id]
    assert [d.id for d in _lister(session, r["cs"], annexes_de="document")] == [annexe.id]


def test_les_annexes_d_une_rubrique_respectent_la_lecture(session, residence, disque):
    r = residence
    _deposer(session, r["cs"], document_parent_id=r["plan"].id)
    assert _lister(session, r["locataire"], annexes_de="document") == []
    assert len(_lister(session, r["proprio"], annexes_de="document")) == 1


def test_une_rubrique_inconnue_rend_404(session, residence):
    with pytest.raises(HTTPException) as leve:
        _lister(session, residence["cs"], annexes_de="publication")
    assert leve.value.status_code == 404


# ── 3. Un porteur, une profondeur, un plafond ─────────────────────────────────


def test_une_annexe_ne_porte_pas_de_categorie(session, residence, disque):
    r = residence
    with pytest.raises(HTTPException) as leve:
        _deposer(
            session,
            r["cs"],
            document_parent_id=r["plan"].id,
            categorie_id=r["plan"].categorie_id,
        )
    assert leve.value.status_code == 400


def test_une_annexe_ne_porte_pas_d_annexe(session, residence, disque):
    r = residence
    annexe = _deposer(session, r["cs"], document_parent_id=r["plan"].id)
    with pytest.raises(HTTPException) as leve:
        _deposer(session, r["cs"], document_parent_id=annexe.id)
    assert leve.value.status_code == 400


def test_une_fiche_porte_au_plus_dix_annexes(session, residence, disque):
    r = residence
    for _ in range(annexes.MAX_ANNEXES):
        _deposer(session, r["cs"], regle_residence_id=r["regle"].id)
    with pytest.raises(HTTPException) as leve:
        _deposer(session, r["cs"], regle_residence_id=r["regle"].id)
    assert leve.value.status_code == 400


def test_une_fiche_inexistante_rend_404(session, residence, disque):
    with pytest.raises(HTTPException) as leve:
        _deposer(session, residence["cs"], diagnostic_rapport_id=987654)
    assert leve.value.status_code == 404


# ── 4. La fiche emporte ses annexes ───────────────────────────────────────────


def test_supprimer_une_fiche_emporte_ses_annexes(session, residence, disque):
    r = residence
    a_plan = _deposer(session, r["cs"], document_parent_id=r["plan"].id)
    a_regle = _deposer(session, r["cs"], regle_residence_id=r["regle"].id)
    a_rapport = _deposer(session, r["cs"], diagnostic_rapport_id=r["rapport"].id)
    chemins = {a_plan.fichier_chemin, a_regle.fichier_chemin, a_rapport.fichier_chemin}
    ids = [a_plan.id, a_regle.id, a_rapport.id]

    documents.delete_document(r["plan"].id, session=session, user=r["cs"])
    regles_residence.delete_regle(r["regle"].id, session=session, _=r["cs"])
    diagnostics.delete_rapport(r["rapport"].id, session=session, _=r["cs"])

    assert all(session.get(Document, i) is None for i in ids)
    assert chemins <= set(disque.effaces)


# ── 5. Le fichier principal se remplace ───────────────────────────────────────


def test_remplacer_le_fichier_d_un_plan(session, residence, disque):
    r = residence
    remplace = documents.remplacer_fichier_document(
        r["plan"].id, file=_fichier("plan-2026.pdf"), session=session, user=r["cs"]
    )
    assert remplace.fichier_nom == "plan-2026.pdf"
    assert remplace.fichier_chemin != "/tmp/plan.pdf"
    assert disque.effaces == ["/tmp/plan.pdf"]


def test_seul_un_document_de_la_bibliotheque_se_remplace(session, residence, disque):
    r = residence
    annexe = _deposer(session, r["cs"], document_parent_id=r["plan"].id)
    with pytest.raises(HTTPException) as leve:
        documents.remplacer_fichier_document(
            annexe.id, file=_fichier(), session=session, user=r["cs"]
        )
    assert leve.value.status_code == 400


def test_remplacer_le_fichier_d_un_rapport(session, residence, disque):
    r = residence
    remplace = diagnostics.remplacer_fichier_rapport(
        r["rapport"].id, file=_fichier("dpe-2026.pdf"), session=session, user=r["cs"]
    )
    assert remplace.fichier_nom == "dpe-2026.pdf"
    assert disque.effaces == ["/tmp/dpe.pdf"]
