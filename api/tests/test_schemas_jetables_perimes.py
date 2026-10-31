"""Un schéma jetable laissé par un passage interrompu part au suivant (#2223).

Le nom d'un schéma jetable porte l'heure de sa création ; la purge retire ceux
qui ont passé l'âge, et laisse tout schéma dont elle ne lit pas l'heure. Sur le
poste, 1 447 orphelins (128 000 tables au catalogue) rendaient chaque
`create_all` 4,6 fois plus lent — la CI, base neuve à chaque passage, ne le
voyait pas.
"""

from __future__ import annotations

import os
import subprocess
import sys
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


# ── Le créateur inscrit et la connexion ouverte (#2399) ─────────────────────
#  Le 31/10/2026, les suites coupées dans la même heure avaient laissé 140 schémas
#  (52 000 relations) : sous le plafond d'une heure, rien ne les retirait.

_MAINTENANT = datetime(2026, 10, 31, 14, 0, 0)
_RECENT = "t_20261031135500_0123456789ab"  # cinq minutes
_ANCIEN = "t_20261031120000_0123456789ab"  # deux heures


def _a_retirer(schemas, *, tenus=frozenset(), vivants=frozenset()):
    return dialecte.schemas_jetables_a_retirer(
        schemas,
        maintenant=_MAINTENANT,
        plus_vieux_que=timedelta(hours=1),
        tenus=set(tenus),
        hote="POSTE",
        vivant=lambda pid: pid in vivants,
    )


def test_aucun_schema_rien_a_retirer():
    assert _a_retirer({}) == []


def test_un_createur_mort_abandonne_son_schema_sans_attendre_l_heure():
    assert _a_retirer({_RECENT: "createur=4242@POSTE"}) == [_RECENT]


def test_un_createur_vivant_garde_son_schema():
    assert _a_retirer({_RECENT: "createur=4242@POSTE"}, vivants={4242}) == []


def test_une_connexion_ouverte_garde_le_schema_meme_vieux_et_createur_mort():
    schemas = {_ANCIEN: "createur=4242@POSTE", _RECENT: "createur=4243@POSTE"}
    assert _a_retirer(schemas, tenus={_ANCIEN, _RECENT}) == []


def test_un_createur_inconnu_n_est_juge_qu_au_plafond():
    schemas = {
        _RECENT: None,  # posé par un code d'avant #2399
        "t_20261031135600_0123456789ac": "createur=4242@AUTRE",  # autre hôte, conteneur
        "t_20261031135700_0123456789ad": "createur=x@POSTE",  # illisible
        _ANCIEN: None,
    }
    assert _a_retirer(schemas) == [_ANCIEN]


def test_un_schema_non_jetable_reste_quel_que_soit_son_commentaire():
    assert _a_retirer({"public": "createur=4242@POSTE"}) == []


def test_poser_schema_inscrit_son_createur_et_la_purge_le_garde_vivant():
    url = url_des_tests()
    nom = dialecte.poser_schema(url)
    moteur = create_engine(url, poolclass=NullPool)
    try:
        with moteur.connect() as c:
            commentaire = c.execute(
                text(
                    "SELECT obj_description(oid, 'pg_namespace') FROM pg_namespace WHERE nspname = :n"
                ),
                {"n": nom},
            ).scalar_one()
        assert commentaire == f"createur={os.getpid()}@{dialecte._hote()}"
        dialecte.retirer_schemas_jetables_perimes(url, plus_vieux_que=timedelta(hours=1))
        assert nom in _schemas(url)
    finally:
        moteur.dispose()
        dialecte.retirer_schema(url, nom)


def test_une_connexion_dans_le_schema_se_nomme_de_lui():
    url = url_des_tests()
    nom = dialecte.poser_schema(url)
    moteur = create_engine(dialecte.url_dans_schema(url, nom), poolclass=NullPool)
    try:
        with moteur.connect() as c:
            assert c.execute(text("SHOW application_name")).scalar_one() == nom
    finally:
        moteur.dispose()
        dialecte.retirer_schema(url, nom)


def test_la_purge_retire_le_schema_d_un_createur_mort():
    url = url_des_tests()
    nom = f"t_{horloge.maintenant():%Y%m%d%H%M%S}_{uuid.uuid4().hex[:12]}"
    _creer(url, nom)
    moteur = create_engine(url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        with moteur.connect() as c:
            #  Le pid d'un processus lancé puis attendu : mort, à coup sûr.
            mort = subprocess.run(
                [sys.executable, "-c", "import os; print(os.getpid())"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            c.execute(text(f"COMMENT ON SCHEMA \"{nom}\" IS 'createur={mort}@{dialecte._hote()}'"))  # noqa: S608
        assert (
            dialecte.retirer_schemas_jetables_perimes(url, plus_vieux_que=timedelta(hours=1)) >= 1
        )
        assert nom not in _schemas(url)
    finally:
        moteur.dispose()
        dialecte.retirer_schema(url, nom)
