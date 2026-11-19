"""🔒 Le transport APNs du relais (#2494, `notifications-push.md` §4 et §5).

Aucun appel réseau : le client HTTP est un double (`httpx.MockTransport`) et la clé une
clé EC P-256 tirée pour le test. Ce fichier tient :

- l'authentification : un JWT ES256 vérifiable par la clé publique, `kid` = l'identifiant
  de la clé, `iss` = l'équipe, gardé moins d'une heure ;
- ce qui part chez Apple : l'hôte de l'environnement, `/3/device/<jeton>`, les en-têtes
  (`apns-topic`, `apns-push-type`, `apns-collapse-id`, `apns-priority`) et la charge du §5 ;
- ce qu'Apple répond : `envoye` (avec l'`apns-id`), `jeton_perime` (410, `BadDeviceToken`),
  `refuse` sans rien répéter de la requête ;
- le relais : la clé posée en base64 se lit, une clé illisible ne part pas.
"""

from __future__ import annotations

import base64
import json
import secrets

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.config import get_settings
from app.utils import horloge
from app.utils.push import apns, relais
from app.utils.push.apns import EQUIPE, SUJET, TransportApns
from app.utils.push.envoi import CORPS, TITRE, Envoi
from app.utils.push.transport import Resultat

JETON = "ab" * 32
ID_CLE = "ESSAI12345"


def _envoi(**champs) -> Envoi:
    return Envoi(
        **{
            "plateforme": "apns",
            "jeton": JETON,
            "environnement": "production",
            "abonnement": secrets.token_urlsafe(24),
            "niveau": "urgent",
            "emis_le": horloge.maintenant(),
            "nonce": "n",
            **champs,
        }
    )


@pytest.fixture(scope="module")
def cle():
    privee = ec.generate_private_key(ec.SECP256R1())
    pem = privee.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return pem, privee.public_key()


def _transport(cle, reponse: httpx.Response | Exception):
    recus: list[httpx.Request] = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        recus.append(requete)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse

    http = httpx.Client(transport=httpx.MockTransport(repondre))
    return TransportApns(cle[0], ID_CLE, http), recus


def test_l_envoi_est_signe_et_ne_porte_que_le_paragraphe_5(cle):
    transport, recus = _transport(cle, httpx.Response(200, headers={"apns-id": "id-apple"}))
    envoi = _envoi()
    assert transport.transmettre(envoi) == Resultat("envoye", apns_id="id-apple")
    (requete,) = recus
    assert str(requete.url) == f"https://api.push.apple.com/3/device/{JETON}"
    assert requete.headers["apns-topic"] == SUJET
    assert requete.headers["apns-push-type"] == "alert"
    assert requete.headers["apns-collapse-id"] == envoi.abonnement
    assert requete.headers["apns-priority"] == "10"
    jeton = requete.headers["authorization"].removeprefix("bearer ")
    assert jwt.get_unverified_header(jeton) == {"alg": "ES256", "kid": ID_CLE, "typ": "JWT"}
    assert jwt.decode(jeton, cle[1], algorithms=["ES256"])["iss"] == EQUIPE
    assert json.loads(requete.content) == {
        "aps": {
            "alert": {"title": TITRE, "body": CORPS},
            "sound": "default",
            "interruption-level": "time-sensitive",
        },
        "a": envoi.abonnement,
    }


def test_un_appareil_de_developpement_vise_le_bac_a_sable_au_niveau_normal(cle):
    transport, recus = _transport(cle, httpx.Response(200))
    transport.transmettre(_envoi(environnement="developpement", niveau="normal"))
    (requete,) = recus
    assert requete.url.host == "api.sandbox.push.apple.com"
    assert requete.headers["apns-priority"] == "5"


def test_le_jeton_d_authentification_se_garde_moins_d_une_heure(cle, monkeypatch):
    transport, recus = _transport(cle, httpx.Response(200))
    instant = [1_000_000.0]
    monkeypatch.setattr(apns.time, "time", lambda: instant[0])
    transport.transmettre(_envoi())
    instant[0] += apns.RENOUVELLEMENT - 1
    transport.transmettre(_envoi())
    instant[0] += 2
    transport.transmettre(_envoi())
    auth = [r.headers["authorization"] for r in recus]
    assert auth[0] == auth[1] != auth[2]
    assert 20 * 60 <= apns.RENOUVELLEMENT < 60 * 60


@pytest.mark.parametrize(
    "reponse",
    [
        httpx.Response(410, json={"reason": "Unregistered"}),
        httpx.Response(400, json={"reason": "BadDeviceToken"}),
    ],
)
def test_un_jeton_qu_apple_ne_connait_plus_se_dit_perime(cle, reponse):
    transport, _ = _transport(cle, reponse)
    assert transport.transmettre(_envoi()).statut == "jeton_perime"


@pytest.mark.parametrize(
    "reponse",
    [
        httpx.Response(403, json={"reason": "InvalidProviderToken"}),
        httpx.Response(500, text="pas du JSON"),
        httpx.ConnectError("injoignable"),
    ],
)
def test_un_autre_refus_ne_repete_rien_de_la_requete(cle, reponse):
    transport, _ = _transport(cle, reponse)
    envoi = _envoi()
    resultat = transport.transmettre(envoi)
    assert resultat.statut == "refuse"
    assert JETON not in resultat.motif and envoi.abonnement not in resultat.motif


def test_un_envoi_fcm_ou_une_cle_incomplete_est_refuse(cle):
    transport, recus = _transport(cle, httpx.Response(200))
    jeton_fcm = "dQw4w9WgXcQ:APA91b" + "x" * 140
    assert transport.transmettre(_envoi(plateforme="fcm", jeton=jeton_fcm)).statut == "refuse"
    assert recus == []
    with pytest.raises(ValueError):
        TransportApns("", ID_CLE)
    with pytest.raises(ValueError):
        TransportApns(cle[0], "")


# ── Le relais lit la clé posée dans son `.env` ───────────────────────────────


def test_le_relais_transmet_un_iphone_avec_la_cle_posee(cle, monkeypatch):
    recus = []

    class Double:
        def __init__(self, pem, id_cle):
            recus.append((pem, id_cle))

        def transmettre(self, envoi):
            return Resultat("envoye", apns_id="x")

    monkeypatch.setattr(relais, "_transports", {})
    monkeypatch.setattr(relais, "TransportApns", Double)
    reglages = get_settings()
    monkeypatch.setattr(reglages, "apns_cle", base64.b64encode(cle[0].encode()).decode())
    monkeypatch.setattr(reglages, "apns_id_cle", ID_CLE)
    assert relais.transmettre(_envoi()).statut == "envoye"
    assert recus == [(cle[0], ID_CLE)]


@pytest.mark.parametrize(
    "valeur,id_cle",
    [
        ("", ID_CLE),
        ("pas du base64 !", ID_CLE),
        (base64.b64encode(b"pas une cle").decode(), ID_CLE),
        ("CLE_VALIDE", ""),
    ],
)
def test_une_cle_absente_illisible_ou_sans_identifiant_ne_part_pas(
    cle, monkeypatch, valeur, id_cle
):
    monkeypatch.setattr(relais, "_transports", {})
    reglages = get_settings()
    if valeur == "CLE_VALIDE":
        valeur = base64.b64encode(cle[0].encode()).decode()
    monkeypatch.setattr(reglages, "apns_cle", valeur)
    monkeypatch.setattr(reglages, "apns_id_cle", id_cle)
    assert relais.transmettre(_envoi()) == Resultat("refuse", relais.SANS_CLE_APNS)


def test_le_client_par_defaut_parle_http2(cle):
    """APNs n'accepte que HTTP/2 : sans `h2` (`httpx[http2]` dans requirements.txt),
    le client par défaut ne se construirait pas — l'image le dit ici, pas en production."""
    transport = TransportApns(cle[0], ID_CLE)
    assert transport._http._transport._pool._http2 is True
