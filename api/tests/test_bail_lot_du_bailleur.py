"""Un bail ne se pose que sur un lot dont on est copropriétaire (#1535).

## 🔴 Le défaut que ce test refuse

`POST /bailleur/baux/creer-multi` relisait chaque lot reçu (« existe-t-il ? »)
sans jamais demander « est-il le vôtre ? ». Tout compte propriétaire pouvait
donc poser un bail sur le lot d'un voisin, en se désignant lui-même locataire :

- il devenait **porteur** des badges remis au locataire de ce lot
  (`utils/porteurs_acces`), donc en lisait les codes et pouvait les déclarer
  perdus ;
- il devenait **bailleur** du bail : `exiger_bail_du_bailleur` le laissait le
  gérer, le terminer, y transférer des accès ;
- le vrai copropriétaire ne pouvait plus créer son propre bail (409 « déjà un
  bail en cours »).

L'écran ne proposait que « mes lots » — mais un écran masqué n'est pas un accès
refusé (`standards/03` §1) : le corps `lot_ids` est libre.

## Ce que le test tient

La règle vit dans `auth/appartenance.exiger_lot_du_bailleur`, et ce test passe
par la **route** : c'est elle qui doit l'appeler. Le lien exigé est ACTIF et de
nature copropriétaire — un locataire du lot n'en est pas le bailleur. Le conseil
syndical et l'administration restent admis, comme pour tout bail
(`exiger_bail_du_bailleur`).
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from sqlmodel import select

from app.models.core import LocationBail, Lot, StatutUtilisateur, TypeLien, UserLot
from app.routers.bailleur.baux import (
    creer_bail_multi,
    locataires_suggeres,
    search_locataire,
    update_bail,
)
from app.routers.bailleur.commun import BailCreateMulti, BailUpdate
from tests.aides_base import compte
from tests.conftest import requete_de_test


def _lot(session, numero: str) -> Lot:
    lot = Lot(numero=numero)
    session.add(lot)
    session.commit()
    session.refresh(lot)
    return lot


def _rattacher(session, user, lot, type_lien=TypeLien.bailleur, actif=True) -> None:
    session.add(UserLot(user_id=user.id, lot_id=lot.id, type_lien=type_lien, actif=actif))
    session.commit()
    session.refresh(user)


def _proprio(session):
    return compte(session, roles_json="propriétaire")


def _creer(session, user, lot_ids, **champs):
    data = BailCreateMulti(lot_ids=lot_ids, date_entree=date(2026, 10, 2), **champs)
    return creer_bail_multi(requete_de_test("/bailleur/baux/creer-multi"), data, user, session)


def _baux(session):
    return session.exec(select(LocationBail)).all()


def test_un_proprietaire_ne_pose_pas_de_bail_sur_le_lot_d_un_autre(session):
    """Le scénario du ticket : A vise le lot de B et s'en désigne locataire."""
    a, b = _proprio(session), _proprio(session)
    lot_de_b = _lot(session, "12")
    _rattacher(session, b, lot_de_b)

    with pytest.raises(HTTPException) as refus:
        _creer(session, a, [lot_de_b.id], locataire_id=a.id)
    assert refus.value.status_code == 403
    assert _baux(session) == []


def test_le_refus_laisse_une_trace_sans_donnee_personnelle(session, caplog):
    """La requête a été forgée : l'écran ne propose que « mes lots »."""
    a, lot = _proprio(session), _lot(session, "13")
    with caplog.at_level("WARNING", logger="securite"), pytest.raises(HTTPException):
        _creer(session, a, [lot.id])
    lignes = [r.getMessage() for r in caplog.records if r.name == "securite"]
    assert lignes == [f"securite bail_hors_de_ses_lots acteur={a.id} cible=- lot={lot.id}"]


def test_un_lien_desactive_ne_suffit_pas(session):
    """Un ancien copropriétaire n'est plus bailleur de ce lot (#1028)."""
    ancien = _proprio(session)
    lot = _lot(session, "14")
    _rattacher(session, ancien, lot, actif=False)

    with pytest.raises(HTTPException) as refus:
        _creer(session, ancien, [lot.id])
    assert refus.value.status_code == 403


def test_le_locataire_du_lot_n_en_est_pas_le_bailleur(session):
    """Un compte propriétaire ailleurs, locataire ICI : il ne loue pas ce lot."""
    u = _proprio(session)
    lot = _lot(session, "16")
    _rattacher(session, u, lot, type_lien=TypeLien.locataire)

    with pytest.raises(HTTPException) as refus:
        _creer(session, u, [lot.id])
    assert refus.value.status_code == 403


def test_un_seul_lot_etranger_et_aucun_bail_n_est_cree(session):
    """La demande est refusée entière : pas de bail posé à moitié."""
    a, b = _proprio(session), _proprio(session)
    le_sien, l_autre = _lot(session, "18"), _lot(session, "20")
    _rattacher(session, a, le_sien)
    _rattacher(session, b, l_autre)

    with pytest.raises(HTTPException) as refus:
        _creer(session, a, [le_sien.id, l_autre.id])
    assert refus.value.status_code == 403
    session.rollback()
    assert _baux(session) == []


@pytest.mark.parametrize("type_lien", [TypeLien.bailleur, TypeLien.propriétaire])
def test_le_coproprietaire_du_lot_pose_son_bail(session, type_lien):
    """Le cas nominal ne doit pas tomber avec le refus."""
    u = _proprio(session)
    lot = _lot(session, "22")
    _rattacher(session, u, lot, type_lien=type_lien)

    crees = _creer(session, u, [lot.id])
    assert [(b.lot_id, b.bailleur_id) for b in crees] == [(lot.id, u.id)]


@pytest.mark.parametrize("role", ["conseil_syndical", "admin"])
def test_le_conseil_et_l_administration_restent_admis(session, role):
    """Comme pour tout bail : ils arbitrent la gestion locative."""
    moderateur = compte(session, roles_json=role)
    lot = _lot(session, "24")

    assert len(_creer(session, moderateur, [lot.id])) == 1


def test_un_locataire_qui_n_existe_pas_est_refuse(session):
    """Un identifiant libre ferait du futur compte de ce numéro le porteur des badges."""
    u = _proprio(session)
    lot = _lot(session, "26")
    _rattacher(session, u, lot)

    with pytest.raises(HTTPException) as refus:
        _creer(session, u, [lot.id], locataire_id=987654)
    assert refus.value.status_code == 404
    assert _baux(session) == []


def test_corriger_le_locataire_vers_un_compte_inexistant_est_refuse(session):
    """La même contrainte à la correction : c'est le même champ, la même conséquence."""
    u = _proprio(session)
    lot = _lot(session, "28")
    _rattacher(session, u, lot)
    (bail,) = _creer(session, u, [lot.id])

    with pytest.raises(HTTPException) as refus:
        _corriger(session, u, bail, locataire_id=987654)
    assert refus.value.status_code == 404


# ── Le locataire désigné : un compte que la recherche rendrait (claude-config#656) ──
#
#  La règle : `auth/appartenance.est_locataire_designable`, que la recherche, les
#  suggestions et les deux routes appellent. Hors de son périmètre, la réponse est
#  celle d'un compte inexistant.


def _corriger(session, user, bail, **champs):
    requete = requete_de_test(f"/bailleur/baux/{bail.id}", "PATCH")
    return update_bail(requete, bail.id, BailUpdate(**champs), user, session)


def _bailleur_et_son_lot(session, numero: str):
    u = compte(session, prefixe="bailleur", roles_json="propriétaire", nom="MARTIN")
    lot = _lot(session, numero)
    _rattacher(session, u, lot)
    return u, lot


def _refus(appel) -> tuple[int, str]:
    with pytest.raises(HTTPException) as refus:
        appel()
    return refus.value.status_code, refus.value.detail


@pytest.mark.parametrize(
    "statut",
    [
        StatutUtilisateur.copropriétaire_résident,
        StatutUtilisateur.syndic,
        StatutUtilisateur.admin_technique,
        None,
    ],
)
def test_un_compte_hors_de_la_recherche_ne_se_designe_pas_locataire(session, statut):
    """La réponse est celle d'un compte inexistant : même code, même message, aucun nom."""
    u, lot = _bailleur_et_son_lot(session, "30")
    autre = compte(session, prefixe="autre", prenom="Claire", nom="LAMBERT", statut=statut)
    inexistant = _refus(lambda: _creer(session, u, [lot.id], locataire_id=987654))

    hors = _refus(lambda: _creer(session, u, [lot.id], locataire_id=autre.id))

    assert hors == inexistant == (404, "Locataire introuvable")
    session.rollback()
    assert _baux(session) == []


def test_corriger_vers_un_compte_hors_de_la_recherche_est_refuse(session):
    u, lot = _bailleur_et_son_lot(session, "32")
    (bail,) = _creer(session, u, [lot.id])
    autre = compte(session, prefixe="autre", statut=StatutUtilisateur.copropriétaire_résident)

    assert _refus(lambda: _corriger(session, u, bail, locataire_id=autre.id)) == (
        404,
        "Locataire introuvable",
    )
    session.rollback()
    session.refresh(bail)
    assert bail.locataire_id is None


def test_un_locataire_trouve_par_la_recherche_se_designe(session):
    """Le parcours de l'écran : chercher, choisir, créer — puis corriger vers un autre."""
    u, lot = _bailleur_et_son_lot(session, "34")
    loc = compte(
        session, prefixe="loc", prenom="Alice", nom="PERRIN", statut=StatutUtilisateur.locataire
    )
    autre = compte(
        session, prefixe="loc", prenom="Bruno", nom="PERRIN", statut=StatutUtilisateur.locataire
    )
    requete = requete_de_test("/bailleur/search-locataire", "GET")
    (trouve,) = search_locataire(requete, q="Alice", user=u, session=session)
    assert trouve.id == loc.id

    (bail,) = _creer(session, u, [lot.id], locataire_id=trouve.id)
    assert bail.locataire_id == loc.id

    assert _corriger(session, u, bail, locataire_id=autre.id).locataire_id == autre.id


def test_un_locataire_suggere_se_designe(session):
    """Les suggestions de l'écran (le locataire a nommé ce bailleur) passent aussi."""
    u, lot = _bailleur_et_son_lot(session, "36")
    loc = compte(
        session, prefixe="loc", statut=StatutUtilisateur.locataire, nom_proprietaire="M. MARTIN"
    )
    (suggere,) = locataires_suggeres(user=u, session=session)

    (bail,) = _creer(session, u, [lot.id], locataire_id=suggere.id)
    assert bail.locataire_id == loc.id


def test_corriger_un_bail_garde_le_locataire_qui_y_est_deja(session):
    """L'écran de correction renvoie le locataire du bail avec chaque modification.

    Il a pu y être rattaché par le serveur (`auto_match_service`,
    `rattachement_bailleur`) ou changer de statut depuis : ce n'est pas une
    désignation nouvelle, la corriger (une date, une note) reste permis.
    """
    u, lot = _bailleur_et_son_lot(session, "38")
    ancien = compte(session, prefixe="loc", statut=StatutUtilisateur.locataire)
    (bail,) = _creer(session, u, [lot.id], locataire_id=ancien.id)
    ancien.statut = StatutUtilisateur.copropriétaire_résident
    session.add(ancien)
    session.commit()

    corrige = _corriger(session, u, bail, locataire_id=ancien.id, notes="Préavis reçu")
    assert (corrige.locataire_id, corrige.notes) == (ancien.id, "Préavis reçu")
