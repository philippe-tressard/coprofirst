"""Les rôles suivent le statut — à l'inscription ET à chaque changement de statut (#2161).

`require_proprietaire` lit les RÔLES. La règle « statut → rôles » n'était écrite
qu'à l'inscription : approuver un changement de statut écrivait `statut` seul, et
un copropriétaire devenu locataire gardait le rôle `propriétaire` — le carnet, la
recherche de locataires, les questions au règlement.

La fiche de l'administrateur écrivait le même `statut` par sa boucle de champs,
sans les rôles : la porte jumelle que #2161 n'avait pas vue (claude-config#603).
Les deux portes passent désormais par `roles_du_statut.changer_statut`.
"""

from __future__ import annotations

import ast
import logging

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.auth.deps import require_proprietaire
from app.models.core import DemandeModificationProfil, StatutDemandeProfil, StatutUtilisateur
from app.routers.admin.profils import DemandeProfilAction, traiter_demande_profil
from app.routers.admin.utilisateurs import AdminUserUpdate, modifier_utilisateur
from tests.aides_base import compte
from tests.aides_sources import modules_app
from tests.conftest import requete_de_test


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


def _par_la_fiche(session, user, statut, admin):
    modifier_utilisateur(
        requete_de_test("/admin/utilisateurs/1", "PATCH"),
        user.id,
        AdminUserUpdate(statut=statut),
        BackgroundTasks(),
        session,
        admin,
    )
    session.refresh(user)


def test_la_fiche_de_l_administrateur_fait_suivre_les_roles(session, caplog):
    """La porte jumelle : passé locataire par la fiche, il n'est plus propriétaire."""
    caplog.set_level(logging.INFO, logger="securite")
    admin = compte(session, prefixe="admin", roles_json="admin")
    proprio = compte(
        session,
        prefixe="proprio",
        roles_json="propriétaire,résident",
        statut=StatutUtilisateur.copropriétaire_résident,
    )
    assert require_proprietaire(proprio) is proprio  # témoin
    _par_la_fiche(session, proprio, StatutUtilisateur.locataire, admin)
    assert proprio.statut == StatutUtilisateur.locataire
    assert proprio.roles == ["résident"]
    with pytest.raises(HTTPException) as refus:
        require_proprietaire(proprio)
    assert refus.value.status_code == 403
    lignes = " ".join(r.getMessage() for r in caplog.records if r.name == "securite")
    assert f"securite role_retire acteur={admin.id} cible={proprio.id} propriétaire" in lignes


def test_la_fiche_qui_renvoie_le_meme_statut_ne_touche_pas_aux_roles(session):
    """L'écran renvoie toujours le statut : le même ne refait pas les rôles."""
    admin = compte(session, prefixe="admin", roles_json="admin")
    membre = compte(
        session,
        prefixe="membre",
        roles_json="conseil_syndical,propriétaire",
        statut=StatutUtilisateur.copropriétaire_résident,
    )
    _par_la_fiche(session, membre, StatutUtilisateur.copropriétaire_résident, admin)
    assert membre.roles == ["conseil_syndical", "propriétaire"]


#: Les schémas d'écriture qui portent le statut d'un compte, et le geste qui l'écrit.
#: Un schéma de plus qui le porte doit dire ici par où il passe : c'est ainsi que
#: la fiche de l'administrateur avait échappé à #2161.
ECRIVENT_LE_STATUT = {
    ("routers/admin/utilisateurs.py", "AdminUserUpdate"): "changer_statut",
    ("routers/auth_schemas.py", "UserCreate"): "poser_roles_du_statut",  # inscription
}


def test_tout_schema_qui_porte_le_statut_passe_par_la_porte():
    trouves = {}
    for m in modules_app("routers"):
        for n in ast.walk(m.arbre):
            if not isinstance(n, ast.ClassDef):
                continue
            for champ in n.body:
                if (
                    isinstance(champ, ast.AnnAssign)
                    and getattr(champ.target, "id", "") == "statut"
                    and "StatutUtilisateur" in ast.unparse(champ.annotation)
                ):
                    trouves[(m.rel, n.name)] = m
    assert trouves, "aucun schéma lu : le relevé ne voit plus rien"  # cas zéro
    assert set(trouves) == set(ECRIVENT_LE_STATUT), (
        f"schémas qui portent le statut d'un compte : {sorted(trouves)} — "
        "déclarer dans ECRIVENT_LE_STATUT le geste qui l'écrit (et les rôles avec)"
    )
    sources = {m.rel: ast.unparse(m.arbre) for m in modules_app("routers")}
    porte = {"routers/auth_schemas.py": "routers/auth.py"}
    for (fichier, _), geste in ECRIVENT_LE_STATUT.items():
        lu = porte.get(fichier, fichier)
        assert f"{geste}(" in sources.get(lu, ""), f"{lu} n'appelle pas {geste}"
