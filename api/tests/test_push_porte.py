"""🔒 La porte d'envoi des notifications push (#2493, spec `notifications-push.md` §5, §6.4).

Ce fichier tient quatre règles, chacune éprouvée d'abord sur son cas fautif :

1. **Une seule porte** : `noter` n'est appelée que par `utils/cloche`, et le
   transport n'est lu que par `utils/push/porte.py` — un envoi dispersé dans les
   routeurs recréerait les vingt-deux copies d'avant #1187.
2. **Rien de personnel ne part** : l'envoi est un schéma fermé ; ni titre, ni corps,
   ni nom, ni adresse de la notification ne s'y trouvent ; la charge APNs n'a que
   les clés du §5, sans pastille, *time-sensitive* pour les seuls avis urgents.
3. **Coupé par défaut** : sur une base neuve, une cloche qui sonne n'avertit rien.
4. **Le jeton d'appareil n'est jamais journalisé**, même tronqué : le journal dit
   l'identifiant de l'appareil (N8). C'est la contrepartie de l'exception déclarée
   dans `models/appareils.py` — le jeton se garde en clair, car il se transmet.

Aucun appel réseau : le transport est remplacé par un double qui retient ce qu'il reçoit.
"""

from __future__ import annotations

import ast
import json
import logging
import secrets

import pytest
from pydantic import ValidationError
from sqlmodel import Session, select

from app.models.appareils import Appareil
from app.models.core import ConfigSite, Notification
from app.utils import cloche
from app.utils.push import porte, transport
from app.utils.push.envoi import CORPS, TITRE, Envoi, charge_apns, entetes_apns, envoi_pour
from app.utils.push.transport import RelaisNonBranche, Resultat
from app.utils.services import SERVICE_PUSH, cle_actif, service_actif
from tests.aides_base import compte
from tests.aides_sources import modules_app

PORTE = "utils/push/porte.py"
CLOCHE = "utils/cloche.py"


# ── 1. Une seule porte ────────────────────────────────────────────────────────


def _appels_hors_porte(arbre: ast.AST) -> list[tuple[int, str]]:
    """Les appels de `noter` et les lectures de `TRANSPORT` de ce module."""
    vus = []
    for n in ast.walk(arbre):
        if isinstance(n, ast.Call):
            nom = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
            if nom == "noter":
                vus.append((n.lineno, "noter"))
        if isinstance(n, ast.Attribute) and n.attr == "TRANSPORT":
            vus.append((n.lineno, "TRANSPORT"))
        if isinstance(n, ast.Name) and n.id == "TRANSPORT" and isinstance(n.ctx, ast.Load):
            vus.append((n.lineno, "TRANSPORT"))
        if isinstance(n, ast.ImportFrom) and any(a.name == "TRANSPORT" for a in n.names):
            vus.append((n.lineno, "TRANSPORT"))
    return vus


def test_le_controle_voit_un_envoi_disperse():
    """Le cas fautif d'abord : un routeur qui avertirait les téléphones lui-même."""
    fautif = (
        "from app.utils.push.transport import TRANSPORT\n"
        "from app.utils.push import porte\n"
        "def creer(session, u):\n"
        "    porte.noter(session, u.id, urgente=False)\n"
        "    TRANSPORT.transmettre(None)\n"
    )
    assert sorted(_appels_hors_porte(ast.parse(fautif))) == [
        (1, "TRANSPORT"),
        (4, "noter"),
        (5, "TRANSPORT"),
    ]


def test_une_seule_porte_d_envoi():
    noter, transport_lu = [], []
    for module in modules_app():
        for ligne, nom in _appels_hors_porte(module.arbre):
            (noter if nom == "noter" else transport_lu).append(f"{module.rel}:{ligne}")
    #  Cas zéro : le relevé voit bien l'appel de la cloche et la lecture de la porte.
    assert noter and all(v.startswith(CLOCHE) for v in noter), (
        f"`noter` appelé hors de utils/cloche — passer par `sonner`/`sonner_systeme` : {noter}"
    )
    assert transport_lu and all(v.startswith(PORTE) for v in transport_lu), (
        f"transport lu hors de la porte d'envoi : {transport_lu}"
    )


# ── Le montage : un transport qui retient, un lancement synchrone ─────────────


class Double:
    def __init__(self, reponse: Resultat | None = None, erreur: Exception | None = None):
        self.recus: list[Envoi] = []
        self.reponse = reponse or Resultat("envoye", apns_id="apns-1")
        self.erreur = erreur

    def transmettre(self, envoi: Envoi) -> Resultat:
        self.recus.append(envoi)
        if self.erreur:
            raise self.erreur
        return self.reponse


@pytest.fixture()
def double(monkeypatch, session):
    d = Double()
    monkeypatch.setattr(transport, "TRANSPORT", d)

    #  Le fil d'envoi devient synchrone, sur la base du test.
    def lancer(copro, attente):
        with Session(session.get_bind()) as s:
            porte.avertir_dans(s, attente)

    monkeypatch.setattr(porte, "lancer", lancer)
    return d


def _allumer(session):
    session.add(ConfigSite(cle=cle_actif(SERVICE_PUSH), valeur="1"))
    session.commit()


def _appareil(session, utilisateur_id: int) -> Appareil:
    a = Appareil(
        utilisateur_id=utilisateur_id,
        jeton=secrets.token_hex(32),
        abonnement=secrets.token_urlsafe(24),
    )
    session.add(a)
    session.commit()
    session.refresh(a)
    return a


def _sonner(session, destinataire_id: int, **champs):
    cloche.sonner_systeme(
        session,
        "compte",
        destinataire_id=destinataire_id,
        type="system",
        titre=champs.pop("titre", "Votre compte est validé"),
        corps=champs.pop("corps", "Bienvenue au 12 rue des Lilas"),
        **champs,
    )


# ── 3. Coupé par défaut ───────────────────────────────────────────────────────


def test_service_coupe_par_defaut(session, double):
    personne = compte(session, prefixe="push-defaut")
    _appareil(session, personne.id)
    assert not service_actif({}, SERVICE_PUSH)
    _sonner(session, personne.id)
    session.commit()
    #  La cloche a sonné, le téléphone non.
    assert session.exec(
        select(Notification).where(Notification.destinataire_id == personne.id)
    ).first()
    assert double.recus == []


def test_le_transport_par_defaut_n_envoie_rien():
    """Tant que le relais (P1, #2494) n'est pas branché, rien ne part — et il le dit."""
    assert isinstance(transport.TRANSPORT, RelaisNonBranche)
    assert transport.TRANSPORT.transmettre(None).statut == "refuse"


# ── L'envoi suit la cloche, après le commit ───────────────────────────────────


def test_un_envoi_par_appareil_apres_le_commit(session, double):
    _allumer(session)
    personne = compte(session, prefixe="push-commit")
    a, b = _appareil(session, personne.id), _appareil(session, personne.id)
    _sonner(session, personne.id)
    _sonner(session, personne.id)
    assert double.recus == [], "rien ne part avant le commit"
    session.commit()
    assert sorted(e.abonnement for e in double.recus) == sorted([a.abonnement, b.abonnement])


def test_un_rollback_n_avertit_personne(session, double):
    _allumer(session)
    personne = compte(session, prefixe="push-rollback")
    _appareil(session, personne.id)
    _sonner(session, personne.id)
    session.rollback()
    session.commit()
    assert double.recus == []


def test_une_cloche_que_le_profil_tait_ne_pousse_rien(session, double, monkeypatch):
    _allumer(session)
    personne = compte(session, prefixe="push-profil")
    _appareil(session, personne.id)
    monkeypatch.setattr(cloche, "cloche_autorisee", lambda *a: False)
    assert not cloche.sonner(session, destinataire_id=personne.id, type="ticket_update", titre="x")
    session.commit()
    assert double.recus == []


def test_time_sensitive_pour_les_seuls_avis_urgents(session, double):
    _allumer(session)
    urgent, normal = compte(session, prefixe="push-urgent"), compte(session, prefixe="push-normal")
    _appareil(session, urgent.id), _appareil(session, normal.id)
    _sonner(session, urgent.id, urgente=True)
    _sonner(session, normal.id)
    session.commit()
    niveaux = {e.abonnement: e.niveau for e in double.recus}
    assert sorted(niveaux.values()) == ["normal", "urgent"]
    for envoi in double.recus:
        aps = charge_apns(envoi)["aps"]
        assert ("interruption-level" in aps) is (envoi.niveau == "urgent")
        if envoi.niveau == "urgent":
            assert aps["interruption-level"] == "time-sensitive"


# ── 2. Rien de personnel ne part ──────────────────────────────────────────────


def test_l_envoi_ne_porte_rien_de_la_notification(session, double):
    _allumer(session)
    personne = compte(session, prefixe="push-perso", prenom="Odile", nom="Mercier")
    _appareil(session, personne.id)
    _sonner(
        session,
        personne.id,
        titre="Fuite au 3e étage",
        corps="Chez Odile Mercier",
        lien="/tickets/7",
    )
    session.commit()
    (envoi,) = double.recus
    assert set(envoi.model_dump()) == {
        "jeton",
        "environnement",
        "abonnement",
        "niveau",
        "emis_le",
        "nonce",
    }
    #  Aucun nombre : ni identifiant d'utilisateur, ni de notification, ni pastille.
    assert not any(isinstance(v, int) for v in envoi.model_dump().values())
    sortie = json.dumps([envoi.model_dump(mode="json"), charge_apns(envoi), entetes_apns(envoi)])
    for personnel in ("Fuite", "Odile", "Mercier", "/tickets/7", personne.email):
        assert personnel not in sortie, personnel


def test_l_envoi_est_un_schema_ferme():
    a = Appareil(utilisateur_id=1, jeton="ab" * 32, abonnement="x" * 20)
    champs = envoi_pour(a, urgent=False).model_dump()
    with pytest.raises(ValidationError):
        Envoi(**champs, titre="Fuite au 3e étage")


def test_la_charge_apns_n_a_que_les_cles_du_paragraphe_5():
    a = Appareil(utilisateur_id=1, jeton="ab" * 32, abonnement="abonnement-opaque-1")
    for urgent in (False, True):
        charge = charge_apns(envoi_pour(a, urgent=urgent))
        assert set(charge) == {"aps", "a"}
        assert set(charge["aps"]) <= {"alert", "sound", "interruption-level"}
        assert "badge" not in charge["aps"], "aucune pastille (décision du 03/11/2026)"
        assert charge["aps"]["alert"] == {"title": TITRE, "body": CORPS}
        assert charge["a"] == "abonnement-opaque-1"
    assert entetes_apns(envoi_pour(a, urgent=False))["apns-collapse-id"] == "abonnement-opaque-1"


# ── 4. Le jeton n'est jamais journalisé ───────────────────────────────────────


@pytest.mark.parametrize(
    "reponse, erreur",
    [
        (Resultat("envoye", apns_id="apns-9"), None),
        (Resultat("refuse", "bail échu"), None),
        (None, RuntimeError("POST /plateforme/notifications jeton=…")),
    ],
)
def test_le_journal_ne_porte_jamais_le_jeton(session, monkeypatch, caplog, reponse, erreur):
    d = Double(reponse, erreur)
    monkeypatch.setattr(transport, "TRANSPORT", d)
    personne = compte(session, prefixe="push-journal")
    a = _appareil(session, personne.id)
    with caplog.at_level(logging.DEBUG):
        porte.avertir_dans(session, {personne.id: False})
    lignes = [r.getMessage() for r in caplog.records]
    assert any(f"appareil {a.id}" in ligne for ligne in lignes), "le journal dit l'identifiant"
    for ligne in lignes:
        for debut in range(0, len(a.jeton) - 8):
            assert a.jeton[debut : debut + 8] not in ligne, "un morceau du jeton est journalisé"
    if erreur:
        assert all("jeton=" not in ligne for ligne in lignes), "le message de l'exception est tu"


def test_aucun_journal_de_la_porte_ne_lit_un_jeton():
    """Statique : aucun appel au journal dans `utils/push/` ne nomme un jeton."""
    fautif = 'logger.info("appareil %s", appareil.jeton)\n'

    def _lectures(arbre):
        return [
            n.lineno
            for appel in ast.walk(arbre)
            if isinstance(appel, ast.Call)
            and getattr(appel.func, "attr", "")
            in {"debug", "info", "warning", "error", "exception"}
            for n in ast.walk(appel)
            if (isinstance(n, ast.Attribute) and n.attr == "jeton")
            or (isinstance(n, ast.Name) and n.id == "jeton")
        ]

    assert _lectures(ast.parse(fautif)) == [1]
    modules = [m for m in modules_app() if m.rel.startswith("utils/push/")]
    assert len(modules) >= 4, "le relevé ne voit pas les modules de la porte"
    ecarts = [f"{m.rel}:{ligne}" for m in modules for ligne in _lectures(m.arbre)]
    assert not ecarts, f"un jeton d'appareil passe au journal : {ecarts}"


def test_un_jeton_perime_retire_l_appareil(session, monkeypatch):
    monkeypatch.setattr(transport, "TRANSPORT", Double(Resultat("jeton_perime")))
    personne = compte(session, prefixe="push-perime")
    a = _appareil(session, personne.id)
    porte.avertir_dans(session, {personne.id: False})
    assert session.get(Appareil, a.id) is None
