"""Les notifications LUES se conservent douze mois, puis la tâche nocturne les retire (#2535).

Décidé par l'administrateur le 08/11/2026 : « 12 mois ». La règle vit dans
`utils/purge_notifications` ; ce fichier la juge, puis la tâche sur une base :
elle retire ce qui est lu ET ancien, et rien d'autre.

🔴 Une notification NON lue ne se purge jamais, quel que soit son âge : elle dit
encore quelque chose à son destinataire.
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import select

from app.models.core import Notification
from app.utils import horloge
from app.utils.purge_notifications import (
    CONSERVATION_JOURS,
    ID_TACHE,
    notification_echue,
    purger_notifications_lues,
)
from tests.aides_base import compte

MAINTENANT = horloge.maintenant()
TREIZE_MOIS = MAINTENANT - timedelta(days=396)
ONZE_MOIS = MAINTENANT - timedelta(days=335)


def _notification(destinataire_id: int, *, lue: bool, cree_le, titre: str = "Avis") -> Notification:
    return Notification(
        destinataire_id=destinataire_id, type="system", titre=titre, lue=lue, cree_le=cree_le
    )


# ── La règle ────────────────────────────────────────────────────────────────


def test_la_conservation_est_de_douze_mois():
    assert CONSERVATION_JOURS == 365


def test_lue_depuis_plus_de_douze_mois_est_echue():
    assert notification_echue(_notification(1, lue=True, cree_le=TREIZE_MOIS), MAINTENANT)


def test_lue_depuis_moins_de_douze_mois_se_garde():
    assert not notification_echue(_notification(1, lue=True, cree_le=ONZE_MOIS), MAINTENANT)


def test_non_lue_ne_se_purge_jamais():
    assert not notification_echue(_notification(1, lue=False, cree_le=TREIZE_MOIS), MAINTENANT)


def test_pile_a_la_limite_se_garde():
    limite = MAINTENANT - timedelta(days=CONSERVATION_JOURS)
    assert not notification_echue(_notification(1, lue=True, cree_le=limite), MAINTENANT)


# ── La tâche ────────────────────────────────────────────────────────────────


def test_la_tache_ne_retire_que_les_lues_echues(session):
    dest = compte(session)
    session.add_all(
        [
            _notification(dest.id, lue=True, cree_le=TREIZE_MOIS, titre="lue-ancienne"),
            _notification(dest.id, lue=True, cree_le=ONZE_MOIS, titre="lue-recente"),
            _notification(dest.id, lue=False, cree_le=TREIZE_MOIS, titre="non-lue-ancienne"),
            _notification(dest.id, lue=False, cree_le=ONZE_MOIS, titre="non-lue-recente"),
        ]
    )
    session.commit()

    assert purger_notifications_lues(session, maintenant=MAINTENANT) == 1

    restantes = set(session.exec(select(Notification.titre)))
    assert restantes == {"lue-recente", "non-lue-ancienne", "non-lue-recente"}


def test_la_tache_vaut_pour_tous_les_destinataires(session):
    a, b = compte(session), compte(session)
    session.add_all(
        [
            _notification(a.id, lue=True, cree_le=TREIZE_MOIS),
            _notification(b.id, lue=True, cree_le=TREIZE_MOIS),
        ]
    )
    session.commit()

    assert purger_notifications_lues(session, maintenant=MAINTENANT) == 2
    assert session.exec(select(Notification)).all() == []


def test_rien_a_retirer_rend_zero_et_ne_leve_pas(session):
    assert purger_notifications_lues(session, maintenant=MAINTENANT) == 0


def test_l_identifiant_de_la_tache_est_stable():
    assert ID_TACHE == "purge_notifications_lues"
