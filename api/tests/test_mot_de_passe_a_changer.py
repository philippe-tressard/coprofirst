"""Un compte au mot de passe TEMPORAIRE ne fait que le changer (#3019, décidé le 23/11/2026).

Le seed crée l'administrateur et l'opérateur d'une installation neuve avec un mot de
passe tiré au sort, écrit au journal du conteneur (#2973). Le drapeau
`mot_de_passe_a_changer` est posé sur les deux ; tant qu'il tient, l'API refuse toute
route authentifiée — 403, motif `mot_de_passe_a_changer` — sauf les deux qui servent à
en sortir : lire son profil, changer son mot de passe. Se déconnecter et renouveler sa
session ne prennent pas la dépendance d'auth, et restent ouverts.

Ce fichier le prouve par le comportement, sur les vrais comptes du seed et la vraie
connexion :

1. **Le balayage** : chaque opération montée qui résout la dépendance d'auth est
   appelée par un compte marqué ; hors des deux routes admises, chacune rend le refus.
2. **La sortie** : changer son mot de passe lève le drapeau, et tout s'ouvre.
3. **Le même mot de passe** ne lève rien : le mot de passe du journal resterait valide.
4. **Un compte non marqué** : rien ne change.
"""

from __future__ import annotations

import logging
import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import app.seed as module_seed
from app.auth import deps
from app.auth.jwt import hash_password
from app.main import app
from app.models.core import RoleUtilisateur, Utilisateur
from tests.aides_base import compte
from tests.aides_http import base_http, client_http
from tests.aides_sources import chemin_concret, operations_montees, resout

#: La décision, écrite ici en clair : la table d'`auth/` doit la porter, rien de plus.
ADMISES = {("GET", "/auth/me"), ("POST", "/auth/change-password")}
#: Le motif du refus, que le site et les apps reconnaissent : le changer les casse.
MOTIF = "mot_de_passe_a_changer"
#: Ces deux-là ferment ou font tourner la session : appelés à part, après le balayage.
SESSION = {("POST", "/auth/logout"), ("POST", "/auth/refresh")}
#: Le cas zéro du balayage — un ordre de grandeur, pas une valeur figée.
MINIMUM_REFUSEES = 300
ADRESSE = "https://testserver"
NOUVEAU = "Nouveau-Secret-2026"
#: Des routes qu'un administrateur lit, de familles différentes : refusées puis ouvertes.
LECTURES = ["/tickets", "/notifications", "/config/services", "/admin/utilisateurs"]


@pytest.fixture()
def moteur(batiments):
    with base_http() as m:
        yield m


def _seed(moteur, caplog) -> dict[str, str]:
    """Les deux comptes initiaux, par le VRAI seed : adresse → mot de passe du journal."""
    with caplog.at_level(logging.WARNING, logger="app.seed"), Session(moteur) as session:
        module_seed._admin_initial(session)
        session.commit()
    admin = re.search(r"Mot de passe temporaire : (\S+)", caplog.text)
    operateur = re.search(r"Mot de passe de l'opérateur : (\S+)", caplog.text)
    assert admin and operateur, "les mots de passe initiaux ne sont plus journalisés"
    return {
        module_seed.ADRESSE_ADMIN_INITIAL: admin.group(1),
        module_seed.ADRESSE_OPERATEUR_INITIAL: operateur.group(1),
    }


def _connecter(email: str, mot_de_passe: str) -> TestClient:
    #  Une erreur du serveur se lit en 500 : le balayage la compte comme un écart, il ne
    #  s'arrête pas sur la première route qui aurait dû être refusée.
    http = TestClient(app, base_url=ADRESSE, raise_server_exceptions=False)
    r = http.post("/auth/login", json={"email": email, "password": mot_de_passe})
    assert r.status_code == 200, r.text
    return http


def _drapeau(moteur, email: str) -> bool:
    with Session(moteur) as s:
        return (
            s.exec(select(Utilisateur).where(Utilisateur.email == email))
            .one()
            .mot_de_passe_a_changer
        )


def _est_le_refus(reponse) -> bool:
    if reponse.status_code != 403:
        return False
    detail = reponse.json().get("detail")
    return isinstance(detail, dict) and detail.get("code") == MOTIF and bool(detail.get("message"))


def test_un_compte_marque_n_ouvre_que_les_routes_admises(moteur, caplog):
    comptes = _seed(moteur, caplog)
    adresse = module_seed.ADRESSE_OPERATEUR_INITIAL  # administrateur ET opérateur : il voit tout
    http = _connecter(adresse, comptes[adresse])
    anonyme = TestClient(app, base_url=ADRESSE, raise_server_exceptions=False)
    gardees = (deps.get_current_user, deps.lecteur_de_la_cloche)
    refusees, admises, ecarts = 0, set(), []
    for methode, gabarit, route in sorted(operations_montees(app), key=lambda o: o[:2]):
        cle = (methode, gabarit)
        if methode == "HEAD" or cle in SESSION or not resout(route.dependant, gardees):
            continue
        r = http.request(methode, chemin_concret(gabarit))
        if cle in ADMISES:
            admises.add(cle)
            if r.status_code in (401, 403):
                ecarts.append(f"{methode} {gabarit} : {r.status_code} sur une route ADMISE")
        elif _est_le_refus(r):
            refusees += 1
        elif r.status_code != anonyme.request(methode, chemin_concret(gabarit)).status_code:
            #  Un refus que l'anonyme reçoit AUSSI précède l'authentification (un paramètre
            #  de chemin jugé avant elle) : il ne laisse rien passer. Tout autre code, si.
            ecarts.append(f"{methode} {gabarit} : {r.status_code} {r.text[:120]}")
    assert not ecarts, "un compte marqué passe ou reçoit un autre refus :\n" + "\n".join(ecarts)
    assert refusees > MINIMUM_REFUSEES, f"{refusees} routes refusées — cas zéro"
    assert admises == ADMISES, admises

    #  Le profil se lit, et dit le drapeau : c'est ce qui mène l'écran au changement.
    me = http.get("/auth/me")
    assert me.status_code == 200 and me.json()["mot_de_passe_a_changer"] is True, me.text
    #  Renouveler puis quitter la session restent possibles.
    assert http.post("/auth/refresh").status_code == 200
    assert http.post("/auth/logout").status_code == 200


def test_la_table_des_routes_admises_est_la_decision():
    from app.auth.mot_de_passe_a_changer import MOTIF as publie
    from app.auth.mot_de_passe_a_changer import ROUTES_ADMISES

    assert set(ROUTES_ADMISES) == ADMISES
    assert publie == MOTIF


def test_changer_son_mot_de_passe_leve_le_drapeau_et_ouvre_tout(moteur, caplog):
    comptes = _seed(moteur, caplog)
    adresse = module_seed.ADRESSE_ADMIN_INITIAL
    http = _connecter(adresse, comptes[adresse])
    for chemin in LECTURES:
        assert _est_le_refus(http.get(chemin)), f"GET {chemin} ouvert avant le changement"

    r = http.post(
        "/auth/change-password",
        json={"mot_de_passe_actuel": comptes[adresse], "nouveau_mot_de_passe": NOUVEAU},
    )
    assert r.status_code == 204, r.text
    assert _drapeau(moteur, adresse) is False
    #  Le jeton d'accès est tombé avec l'empreinte du compte (#1063) : la session se renouvelle.
    assert http.post("/auth/refresh").status_code == 200
    assert http.get("/auth/me").json()["mot_de_passe_a_changer"] is False
    for chemin in LECTURES:
        r = http.get(chemin)
        assert r.status_code == 200, f"GET {chemin} : {r.status_code} {r.text[:200]}"
    #  L'autre compte initial, lui, reste marqué : chacun change le sien.
    assert _drapeau(moteur, module_seed.ADRESSE_OPERATEUR_INITIAL) is True


def test_reposer_le_meme_mot_de_passe_ne_leve_pas_le_drapeau(moteur):
    secret = "Temporaire-Robuste-1"
    with Session(moteur) as s:
        email = compte(
            s,
            prefixe="temporaire",
            hashed_password=hash_password(secret),
            email_verifie=True,
            roles_json=RoleUtilisateur.admin.value,
            mot_de_passe_a_changer=True,
        ).email
    http = _connecter(email, secret)
    r = http.post(
        "/auth/change-password",
        json={"mot_de_passe_actuel": secret, "nouveau_mot_de_passe": secret},
    )
    assert r.status_code == 400, r.text
    assert _drapeau(moteur, email) is True, "le mot de passe du journal resterait valide"
    assert _est_le_refus(http.get("/tickets"))


def test_la_reinitialisation_leve_aussi_le_drapeau(moteur):
    """« Mot de passe oublié » pose un mot de passe par la même porte : le drapeau tombe."""
    from app.utils.mots_de_passe import poser_mot_de_passe

    with Session(moteur) as s:
        u = compte(
            s,
            prefixe="oubli",
            hashed_password=hash_password("Temporaire-Robuste-1"),
            mot_de_passe_a_changer=True,
        )
        poser_mot_de_passe(s, u, NOUVEAU)
        s.commit()
        s.refresh(u)
        assert u.mot_de_passe_a_changer is False


def test_un_compte_non_marque_ne_change_rien(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    me = http.get("/auth/me")
    assert me.status_code == 200 and me.json()["mot_de_passe_a_changer"] is False, me.text
    for chemin in LECTURES:
        r = http.get(chemin)
        assert r.status_code == 200, f"GET {chemin} : {r.status_code} {r.text[:200]}"
