"""Le rôle d'une copropriété peut différer ses clés : sa sauvegarde se vérifie (#3113).

POURQUOI (25/11/2026) — l'essai de mise à jour d'une installation commune (#3007)
a vu la sauvegarde de la seconde copropriété refusée :
`permission denied to set parameter "session_replication_role"`. Son rôle, créé par
`creer-copropriete.sh` (`lib-bases.base_creer`), n'est pas superutilisateur — c'est
voulu ; or réimporter une archive dont les tables se citent en cycle suspend les
clés le temps de la transaction (`dialecte.differer_cles_etrangeres`), ce que
PostgreSQL réserve au superutilisateur ou au rôle qui en a reçu le DROIT. La
sauvegarde nocturne, la vérification de l'administration et la sauvegarde avant
mise à jour échouaient toutes : la copropriété n'avait aucune sauvegarde valide.

La suite joue sous un rôle superutilisateur : elle était verte. Ce test crée donc
son PROPRE rôle sans superpouvoir, et prouve :

- sans le droit, la vérification d'une archive à cycles est refusée (témoin) ;
- avec le droit qu'écrit `base_autoriser_differer` (`lib-bases.sh`) — sa requête,
  lue en exécutant la fonction, jamais recopiée —, elle passe, clés relevées ;
- `creer-copropriete.sh` l'accorde à chaque copropriété qu'il crée.
"""

from __future__ import annotations

import secrets
import shutil
import subprocess

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError

from app.utils import export_copropriete as ex
from app.utils import import_copropriete as im
from tests.aides_base import url_des_tests
from tests.aides_compose import RACINE
from tests.test_export_copropriete import _base_peuplee, _copropriete_et_batiment

LIB_BASES = RACINE / "deploiement" / "standard" / "lib-bases.sh"
CREER = RACINE / "deploiement" / "standard" / "commune" / "creer-copropriete.sh"


def _superutilisateur(sql: str) -> None:
    moteur = create_engine(url_des_tests(), isolation_level="AUTOCOMMIT")
    try:
        with moteur.connect() as c:
            c.execute(text(sql))
    finally:
        moteur.dispose()


@pytest.fixture
def role_de_copropriete():
    """Un rôle comme celui de `base_creer` : LOGIN, sans superpouvoir ; et son adresse."""
    nom = f"t_copro_{secrets.token_hex(6)}"  # [a-z0-9_] : interpolable, comme base_creer
    mdp = secrets.token_hex(16)
    url = make_url(url_des_tests())
    _superutilisateur(f"CREATE ROLE {nom} WITH LOGIN NOSUPERUSER PASSWORD '{mdp}'")
    #  Sa base lui appartient en vrai : il y crée le schéma jetable de l'épreuve.
    _superutilisateur(f"GRANT CREATE ON DATABASE {url.database} TO {nom}")
    try:
        yield nom, url.set(username=nom, password=mdp)
    finally:
        _superutilisateur(f"REVOKE SET ON PARAMETER session_replication_role FROM {nom}")
        _superutilisateur(f"DROP OWNED BY {nom}")
        _superutilisateur(f"DROP ROLE {nom}")


@pytest.fixture
def archive_a_cycles(tmp_path):
    source = _base_peuplee()
    _copropriete_et_batiment(source)
    archive = tmp_path / "export.tar.gz"
    ex.exporter(source, archive)
    ordre = [t.name for t in ex.tables()]
    assert ordre.index("batiment") < ordre.index("copropriete"), (
        "cas zéro : plus de cycle — l'épreuve passerait sans différer les clés"
    )
    return archive


def _requete_du_droit(role: str) -> str:
    """La requête qu'émet `base_autoriser_differer`, captée par un faux psql."""
    if shutil.which("bash") is None:
        pytest.skip("bash absent : la bibliothèque ne peut pas être exécutée")
    #  La fonction fait taire la sortie de psql : le faux psql écrit sur stderr.
    res = subprocess.run(
        [
            "bash",
            "-c",
            f"source '{LIB_BASES.as_posix()}'; "
            'faux_psql() { [ "$1" = -c ] && printf "%s\\n" "$2" >&2; }; '
            f"base_autoriser_differer faux_psql {role}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert res.returncode == 0, res.stdout + res.stderr
    requete = res.stderr.strip()
    assert role in requete, requete
    return requete


def test_sans_le_droit_la_verification_est_refusee(role_de_copropriete, archive_a_cycles):
    """Témoin (`standards/04` §2) : l'incident du 25/11, reproduit sous un vrai rôle."""
    _, url = role_de_copropriete
    with pytest.raises(ProgrammingError, match="session_replication_role"):
        im.verifier_archive(archive_a_cycles, url)


def test_avec_le_droit_de_lib_bases_la_verification_passe(role_de_copropriete, archive_a_cycles):
    role, url = role_de_copropriete
    _superutilisateur(_requete_du_droit(role))
    bilan = im.verifier_archive(archive_a_cycles, url)
    assert bilan.ecarts == []
    assert bilan.tables > 0 and bilan.lignes > 0


def test_creer_copropriete_accorde_le_droit_apres_la_creation():
    texte = CREER.read_text(encoding="utf-8")
    assert "base_autoriser_differer psql_installation" in texte, (
        "creer-copropriete.sh n'accorde plus le droit de différer les clés : la "
        "copropriété créée n'aurait aucune sauvegarde valide (#3113)"
    )
    assert texte.index("base_creer psql_installation") < texte.index(
        "base_autoriser_differer psql_installation"
    ), "le droit s'accorde à un rôle qui existe : après base_creer"
