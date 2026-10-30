"""La transcription d'un PV d'AG par l'assistant, puis sa relecture (29/10/2026).

Le routeur `routers/reglement_transcriptions.py` et le module
`utils/question_reglement/transcription.py`.

Ce qui est tenu ici :

- « Transcrire » ouvre une transcription à relire ; rien n'entre dans ce que lisent
  les questions avant la VALIDATION de l'administration ;
- le texte relu — corrigé — devient un fichier des décisions d'AG, daté de l'AG ;
- une transcription en cours ou à relire bloque la suivante ; une rejetée la permet ;
- la tâche quotidienne ne transcrit que les PV récents, jamais deux fois, et rien
  quand l'usage est éteint ;
- tout est à l'administration : le conseil est refusé.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app import contexte
from app.models.core import Document
from app.models.reglement import TranscriptionPV
from app.utils import horloge
from app.utils.question_reglement import transcription as tr
from app.utils.question_reglement.texte import CODE_CATEGORIE_AG
from tests.aides_reglement import categorie_reglement, joindre
from tests.aides_reglement import client_admin, client_cs
from tests.aides_reglement import assistant, moteur_fixture  # noqa: F401

#: Une transcription FICTIVE, telle que l'assistant la rendrait.
TRANSCRIPTION = (
    "## Résolution n° 7 — Fermeture des balcons\n\n"
    "⟦ PV — p. 3 ⟧\n\n"
    "Majorité de l'article 25. Adoptée.\n\n"
    "L'assemblée autorise la fermeture des balcons par des vérandas en aluminium de teinte "
    "grise, selon le modèle annexé au procès-verbal. " + "Texte de la résolution. " * 8
)


def _deposer_pv(http, moteur, date_ag: str = "2025-06-12") -> int:
    reponse = http.post(
        "/documents",
        data={
            "titre": f"PV de l'AG {date_ag}",
            "categorie_id": str(categorie_reglement(moteur, tr.CODE_PV, ["propriétaire"])),
            "date_ag": date_ag,
        },
        files={"file": ("pv.pdf", b"%PDF-1.4 proces-verbal fictif", "application/pdf")},
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["id"]


@pytest.fixture()
def pret(moteur, assistant, monkeypatch):
    #  La tâche de fond ouvre sa propre session : sur la base du test (même forme
    #  que `test_etat_descriptif_ia.py`).
    monkeypatch.setattr(contexte, "nouvelle_session", lambda: Session(moteur))
    assistant.reponses[tr.USAGE_TRANSCRIPTION_PV] = TRANSCRIPTION
    categorie_reglement(moteur, CODE_CATEGORIE_AG, [])
    return assistant


def test_transcrire_puis_valider_fait_entrer_les_decisions(moteur, pret):
    admin = client_admin(moteur)
    joindre(admin, moteur)
    pv_id = _deposer_pv(admin, moteur)
    assert admin.post(f"/reglement/transcriptions/pv/{pv_id}").status_code == 202
    (pv,) = admin.get("/reglement/transcriptions").json()["pvs"]
    ligne = pv["transcription"]
    assert ligne["statut"] == tr.A_RELIRE and ligne["statut_libelle"] == "À relire"
    #  Pas encore lue : la question ne voit que le règlement.
    admin.post("/reglement/questions", json={"question": "Puis-je fermer mon balcon ?"})
    assert "DECISIONS_AG" not in pret.messages[-1]
    relu = ligne["contenu"].replace("teinte grise", "teinte gris anthracite")
    valide = admin.post(f"/reglement/transcriptions/{ligne['id']}/valider", json={"contenu": relu})
    assert valide.status_code == 200 and valide.json()["statut"] == tr.VALIDEE
    admin.post("/reglement/questions", json={"question": "Puis-je fermer mon balcon ?"})
    assert "# Assemblée générale du 12 juin 2025" in pret.messages[-1]
    assert "teinte gris anthracite" in pret.messages[-1]
    with Session(moteur) as s:
        (doc,) = s.exec(
            select(Document).where(
                Document.categorie_id == categorie_reglement(moteur, CODE_CATEGORIE_AG, [])
            )
        ).all()
        assert doc.date_ag.isoformat() == "2025-06-12" and doc.fichier_nom.endswith(".md")


def test_une_transcription_a_relire_bloque_la_suivante_et_se_rejette(moteur, pret):
    admin = client_admin(moteur)
    pv_id = _deposer_pv(admin, moteur)
    admin.post(f"/reglement/transcriptions/pv/{pv_id}")
    assert admin.post(f"/reglement/transcriptions/pv/{pv_id}").status_code == 409
    ligne = admin.get("/reglement/transcriptions").json()["pvs"][0]["transcription"]
    assert admin.delete(f"/reglement/transcriptions/{ligne['id']}").status_code == 204
    assert admin.post(f"/reglement/transcriptions/pv/{pv_id}").status_code == 202


def test_une_reponse_sans_resolution_est_un_echec(moteur, pret):
    pret.reponses[tr.USAGE_TRANSCRIPTION_PV] = "Je ne peux pas lire ce document."
    admin = client_admin(moteur)
    pv_id = _deposer_pv(admin, moteur)
    admin.post(f"/reglement/transcriptions/pv/{pv_id}")
    ligne = admin.get("/reglement/transcriptions").json()["pvs"][0]["transcription"]
    assert ligne["statut"] == tr.ECHEC and "aucune résolution" in ligne["erreur"]


def test_seul_un_pv_se_transcrit(moteur, pret):
    admin = client_admin(moteur)
    reponse = joindre(admin, moteur)
    assert admin.post(f"/reglement/transcriptions/pv/{reponse.json()['id']}").status_code == 400


def test_le_conseil_ne_transcrit_ni_ne_valide(moteur, pret):
    admin, cs = client_admin(moteur), client_cs(moteur)
    pv_id = _deposer_pv(admin, moteur)
    assert cs.get("/reglement/transcriptions").status_code == 403
    assert cs.post(f"/reglement/transcriptions/pv/{pv_id}").status_code == 403


def test_la_tache_ne_transcrit_que_les_pv_recents_et_une_fois(moteur, pret):
    admin = client_admin(moteur)
    recent = _deposer_pv(admin, moteur, "2025-06-12")
    ancien = _deposer_pv(admin, moteur, "2019-05-20")
    with Session(moteur) as s:
        doc = s.get(Document, ancien)
        doc.publie_le = horloge.maintenant() - tr.AGE_MAX_AUTO - timedelta(days=1)
        s.add(doc)
        s.commit()
        assert tr.traiter_file(s) == {"a_relire": 1, "echecs": 0}
        assert tr.traiter_file(s) == {"a_relire": 0, "echecs": 0}
        lignes = s.exec(select(TranscriptionPV)).all()
    assert [ligne.pv_id for ligne in lignes] == [recent]
    assert pret.usages == [tr.USAGE_TRANSCRIPTION_PV]


def test_la_tache_ne_fait_rien_quand_l_usage_est_eteint(moteur, pret):
    pret.pret = False
    _deposer_pv(client_admin(moteur), moteur)
    with Session(moteur) as s:
        assert tr.traiter_file(s) == {"a_relire": 0, "echecs": 0}
    assert pret.usages == []


@pytest.mark.parametrize(
    "brut", ["```markdown\n" + TRANSCRIPTION + "\n```", TRANSCRIPTION], ids=["cloture", "nu"]
)
def test_la_cloture_d_un_bloc_de_code_est_retiree(brut):
    assert tr.nettoyer(brut) == TRANSCRIPTION.strip()


def test_une_reponse_trop_courte_n_est_pas_une_transcription():
    with pytest.raises(ValueError):
        tr.nettoyer("## Résolution 1")
