"""L'avis d'une question au règlement : synthèse courte à renvois (08/11/2026, #2597).

Ce qui est tenu ici :

- la RUBRIQUE d'un extrait — le « § » du recueil, qui n'a pas d'articles numérotés —
  est le chemin des titres qui le contiennent, déduit du texte par le code ;
- le RENVOI d'un extrait (`R1`, `AG2`) est celui que le modèle propose quand il est
  cohérent avec la source retrouvée par le code, sinon un numéro attribué ;
- un renvoi cité par l'avis sans extrait derrière est relevé ;
- les renvois ne fuient ni dans l'aperçu, ni dans le fil, ni dans la FAQ ;
- le format demandé au modèle réclame les renvois, et un avis d'avant se relit.
"""

from __future__ import annotations

import json

from app.utils.question_reglement.extraits import (
    Extrait,
    attribuer_renvois,
    renvois_cites,
    renvois_sans_extrait,
    sans_renvois,
    verifier,
)
from app.utils.question_reglement.format import FORMAT_REPONSE, lire_reponse
from tests.aides_reglement import CITATION_VRAIE, client_admin, joindre
from tests.aides_reglement import assistant, moteur_fixture  # noqa: F401

#: Un recueil FICTIF à trois niveaux de titres, puis une AG fictive.
RECUEIL = (
    "# LIVRE I — Règlement fictif (1 janvier 1990)\n\n"
    "## CHAPITRE DEUX : CHARGES\n\n"
    "### ASSURANCES\n\n"
    "⟦ RCP 1990 — PDF p. 30 ⟧\n\n"
    "L'assurance de l'immeuble est souscrite par le syndic pour le compte de tous.\n\n"
    "### FRAIS\n\n"
    "Les frais de mutation restent à la charge du copropriétaire vendeur sans exception.\n\n"
    "## CHAPITRE TROIS : PARTIES COMMUNES\n\n"
    "Les couloirs ne peuvent servir de dépôt de quelque nature que ce soit.\n\n"
    "# Assemblée générale du 12 juin 2025\n\n"
    "## Résolution n° 7 — Fermeture des balcons\n\n"
    "L'assemblée autorise la fermeture des balcons par des vérandas en aluminium.\n"
)
ASSURANCE = "L'assurance de l'immeuble est souscrite par le syndic pour le compte de tous"
FRAIS = "Les frais de mutation restent à la charge du copropriétaire vendeur"
COULOIRS = "Les couloirs ne peuvent servir de dépôt de quelque nature"
BALCONS = "L'assemblée autorise la fermeture des balcons par des vérandas"
DEBUT_AG = RECUEIL.index("# Assemblée générale")


def _verifie(*citations_et_renvois):
    bruts = [{"citation": c, "renvoi": r} for c, r in citations_et_renvois]
    return verifier(RECUEIL, bruts, DEBUT_AG)


# ── La rubrique ────────────────────────────────────────────────────────────


def test_la_rubrique_est_le_chapitre_puis_la_section():
    assurance, frais = _verifie((ASSURANCE, "R1"), (FRAIS, "R2"))
    assert assurance.rubrique == "CHAPITRE DEUX : CHARGES › ASSURANCES"
    assert frais.rubrique == "CHAPITRE DEUX : CHARGES › FRAIS"


def test_un_extrait_sans_section_prend_son_chapitre_seul_et_ne_garde_pas_la_section_d_avant():
    (couloirs,) = _verifie((COULOIRS, "R1"))
    assert couloirs.rubrique == "CHAPITRE TROIS : PARTIES COMMUNES"


def test_la_rubrique_d_une_decision_d_ag_est_sa_resolution():
    (balcons,) = _verifie((BALCONS, "AG1"))
    assert balcons.source == "ag"
    assert balcons.acte == "Assemblée générale du 12 juin 2025"
    assert balcons.rubrique == "Résolution n° 7 — Fermeture des balcons"


def test_un_extrait_non_retrouve_n_a_ni_rubrique_ni_source():
    (faux,) = _verifie(("Une phrase que le texte ne contient pas du tout", "R1"))
    assert faux.verifie is False and faux.rubrique is None and faux.source is None


# ── Le renvoi ──────────────────────────────────────────────────────────────


def test_le_renvoi_propose_par_le_modele_est_garde_quand_il_est_coherent():
    assurance, balcons = _verifie((ASSURANCE, "R3"), (BALCONS, "AG2"))
    assert (assurance.renvoi, balcons.renvoi) == ("R3", "AG2")


def test_un_renvoi_incoherent_ou_en_double_est_remplace_par_le_premier_numero_libre():
    #  L'extrait d'AG est annoncé « R1 » : le code a retrouvé une décision, c'est AG1.
    #  Le second « R1 » est un doublon : R2.
    ag, a, b, sans = _verifie((BALCONS, "R1"), (ASSURANCE, "R1"), (FRAIS, "R1"), (COULOIRS, ""))
    assert ag.renvoi == "AG1"
    assert a.renvoi == "R1" and b.renvoi == "R2"
    assert sans.renvoi == "R3"


def test_le_renvoi_se_lit_avec_ses_crochets_ses_espaces_et_sa_casse():
    (e,) = _verifie((ASSURANCE, " [r 2] "))
    assert e.renvoi == "R2"


def test_un_extrait_non_retrouve_se_range_avec_le_reglement():
    sortie = attribuer_renvois(
        [Extrait("x", "", "", verifie=False, renvoi="AG1"), Extrait("y", "", "", verifie=False)]
    )
    assert [e.renvoi for e in sortie] == ["R1", "R2"]


# ── Les renvois d'un texte ─────────────────────────────────────────────────


def test_les_renvois_cites_sont_lus_seuls_ou_groupes_sans_doublon():
    texte = "<p>Oui [R2], sous condition [AG1].</p><ul><li>Voir [R2, R3] et [AG1].</li></ul>"
    assert renvois_cites(texte, None, "<p>[AG2]</p>") == ["R2", "AG1", "R3", "AG2"]
    assert renvois_cites("<p>Un [crochet] ou [R] ou [AG] ou [Rx].</p>") == []


def test_un_renvoi_sans_extrait_derriere_est_releve():
    textes = ["<p>Oui [R1] et [R4].</p>", "<li>[AG1]</li>", None]
    extraits = [{"renvoi": "R1"}, {"renvoi": "R2"}]
    assert renvois_sans_extrait(textes, extraits) == ["R4", "AG1"]


def test_sans_renvois_retire_les_crochets_et_l_espace_qui_les_precede():
    assert sans_renvois("<p>Oui [R2], sous condition [AG1] [R3, R4].</p>") == (
        "<p>Oui, sous condition.</p>"
    )
    assert sans_renvois("<p>Un [crochet] reste.</p>") == "<p>Un [crochet] reste.</p>"
    assert sans_renvois(None) == ""


# ── Le format demandé et relu ──────────────────────────────────────────────


def test_le_format_demande_une_synthese_courte_a_renvois_en_six_cles():
    assert "à six clés" in FORMAT_REPONSE
    for exigence in ("[R2]", "[AG1]", '"renvoi"', "trois ou quatre phrases"):
        assert exigence in FORMAT_REPONSE
    assert '"synthese"' not in FORMAT_REPONSE


def test_le_renvoi_du_modele_traverse_la_lecture_et_un_avis_d_avant_se_relit():
    lu = lire_reponse(
        json.dumps(
            {
                "verdict": "oui",
                "reponse": "<p>Oui [R1].</p>",
                "extraits": [{"citation": "Texte cité", "renvoi": "R1"}, {"citation": "Autre"}],
            }
        )
    )
    assert [e["renvoi"] for e in lu["extraits"]] == ["R1", ""]
    assert lu["synthese"] == ""


# ── Ce que l'API sert ──────────────────────────────────────────────────────


def _reponse_a_renvois() -> str:
    return json.dumps(
        {
            "verdict": "sous_conditions",
            "reponse": "<p>Oui, sans nuire à la tranquillité [R1]. Voir aussi [R9].</p>",
            "selon_reglement": "<ul><li>La profession libérale est tolérée [R1].</li></ul>",
            "extraits": [{"renvoi": "R1", "citation": CITATION_VRAIE, "reference": "p. 12"}],
            "reserves": "",
        }
    )


def test_l_avis_a_renvois_est_servi_avec_rubrique_renvoi_et_synthese_sans_crochets(
    moteur, assistant
):
    assistant.reponses["question_reglement"] = _reponse_a_renvois()
    admin = client_admin(moteur)
    joindre(admin, moteur)
    admin.post("/reglement/questions", json={"question": "Puis-je exercer ?"})
    (q,) = admin.get("/reglement/questions").json()
    (e,) = q["extraits"]
    assert e["renvoi"] == "R1" and e["rubrique"] == "DESTINATION DE L'IMMEUBLE"
    assert e["acte"] == "LIVRE I" and e["verifie"] is True
    assert "[R1]" in q["reponse"]
    assert q["reponse_sans_renvois"] == ("<p>Oui, sans nuire à la tranquillité. Voir aussi.</p>")
    assert q["renvois_sans_extrait"] == ["R9"]


def test_un_avis_d_avant_n_a_ni_renvoi_ni_rubrique_de_force_et_rien_a_signaler(moteur, assistant):
    admin = client_admin(moteur)
    joindre(admin, moteur)
    admin.post("/reglement/questions", json={"question": "Puis-je exercer ?"})
    (q,) = admin.get("/reglement/questions").json()
    #  Le modèle de test ne propose aucun renvoi : le code en attribue, la lecture reste valable.
    assert [e["renvoi"] for e in q["extraits"]] == ["R1", "R2"]
    assert q["reponse_sans_renvois"] == q["reponse"]
    assert q["renvois_sans_extrait"] == []


def test_le_fil_ne_montre_pas_les_renvois(moteur, assistant):
    assistant.reponses["question_reglement"] = _reponse_a_renvois()
    admin = client_admin(moteur)
    joindre(admin, moteur)
    admin.post("/reglement/questions", json={"question": "Puis-je exercer ?"})
    (carte,) = [i for i in admin.get("/flux").json()["items"] if i["type"] == "question_reglement"]
    assert (
        carte["detail"] == "Question au règlement — Oui, sans nuire à la tranquillité. Voir aussi."
    )
