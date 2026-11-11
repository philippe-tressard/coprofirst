"""Les réponses d'aperçu que les e2e SIMULENT sont celles du serveur (#2633).

Un e2e ne recopie pas la règle « qui la lit » : quand le formulaire demande
`POST /lectures/apercu`, il rend la réponse rangée dans
`front/e2e/apercus-lecture.json`. Ce test la recalcule par la fonction de la route
(`lecture_pastille.regle.apercu_de`) : une réponse fausse, ou périmée après un
changement de règle, échoue ici — pas en silence dans un écran simulé.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from app.utils.lecture_pastille.regle import apercu_de

FICHIER = pathlib.Path(__file__).resolve().parents[2] / "front" / "e2e" / "apercus-lecture.json"
REPONSES = json.loads(FICHIER.read_text(encoding="utf-8"))["reponses"]


def test_cas_zero():
    assert REPONSES, f"aucune réponse dans {FICHIER} : les e2e ne simuleraient rien"


@pytest.mark.parametrize(
    "r", REPONSES, ids=[json.dumps(r["saisie"], ensure_ascii=False) for r in REPONSES]
)
def test_la_reponse_simulee_est_celle_du_serveur(r):
    s = r["saisie"]
    attendu = apercu_de(
        categorie=s.get("categorie"),
        statut=s.get("statut"),
        confidentiel=bool(s.get("confidentiel")),
        public_cible=s.get("public_cible") or [],
        perimetre_restreint=r["perimetre_restreint"],
        reserve_perimetre=bool(s.get("reserve_perimetre")),
    )
    assert r["apercu"] == attendu.model_dump()
