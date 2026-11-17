"""Le jeton d'une montre : lire la cloche, rien d'autre — révocable, expirant (#2771).

Portée arrêtée le 16/11/2026 (coprofirst-ios#226) : `GET /notifications` seul, aucun
marquage comme lu, la même pour Apple Watch et Wear OS. Les routes passent par la VRAIE
authentification (`aides_http`) : le téléphone émet par sa session, la montre lit par
`Authorization: Bearer`.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.auth.jetons_appareil import PORTEES, purger_echus
from app.auth.jetons_montre import MONTRES_PAR_COMPTE
from app.auth.jetons_rafraichissement import fermer_apres_rejeu
from app.models.core import Notification, RoleUtilisateur, Utilisateur
from app.models.jetons import JetonMontre
from app.utils import horloge
from app.utils.suppression_compte import supprimer_compte
from tests.aides_http import base_http, client_http
from tests.aides_sources import routes_declarees

PROPRIO = RoleUtilisateur.propriétaire
#: La durée de vie du jeton d'une montre — une ligne de la table commune (#2770).
DUREE_JOURS = PORTEES["montre"].duree.days


@pytest.fixture()
def moteur():
    with base_http() as m:
        yield m


def _relier(moteur, plateforme: str = "watchos"):
    """Un téléphone connecté qui relie une montre : (client du téléphone, id, jeton brut)."""
    telephone, ident = client_http(moteur, PROPRIO)
    with Session(moteur) as s:
        s.add(Notification(destinataire_id=ident, titre="Fuite", corps="Cave B", type="ticket"))
        s.commit()
    r = telephone.post("/montres", json={"plateforme": plateforme})
    assert r.status_code == 201, r.text
    return telephone, ident, r.json()


def _montre(moteur, brut: str):
    """Un client SANS cookie, qui présente le jeton de la montre."""
    http, _ = client_http(moteur, None)
    http.headers["Authorization"] = f"Bearer {brut}"
    return http


@pytest.mark.parametrize("plateforme", ["watchos", "wearos"])
def test_la_montre_lit_la_cloche_et_rien_d_autre(moteur, plateforme):
    _, _, emise = _relier(moteur, plateforme)
    montre = _montre(moteur, emise["jeton"])
    lues = montre.get("/notifications")
    assert lues.status_code == 200 and [n["titre"] for n in lues.json()] == ["Fuite"]
    notif_id = lues.json()[0]["id"]
    #  Aucune écriture, pas même sur la cloche ; aucune autre lecture, pas même le profil.
    assert montre.patch(f"/notifications/{notif_id}/lue").status_code == 401
    assert montre.post("/notifications/tout-marquer-lu").status_code == 401
    assert montre.delete(f"/notifications/{notif_id}").status_code == 401
    assert montre.get("/auth/me").status_code == 401
    assert montre.get("/montres").status_code == 401
    assert montre.post("/montres", json={"plateforme": plateforme}).status_code == 401


def test_aucune_autre_route_ne_prend_la_dependance_de_la_cloche():
    """La portée tient à ce qu'UNE route accepte le jeton : toute autre le refuse."""
    from app.auth.deps import lecteur_de_la_cloche

    def prend(dependant) -> bool:
        return any(d.call is lecteur_de_la_cloche or prend(d) for d in dependant.dependencies)

    routes = routes_declarees()
    assert len(routes) > 300, f"{len(routes)} routes lues — cas zéro, la lecture a échoué"
    preneuses = sorted((sorted(r.methods), r.path) for r in routes if prend(r.dependant))
    assert preneuses == [(["GET"], "/notifications")], preneuses


def test_le_jeton_n_est_rendu_qu_a_l_emission_et_se_stocke_par_son_empreinte(moteur):
    telephone, ident, emise = _relier(moteur)
    liste = telephone.get("/montres").json()
    assert [m["id"] for m in liste] == [emise["id"]] and "jeton" not in liste[0]
    with Session(moteur) as s:
        (ligne,) = s.exec(select(JetonMontre).where(JetonMontre.utilisateur_id == ident)).all()
        assert ligne.empreinte != emise["jeton"] and len(ligne.empreinte) == 64


def test_retirer_une_montre_la_fait_taire_aussitot(moteur):
    telephone, _, emise = _relier(moteur)
    assert telephone.delete(f"/montres/{emise['id']}").status_code == 204
    assert _montre(moteur, emise["jeton"]).get("/notifications").status_code == 401


def test_la_montre_d_un_autre_compte_rend_404(moteur):
    _, _, emise = _relier(moteur)
    voisin, _ = client_http(moteur, PROPRIO)
    assert voisin.delete(f"/montres/{emise['id']}").status_code == 404
    assert voisin.post(f"/montres/{emise['id']}/renouveler").status_code == 404
    assert _montre(moteur, emise["jeton"]).get("/notifications").status_code == 200


def test_le_jeton_expire_et_le_telephone_le_renouvelle(moteur):
    telephone, _, emise = _relier(moteur)
    with Session(moteur) as s:
        ligne = s.get(JetonMontre, emise["id"])
        ligne.expire_le = horloge.maintenant() - timedelta(seconds=1)
        s.add(ligne)
        s.commit()
    assert _montre(moteur, emise["jeton"]).get("/notifications").status_code == 401
    neuf = telephone.post(f"/montres/{emise['id']}/renouveler")
    assert neuf.status_code == 200 and neuf.json()["jeton"] != emise["jeton"]
    assert _montre(moteur, neuf.json()["jeton"]).get("/notifications").status_code == 200
    assert _montre(moteur, emise["jeton"]).get("/notifications").status_code == 401
    with Session(moteur) as s:
        restant = s.get(JetonMontre, emise["id"]).expire_le - horloge.maintenant()
        assert timedelta(days=DUREE_JOURS - 1) < restant <= timedelta(days=DUREE_JOURS)
        assert purger_echus(s, horloge.maintenant() + timedelta(days=DUREE_JOURS + 1)) == 1


def test_les_sessions_fermees_ou_le_mot_de_passe_change_font_tomber_la_montre(moteur):
    _, ident, emise = _relier(moteur)
    #  Mot de passe changé : l'empreinte du compte change, le jeton tombe à la lecture.
    with Session(moteur) as s:
        user = s.get(Utilisateur, ident)
        user.hashed_password = "autre"
        s.add(user)
        s.commit()
    assert _montre(moteur, emise["jeton"]).get("/notifications").status_code == 401
    #  Sessions fermées après un rejeu : la ligne même est retirée.
    _, ident2, emise2 = _relier(moteur)
    with Session(moteur) as s:
        fermer_apres_rejeu(s, ident2)
        s.commit()
        assert s.exec(select(JetonMontre).where(JetonMontre.utilisateur_id == ident2)).all() == []
    assert _montre(moteur, emise2["jeton"]).get("/notifications").status_code == 401


def test_un_compte_supprime_emporte_ses_montres(moteur):
    _, ident, emise = _relier(moteur)
    with Session(moteur) as s:
        supprimer_compte(s, ident)
        s.commit()
        assert s.exec(select(JetonMontre).where(JetonMontre.utilisateur_id == ident)).all() == []
    assert _montre(moteur, emise["jeton"]).get("/notifications").status_code == 401


def test_un_jeton_inconnu_ou_mal_forme_est_refuse(moteur):
    for entete in ("Bearer inconnu", "Bearer ", "Basic abc", "inconnu"):
        http, _ = client_http(moteur, None)
        http.headers["Authorization"] = entete
        assert http.get("/notifications").status_code == 401, entete


def test_un_compte_ne_relie_qu_un_nombre_borne_de_montres(moteur):
    telephone, ident, _ = _relier(moteur)
    for _ in range(MONTRES_PAR_COMPTE + 2):
        assert telephone.post("/montres", json={"plateforme": "wearos"}).status_code == 201
    assert len(telephone.get("/montres").json()) == MONTRES_PAR_COMPTE
    assert telephone.post("/montres", json={"plateforme": "garmin"}).status_code == 422
