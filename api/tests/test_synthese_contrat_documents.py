"""Ce qui part au modèle pour synthétiser un contrat — texte, fichier joint, écart, budget.

Sorti de `test_synthese_contrat.py`, qui dépassait 500 lignes avec #2890.

## Ce que ce test protège

1. **Un PDF sans texte part tel quel** : un contrat signé est numérisé, c'est
   le cas normal.
2. **Ce qui ne part pas est nommé**, avec son motif : l'encart de provenance
   le dit, sinon la synthèse se lit comme une lecture complète.
3. **Le budget de la requête garde les documents RÉCENTS** (#2890) : un avenant
   l'emporte sur le contrat initial, c'est donc l'initial qu'on tronque ou
   qu'on écarte — et le modèle reçoit le tout dans l'ordre chronologique.
"""

from __future__ import annotations

import base64
from datetime import datetime

import app.utils.synthese_contrat as mod
from app.utils.synthese_contrat import MOTIF_INTROUVABLE, MOTIF_TROP_LOURD, construire_matiere
from tests.aides_synthese_contrat import _config, _contrat, _document, session  # noqa: F401


#  ── Un PDF sans couche de texte part TEL QUEL ─────────────────────────────
#
#  🔴 C'est le cas NORMAL, pas l'exception : un contrat signé est numérisé. Les
#  deux PDF du contrat de porte de parking rendaient zéro caractère à `pypdf`
#  (mesuré en production le 11/09/2026, 2 pages et 1 page, 212 et 417 Ko).


def _pdf_sans_texte(tmp_path, nom="scan.pdf"):
    """Un PDF valide dont aucune page ne porte de texte — comme une numérisation."""
    from pypdf import PdfWriter

    chemin = tmp_path / nom
    ecrivain = PdfWriter()
    ecrivain.add_blank_page(width=595, height=842)
    with open(chemin, "wb") as f:
        ecrivain.write(f)
    return nom  # la clé : `tmp_path` est la racine du stockage (`disque_jetable`)


def test_un_pdf_sans_texte_est_JOINT_au_lieu_d_etre_abandonne(session, disque_jetable):
    c = _contrat(session)
    _document(session, c, titre="Contrat signé", fichier_cle=_pdf_sans_texte(disque_jetable))
    _config(session)
    m = construire_matiere(session, c, avec_document=True)
    assert len(m.fichiers) == 1
    assert m.joints == ("Contrat signé",)
    assert m.lus_en_texte == ()
    #  Et le message DIT au modèle de les lire lui-même, sinon il ne sait pas
    #  qu'il a reçu autre chose que du texte.
    assert "lis-les toi-même" in m.message
    #  ⚠️ Surtout, il ne porte PLUS la phrase qui ordonne de rendre les sections
    #  vides : elle ferait rendre « non précisé » alors que le contrat est joint.
    assert "Aucun texte de contrat n'a pu être lu" not in m.message


def test_un_pdf_LISIBLE_part_en_texte_et_pas_en_fichier(session, tmp_path):
    """Joindre un fichier dont le texte s'extrait coûterait bien plus cher pour
    exactement le même contenu."""
    c = _contrat(session)
    d = _document(session, c, titre="Contrat natif")
    _config(session)
    #  `texte_du_document` rend du texte : on simule un PDF avec couche texte.
    origine = mod.texte_du_document
    mod.texte_du_document = lambda doc: "ARTICLE 1 — Objet du contrat"
    try:
        m = construire_matiere(session, c, avec_document=True)
    finally:
        mod.texte_du_document = origine
    assert d.titre
    assert m.fichiers == ()
    assert m.lus_en_texte == ("Contrat natif",)


def test_un_fichier_ABSENT_est_ecarte_avec_son_motif(session):
    """Le chemin des fixtures est introuvable : ni texte, ni fichier joignable."""
    c = _contrat(session)
    _document(session, c, titre="Fantôme")
    _config(session)
    m = construire_matiere(session, c, avec_document=True)
    assert m.fichiers == ()
    assert m.ecartes == (("Fantôme", MOTIF_INTROUVABLE),)


def test_un_fichier_TROP_LOURD_n_est_pas_joint(session, disque_jetable, monkeypatch):
    """Une requête trop lourde est refusée par le service — et le base64
    l'alourdit encore d'un tiers. Mieux vaut l'écarter en le disant."""
    monkeypatch.setattr(mod, "MAX_OCTETS_JOINTS", 10)
    c = _contrat(session)
    _document(session, c, titre="Plan", fichier_cle=_pdf_sans_texte(disque_jetable))
    _config(session)
    m = construire_matiere(session, c, avec_document=True)
    assert m.fichiers == ()
    assert m.ecartes == (("Plan", MOTIF_TROP_LOURD),)


def test_un_scan_de_plus_de_4_Mio_part_s_il_tient_dans_la_requete(session, disque_jetable):
    """#2889 : un devis signé de 4,5 Mio était écarté par un plafond PAR fichier,
    alors que la requête le portait avec l'autre devis. Tailles du 22/11/2026 ;
    un troisième qui déborde est écarté SEUL, les deux autres restent joints.

    Le troisième est le plus ANCIEN : le budget garde les récents (#2890). Daté
    du 23, c'est le devis initial qu'il aurait évincé."""
    c = _contrat(session)
    for jour, nom, taille in (
        (1, "plan", 2 << 20),
        (15, "initial", 4_735_203),
        (22, "modifie", 984_716),
    ):
        (disque_jetable / nom).write_bytes(b"\0" * taille)  # illisible par pypdf, comme un scan
        _document(session, c, titre=nom, fichier_cle=nom, publie_le=datetime(2026, 11, jour))
    _config(session)
    m = construire_matiere(session, c, avec_document=True)
    assert m.joints == ("initial", "modifie")
    assert m.ecartes == (("plan", MOTIF_TROP_LOURD),)


# ── Le budget garde les documents RÉCENTS (#2890) ──────────────────────────
#
#  Les deux budgets (texte, fichiers joints) se dépensaient dans l'ordre
#  chronologique : sur un contrat qui débordait, l'avenant — le document qui
#  fait foi — était tronqué ou écarté au profit du contrat initial.


def test_le_budget_de_TEXTE_garde_l_avenant_recent_et_tronque_l_initial(session, monkeypatch):
    c = _contrat(session)
    _document(session, c, titre="Contrat initial", publie_le=datetime(2024, 1, 1))
    _document(session, c, titre="Avenant n° 1", publie_le=datetime(2026, 5, 1))
    textes = {
        "Contrat initial": "I" * mod.MAX_CARACTERES_DOCUMENT,
        "Avenant n° 1": "ARTICLE 6 — le prix annuel devient 1 234 €",
    }
    monkeypatch.setattr(mod, "texte_du_document", lambda doc: textes[doc.titre])
    _config(session)
    m = construire_matiere(session, c, avec_document=True)
    assert m.ecartes == ()
    #  L'avenant ENTIER ; l'initial tronqué, et annoncé comme tel.
    assert "« Avenant n° 1 » (déposé le 2026-05-01) ---\nARTICLE 6" in m.message
    assert "« Contrat initial » (déposé le 2024-01-01) — TRONQUÉ ---" in m.message
    #  Présentés dans l'ordre CHRONOLOGIQUE : ce qui vient après modifie ce qui précède.
    assert m.lus_en_texte == ("Contrat initial", "Avenant n° 1")
    assert m.message.index("« Contrat initial »") < m.message.index("« Avenant n° 1 »")


def test_le_budget_des_FICHIERS_garde_les_scans_recents_et_ecarte_l_initial(
    session, disque_jetable
):
    c = _contrat(session)
    for annee, nom, octet, taille in (
        (2020, "initial", b"\1", 6 << 20),  # 8 Mio en base64 : tout le budget à lui seul
        (2023, "conditions", b"\2", 1 << 20),
        (2026, "avenant", b"\3", 512 << 10),
    ):
        (disque_jetable / nom).write_bytes(octet * taille)  # illisible par pypdf, comme un scan
        _document(session, c, titre=nom, fichier_cle=nom, publie_le=datetime(annee, 1, 15))
    _config(session)
    m = construire_matiere(session, c, avec_document=True)
    assert m.ecartes == (("initial", MOTIF_TROP_LOURD),)
    #  Joints dans l'ordre CHRONOLOGIQUE, et chaque pièce reste en face de son titre.
    assert m.joints == ("conditions", "avenant")
    assert [base64.b64decode(f.donnees_b64)[:1] for f in m.fichiers] == [b"\2", b"\3"]
