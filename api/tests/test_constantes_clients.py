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


def test_un_motif_et_une_dataclasse_se_publient():
    import re
    from dataclasses import dataclass

    assert cc.en_json(re.compile(r"^a_", re.IGNORECASE)) == {"motif": "^a_", "ignorerCasse": True}

    @dataclass(frozen=True)
    class F:
        types: dict
        plafond: int

    assert cc.en_json(F({"image/png": ".png"}, 5)) == {"types": {"image/png": ".png"}, "plafond": 5}


def test_le_motif_publie_juge_comme_le_serveur():
    """Compilé tel que publié, le motif d'image dit ce que dit `est_image` (#2764)."""
    import re

    from app.utils.fichiers import FAMILLES, est_image, nom_lisible

    publie = cc.lire()
    m = publie["motifImage"]["valeur"]
    motif = re.compile(m["motif"], re.IGNORECASE if m["ignorerCasse"] else 0)
    noms = [f"a{ext}" for f in FAMILLES.values() for ext in f.extensions] + ["a.PDF", "a.JPG", "a"]
    assert [bool(motif.search(n)) for n in noms] == [est_image(n) for n in noms]

    p = publie["prefixeStockage"]["valeur"]
    prefixe = re.compile(p["motif"], re.IGNORECASE if p["ignorerCasse"] else 0)
    stocke = "0123456789abcdef0123456789ABCDEF_rapport.pdf"
    assert prefixe.sub("", stocke) == nom_lisible(stocke) == "rapport.pdf"
    assert (
        publie["famillesFichiers"]["valeur"]["image"]["plafond_mo"] == FAMILLES["image"].plafond_mo
    )


def test_une_cle_ajoutee_a_un_objet_est_un_ajout_et_une_cle_retiree_un_retrait():
    """Un type de notification neuf (#2789) : l'app générée avant le lit par son défaut."""
    ancien = {"t": _publiee({"a": {"p": "x"}})}
    ajout = {"t": _publiee({"a": {"p": "x"}, "b": {"p": "y"}})}
    assert cc.refus(ancien, ajout, {}) == []
    assert cc.version_suivante("1.2.3", ancien, ajout) == "1.3.0"
    #  Le cas fautif : la clé `a` disparaît, ou change de forme — une rupture.
    assert cc.refus(ajout, ancien, {}) == ["t : retirée ou de forme changée, sans annonce"]
    assert cc.refus(ancien, {"t": _publiee({"a": 1})}, {}) != []
    assert cc.version_suivante("1.2.3", ajout, ancien) == "2.0.0"
