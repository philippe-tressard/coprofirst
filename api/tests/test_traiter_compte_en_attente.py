"""Le conseil syndical ne traite que les comptes EN ATTENTE (#2152).

## 🔴 Pourquoi

`POST /admin/comptes/{id}/traiter` prend `require_cs_or_admin` et ne regardait
pas l'état du compte. La file n'affichait que les comptes en attente ; la route
acceptait tous les autres. Un membre du conseil « validait » ainsi un compte que
l'administrateur avait désactivé — la fermeture effacée, la purge suspendue —,
ou le « refusait » pour avancer sa suppression définitive. Désactiver est un
geste d'administrateur (`PATCH /admin/utilisateurs/{id}`, `require_admin`).

## Ce que ces tests tiennent

1. Le geste refuse (409) un compte désactivé, refusé ou déjà validé, et n'en
   change rien — ni `actif`, ni la fermeture.
2. Le compte en attente se traite toujours.
3. Le prédicat du geste (`est_en_attente`) et la clause de la file
   (`condition_compte_en_attente`) répondent pareil dans chaque état : une liste
   qui filtre et un geste qui refuse posent la même question.
"""

from __future__ import annotations

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import select

from app.models.core import Utilisateur
from app.routers.admin.comptes import CompteAction, traiter_compte
from app.routers.admin.utilisateurs import AdminUserUpdate, modifier_utilisateur
from app.utils.comptes import DESACTIVATION, condition_compte_en_attente, est_en_attente
from tests.aides_base import compte


def _cs(session):
    return compte(session, prefixe="cs", roles_json="conseil_syndical")


def _admin(session):
    return compte(session, prefixe="admin", roles_json="admin")


def _desactive_par_l_admin(session):
    resident = compte(session, prefixe="resident")
    modifier_utilisateur(
        resident.id, AdminUserUpdate(actif=False), BackgroundTasks(), session, _admin(session)
    )
    session.refresh(resident)
    assert resident.actif is False and resident.fermeture_compte == DESACTIVATION
    return resident


@pytest.mark.parametrize("action", ["valider", "refuser"])
def test_le_conseil_ne_rouvre_ni_ne_refuse_un_compte_desactive(session, action):
    resident = _desactive_par_l_admin(session)
    ferme_le = resident.compte_ferme_le
    with pytest.raises(HTTPException) as refus:
        traiter_compte(
            resident.id, CompteAction(action=action), BackgroundTasks(), session, _cs(session)
        )
    assert refus.value.status_code == 409
    session.refresh(resident)
    assert resident.actif is False
    assert resident.fermeture_compte == DESACTIVATION and resident.compte_ferme_le == ferme_le


def test_un_compte_refuse_ne_se_retraite_pas(session):
    cs = _cs(session)
    arrivant = compte(session, prefixe="arrivant", actif=False)
    traiter_compte(arrivant.id, CompteAction(action="refuser"), BackgroundTasks(), session, cs)
    with pytest.raises(HTTPException) as refus:
        traiter_compte(arrivant.id, CompteAction(action="valider"), BackgroundTasks(), session, cs)
    assert refus.value.status_code == 409
    session.refresh(arrivant)
    assert arrivant.actif is False


def test_un_compte_actif_ne_se_retraite_pas(session):
    resident = compte(session, prefixe="resident")
    with pytest.raises(HTTPException) as refus:
        traiter_compte(
            resident.id, CompteAction(action="refuser"), BackgroundTasks(), session, _cs(session)
        )
    assert refus.value.status_code == 409


def test_un_compte_en_attente_se_valide(session):
    arrivant = compte(session, prefixe="arrivant", actif=False)
    traiter_compte(
        arrivant.id, CompteAction(action="valider"), BackgroundTasks(), session, _cs(session)
    )
    session.refresh(arrivant)
    assert arrivant.actif is True and arrivant.decision_compte_le is not None


def test_le_geste_et_la_file_posent_la_meme_question(session):
    etats = {
        "en attente": compte(session, prefixe="attente", actif=False),
        "actif": compte(session, prefixe="actif"),
        "désactivé": _desactive_par_l_admin(session),
    }
    refuse = compte(session, prefixe="refuse", actif=False)
    traiter_compte(
        refuse.id, CompteAction(action="refuser"), BackgroundTasks(), session, _cs(session)
    )
    etats["refusé"] = refuse

    dans_la_file = {
        u.id for u in session.exec(select(Utilisateur).where(condition_compte_en_attente())).all()
    }
    for nom, u in etats.items():
        session.refresh(u)
        assert est_en_attente(u) == (u.id in dans_la_file), nom
    assert est_en_attente(etats["en attente"]), "cas témoin : le contrôle ne compare plus rien"
