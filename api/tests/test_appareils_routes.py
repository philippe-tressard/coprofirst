"""Les appareils d'une personne — routes, changement de main, retraits, purge (#2493).

Spécification : `specs/architecture/notifications-push.md` §6.2 et §6.3. Les routes
passent par la VRAIE authentification (`aides_http`) : un anonyme est refusé, et
l'abonnement d'un autre compte rend 404.

Fermer les sessions d'un compte (`revoquer_sessions` : rejeu d'un jeton, mot de passe
changé ou réinitialisé) retire aussi ses appareils — tous : rien ne relie un appareil à
une session, et le téléphone qui a changé le mot de passe se ré-enregistre à l'ouverture.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.models.appareils import Appareil
from app.models.core import RoleUtilisateur, Utilisateur
from app.utils import horloge
from app.utils.push.appareils import ABANDON_JOURS, purger_abandonnes, retirer_appareils
from app.auth.jetons_rafraichissement import fermer_apres_rejeu, revoquer_sessions
from app.utils.suppression_compte import supprimer_compte
from tests.aides_base import compte
from tests.aides_http import base_http, client_http


@pytest.fixture()
def moteur():
    with base_http() as m:
        yield m


def _corps(**champs) -> dict:
    return {
        "jeton": secrets.token_hex(32),
        "environnement": "production",
        "abonnement": secrets.token_urlsafe(24),
        **champs,
    }


def _appareils(moteur, utilisateur_id: int) -> list[Appareil]:
    with Session(moteur) as s:
        return list(s.exec(select(Appareil).where(Appareil.utilisateur_id == utilisateur_id)).all())


def test_un_anonyme_n_enregistre_rien(moteur):
    http, _ = client_http(moteur, None)
    assert http.post("/appareils", json=_corps()).status_code == 401
    assert http.delete("/appareils/abcdefghijklmnopqrstu").status_code == 401


def test_enregistrer_puis_retirer(moteur):
    http, ident = client_http(moteur, RoleUtilisateur.propriétaire)
    corps = _corps()
    r = http.post("/appareils", json=corps)
    assert r.status_code == 204 and r.content == b"", "rien n'est rendu, pas même le jeton"
    #  Le même appareil, ré-enregistré : rafraîchi, pas doublé.
    assert (
        http.post("/appareils", json={**corps, "environnement": "developpement"}).status_code == 204
    )
    (appareil,) = _appareils(moteur, ident)
    assert appareil.environnement == "developpement"
    assert http.delete(f"/appareils/{corps['abonnement']}").status_code == 204
    assert _appareils(moteur, ident) == []


@pytest.mark.parametrize(
    "fautif",
    [
        {"jeton": "pas-un-jeton"},
        {"abonnement": "court"},
        {"environnement": "staging"},
        {"titre": "un champ de trop"},
    ],
)
def test_un_corps_hors_contrat_est_refuse(moteur, fautif):
    http, ident = client_http(moteur, RoleUtilisateur.propriétaire)
    assert http.post("/appareils", json=_corps(**fautif)).status_code == 422
    assert _appareils(moteur, ident) == []


def test_un_jeton_connu_change_de_main(moteur):
    """Le téléphone a changé de session : l'appareil suit le compte connecté."""
    premier, ident_1 = client_http(moteur, RoleUtilisateur.propriétaire)
    second, ident_2 = client_http(moteur, RoleUtilisateur.résident)
    corps = _corps()
    assert premier.post("/appareils", json=corps).status_code == 204
    neuf = {**corps, "abonnement": secrets.token_urlsafe(24)}
    assert second.post("/appareils", json=neuf).status_code == 204
    assert _appareils(moteur, ident_1) == []
    (appareil,) = _appareils(moteur, ident_2)
    assert appareil.abonnement == neuf["abonnement"]


def test_l_abonnement_d_un_autre_compte_rend_404(moteur):
    proprietaire, ident = client_http(moteur, RoleUtilisateur.propriétaire)
    voisin, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    corps = _corps()
    assert proprietaire.post("/appareils", json=corps).status_code == 204
    assert voisin.delete(f"/appareils/{corps['abonnement']}").status_code == 404
    assert len(_appareils(moteur, ident)) == 1


def test_desactiver_un_compte_retire_ses_appareils(moteur):
    resident, ident = client_http(moteur, RoleUtilisateur.propriétaire)
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    assert resident.post("/appareils", json=_corps()).status_code == 204
    #  Renvoyer l'état actif ne retire rien : seule la bascule compte.
    assert admin.patch(f"/admin/utilisateurs/{ident}", json={"actif": True}).status_code == 200
    assert len(_appareils(moteur, ident)) == 1
    assert admin.patch(f"/admin/utilisateurs/{ident}", json={"actif": False}).status_code == 200
    assert _appareils(moteur, ident) == []


def _poser(session, utilisateur_id: int, **champs) -> Appareil:
    a = Appareil(
        utilisateur_id=utilisateur_id,
        jeton=secrets.token_hex(32),
        abonnement=secrets.token_urlsafe(24),
        **champs,
    )
    session.add(a)
    session.commit()
    return a


def test_supprimer_un_compte_retire_ses_appareils(session):
    personne = compte(session, prefixe="appareil-supprime")
    ident = personne.id
    _poser(session, ident)
    supprimer_compte(session, ident)
    session.commit()
    session.expunge_all()
    assert session.exec(select(Appareil)).all() == []
    assert session.get(Utilisateur, ident) is None


def test_retirer_les_appareils_d_un_compte(session):
    personne, autre = compte(session, prefixe="appareil-a"), compte(session, prefixe="appareil-b")
    _poser(session, personne.id), _poser(session, personne.id), _poser(session, autre.id)
    assert retirer_appareils(session, personne.id) == 2
    session.commit()
    assert [a.utilisateur_id for a in session.exec(select(Appareil)).all()] == [autre.id]


def test_la_purge_retire_les_seuls_appareils_abandonnes(session):
    personne = compte(session, prefixe="appareil-purge")
    maintenant = horloge.maintenant()
    garde = _poser(session, personne.id, vu_le=maintenant - timedelta(days=ABANDON_JOURS - 1))
    _poser(session, personne.id, vu_le=maintenant - timedelta(days=ABANDON_JOURS + 1))
    assert purger_abandonnes(session) == 1
    session.commit()
    assert [a.id for a in session.exec(select(Appareil)).all()] == [garde.id]


@pytest.mark.parametrize("fermer", [revoquer_sessions, fermer_apres_rejeu])
def test_fermer_les_sessions_retire_les_appareils(session, fermer):
    """Une session fermée ne laisse pas un téléphone sonner (spec §6.3)."""
    personne, autre = (
        compte(session, prefixe="appareil-sessions"),
        compte(session, prefixe="appareil-x"),
    )
    _poser(session, personne.id), _poser(session, autre.id)
    fermer(session, personne.id)
    session.commit()
    assert [a.utilisateur_id for a in session.exec(select(Appareil)).all()] == [autre.id]
