"""Android : l'appareil `fcm`, sa charge et son transport FCM HTTP v1 (#2789).

Aucun appel réseau : le client HTTP est un `httpx.MockTransport`, et le compte de service
une clé RSA tirée pour le test.
"""

from __future__ import annotations

import json
import secrets

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from app.models.core import RoleUtilisateur
from app.utils import horloge
from app.utils.push.envoi import CORPS, TITRE, Envoi, charge_fcm
from app.utils.push.fcm import PORTEE, TransportFcm
from tests.aides_http import base_http, client_http

JETON_FCM = "dQw4w9WgXcQ:APA91b" + "x" * 140


def _envoi(**champs) -> Envoi:
    return Envoi(
        **{
            "plateforme": "fcm",
            "jeton": JETON_FCM,
            "environnement": "production",
            "abonnement": secrets.token_urlsafe(24),
            "niveau": "normal",
            "emis_le": horloge.maintenant(),
            "nonce": "n",
            **champs,
        }
    )


@pytest.fixture(scope="module")
def cle():
    privee = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = privee.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return pem, privee.public_key()


def _compte(pem: str) -> dict:
    return {
        "type": "service_account",
        "project_id": "coprofirst-essai",
        "client_email": "relais@coprofirst-essai.iam.gserviceaccount.example",
        "private_key": pem,
        "token_uri": "https://oauth2.example/token",
    }


def _transport(cle, reponse_envoi: httpx.Response):
    recus: list[httpx.Request] = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        recus.append(requete)
        if requete.url.host == "oauth2.example":
            return httpx.Response(200, json={"access_token": "acces-1", "expires_in": 3600})
        return reponse_envoi

    http = httpx.Client(transport=httpx.MockTransport(repondre))
    return TransportFcm(_compte(cle[0]), http), recus


def test_la_charge_ne_porte_que_le_texte_fixe_et_l_abonnement():
    envoi = _envoi()
    assert charge_fcm(envoi) == {
        "message": {
            "token": JETON_FCM,
            "notification": {"title": TITRE, "body": CORPS},
            "data": {"a": envoi.abonnement},
            "android": {"collapse_key": envoi.abonnement, "priority": "normal"},
        }
    }
    assert charge_fcm(_envoi(niveau="urgent"))["message"]["android"]["priority"] == "high"


def test_le_jeton_se_juge_selon_sa_plateforme():
    with pytest.raises(ValidationError):
        _envoi(plateforme="apns")  # un jeton FCM n'est pas un jeton APNs
    with pytest.raises(ValidationError):
        _envoi(jeton="a" * 64 + "<script>")
    assert _envoi(plateforme="apns", jeton="ab" * 32).plateforme == "apns"


def test_le_transport_signe_son_assertion_et_envoie_la_charge(cle):
    transport, recus = _transport(cle, httpx.Response(200, json={"name": "m/1"}))
    envoi = _envoi()
    assert transport.transmettre(envoi).statut == "envoye"
    jeton_req, envoi_req = recus
    assertion = dict(x.split("=", 1) for x in jeton_req.content.decode().split("&"))["assertion"]
    lue = jwt.decode(
        assertion, cle[1], algorithms=["RS256"], audience="https://oauth2.example/token"
    )
    assert lue["scope"] == PORTEE and lue["iss"].startswith("relais@")
    assert envoi_req.url.path == "/v1/projects/coprofirst-essai/messages:send"
    assert envoi_req.headers["Authorization"] == "Bearer acces-1"
    assert json.loads(envoi_req.content) == charge_fcm(envoi)
    #  Le jeton d'accès se garde : un second envoi ne redemande rien.
    transport.transmettre(_envoi())
    assert len(recus) == 3


@pytest.mark.parametrize("code", ["UNREGISTERED", "INVALID_ARGUMENT"])
def test_un_jeton_inscrit_nulle_part_se_dit_perime(cle, code):
    corps = {"error": {"status": "NOT_FOUND", "details": [{"errorCode": code}]}}
    transport, _ = _transport(cle, httpx.Response(404, json=corps))
    resultat = transport.transmettre(_envoi())
    assert resultat.statut == "jeton_perime" and JETON_FCM not in resultat.motif


def test_un_autre_refus_ne_repete_rien_de_la_requete(cle):
    transport, _ = _transport(cle, httpx.Response(503, text="indisponible"))
    envoi = _envoi()
    resultat = transport.transmettre(envoi)
    assert resultat.statut == "refuse"
    assert envoi.jeton not in resultat.motif and envoi.abonnement not in resultat.motif
    assert transport.transmettre(_envoi(plateforme="apns", jeton="ab" * 32)).statut == "refuse"


def test_un_compte_de_service_incomplet_est_refuse(cle):
    with pytest.raises(ValueError, match="private_key"):
        TransportFcm({**_compte(cle[0]), "private_key": ""})


@pytest.fixture()
def moteur():
    with base_http() as m:
        yield m


def test_un_telephone_android_s_enregistre_et_l_ios_publie_reste_admis(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    abonnement = secrets.token_urlsafe(24)
    corps = {"plateforme": "fcm", "jeton": JETON_FCM, "abonnement": abonnement}
    assert http.post("/appareils", json=corps).status_code == 204
    #  Un jeton FCM présenté comme APNs, ou l'inverse : 422.
    assert http.post("/appareils", json={**corps, "plateforme": "apns"}).status_code == 422
    ios = {
        "jeton": "ab" * 32,
        "environnement": "production",
        "abonnement": secrets.token_urlsafe(24),
    }
    assert http.post("/appareils", json=ios).status_code == 204
    assert http.post("/appareils", json={**ios, "plateforme": "fcm"}).status_code == 422
