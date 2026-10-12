"""Un envoi WhatsApp sans réponse ne doit JAMAIS être rejoué.

Le 14/08/2026, le message planifié « 📢 Infos copro – Encombrants (Boulevard
Fernand Hostachy) » est parti **trois fois** dans le groupe de la copropriété.
Aucun composant n'était en panne : le bridge dépassait le délai d'attente HTTP
tout en délivrant le message. L'API concluait « échec », et la fenêtre de
rattrapage — ajoutée le 24/07/2026 pour ne plus *perdre* le message du mois —
renvoyait toutes les 15 minutes. Sans intervention, seize exemplaires seraient
partis avant 21h45.

La déduplication n'observait pas ce qu'elle croyait observer : elle lisait
l'**acquittement du transport** (« ai-je reçu une réponse ? ») et en déduisait
le **fait** (« le message est-il parti ? »). Ce sont deux questions différentes,
et un client HTTP qui n'obtient pas de réponse ne sait rien de la seconde.

Ce fichier verrouille la seule règle qui empêche la récidive : on ne rejoue que
sur un échec **établi**. Il ne teste pas la valeur du délai d'attente — la porter
de 15 s à 60 s rend le cas rare, elle ne le supprime pas.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import ConfigSite, WhatsAppLog, WhatsAppScheduled
from app.utils import horloge
from app.utils import whatsapp as W
from app.utils import whatsapp_scheduler as S

#: Vendredi 14/08/2026 18h00 (Paris) — veille du 3ᵉ samedi, l'instant de l'incident.
VENDREDI_INCIDENT = datetime(2026, 8, 14, 18, 0, tzinfo=ZoneInfo("Europe/Paris"))

PARIS = ZoneInfo("Europe/Paris")


class _HorlogeFigee(datetime):
    """`datetime` dont `now()` rend un instant choisi — et `maintenant()` le même, en UTC naïf."""

    instant = VENDREDI_INCIDENT

    @classmethod
    def now(cls, tz=None):
        return cls.instant if tz else cls.instant.replace(tzinfo=None)

    @classmethod
    def maintenant(cls):
        return cls.instant.astimezone(timezone.utc).replace(tzinfo=None)


def _requete() -> httpx.Request:
    return httpx.Request("POST", "http://whatsapp-bridge:3000/send")


def _reponse_ok() -> httpx.Response:
    return httpx.Response(200, json={"ok": True}, request=_requete())


class _ClientFactice:
    """Client httpx dont le `post` est fourni par le test."""

    def __init__(self, post):
        self._post = post

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, *args, **kwargs):
        return self._post(*args, **kwargs)


def _leve(exc):
    """Un `post` qui lève `exc`."""

    def _post(*args, **kwargs):
        raise exc

    return _post


def _bridge_simule(monkeypatch, *resultats):
    """Simule le bridge **au niveau du transport HTTP**, et compte les envois.

    Chaque élément de `resultats` est soit une exception à lever, soit une
    réponse à rendre ; le dernier vaut pour tous les appels suivants.

    Le point de simulation est délibérément bas. Patcher `envoyer_whatsapp_raw`
    aurait court-circuité la classification échec/incertain — or c'est elle qui
    décide du rejeu. On aurait alors testé la décision sans le tuyau qui la
    nourrit, et le test serait passé au vert sur le code défectueux.
    """
    appels: list[dict] = []

    def _post(*args, **kwargs):
        appels.append(kwargs.get("json") or {})
        issue = resultats[min(len(appels) - 1, len(resultats) - 1)]
        if isinstance(issue, Exception):
            raise issue
        return issue

    monkeypatch.setattr(W.httpx, "Client", lambda **kw: _ClientFactice(_post))
    return appels


@pytest.fixture()
def planifie(monkeypatch):
    """Un message planifié pour ce soir, WhatsApp activé, l'horloge figée.

    Rend une liste qui collecte les alertes e-mail : aucune ne part réellement.
    """
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for modele in (WhatsAppLog, WhatsAppScheduled):
            for ligne in session.exec(select(modele)).all():
                session.delete(ligne)
        for cle in (
            "whatsapp_enabled",
            "whatsapp_api_url",
            "whatsapp_group_jid",
            "whatsapp_footer",
        ):
            existant = session.get(ConfigSite, cle)
            if existant:
                session.delete(existant)
        session.commit()
        session.add_all(
            [
                ConfigSite(cle="whatsapp_enabled", valeur="1"),
                ConfigSite(cle="whatsapp_api_url", valeur="http://whatsapp-bridge:3000"),
                ConfigSite(cle="whatsapp_group_jid", valeur="123@g.us"),
                WhatsAppScheduled(
                    label="Encombrants Bd Hostachy",
                    message="📢 Infos copro – Encombrants",
                    cron_rule="3eme_samedi",
                    enabled=True,
                ),
            ]
        )
        session.commit()

    _HorlogeFigee.instant = VENDREDI_INCIDENT
    monkeypatch.setattr(S, "datetime", _HorlogeFigee)
    #  L'heure UTC du module passe par `horloge` depuis #1047 : c'est elle qu'on
    #  fige, et dans CE module seulement — comme `datetime` juste au-dessus.
    monkeypatch.setattr(
        S,
        "horloge",
        SimpleNamespace(
            maintenant=_HorlogeFigee.maintenant, debut_du_jour_utc=horloge.debut_du_jour_utc
        ),
    )

    alertes: list[list[str]] = []
    import app.utils.health_monitor as HM
    import app.utils.email as E

    monkeypatch.setattr(HM, "_send_alert", lambda to, issues, session: alertes.append(issues))
    monkeypatch.setattr(
        E, "get_site_manager_notification_email", lambda session: ("admin@test", {})
    )
    yield alertes


def _statuts() -> list[str]:
    with Session(engine) as session:
        return [log.statut for log in session.exec(select(WhatsAppLog)).all()]


# ── Le défaut du 14/08/2026 ───────────────────────────────────────────────────


def test_un_delai_depasse_ne_declenche_aucun_rejeu(planifie, monkeypatch):
    """Le cœur de l'incident : timeout de lecture → un seul envoi, jamais deux."""
    appels = _bridge_simule(monkeypatch, httpx.ReadTimeout("timed out", request=_requete()))

    S.check_and_send()
    assert len(appels) == 1
    assert _statuts() == [W.STATUT_INCERTAIN]

    #  Créneau suivant (18h15) : c'est ici que le 2ᵉ exemplaire était parti.
    _HorlogeFigee.instant = VENDREDI_INCIDENT + timedelta(minutes=15)
    S.check_and_send()
    assert len(appels) == 1, "un envoi non acquitté a été rejoué — le doublon est de retour"

    #  Et jusqu'à la fermeture de la fenêtre.
    _HorlogeFigee.instant = VENDREDI_INCIDENT.replace(hour=21, minute=45)
    S.check_and_send()
    assert len(appels) == 1


def test_un_delai_depasse_alerte_un_humain(planifie, monkeypatch):
    """Ne pas rejouer n'est acceptable que si quelqu'un est prévenu d'aller voir."""
    _bridge_simule(monkeypatch, httpx.ReadTimeout("timed out", request=_requete()))
    S.check_and_send()

    assert len(planifie) == 1
    assert "peut-être arrivé" in planifie[0][0]


# ── Ce qu'il faut continuer de rejouer ────────────────────────────────────────


def test_un_echec_etabli_est_rejoue(planifie, monkeypatch):
    """Bridge injoignable = rien n'est parti : la fenêtre de rattrapage doit jouer.

    C'est la raison d'être du rattrapage (incident du 24/07/2026) ; le correctif
    du doublon ne doit pas la supprimer au passage.
    """
    appels = _bridge_simule(
        monkeypatch,
        httpx.ConnectError("Name or service not known", request=_requete()),
        _reponse_ok(),
    )

    S.check_and_send()
    assert _statuts() == [W.STATUT_ECHEC]

    _HorlogeFigee.instant = VENDREDI_INCIDENT + timedelta(minutes=15)
    S.check_and_send()
    assert len(appels) == 2, "un échec établi n'a pas été rejoué"
    assert _statuts() == [W.STATUT_ENVOYE]


def test_un_envoi_reussi_nest_pas_rejoue(planifie, monkeypatch):
    appels = _bridge_simule(monkeypatch, _reponse_ok())
    S.check_and_send()
    _HorlogeFigee.instant = VENDREDI_INCIDENT + timedelta(minutes=15)
    S.check_and_send()
    assert len(appels) == 1
    assert _statuts() == [W.STATUT_ENVOYE]


def test_une_tentative_interrompue_bloque_le_rejeu(planifie, monkeypatch):
    """Le verrou « en cours » survit à un redémarrage en plein envoi.

    Le processus meurt entre le POST et la réponse : le log reste « en cours ».
    On ne sait pas ce que le groupe a reçu, donc on ne renvoie pas — et l'alerte
    de fin de fenêtre dit à un humain d'aller trancher.
    """
    with Session(engine) as session:
        sched = session.exec(select(WhatsAppScheduled)).one()
        session.add(
            WhatsAppLog(
                scheduled_id=sched.id,
                label=sched.label,
                message="…",
                statut=W.STATUT_EN_COURS,
                envoye_le=_HorlogeFigee.maintenant(),
            )
        )
        session.commit()

    appels = _bridge_simule(monkeypatch, _reponse_ok())
    _HorlogeFigee.instant = VENDREDI_INCIDENT.replace(hour=21, minute=45)
    S.check_and_send()

    assert appels == []
    assert len(planifie) == 1


# ── Classification : ce qu'on sait, ce qu'on ne sait pas ──────────────────────


@pytest.mark.parametrize(
    "exc, incertain",
    [
        (httpx.ConnectError("refused", request=_requete()), False),
        (httpx.ConnectTimeout("connect timed out", request=_requete()), False),
        (httpx.PoolTimeout("pool", request=_requete()), False),
        (httpx.ReadTimeout("timed out", request=_requete()), True),
        (httpx.WriteTimeout("timed out", request=_requete()), True),
        (httpx.RemoteProtocolError("tronqué", request=_requete()), True),
    ],
)
def test_classification_des_pannes_de_transport(monkeypatch, exc, incertain):
    """Connexion jamais établie ⇒ rien n'est parti. Coupure ensuite ⇒ on ne sait pas."""
    monkeypatch.setattr(W.httpx, "Client", lambda **kw: _ClientFactice(_leve(exc)))
    with pytest.raises(W.EnvoiIncertain if incertain else type(exc)):
        W._poster_au_bridge("http://b/send", {}, {})


#: Ce que le bridge répond → ce que l'API en conclut, et ce que la RAISON doit
#: dire (`contient`) ou taire (`tait`) : c'est elle que l'historique affiche.
#:
#: 🔴 202 et 500 ne se confondent plus (19/08/2026). Le bridge répondait 500 dans
#: les deux cas — son `catch` était commun —, et l'historique affichait
#: « incertain — réponse 500 du bridge » sur des messages que WhatsApp montrait
#: remis, double coche à l'appui. Les deux restent incertains ; seule la raison
#: les distingue, donc c'est elle qui s'éprouve.
CLASSIFICATION_DES_REPONSES = [
    # (code, exception attendue, la raison contient, la raison tait)
    (400, httpx.HTTPStatusError, None, None),  # refusée sans être traitée : rejouable
    (401, httpx.HTTPStatusError, None, None),
    (202, W.EnvoiIncertain, "émis", "500"),  # parti, accusé non observé
    (500, W.EnvoiIncertain, "500", None),  # cassé en route, on ne sait pas où
    (503, W.EnvoiIncertain, None, None),
]


@pytest.mark.parametrize("code, attendue, contient, tait", CLASSIFICATION_DES_REPONSES)
def test_classification_des_reponses_du_bridge(monkeypatch, code, attendue, contient, tait):
    """4xx : la requête a été refusée sans être traitée. 202 : émis, accusé non
    observé. 5xx : on ignore où ça a cassé."""
    reponse = httpx.Response(code, request=_requete())
    monkeypatch.setattr(W.httpx, "Client", lambda **kw: _ClientFactice(lambda *a, **k: reponse))
    with pytest.raises(attendue) as exc:
        W._poster_au_bridge("http://b/send", {}, {})
    raison = str(exc.value)
    if contient:
        assert contient in raison, (
            f"Réponse {code} : la raison « {raison} » doit dire « {contient} » — "
            "c'est ce que l'historique des envois affiche."
        )
    if tait:
        assert tait not in raison, (
            f"Réponse {code} : la raison « {raison} » ne doit pas dire « {tait} » — "
            "un message parti ne se décrit pas comme une réponse 500."
        )


def test_refus_du_serveur_whatsapp_incertain_jamais_rejoue(monkeypatch):
    """502 « refusé » (accusé d'erreur du serveur, 12/10/2026) : le message a été
    émis, donc INCERTAIN — statut qui interdit le rejeu, un doublon dans le groupe
    ne se retire pas —, et la raison porte le motif du serveur."""
    corps = {"refuse": True, "envoye": True, "error": "refusé par le serveur WhatsApp : code 479"}
    reponse = httpx.Response(502, json=corps, request=_requete())
    monkeypatch.setattr(W.httpx, "Client", lambda **kw: _ClientFactice(lambda *a, **k: reponse))
    with pytest.raises(W.EnvoiIncertain) as exc:
        W._poster_au_bridge("http://b/send", {}, {})
    assert "code 479" in str(exc.value)
    statut, _ = W.verdict_envoi(lambda: W._poster_au_bridge("http://b/send", {}, {}))
    assert statut == W.STATUT_INCERTAIN
    assert statut in W.STATUTS_NON_REJOUABLES


# ── La purge ne doit pas manger le verrou ─────────────────────────────────────


def test_la_purge_epargne_le_verrou_du_jour(planifie):
    """Six publications dans la soirée évinçaient le log qui bloquait le rejeu.

    `_prune_logs` ne garde que les 6 derniers logs, tous messages confondus. Le
    log d'un message planifié n'est pas de l'historique : c'est la déduplication.
    """
    maintenant = _HorlogeFigee.maintenant()
    with Session(engine) as session:
        sched = session.exec(select(WhatsAppScheduled)).one()
        session.add(
            WhatsAppLog(
                scheduled_id=sched.id,
                label=sched.label,
                message="planifié",
                statut=W.STATUT_ENVOYE,
                envoye_le=maintenant,
            )
        )
        #  Huit publications postérieures : le verrou sort largement des 6 derniers.
        for i in range(8):
            session.add(
                WhatsAppLog(
                    label=f"Publication {i}",
                    message="…",
                    statut=W.STATUT_ENVOYE,
                    envoye_le=maintenant + timedelta(minutes=i + 1),
                )
            )
        session.commit()
        S._prune_logs(session)

    with Session(engine) as session:
        restants = session.exec(select(WhatsAppLog)).all()
    assert any(log.scheduled_id is not None for log in restants), (
        "le verrou du message planifié a été purgé — le rejeu peut recommencer"
    )


# ── La borne du jour ──────────────────────────────────────────────────────────


def test_la_borne_du_jour_est_en_utc():
    """`envoye_le` est écrit en UTC : la borne de déduplication doit l'être aussi.

    La borne était un minuit de Paris comparé à des horodatages UTC. Ça ne
    « marchait » que parce que la fenêtre d'envoi est en soirée — à 1 h du matin,
    minuit de Paris vaut 23 h UTC la veille, et la requête ramène les logs du
    jour précédent.
    """
    minuit_paris = datetime(2026, 8, 14, 1, 30, tzinfo=PARIS)
    assert horloge.debut_du_jour_utc(minuit_paris) == datetime(2026, 8, 13, 22, 0)
