"""L'assistant lit l'état descriptif du règlement et remplit l'atelier (#2218).

Ce que ces tests tiennent :

- la réponse du modèle se VALIDE — sans source, un tantième non entier, une clé
  citée sans dénominateur : toute la lecture est refusée ;
- elle devient le MÊME tableau qu'un fichier téléversé, et passe par les mêmes
  contrôles ; une ligne douteuse est relevée ;
- la route ne lance rien sans assistant ni règlement, et la tâche de fond ne
  remplit que la table de passage — 🔴 jamais le patrimoine.
"""

from __future__ import annotations

import ast
import json
import pathlib
from types import SimpleNamespace

import pytest
from sqlmodel import Session, select

from app import contexte
from app.models.charges import CleDeCharges, QuotePartLot
from app.models.etat_descriptif import ImportEtatDescriptif, LigneEtatDescriptif
from app.utils import constats as C
from app.utils import etat_descriptif as E
from app.utils import llm
from app.utils.description_format import ReponseIllisible
from app.utils.etat_descriptif_ia import en_tableau, lire_reponse
from tests.aides_reglement import client_admin, client_cs, joindre
from tests.aides_reglement import moteur_fixture  # noqa: F401

ROUTE = "/lots/admin/etat-descriptif/lire-reglement"


def _reponse(**surcharges) -> dict:
    lot_sur = {
        "lot": 901,
        "batiment": "X",
        "nature": "logement",
        "numero_usage": "12",
        "niveau": 1,
        "circulation": "X",
        "quotes": {"Charges générales": 60, "Escalier X'": 10},
        "lot_origine": None,
        "page_source": "p. 14, état descriptif",
        "confiance": "sûr",
    }
    lot_douteux = {
        **lot_sur,
        "lot": "902",
        "nature": "cave",
        "numero_usage": None,
        "niveau": -1,
        "circulation": None,
        "quotes": {"Charges générales": 40},
        "page_source": "p. 15",
        "confiance": "douteux",
    }
    reponse = {
        "cles": [
            {"libelle": "Charges générales", "denominateur": 100},
            {"libelle": "Escalier X'", "denominateur": 10},
        ],
        "lots": [lot_sur, lot_douteux],
    }
    reponse.update(surcharges)
    return reponse


# ── La réponse du modèle ─────────────────────────────────────────────────────


def test_une_reponse_conforme_se_lit_et_un_numero_reste_un_texte():
    lecture = lire_reponse(json.dumps(_reponse()))
    assert [lot.lot for lot in lecture.lots] == ["901", "902"]


@pytest.mark.parametrize(
    "abimer",
    [
        lambda r: r["lots"][0].pop("page_source"),
        lambda r: r["lots"][0].update(page_source=""),
        lambda r: r["lots"][0]["quotes"].update({"Charges générales": 60.5}),
        lambda r: r["lots"][0]["quotes"].update({"Ascenseur Z": 3}),
        lambda r: r.update(lots=[]),
    ],
    ids=["sans_source", "source_vide", "tantieme_decimal", "cle_non_declaree", "aucun_lot"],
)
def test_une_reponse_hors_format_est_refusee_en_entier(abimer):
    reponse = _reponse()
    abimer(reponse)
    with pytest.raises(ReponseIllisible):
        lire_reponse(json.dumps(reponse))


def test_la_lecture_devient_le_tableau_d_un_fichier_et_passe_les_memes_controles():
    rows = en_tableau(lire_reponse(json.dumps(_reponse())))
    lu = E.lire(rows)
    assert not lu.erreurs
    assert [(c.code, c.denominateur) for c in lu.cles] == [
        ("charges-generales", 100),
        ("escalier-x-prime", 10),
    ]
    #  La ligne douteuse passe en tête, sa source porte la marque.
    premier, second = lu.lignes
    assert premier.lot == "902" and E.MARQUE_DOUTEUX in premier.source
    assert premier.circulation == "/" and premier.niveau == "-1"
    assert second.quotes == {"charges-generales": 60, "escalier-x-prime": 10}
    trouves = E.controler(lu, [], {"X": 1}, {1})
    douteux = next(c for c in trouves if c.code == "douteux")
    assert douteux.gravite == C.AVERTISSEMENT and douteux.lots == ["902"]


# ── La route et la tâche de fond ─────────────────────────────────────────────


def _assistant(monkeypatch, moteur, pret=True, texte=None):
    """Un assistant simulé ; la tâche de fond ouvre sa session sur la base du test."""
    recus: list[str] = []
    monkeypatch.setattr(contexte, "nouvelle_session", lambda: Session(moteur))

    def config(session, usage=None):
        return SimpleNamespace(pret=pret, prompt="PROMPT", modele="modele-test")

    async def demander(session, *, usage, message, consigne=None, **_):
        recus.append(consigne or "")
        return SimpleNamespace(
            texte=texte if texte is not None else json.dumps(_reponse()),
            jetons_entree=1,
            jetons_sortie=1,
            jetons_cache=0,
        )

    monkeypatch.setattr(llm, "config_llm", config)
    monkeypatch.setattr(llm, "demander", demander)
    return recus


def test_sans_assistant_ou_sans_reglement_la_route_refuse_en_400(moteur, monkeypatch):
    _assistant(monkeypatch, moteur, pret=False)
    assert client_cs(moteur).post(ROUTE).status_code == 400
    _assistant(monkeypatch, moteur, pret=True)
    reponse = client_cs(moteur).post(ROUTE)
    assert reponse.status_code == 400 and "règlement" in reponse.json()["detail"]


def test_la_lecture_remplit_la_table_de_passage_et_rien_d_autre(moteur, monkeypatch):
    consignes = _assistant(monkeypatch, moteur)
    assert joindre(client_admin(moteur), moteur).status_code in (200, 201)
    with Session(moteur) as s:
        cles_avant = len(s.exec(select(CleDeCharges)).all())
        parts_avant = len(s.exec(select(QuotePartLot)).all())

    reponse = client_cs(moteur).post(ROUTE)
    assert reponse.status_code == 202, reponse.text
    #  Le format imposé suit toujours la consigne réglable.
    assert consignes and consignes[0].startswith("PROMPT") and '"cles"' in consignes[0]

    etat = client_cs(moteur).get("/lots/admin/etat-descriptif").json()
    assert etat["lecture_ia"] == "terminee" and len(etat["lignes"]) == 2
    assert not etat["applique_le"]
    with Session(moteur) as s:
        assert len(s.exec(select(LigneEtatDescriptif)).all()) == 2
        assert len(s.exec(select(CleDeCharges)).all()) == cles_avant
        assert len(s.exec(select(QuotePartLot)).all()) == parts_avant


def test_une_reponse_illisible_note_l_echec_sans_ligne(moteur, monkeypatch):
    _assistant(monkeypatch, moteur, texte="Je ne peux pas.")
    joindre(client_admin(moteur), moteur)
    assert client_cs(moteur).post(ROUTE).status_code == 202
    etat = client_cs(moteur).get("/lots/admin/etat-descriptif").json()
    assert etat["lecture_ia"] == "echec" and etat["erreur_ia"]
    assert etat["lignes"] == [] and not etat["applicable"]
    with Session(moteur) as s:
        imp = s.exec(select(ImportEtatDescriptif)).one()
        assert not s.exec(
            select(LigneEtatDescriptif).where(LigneEtatDescriptif.import_id == imp.id)
        ).all()


def test_le_module_de_l_assistant_n_ecrit_jamais_le_patrimoine():
    """🔴 Garde-fou : l'assistant passe par la table de passage, jamais par les
    lots, les clés ni les tantièmes — c'est le geste « Appliquer » qui écrit."""
    source = pathlib.Path(__file__).resolve().parents[1] / "app/utils/etat_descriptif_ia.py"
    interdits = {"Lot", "QuotePartLot", "CleDeCharges", "appliquer", "rederiver"}
    importes = {
        alias.asname or alias.name
        for noeud in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
        if isinstance(noeud, ast.ImportFrom)
        for alias in noeud.names
    }
    assert not importes & interdits, importes & interdits


def test_une_limite_d_appels_atteinte_refuse_avant_d_ouvrir_la_lecture(moteur, monkeypatch):
    """Le standard IA du projet (`llm_limites`) : refusé AVANT, rien n'est remplacé."""
    from app.utils import llm_limites

    _assistant(monkeypatch, moteur)
    joindre(client_admin(moteur), moteur)
    monkeypatch.setattr(
        llm_limites, "refus_avant_envoi", lambda *_: ("plafond", "Limite du mois atteinte.")
    )
    reponse = client_cs(moteur).post(ROUTE)
    assert reponse.status_code == 429 and "Limite" in reponse.json()["detail"]
    with Session(moteur) as s:
        assert not s.exec(select(ImportEtatDescriptif)).all()


def test_un_echec_inattendu_ne_laisse_pas_la_lecture_en_cours(moteur, monkeypatch):
    from app.utils import etat_descriptif_ia

    _assistant(monkeypatch, moteur)
    joindre(client_admin(moteur), moteur)

    async def panne(*_):
        raise ValueError("panne")

    monkeypatch.setattr(etat_descriptif_ia, "lire_le_reglement", panne)
    assert client_cs(moteur).post(ROUTE).status_code == 202
    etat = client_cs(moteur).get("/lots/admin/etat-descriptif").json()
    assert etat["lecture_ia"] == "echec" and "réessayez" in etat["erreur_ia"]
