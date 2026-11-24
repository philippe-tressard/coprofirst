"""La déconnexion ferme la session présentée, jetons d'accès compris (23/11/2026).

## La règle (arbitrée le 23/11/2026, « cette session »)

`POST /auth/logout` ferme la SESSION qui se présente : son jeton de
rafraîchissement, et les jetons d'accès émis pour elle. Les autres sessions du
compte — un autre appareil, un autre navigateur — restent ouvertes ; les montres
et les appareils push ne sont pas touchés.

Le jeton d'accès porte l'identifiant de sa session (`sid`), que les jetons de
rafraîchissement de la même session portent aussi, rotation après rotation
(`auth/jetons_rafraichissement.py`). `_get_current_user` n'accepte un jeton qui
porte une session que si elle est encore ouverte. Un jeton d'accès émis avant ce
lot n'en porte pas : il reste jugé comme avant, et expire seul.

Le parcours passe par HTTP, avec deux clients : deux appareils, deux sessions du
même compte. Le jeton d'accès se relève AVANT la déconnexion, qui vide le jar.
"""

from __future__ import annotations

import ast
import logging

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth.jwt import creer_jeton_acces, hash_password
from app.main import app
from app.models.core import Utilisateur
from tests.aides_base import compte
from tests.aides_http import base_http
from tests.aides_sources import modules_app

MOT_DE_PASSE = "Deconnexion-Essai-1"
ADRESSE = "https://testserver"


@pytest.fixture()
def moteur():
    with base_http() as m:
        yield m


def _compte(moteur) -> tuple[int, str]:
    with Session(moteur) as s:
        u = compte(
            s,
            prefixe="deconnexion",
            hashed_password=hash_password(MOT_DE_PASSE),
            email_verifie=True,
        )
        return u.id, u.email


def _connecter(email: str) -> TestClient:
    http = TestClient(app, base_url=ADRESSE)
    r = http.post("/auth/login", json={"email": email, "password": MOT_DE_PASSE})
    assert r.status_code == 200, r.text
    return http


def _porteur(jeton_acces: str) -> TestClient:
    """Un client qui ne présente QUE ce jeton d'accès."""
    http = TestClient(app, base_url=ADRESSE)
    http.cookies.set("access_token", jeton_acces)
    return http


def test_apres_la_deconnexion_le_jeton_d_acces_de_cette_session_est_refuse(moteur):
    _, email = _compte(moteur)
    telephone = _connecter(email)
    acces = telephone.cookies["access_token"]
    assert _porteur(acces).get("/auth/me").status_code == 200

    assert telephone.post("/auth/logout").status_code == 200

    assert _porteur(acces).get("/auth/me").status_code == 401, (
        "La session est fermée, et son jeton d'accès ouvre encore la porte jusqu'à son échéance."
    )


def test_la_deconnexion_laisse_ouvertes_les_autres_sessions_du_compte(moteur):
    _, email = _compte(moteur)
    telephone = _connecter(email)
    tablette = _connecter(email)

    assert telephone.post("/auth/logout").status_code == 200

    assert tablette.get("/auth/me").status_code == 200, (
        "Se déconnecter du téléphone a fermé la tablette."
    )
    assert tablette.post("/auth/refresh").status_code == 200
    assert tablette.get("/auth/me").status_code == 200


def test_la_session_survit_a_la_rotation_puis_ferme_en_entier(moteur):
    """La session est portée d'un jeton de rafraîchissement au suivant."""
    _, email = _compte(moteur)
    http = _connecter(email)
    avant = http.cookies["access_token"]

    assert http.post("/auth/refresh").status_code == 200
    apres = http.cookies["access_token"]
    for nom, jeton in (("avant", avant), ("après", apres)):
        assert _porteur(jeton).get("/auth/me").status_code == 200, (
            f"le jeton d'accès émis {nom} la rotation est refusé : la session ne l'a pas suivie"
        )

    assert http.post("/auth/logout").status_code == 200

    for nom, jeton in (("avant", avant), ("après", apres)):
        assert _porteur(jeton).get("/auth/me").status_code == 401, (
            f"le jeton d'accès émis {nom} la rotation survit à la déconnexion"
        )


def test_un_jeton_d_acces_sans_session_reste_juge_comme_avant(moteur):
    """Compatibilité : un jeton émis avant ce lot ne porte pas de session, il expire seul."""
    ident, email = _compte(moteur)
    with Session(moteur) as s:
        u = s.get(Utilisateur, ident)
        ancien = creer_jeton_acces(u.id, u.hashed_password, u.generation_sessions)
    assert _porteur(ancien).get("/auth/me").status_code == 200

    http = _connecter(email)
    assert http.post("/auth/logout").status_code == 200

    assert _porteur(ancien).get("/auth/me").status_code == 200


def test_la_deconnexion_laisse_une_ligne_au_journal(moteur, caplog):
    ident, email = _compte(moteur)
    http = _connecter(email)
    rafraichissement = http.cookies["refresh_token"]
    caplog.set_level(logging.INFO, logger="securite")

    assert http.post("/auth/logout").status_code == 200
    #  Une seconde déconnexion de la même session ne ferme rien : pas de seconde ligne.
    http.cookies.set("refresh_token", rafraichissement)
    assert http.post("/auth/logout").status_code == 200

    lignes = [r.getMessage() for r in caplog.records if r.name == "securite"]
    fermees = [ligne for ligne in lignes if "session_fermee" in ligne]
    assert len(fermees) == 1, lignes
    assert f"cible={ident}" in fermees[0]
    assert email not in fermees[0]


# ── Un émetteur qui oublierait la session ───────────────────────────────────
#
#  Un jeton d'accès émis sans session est jugé sur l'empreinte seule : aucune
#  déconnexion ne le ferme, et rien ne le dirait. Sous `app/`, chaque appel de
#  `creer_jeton_acces` passe donc la session (4ᵉ argument ou `session_id=`).


def _sans_session(source: str) -> list[int]:
    return [
        n.lineno
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.Call)
        and getattr(n.func, "id", getattr(n.func, "attr", None)) == "creer_jeton_acces"
        and len(n.args) < 4
        and not any(k.arg == "session_id" for k in n.keywords)
    ]


def test_le_controle_voit_un_emetteur_sans_session():
    """Un contrôle qui ne peut pas échouer ne prouve rien (`standards/04`)."""
    assert _sans_session("creer_jeton_acces(u.id, u.hashed_password, 0)") == [1]
    assert _sans_session("creer_jeton_acces(u.id, h, 0, sid)") == []
    assert _sans_session("jwt.creer_jeton_acces(u.id, h, session_id=sid)") == []


def test_tout_jeton_d_acces_emis_par_l_application_porte_sa_session():
    fichiers = modules_app()
    appelants = [m.rel for m in fichiers if "creer_jeton_acces(" in m.source]
    assert "auth/session_ouverte.py" in appelants, "le contrôle ne voit plus l'émetteur connu"
    ecarts = [f"app/{m.rel}:{ligne}" for m in fichiers for ligne in _sans_session(m.source)]
    assert not ecarts, "Un jeton d'accès émis sans session échappe à la déconnexion :\n" + (
        "\n".join(f"  • {e}" for e in ecarts)
    )
