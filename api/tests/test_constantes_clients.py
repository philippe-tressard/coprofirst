"""Les constantes de l'API publiées aux apps sont celles que le code porte (#2686).

`api/app/contrat/constantes-clients.json` est joint à la release : les apps le
génèrent au lieu de lire les sources de l'API. Ce test refuse une référence en
retard sur le code, un retrait ou un changement de forme non annoncé, et une
annonce qui ne sert plus.
"""

from __future__ import annotations

import pytest

from app.contrat import constantes_clients as cc


def test_la_reference_est_celle_que_le_code_produit():
    assert cc.juger() == []


def test_chaque_valeur_est_lue_dans_son_module():
    from app.utils import avis, html_sur, mots_de_passe, preferences_mail

    lues = cc.lire()
    assert lues["schemasDeLien"]["valeur"] == sorted(html_sur.SCHEMAS_URL)
    assert lues["defautsPreferences"]["valeur"] == preferences_mail.DEFAUTS
    assert lues["longueurMinMotDePasse"]["valeur"] == mots_de_passe.LONGUEUR_MIN_MOT_DE_PASSE
    assert lues["notePubliable"]["valeur"] == avis.NOTE_PUBLIABLE


def test_la_longueur_publiee_est_celle_que_le_serveur_exige():
    """La constante publiée est celle que `verifier_robustesse` applique — pas une copie."""
    from fastapi import HTTPException

    from app.utils.mots_de_passe import LONGUEUR_MIN_MOT_DE_PASSE, verifier_robustesse

    juste = "Aa1!" + "x" * (LONGUEUR_MIN_MOT_DE_PASSE - 4)
    verifier_robustesse(juste)  # ne lève pas
    with pytest.raises(HTTPException) as refus:
        verifier_robustesse(juste[:-1])
    assert f"au moins {LONGUEUR_MIN_MOT_DE_PASSE} caractères" in refus.value.detail


def _publiee(valeur):
    return {"source": "s", "quoi": "q", "valeur": valeur}


def test_un_retrait_non_annonce_est_refuse():
    ancien = {"a": _publiee(1), "b": _publiee(["x"])}
    assert cc.refus(ancien, {"a": _publiee(1)}, {}) == [
        "b : retirée ou de forme changée, sans annonce"
    ]


def test_un_changement_de_type_non_annonce_est_refuse():
    ancien = {"a": _publiee({"k": True})}
    assert cc.refus(ancien, {"a": _publiee({"k": 1})}, {}) != []


def test_un_retrait_annonce_passe_et_une_annonce_inutile_est_refusee():
    ancien = {"a": _publiee(1), "b": _publiee(2)}
    assert cc.refus(ancien, {"a": _publiee(1)}, {"b": ("#1", "r")}) == []
    assert cc.refus(ancien, ancien, {"b": ("#1", "r")}) == ["b : annoncée, mais rien n'est retiré"]


def test_la_version_suit_les_ecarts():
    ancien = {"a": _publiee(1)}
    assert cc.version_suivante("1.2.3", ancien, ancien) == "1.2.3"
    assert cc.version_suivante("1.2.3", ancien, {**ancien, "b": _publiee(2)}) == "1.3.0"
    assert cc.version_suivante("1.2.3", ancien, {"a": _publiee(9)}) == "1.3.0"
    assert cc.version_suivante("1.2.3", ancien, {}) == "2.0.0"


def test_un_ensemble_se_publie_trie_et_un_objet_inconnu_est_refuse():
    assert cc.en_json(frozenset({"b", "a"})) == ["a", "b"]
    with pytest.raises(TypeError):
        cc.en_json(object())
