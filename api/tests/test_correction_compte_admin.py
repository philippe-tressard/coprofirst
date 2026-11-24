"""Corriger une saisie de l'inscription depuis l'administration (#1155).

Demandé à l'écran le 22/09/2026 : « ça permet de corriger les erreurs de
saisie », précisé le 23/09 : « ajouter le champ du nom du bailleur ». L'étage et
le nom du bailleur se saisissaient à l'inscription et ne se reprenaient nulle
part — une faute de frappe ne se corrigeait que par la base.

Mêmes règles qu'à l'inscription : l'étage dans ses bornes, les noms en capitales.
"""

from __future__ import annotations

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.routers.admin.utilisateurs import AdminUserUpdate, modifier_utilisateur
from tests.aides_badges import _compte
from tests.conftest import requete_de_test


def _corriger(session, cible, **champs):
    admin = _compte(session, "Admin")
    return modifier_utilisateur(
        requete_de_test("/admin/utilisateurs/1", "PATCH"),
        cible.id,
        AdminUserUpdate(**champs),
        background_tasks=BackgroundTasks(),
        session=session,
        admin=admin,
    )


def test_l_administrateur_corrige_l_etage_et_le_bailleur(session):
    locataire = _compte(session, "Locataire")
    lu = _corriger(session, locataire, etage=3, nom_proprietaire="  dupont ")
    assert (lu.etage, lu.nom_proprietaire) == (3, "DUPONT")


def test_le_nom_corrige_passe_en_capitales_comme_a_l_inscription(session):
    assert _corriger(session, _compte(session, "Resident"), nom="martin").nom == "MARTIN"


def test_un_etage_hors_bornes_est_refuse(session):
    with pytest.raises(HTTPException) as refus:
        _corriger(session, _compte(session, "Resident"), etage=444)
    assert refus.value.status_code == 400


def test_cas_zero_le_rez_de_chaussee_n_est_pas_une_absence(session):
    """`0` est le rez-de-chaussée : un test de vérité l'aurait pris pour « rien »."""
    assert _corriger(session, _compte(session, "Resident"), etage=0).etage == 0
