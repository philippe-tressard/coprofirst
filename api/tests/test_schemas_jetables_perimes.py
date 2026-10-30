"""Un schéma jetable laissé par un passage interrompu part au suivant (#2223).

Le nom d'un schéma jetable porte l'heure de sa création ; la purge retire ceux
qui ont passé l'âge, et laisse tout schéma dont elle ne lit pas l'heure. Sur le
poste, 1 447 orphelins (128 000 tables au catalogue) rendaient chaque
`create_all` 4,6 fois plus lent — la CI, base neuve à chaque passage, ne le
voyait pas.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app import dialecte
from app.utils import horloge
from tests.aides_base import url_des_tests


def test_le_nom_d_un_schema_jetable_porte_son_heure():
    nom = dialecte.poser_schema(url_des_tests())
    try:
        heure = dialecte.heure_du_schema_jetable(nom)
        assert heure is not None, nom
        assert abs(horloge.maintenant() - heure) < timedelta(minutes=5)
    finally:
        dialecte.retirer_schema(url_des_tests(), nom)


def test_un_nom_sans_heure_lisible_n_a_pas_d_age():
    for nom in (
        "public",
        "t_0123456789abcdef",  # la forme d'avant #2223 : âge inconnu
        "t_20261332250000_0123456789ab",  # mois 13
        "t_20261024211530_0123456789ab_x",
    ):
        assert dialecte.heure_du_schema_jetable(nom) is None, nom


def _schemas(url) -> set[str]:
    moteur = create_engine(url, poolclass=NullPool)
    try:
        with moteur.connect() as c:
            return set(c.execute(text("SELECT nspname FROM pg_namespace")).scalars())
    finally:
        moteur.dispose()


def _creer(url, nom: str) -> None:
    moteur = create_engine(url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        with moteur.connect() as c:
            c.execute(text(f'CREATE SCHEMA "{nom}"'))  # noqa: S608 — nom écrit par le test
            c.execute(text(f'CREATE TABLE "{nom}".t (id int)'))  # noqa: S608
    finally:
        moteur.dispose()


def test_la_purge_retire_le_perime_et_laisse_le_recent_et_l_illisible():
    url = url_des_tests()
    marque = uuid.uuid4().hex[:12]
    perime = f"t_20000101000000_{marque}"
    illisible = f"t_{marque}abcd"  # 16 caractères hexadécimaux, la forme d'avant
    recent = dialecte.poser_schema(url)
    _creer(url, perime)
    _creer(url, illisible)
    try:
        assert (
            dialecte.retirer_schemas_jetables_perimes(url, plus_vieux_que=timedelta(hours=6)) >= 1
        )
        restants = _schemas(url)
        assert perime not in restants
        assert recent in restants
        assert illisible in restants
    finally:
        for nom in (perime, illisible, recent):
            dialecte.retirer_schema(url, nom)


def test_un_schema_pose_sous_une_horloge_figee_n_est_pas_perime(monkeypatch):
    """L'âge d'un schéma se lit à l'heure du SERVEUR, que les tests ne figent pas (#2350).

    Une sauvegarde testée sous une horloge figée au 09/10 posait son schéma de
    vérification « vieux de trois semaines » ; la purge d'un autre worker le retirait
    en plein import, et la sauvegarde se disait échouée. L'inverse — une purge sous
    une horloge figée dans le futur — retirait les schémas vivants de tous les autres.
    """
    url = url_des_tests()
    with monkeypatch.context() as figee:
        figee.setattr(horloge, "maintenant", lambda: datetime(2026, 10, 9, 1, 0, 0))
        nom = dialecte.poser_schema(url)
    try:
        assert abs(horloge.maintenant() - dialecte.heure_du_schema_jetable(nom)) < timedelta(
            minutes=5
        )
        with monkeypatch.context() as figee:
            figee.setattr(horloge, "maintenant", lambda: datetime(2099, 1, 1))
            dialecte.retirer_schemas_jetables_perimes(url, plus_vieux_que=timedelta(hours=6))
        assert nom in _schemas(url)
    finally:
        dialecte.retirer_schema(url, nom)
