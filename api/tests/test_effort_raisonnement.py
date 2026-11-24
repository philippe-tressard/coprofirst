"""L'effort de raisonnement, réglé par usage (30/09/2026).

Demandé : « gpt-5.6-luna + reasoning.effort=low = choix par défaut ? faut-il le
paramétrer ? » — rien n'était envoyé, chaque modèle raisonnait à son défaut.

Ce que ce test protège :

1. **Une seule table des niveaux** (`llm_usages.EFFORTS`), servie à l'écran ;
   un code inconnu ou vide n'envoie RIEN — le modèle garde son défaut.
2. **Chaque fournisseur a son nom de paramètre** : `reasoning_effort` chez
   OpenAI et Azure, `output_config.effort` chez Anthropic.
3. **Un modèle qui refuse le réglage ne fait pas échouer l'appel** : il repart
   sans lui — y compris chez Anthropic, dont le refus ne nomme aucun paramètre.
4. **Une réponse Claude qui commence par sa réflexion se lit quand même.**
"""

from __future__ import annotations

import asyncio

import pytest

from app.utils.llm import config_llm, demander
from app.utils.llm_fournisseurs import FOURNISSEURS
from app.utils.llm_usages import EFFORTS, decrire, valeur_effort
from tests.aides_reglages import poser_reglages

USAGE = "description"


# ── 1. La table ─────────────────────────────────────────────────────────────


def test_les_niveaux_se_traduisent_et_l_inconnu_n_envoie_rien():
    assert [valeur_effort(c) for c, _, _ in EFFORTS] == ["low", "medium", "high"]
    assert valeur_effort("") == ""
    assert valeur_effort(None) == ""
    assert valeur_effort("maximal") == ""


def test_l_ecran_recoit_la_table_et_la_cle_de_chaque_usage():
    for u in decrire():
        assert u["cles"]["effort"] == f"llm_{u['code']}_effort"
        assert [e["val"] for e in u["efforts"]] == ["faible", "moyen", "eleve"]


def test_la_configuration_lit_l_effort_de_l_usage(session):
    poser_reglages(session, **{f"llm_{USAGE}_effort": "faible"})
    assert config_llm(session, USAGE).effort == "low"
    assert config_llm(session, "synthese_contrat").effort == ""


# ── 2. Un nom par fournisseur ───────────────────────────────────────────────


def test_chaque_fournisseur_porte_l_effort_a_sa_facon():
    base = {"model": "m", "max_tokens": 10}
    assert FOURNISSEURS["openai"].avec_effort(base, "low")["reasoning_effort"] == "low"
    assert FOURNISSEURS["azure_openai"].avec_effort(base, "low")["reasoning_effort"] == "low"
    assert FOURNISSEURS["anthropic"].avec_effort(base, "high")["output_config"] == {
        "effort": "high"
    }
    for f in FOURNISSEURS.values():
        assert f.avec_effort(base, "") == base, f.code
    assert base == {"model": "m", "max_tokens": 10}, "le corps d'origine ne doit pas changer"


# ── 3. Un refus retire le réglage ───────────────────────────────────────────


def test_openai_retire_l_effort_qu_un_modele_refuse():
    corps = {"model": "gpt-4o-mini", "reasoning_effort": "low"}
    assert FOURNISSEURS["openai"].adapter(corps, "reasoning_effort", "unsupported_parameter") == {
        "model": "gpt-4o-mini"
    }


@pytest.mark.parametrize(
    ("message", "retire"),
    [
        ("temperature is deprecated for this model.", "temperature"),
        ("output_config.effort: Extra inputs are not permitted", "output_config"),
        ("This model does not support the effort parameter.", "output_config"),
    ],
)
def test_anthropic_classe_son_refus_et_retire_le_parametre(message, retire):
    a = FOURNISSEURS["anthropic"]
    charge = {"type": "error", "error": {"type": "invalid_request_error", "message": message}}
    param, code = a.lire_erreur(charge)
    corps = {"model": "m", "temperature": 0.2, "output_config": {"effort": "low"}}
    suite = a.adapter(corps, param, code)
    assert suite is not None and retire not in suite
    assert set(corps) - set(suite) == {retire}


# ── 4. Claude réfléchit d'abord ─────────────────────────────────────────────


def test_une_reponse_claude_qui_commence_par_sa_reflexion_se_lit():
    reponse = {
        "content": [
            {"type": "thinking", "thinking": ""},
            {"type": "text", "text": "Bonjour "},
            {"type": "text", "text": "le conseil."},
        ]
    }
    assert FOURNISSEURS["anthropic"].lire(reponse) == "Bonjour le conseil."


# ── De bout en bout : le refus, puis la reprise sans le réglage ─────────────


class _Reponse:
    def __init__(self, statut, charge):
        self.status_code = statut
        self._charge = charge
        self.text = str(charge)

    def json(self):
        return self._charge


def test_l_appel_repart_sans_l_effort_quand_le_modele_le_refuse(monkeypatch, session):
    import httpx

    envoyes: list[dict] = []
    reponses = [
        _Reponse(
            400,
            {"error": {"param": "reasoning_effort", "code": "unsupported_parameter"}},
        ),
        _Reponse(
            200,
            {
                "choices": [{"message": {"content": "Texte."}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        ),
    ]

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            envoyes.append(k.get("json"))
            return reponses.pop(0)

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    poser_reglages(
        session,
        llm_actif="1",
        llm_fournisseur="openai",
        llm_api_key="sk-test",
        **{
            f"llm_{USAGE}_actif": "1",
            f"llm_{USAGE}_modele": "gpt-4o-mini",
            f"llm_{USAGE}_effort": "faible",
        },
    )
    rep = asyncio.run(demander(session, usage=USAGE, message="Bonjour", demandeur=None))
    assert rep.texte == "Texte."
    assert envoyes[0]["reasoning_effort"] == "low"
    assert "reasoning_effort" not in envoyes[1]
