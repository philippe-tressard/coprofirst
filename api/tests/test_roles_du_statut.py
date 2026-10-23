"""Les rôles suivent le statut — à l'inscription ET au changement de statut (#2161).

`require_proprietaire` lit les RÔLES. La règle « statut → rôles » n'était écrite
qu'à l'inscription : approuver un changement de statut écrivait `statut` seul, et
un copropriétaire devenu locataire gardait le rôle `propriétaire` — le carnet, la
recherche de locataires, les questions au règlement.
"""

from __future__ import annotations

import ast
import logging

import pytest
from fastapi import HTTPException

from app.auth.deps import require_proprietaire
from app.models.core import DemandeModificationProfil, StatutDemandeProfil, StatutUtilisateur
from app.routers.admin.profils import DemandeProfilAction, traiter_demande_profil
from tests.aides_base import compte
from tests.aides_sources import modules_app


def _changer(session, user, statut, cs):
    demande = DemandeModificationProfil(
        utilisateur_id=user.id,
        statut_souhaite=statut.value,
        statut_demande=StatutDemandeProfil.en_attente,
    )
    session.add(demande)
    session.commit()
    traiter_demande_profil(demande.id, DemandeProfilAction(action="approuver"), session, cs)
    session.refresh(user)


def test_un_proprietaire_devenu_locataire_perd_le_role_proprietaire(session, caplog):
    caplog.set_level(logging.INFO, logger="securite")
    cs = compte(session, prefixe="cs", roles_json="conseil_syndical")
    proprio = compte(
        session,
        prefixe="proprio",
        roles_json="propriétaire,résident",
        statut=StatutUtilisateur.copropriétaire_résident,
    )
    assert require_proprietaire(proprio) is proprio  # témoin
    _changer(session, proprio, StatutUtilisateur.locataire, cs)
    assert proprio.roles == ["résident"]
    with pytest.raises(HTTPException) as refus:
        require_proprietaire(proprio)
    assert refus.value.status_code == 403
    lignes = [r.getMessage() for r in caplog.records if r.name == "securite"]
    assert f"securite role_retire acteur={cs.id} cible={proprio.id} propriétaire" in " ".join(
        lignes
    ), lignes


def test_un_role_qui_ne_vient_pas_du_statut_est_garde(session):
    cs = compte(session, prefixe="cs", roles_json="conseil_syndical")
    membre = compte(
        session,
        prefixe="membre",
        roles_json="conseil_syndical,propriétaire",
        statut=StatutUtilisateur.copropriétaire_bailleur,
    )
    _changer(session, membre, StatutUtilisateur.copropriétaire_résident, cs)
    assert set(membre.roles) == {"conseil_syndical", "propriétaire", "résident"}
    assert membre.role.value == "conseil_syndical"


def test_la_regle_ne_s_ecrit_qu_une_fois():
    """Plus aucun routeur ne compose « statut → rôles » lui-même."""
    fautes = [
        f"{m.rel}:{n.lineno}"
        for m in modules_app("routers")
        for n in ast.walk(m.arbre)
        if isinstance(n, ast.Assign)
        and any(getattr(t, "attr", "") == "roles_json" for t in n.targets)
    ]
    assert not fautes, f"rôles posés à la main dans un routeur : {fautes}"
