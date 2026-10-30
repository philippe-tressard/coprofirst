"""Les questions au règlement lisent aussi les décisions d'AG (29/10/2026).

Ce qui est tenu ici :

- les décisions d'AG validées passent APRÈS le règlement (le règlement reste en
  cache), dans l'ordre des assemblées, chacune sous un titre posé par le code ;
- la méthode des AG ne s'ajoute à la consigne que si des décisions sont jointes ;
- l'avis garde ses sections ; un extrait se dit « règlement » ou « AG » selon sa
  POSITION dans le texte, et l'AG concernée se lit du titre, pas du modèle ;
- l'état descriptif ne lit que le règlement ;
- les décisions sont à l'administration seule, comme le règlement.
"""

from __future__ import annotations

import json

from sqlmodel import Session

from app.utils.question_reglement.format import METHODE_AG
from app.utils.question_reglement.texte import CODE_CATEGORIE_AG, assembler
from tests.aides_reglement import CITATION_VRAIE, categorie_reglement, joindre
from tests.aides_reglement import client_admin, client_cs
from tests.aides_reglement import assistant, moteur_fixture  # noqa: F401

#: Des décisions FICTIVES — aucune assemblée réelle n'entre dans le dépôt public.
DECISIONS_2025 = (
    "## Résolution n° 7 — Fermeture des balcons\n\n"
    "⟦ PV — p. 3 ⟧\n\n"
    "Majorité de l'article 25. Adoptée.\n\n"
    "L'assemblée autorise la fermeture des balcons par des vérandas en aluminium de teinte "
    "grise, selon le modèle annexé au procès-verbal.\n"
)
DECISIONS_2019 = (
    "## Résolution n° 4 — Local vélos\n\nAdoptée.\n\nLe local vélos est créé au sous-sol.\n"
)
CITATION_AG = (
    "L'assemblée autorise la fermeture des balcons par des vérandas en aluminium de teinte grise"
)


def _joindre_ag(http, moteur, contenu: str, nom: str, date_ag: str):
    return http.post(
        "/documents",
        data={
            "titre": nom,
            "categorie_id": str(categorie_reglement(moteur, CODE_CATEGORIE_AG, [])),
            "date_ag": date_ag,
        },
        files={"file": (nom, contenu.encode("utf-8"), "text/markdown")},
    )


def _reponse_en_sections() -> str:
    return json.dumps(
        {
            "verdict": "sous_conditions",
            "reponse": "<p>Oui, avec le modèle voté.</p>",
            "selon_reglement": "<p>Le modificatif exige une autorisation.</p>",
            "selon_ag": "<p>L'AG du 12 juin 2025 l'a donnée (résolution 7).</p>",
            "synthese": "<p>L'autorisation générale vaut pour tous les lots.</p>",
            "extraits": [
                {"citation": CITATION_VRAIE, "reference": "Livre I, p. 12"},
                {"citation": CITATION_AG, "reference": "AG 2025, résolution 7"},
            ],
            "reserves": "",
        }
    )


def test_les_decisions_passent_apres_le_reglement_dans_l_ordre_des_assemblees(moteur, assistant):
    admin = client_admin(moteur)
    joindre(admin, moteur)
    assert _joindre_ag(admin, moteur, DECISIONS_2025, "ag-2025.md", "2025-06-12").status_code == 201
    assert _joindre_ag(admin, moteur, DECISIONS_2019, "ag-2019.md", "2019-05-20").status_code == 201
    admin.post("/reglement/questions", json={"question": "Puis-je fermer mon balcon ?"})
    message = assistant.messages[0]
    assert (
        message.index("DESTINATION DE L'IMMEUBLE")
        < message.index("<<<DECISIONS_AG")
        < message.index("# Assemblée générale du 20 mai 2019")
        < message.index("# Assemblée générale du 12 juin 2025")
        < message.index("Question : Puis-je fermer mon balcon ?")
    )
    assert METHODE_AG in assistant.consignes[0]


def test_sans_decision_la_consigne_et_le_message_restent_ceux_du_reglement(moteur, assistant):
    admin = client_admin(moteur)
    joindre(admin, moteur)
    q = admin.post("/reglement/questions", json={"question": "Puis-je exercer ?"}).json()
    assert "DECISIONS_AG" not in assistant.messages[0]
    assert METHODE_AG not in assistant.consignes[0]
    assert [e["source"] for e in q["extraits"]] == [None, None]
    assert q["selon_ag"] is None and q["synthese"] is None


def test_l_avis_garde_ses_sections_et_chaque_extrait_sa_source(moteur, assistant):
    assistant.reponses["question_reglement"] = _reponse_en_sections()
    admin = client_admin(moteur)
    joindre(admin, moteur)
    _joindre_ag(admin, moteur, DECISIONS_2025, "ag-2025.md", "2025-06-12")
    admin.post("/reglement/questions", json={"question": "Puis-je fermer mon balcon ?"})
    (q,) = admin.get("/reglement/questions").json()
    assert q["selon_reglement"].startswith("<p>Le modificatif")
    assert "résolution 7" in q["selon_ag"]
    assert q["synthese"].startswith("<p>L'autorisation")
    reglement, decision = q["extraits"]
    assert reglement["source"] == "reglement" and reglement["acte"] == "LIVRE I"
    assert decision["verifie"] is True and decision["source"] == "ag"
    assert decision["acte"] == "Assemblée générale du 12 juin 2025"
    assert decision["page"] == "PV — p. 3"


def test_l_etat_descriptif_ne_lit_que_le_reglement(moteur, assistant):
    admin = client_admin(moteur)
    joindre(admin, moteur)
    _joindre_ag(admin, moteur, DECISIONS_2025, "ag-2025.md", "2025-06-12")
    with Session(moteur) as s:
        texte = assembler(s)
    assert "Résolution n° 7" not in texte.reglement
    assert "Résolution n° 7" in texte.contenu[texte.debut_ag :]


def test_les_decisions_sont_a_l_administration_seule(moteur, assistant):
    categorie_reglement(moteur, CODE_CATEGORIE_AG, [])
    admin, cs = client_admin(moteur), client_cs(moteur)
    assert admin.get("/reglement").json()["categorie_ag_id"] is not None
    assert cs.get("/reglement").json()["categorie_ag_id"] is None
    assert _joindre_ag(cs, moteur, DECISIONS_2025, "ag-2025.md", "2025-06-12").status_code == 403
