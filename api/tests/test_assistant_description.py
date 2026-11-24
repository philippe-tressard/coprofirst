"""Retravailler un titre et une description avec l'assistant (#985, 17/09/2026).

## Ce que ce test protège

1. **Le format est tenu par le code** : `FORMAT_REPONSE` est ajouté APRÈS le
   prompt de l'administrateur, et `lire_reponse` relit ce format — tolérant
   sur l'emballage (bloc de code, texte parasite), intransigeant sur la
   description.
2. **Ce qui a changé est dit par le serveur**, sur du texte normalisé : l'écran
   affiche « Titre modifié » sans comparer du HTML brut.
3. **Le geste n'est proposé que s'il a un sens** (`disponible`), décidé par le
   serveur, et rien de la configuration ne sort.
4. **Le contexte ne se réécrit pas** — annoncé au modèle dans le MESSAGE, pas
   seulement dans le prompt modifiable.
"""

from __future__ import annotations

import pytest

from app.utils.assistant_description import Demande, disponible, preparer
from app.utils.description_format import (
    CONSIGNE_DEFAUT,
    FORMAT_REPONSE,
    MAX_CARACTERES_CONTEXTE,
    ReponseIllisible,
    a_change,
    construire_message,
    lire_reponse,
)
from app.utils.llm import ErreurLLM
from tests.aides_reglages import poser_reglages


# ── 1. Lire la réponse ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "texte",
    [
        '{"titre": "Fuite", "description": "<p>Une fuite.</p>"}',
        '```json\n{"titre": "Fuite", "description": "<p>Une fuite.</p>"}\n```',
        'Voici :\n{"titre": "Fuite", "description": "<p>Une fuite.</p>"}\nBonne journée.',
    ],
)
def test_le_json_est_relu_quel_que_soit_son_emballage(texte):
    """Beaucoup de modèles posent un bloc de code malgré la consigne ; refuser
    la réponse pour cela ferait échouer un appel facturé et correct."""
    assert lire_reponse(texte) == {"titre": "Fuite", "description": "<p>Une fuite.</p>"}


def test_un_titre_null_reste_None():
    assert lire_reponse('{"titre": null, "description": "x"}')["titre"] is None
    assert lire_reponse('{"titre": "  ", "description": "x"}')["titre"] is None


@pytest.mark.parametrize(
    "texte",
    ["", "Une fuite d'eau au 3e.", '{"titre": "x"}', "{pas du json}", "[1, 2]"],
)
def test_sans_description_la_reponse_est_ILLISIBLE_jamais_un_texte(texte):
    """Prendre la prose du modèle pour une proposition ferait remplacer une
    description par « Voici une reformulation : … »."""
    with pytest.raises(ReponseIllisible):
        lire_reponse(texte)


# ── 2. Le format appartient au code ────────────────────────────────────────


def test_le_prompt_d_origine_ne_porte_PAS_le_format():
    """Sinon l'administrateur pourrait le retirer en croyant alléger le texte,
    et chaque appel échouerait sans qu'un écran dise pourquoi."""
    assert "JSON" not in CONSIGNE_DEFAUT
    assert "JSON" in FORMAT_REPONSE
    assert '"description"' in FORMAT_REPONSE


def test_le_prompt_d_origine_porte_les_quatre_consignes_de_philippe():
    for exigence in ("langage simple", "législation française", "synthétique", "locataires"):
        assert exigence in CONSIGNE_DEFAUT


# ── 3. Le message ──────────────────────────────────────────────────────────


def test_le_contexte_est_annonce_comme_a_ne_pas_reecrire():
    m = construire_message(
        entite="ticket",
        titre="Fuite",
        description="<p>Au 3e.</p>",
        contexte={"Catégorie": "Panne", "Périmètre": "Bât. 2", "Vide": ""},
        precision="plus court",
        avec_titre=True,
    )
    assert "à ne pas réécrire" in m
    assert "- Catégorie : Panne" in m
    assert "Vide" not in m
    assert "Titre actuel :\nFuite" in m
    assert "plus court" in m


def test_sans_titre_demande_le_message_le_dit():
    m = construire_message(
        entite="commentaire",
        titre=None,
        description="x",
        contexte={},
        precision=None,
        avec_titre=False,
    )
    assert "Aucun titre n'est demandé" in m
    assert "Titre actuel" not in m


def test_un_champ_vide_est_annonce_vide_pas_omis():
    """Le modèle doit SAVOIR qu'il n'y a pas de titre pour en proposer un."""
    m = construire_message(
        entite="ticket",
        titre="",
        description="x",
        contexte={},
        precision=None,
        avec_titre=True,
    )
    assert "Titre actuel :\n(aucun)" in m


# ── 4. Ce qui a changé ─────────────────────────────────────────────────────


def test_le_changement_ignore_les_espaces_que_l_editeur_ajoute():
    assert a_change("<p>Bonjour</p>", "<p>Bonjour</p>\n") is False
    assert a_change("Bonjour", "Bonjour !") is True
    assert a_change(None, "") is False


# ── 5. Préparer la demande ─────────────────────────────────────────────────


def test_une_demande_vide_est_refusee_AVANT_l_appel():
    with pytest.raises(ErreurLLM):
        preparer(Demande("ticket", "  ", "", {}, None, True))


def test_le_contexte_est_borne_et_les_vides_ecartes():
    d = preparer(Demande("ticket", "t", None, {"a": "x" * 2000, "b": ""}, "p" * 9999, True))
    assert len(d.contexte["a"]) == MAX_CARACTERES_CONTEXTE
    assert "b" not in d.contexte
    assert len(d.precision) < 9999


# ── 6. Disponible ? — le serveur décide ────────────────────────────────────


def test_indisponible_tant_que_l_usage_n_est_pas_active(session):
    poser_reglages(session, llm_actif="1", llm_api_key="sk-x", llm_description_modele="m")
    assert disponible(session) is False


def test_disponible_quand_les_deux_etages_le_sont(session):
    poser_reglages(
        session,
        llm_actif="1",
        llm_api_key="sk-x",
        llm_description_actif="1",
        llm_description_modele="m",
    )
    assert disponible(session) is True


def test_la_route_est_reservee_au_conseil_syndical():
    """L'appel est facturé : réservé au CS et à l'admin, et c'est le SERVEUR
    qui le tient — l'icône masquée n'est qu'un confort (`standards/03` §1)."""
    import inspect

    from app.auth.deps import require_cs_or_admin
    from app.routers import assistant

    for fonction in (assistant.assistant_disponible, assistant.proposer_description):
        defauts = [p.default for p in inspect.signature(fonction).parameters.values()]
        assert any(getattr(d, "dependency", None) is require_cs_or_admin for d in defauts), (
            fonction.__name__
        )
