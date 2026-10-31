"""Le canari nocturne de l'assistant IA : il mesure, et il sait dire qu'il n'a rien mesuré (#2369).

Voir `app/utils/canari_ia.py`. Ce qui est vérifié ici :

1. la rotation fait passer chaque cas du corpus, et la charge ne se lit ni dans
   le courriel ni dans une mise en forme fidèle — sans quoi le canari crierait seul ;
2. le verdict distingue le modèle qui obéit de la porte qui cède — et la porte
   cassée (mutation) se VOIT ;
3. le contrôle de 06:00 : rien quand tout va bien ou que l'usage est coupé, une
   ligne quand le modèle a obéi, et INCONNU — jamais OK — sans mesure récente ;
4. rien du courriel ni de la sortie n'entre au journal.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlmodel import select

from app.models.exploitation import HistoriqueMaintenance
from app.utils import canari_ia, horloge, ia_courriel, llm
from app.utils.canari_ia import (
    CONFORME,
    ECARTE,
    INCONNU,
    OBEI_ECARTE,
    PORTE_PERCEE,
    VIDE,
    cas_du_jour,
    lancer,
    problemes_canari,
)
from app.utils.ia_courriel import contient_la_charge
from app.utils.ia_courriel_corpus import CORPUS

_LUNDI = date(2026, 11, 2)


def _modele(rendu, appels: list | None = None):
    """Un faux `demander` : `rendu(cas)` dit ce que le modèle écrit pour ce cas."""

    async def faux(session, *, usage, message, **_):
        cas = next(c for c in CORPUS if c.corps.split("\n")[0] in message)
        if appels is not None:
            appels.append(usage)
        if isinstance(rendu, Exception):
            raise rendu
        return SimpleNamespace(texte=rendu(cas))

    return faux


@pytest.fixture()
def usage_pret(monkeypatch):
    monkeypatch.setattr(
        llm,
        "config_llm",
        lambda session, usage: SimpleNamespace(prompt="Mets en forme.", pret=True),
    )


def _jour_de(cas) -> date:
    return next(
        j for j in (_LUNDI + timedelta(days=n) for n in range(len(CORPUS))) if cas_du_jour(j) == cas
    )


def _rapports(session) -> list[HistoriqueMaintenance]:
    return list(
        session.exec(
            select(HistoriqueMaintenance).where(HistoriqueMaintenance.tache == "canari_ia")
        ).all()
    )


# ── 1. Le corpus et la rotation ───────────────────────────────────────────────


def test_la_rotation_fait_passer_chaque_cas():
    vus = {cas_du_jour(_LUNDI + timedelta(days=n)).code for n in range(len(CORPUS))}
    assert vus == {c.code for c in CORPUS}


@pytest.mark.parametrize("cas", CORPUS, ids=lambda c: c.code)
def test_la_charge_ne_se_lit_que_chez_un_modele_qui_obeit(cas):
    """Pas de faux positif : ni le courriel, ni la mise en forme fidèle ne la portent ;
    elle se lit même espacée, ponctuée ou en minuscules."""
    assert not contient_la_charge(cas.corps, cas.charge)
    assert not contient_la_charge(cas.sortie_sage, cas.charge)
    milieu = len(cas.charge) // 2
    variante = f"« {cas.charge[:milieu].lower()} - {cas.charge[milieu:]} »"
    assert contient_la_charge(variante, cas.charge)
    assert not contient_la_charge("rien", "")


# ── 2. Le verdict ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("cas", CORPUS, ids=lambda c: c.code)
def test_un_modele_fidele_passe(session, usage_pret, monkeypatch, cas):
    monkeypatch.setattr(llm, "demander", _modele(lambda c: c.sortie_sage))
    jour = _jour_de(cas)
    verdict = canari_ia.mesurer(session, jour)
    assert (verdict.code, verdict.cas) == (CONFORME, cas.code)


@pytest.mark.parametrize("cas", CORPUS, ids=lambda c: c.code)
def test_un_modele_qui_obeit_est_vu_et_la_porte_l_ecarte(session, usage_pret, monkeypatch, cas):
    monkeypatch.setattr(llm, "demander", _modele(lambda c: c.charge))
    jour = _jour_de(cas)
    assert canari_ia.mesurer(session, jour).code == OBEI_ECARTE


def test_une_porte_cassee_se_voit(session, usage_pret, monkeypatch):
    """Mutation : un contrat qui admet tout laisse la charge entrer au fil — le canari
    le dit PORTE_PERCEE, et non « le modèle a obéi »."""
    monkeypatch.setattr(llm, "demander", _modele(lambda c: c.charge))
    monkeypatch.setattr(
        ia_courriel, "sortie_conforme", lambda entree, sortie: ia_courriel.Conformite(True)
    )
    assert canari_ia.mesurer(session, _LUNDI).code == PORTE_PERCEE


def test_hors_contrat_sans_la_charge_ni_vide_ne_sont_pas_des_echecs(
    session, usage_pret, monkeypatch
):
    monkeypatch.setattr(
        llm, "demander", _modele(lambda c: c.sortie_sage + " Salutations distinguées.")
    )
    assert canari_ia.mesurer(session, _LUNDI).code == ECARTE
    monkeypatch.setattr(llm, "demander", _modele(lambda c: "  "))
    assert canari_ia.mesurer(session, _LUNDI).code == VIDE


def test_le_canari_emprunte_la_porte_de_la_releve(session, usage_pret, monkeypatch):
    appels: list = []
    monkeypatch.setattr(llm, "demander", _modele(lambda c: c.sortie_sage, appels))
    canari_ia.mesurer(session, _LUNDI)
    assert appels == ["reponse_courriel"]


# ── 3. Le contrôle de 06:00 ───────────────────────────────────────────────────


def test_usage_coupe_rien_a_prouver_et_rien_a_dire(session, monkeypatch):
    monkeypatch.setattr(llm, "config_llm", lambda session, usage: SimpleNamespace(pret=False))
    monkeypatch.setattr(llm, "demander", _modele(AssertionError("aucun appel")))
    assert lancer(session) is None
    assert _rapports(session) == []
    assert problemes_canari(session) == []


def test_sans_mesure_recente_c_est_inconnu_jamais_ok(session, usage_pret):
    """Cas zéro : l'usage est prêt, rien n'a tourné — une ligne INCONNU."""
    (ligne,) = problemes_canari(session)
    assert "INCONNUE" in ligne
    session.add(
        HistoriqueMaintenance(
            tache="canari_ia",
            statut="succes",
            cree_le=horloge.maintenant() - canari_ia.FENETRE - timedelta(minutes=1),
        )
    )
    session.commit()
    (ligne,) = problemes_canari(session)
    assert "aucun passage depuis 30 h" in ligne


def test_un_passage_conforme_se_tait(session, usage_pret, monkeypatch):
    monkeypatch.setattr(llm, "demander", _modele(lambda c: c.sortie_sage))
    assert lancer(session).code == CONFORME
    (rapport,) = _rapports(session)
    assert rapport.statut == "succes"
    assert problemes_canari(session) == []


def test_un_modele_qui_obeit_fait_une_ligne(session, usage_pret, monkeypatch):
    monkeypatch.setattr(llm, "demander", _modele(lambda c: c.charge))
    verdict = lancer(session)
    (ligne,) = problemes_canari(session)
    assert "OBÉI" in ligne and verdict.cas in ligne


def test_un_appel_qui_echoue_est_inconnu(session, usage_pret, monkeypatch):
    monkeypatch.setattr(llm, "demander", _modele(llm.ErreurLLM("délai dépassé")))
    assert lancer(session).code == INCONNU
    (rapport,) = _rapports(session)
    assert rapport.statut == "erreur"
    (ligne,) = problemes_canari(session)
    assert "INCONNUE" in ligne and "ErreurLLM" in ligne


# ── 4. Rien du courriel au journal ────────────────────────────────────────────


def test_le_compte_rendu_ne_porte_ni_le_courriel_ni_la_sortie(session, usage_pret, monkeypatch):
    monkeypatch.setattr(llm, "demander", _modele(lambda c: c.charge + " " + c.corps))
    verdict = lancer(session)
    cas = next(c for c in CORPUS if c.code == verdict.cas)
    (rapport,) = _rapports(session)
    trace = (rapport.details or "") + (rapport.erreur or "")
    assert set(json.loads(rapport.details)) == {"cas", "verdict", "motif", "longueur_sortie"}
    assert not contient_la_charge(trace, cas.charge)
    assert cas.corps.split("\n")[0] not in trace
