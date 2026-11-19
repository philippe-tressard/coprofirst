"""🔒 Le relais des notifications push, de bout en bout (#2494, #2789, `notifications-push.md` §4).

Les deux côtés tournent dans ce processus (`aides_registre.installation_branchee`) : une
RÉPLIQUE signe sa demande et joint son bail, réellement délivré et signé par la clé des
baux ; la référence la juge (`registre/relais.py`) et transmet au service de push — ici
un double : aucun appel ne part chez Google ni chez Apple.

Chaque garde du §4 est éprouvée sur son cas fautif : sans bail cru, bail d'une autre
clé, service non accordé, signature d'une autre clé, envoi périmé, nonce rejoué, champ
inconnu. Puis ce que le relais transmet : FCM au compte de service, APNs refusé tant
que la clé `.p8` manque (#2494), et rien sans secret.
"""

from __future__ import annotations

import base64
import json
import secrets
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.inscription import client, depot
from app.inscription.depot import Contact
from app.main import app
from app.registre import relais as route_relais
from app.registre import signature
from app.registre.contrat import EN_TETE_SIGNATURE, DemandeNotification
from app.registre.modeles import EtatInscription
from app.utils import horloge, installation
from app.utils.push import fcm, relais, transport
from app.utils.push.envoi import Envoi
from app.utils.push.transport import Resultat
from app.utils.services import SERVICE_PUSH
from tests.aides_registre import HOTE, installation_branchee, modifier_inscrite

JETON_FCM = "dQw4w9WgXcQ:APA91b" + "x" * 140
JETON_APNS = "ab" * 32
CONTACT = Contact(prenom="Alix", nom="Durand", courriel="alix@example.org")


def _envoi(**champs) -> Envoi:
    return Envoi(
        **{
            "plateforme": "fcm",
            "jeton": JETON_FCM,
            "environnement": "production",
            "abonnement": secrets.token_urlsafe(24),
            "niveau": "urgent",
            "emis_le": horloge.maintenant(),
            "nonce": secrets.token_urlsafe(16),
            **champs,
        }
    )


class FcmDouble:
    """Le transport FCM du relais, remplacé : il retient le compte et les envois reçus."""

    instances: list["FcmDouble"] = []

    def __init__(self, compte: dict):
        self.compte = compte
        self.recus: list[Envoi] = []
        FcmDouble.instances.append(self)

    def transmettre(self, envoi: Envoi) -> Resultat:
        self.recus.append(envoi)
        return Resultat("envoye")


COMPTE = {
    "project_id": "coprofirst-essai",
    "client_email": "relais@coprofirst-essai.iam.gserviceaccount.example",
    "private_key": "-----BEGIN PRIVATE KEY-----\nessai\n-----END PRIVATE KEY-----\n",
    "token_uri": "https://oauth2.example/token",
}


def _en_base64(compte: dict) -> str:
    return base64.b64encode(json.dumps(compte).encode()).decode()


@pytest.fixture(autouse=True)
def _etat_vierge(monkeypatch):
    """Ni nonce, ni envoi d'un test à l'autre ; le transport FCM est un double."""
    monkeypatch.setattr(route_relais, "_nonces", {})
    monkeypatch.setattr(route_relais, "_envois", {})
    monkeypatch.setattr(relais, "_transports", {})
    monkeypatch.setattr(relais, "TransportFcm", FcmDouble)
    FcmDouble.instances = []


@pytest.fixture
def registre(monkeypatch, tmp_path):
    """Une réplique inscrite, ACTIVE, à qui le registre accorde le push ; le relais a son compte FCM."""
    monkeypatch.setattr(get_settings(), "fcm_compte_service", _en_base64(COMPTE))
    with installation_branchee(monkeypatch, tmp_path) as moteur:
        client.inscrire(CONTACT)
        modifier_inscrite(
            moteur, etat=EtatInscription.active, services_autorises=json.dumps([SERVICE_PUSH])
        )
        client.renouveler()
        yield moteur


def _poster_tel_quel(corps: dict, signer=True):
    """Une demande au relais, hors du client : pour éprouver une garde sur son cas fautif."""
    octets = json.dumps(corps).encode()
    entetes = {"host": HOTE, "Content-Type": "application/json"}
    if signer:
        entetes[EN_TETE_SIGNATURE] = signature.signer(depot.cle_privee(), octets)
    return TestClient(app).post("/plateforme/notifications", content=octets, headers=entetes)


def _demande(envoi: Envoi | None = None) -> dict:
    etat = depot.lire()
    return DemandeNotification(
        version_contrat=1,
        identifiant=etat.identifiant,
        cle_publique=client.cle_publique(),
        bail=etat.bail,
        envoi=envoi or _envoi(),
    ).model_dump(mode="json")


# ── De bout en bout ───────────────────────────────────────────────────────────


def test_une_replique_au_bail_cru_avertit_un_telephone_android(registre):
    envoi = _envoi()
    resultat = transport.TRANSPORT.transmettre(envoi)
    assert resultat == Resultat("envoye", "")
    (fcm,) = FcmDouble.instances
    assert fcm.compte == COMPTE
    assert fcm.recus == [envoi]


def test_un_iphone_est_refuse_tant_que_la_cle_p8_manque(registre):
    resultat = transport.TRANSPORT.transmettre(_envoi(plateforme="apns", jeton=JETON_APNS))
    assert (resultat.statut, resultat.motif) == ("refuse", relais.SANS_CLE_APNS)


def test_un_jeton_perime_chez_google_revient_a_l_installation(registre, monkeypatch):
    monkeypatch.setattr(
        FcmDouble, "transmettre", lambda self, envoi: Resultat("jeton_perime", "FCM : UNREGISTERED")
    )
    assert transport.TRANSPORT.transmettre(_envoi()).statut == "jeton_perime"


def test_le_journal_du_relais_ne_porte_jamais_le_jeton(registre, caplog):
    caplog.set_level("INFO")
    transport.TRANSPORT.transmettre(_envoi())
    assert "relais push : CF-000001, fcm, envoye" in caplog.text
    assert JETON_FCM not in caplog.text and JETON_FCM[:12] not in caplog.text


# ── Les gardes, chacune sur son cas fautif ───────────────────────────────────


def test_hors_du_nom_dedie_la_route_n_existe_pas(registre):
    reponse = TestClient(app).post("/plateforme/notifications", content=b"{}")
    assert reponse.status_code == 404


def test_un_service_non_accorde_est_refuse(registre):
    modifier_inscrite(registre, services_autorises="[]")
    client.renouveler()
    resultat = transport.TRANSPORT.transmettre(_envoi())
    assert resultat.statut == "refuse" and "notifications sur téléphone" in resultat.motif
    assert FcmDouble.instances == []


def test_un_bail_suspendu_est_refuse(registre):
    modifier_inscrite(registre, etat=EtatInscription.suspendue)
    client.renouveler()
    resultat = transport.TRANSPORT.transmettre(_envoi())
    assert resultat.statut == "refuse" and "403" in resultat.motif


def test_un_bail_echu_est_refuse(registre, monkeypatch):
    plus_tard = horloge.maintenant() + timedelta(days=31)
    monkeypatch.setattr(horloge, "maintenant", lambda: plus_tard)
    reponse = _poster_tel_quel(_demande(_envoi(emis_le=plus_tard)))
    assert reponse.status_code == 403 and "échu" in reponse.json()["detail"]


def test_le_bail_d_une_autre_cle_est_refuse(registre):
    _, autre = signature.generer_paire()
    corps = _demande() | {"cle_publique": autre}
    reponse = _poster_tel_quel(corps)
    assert reponse.status_code == 403 and "autre installation" in reponse.json()["detail"]


def test_un_bail_falsifie_est_refuse(registre):
    corps = _demande()
    corps["bail"]["bail"]["services_autorises"] = [SERVICE_PUSH, "assistant_ia"]
    assert _poster_tel_quel(corps).status_code == 403


def test_une_demande_sans_signature_ou_signee_d_une_autre_cle_est_refusee(registre):
    assert _poster_tel_quel(_demande(), signer=False).status_code == 401
    corps = _demande()
    octets = json.dumps(corps).encode()
    autre, _ = signature.generer_paire()
    reponse = TestClient(app).post(
        "/plateforme/notifications",
        content=octets,
        headers={"host": HOTE, EN_TETE_SIGNATURE: signature.signer(autre, octets)},
    )
    assert reponse.status_code == 401
    assert FcmDouble.instances == []


def test_un_envoi_hors_de_la_fenetre_est_refuse(registre):
    vieux = _envoi(emis_le=horloge.maintenant() - route_relais.FENETRE - timedelta(seconds=1))
    assert _poster_tel_quel(_demande(vieux)).status_code == 400


def test_un_envoi_rejoue_n_avertit_pas_deux_fois(registre):
    corps = _demande()
    assert _poster_tel_quel(corps).status_code == 200
    assert _poster_tel_quel(corps).status_code == 409
    assert len(FcmDouble.instances[0].recus) == 1


def test_un_champ_inconnu_est_refuse(registre):
    corps = _demande()
    corps["envoi"]["titre"] = "Fuite au 3e étage"
    assert _poster_tel_quel(corps).status_code == 422
    corps = _demande() | {"residence": "Les Tilleuls"}
    assert _poster_tel_quel(corps).status_code == 422


def test_une_installation_bavarde_est_plafonnee_seule(registre, monkeypatch):
    monkeypatch.setattr(route_relais, "PLAFOND_PAR_MINUTE", 2)
    assert _poster_tel_quel(_demande()).status_code == 200
    assert _poster_tel_quel(_demande()).status_code == 200
    assert _poster_tel_quel(_demande()).status_code == 429


def test_le_refus_ne_repete_rien_de_la_demande(registre):
    corps = _demande(_envoi(emis_le=horloge.maintenant() - timedelta(hours=1)))
    detail = _poster_tel_quel(corps).text
    assert JETON_FCM not in detail and corps["envoi"]["abonnement"] not in detail


# ── La transmission, chez la référence ───────────────────────────────────────


def test_sans_compte_de_service_rien_ne_part(monkeypatch):
    monkeypatch.setattr(get_settings(), "fcm_compte_service", "")
    assert relais.transmettre(_envoi()) == Resultat("refuse", relais.SANS_COMPTE_FCM)
    assert FcmDouble.instances == []


@pytest.mark.parametrize(
    "valeur", ["pas du base64 !", base64.b64encode(b"[1, 2]").decode(), "e30="]
)
def test_un_compte_de_service_illisible_ou_incomplet_ne_part_pas(monkeypatch, valeur):
    """Le vrai transport : `e30=` (« {} ») se lit, mais il lui manque tout — refusé."""
    monkeypatch.setattr(relais, "TransportFcm", fcm.TransportFcm)
    monkeypatch.setattr(get_settings(), "fcm_compte_service", valeur)
    assert relais.transmettre(_envoi()) == Resultat("refuse", relais.SANS_COMPTE_FCM)


def test_la_reference_transmet_en_processus_sans_bail(monkeypatch):
    """La référence n'a pas de bail (règle 7) : la même transmission, sans requête."""
    monkeypatch.setattr(installation, "role_installation", lambda valeur=None: "reference")
    monkeypatch.setattr(get_settings(), "fcm_compte_service", _en_base64(COMPTE))
    assert transport.TRANSPORT.transmettre(_envoi()).statut == "envoye"


def test_une_installation_d_essai_n_appelle_jamais_la_reference(monkeypatch):
    monkeypatch.setattr(installation, "role_installation", lambda valeur=None: "replique")
    monkeypatch.setattr(client, "essai_admis", lambda: True)
    resultat = transport.TRANSPORT.transmettre(_envoi())
    assert resultat.statut == "refuse" and "essai" in resultat.motif
