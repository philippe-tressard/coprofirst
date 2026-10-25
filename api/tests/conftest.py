"""Configuration pytest — variables d'environnement minimales avant import de l'app.

L'import de `app.config` exige un SECRET_KEY ≥ 32 caractères et `app.database`
instancie un engine depuis `database_url`. On fournit des valeurs neutres pour
que les tests s'exécutent sans .env.

La base est un serveur PostgreSQL (`TESTS_BASE_URL`). Le moteur de
l'APPLICATION (`app.database.engine`, `contexte.moteur()`) y reçoit un schéma
propre à ce processus, retiré à la fin de la session : deux tranches de la
suite, lancées en parallèle sur le même serveur, ne se voient pas. Chaque base
de test (`aides_base.moteur_de_test`) a, elle, son schéma à elle.
Sans `TESTS_BASE_URL`, l'adresse ne mène nulle part : les tests qui ne touchent
pas la base tournent, les autres échouent en le disant.
"""

import itertools
import os
import tempfile

os.environ.setdefault("SECRET_KEY", "x" * 40)
_URL_TESTS = os.environ.get("TESTS_BASE_URL")
_SCHEMA_DU_PROCESSUS = None
#  Un worker de `pytest -n` hérite du `DATABASE_URL` du maître : il pose le
#  sien, sans quoi tous écrivaient dans le même schéma (`tests/aides_processus`).
from tests.aides_processus import MARQUE as _POSEE_ICI  # noqa: E402
from tests.aides_processus import SERVEUR_INJOIGNABLE, base_a_poser  # noqa: E402

if base_a_poser(os.environ):
    os.environ.pop("DATABASE_URL", None)
    if _URL_TESTS:
        from datetime import timedelta

        from app.dialecte import poser_schema, retirer_schemas_jetables_perimes, url_dans_schema

        #  Ce qu'un passage INTERROMPU a laissé — ses schémas n'ont pas été
        #  retirés — part au suivant (#2223) : 1 447 orphelins rendaient chaque
        #  `create_all` 4,6 fois plus lent sur le poste. Six heures : aucune
        #  suite n'en dure une, et celles d'autres sessions tournent peut-être.
        #  Le processus maître seul (`PYTEST_XDIST_WORKER` absent) : ses workers
        #  partent au même instant, et retireraient les mêmes schémas que lui.
        if "PYTEST_XDIST_WORKER" not in os.environ:
            try:
                retirer_schemas_jetables_perimes(_URL_TESTS, plus_vieux_que=timedelta(hours=6))
            except Exception as exc:  # noqa: BLE001 — une purge manquée ne change pas le verdict
                print(f"schémas périmés non retirés : {exc}")
        _SCHEMA_DU_PROCESSUS = poser_schema(_URL_TESTS)
        os.environ["DATABASE_URL"] = url_dans_schema(
            _URL_TESTS, _SCHEMA_DU_PROCESSUS
        ).render_as_string(hide_password=False)
        os.environ[_POSEE_ICI] = os.environ["DATABASE_URL"]
    else:
        os.environ["DATABASE_URL"] = (
            f"postgresql+psycopg://essai@{SERVEUR_INJOIGNABLE}/sans-serveur"
        )
os.environ.setdefault("ENABLE_API_DOCS", "false")
#  Pas de cache du manuel PDF : il s'écrirait sous `/app/data` du poste.
os.environ.setdefault("CACHE_MANUEL_DIR", "")
#  Le client de test se présente sous l'hôte `testserver` : il se déclare au
#  registre comme un nom de l'installation (#1751), sans quoi tout rendrait 421.
os.environ.setdefault("HOTES_COPROPRIETE", "testserver")

#  Importer `app.main` monte `/uploads` en statique et crée le répertoire au
#  passage. Sans redirection, ce `mkdir` vise un chemin absolu de conteneur —
#  il échoue sur un poste Windows comme sur un exécuteur d'intégration continue,
#  et rendait l'application entière intestable. Cf. tests/test_demarrage.py.
os.environ.setdefault("UPLOADS_DIR", os.path.join(tempfile.gettempdir(), "hostachy-tests-uploads"))

import pytest  # noqa: E402  (après les variables d'environnement, par construction)


# ── Intégrité référentielle : la règle est celle de l'APPLICATION ────────────
#
#  Les clés étrangères sont vérifiées sur le moteur de l'application comme en
#  production ; une base de test les suspend sauf `cles_etrangeres=True`
#  (`aides_base.moteur_de_test`). Ce fichier n'en garde aucune autre règle (#1496).


# ── Patrimoine de test ────────────────────────────────────────────────────────
#
#  Monter une copropriété de quatre bâtiments et semer l'arbre des périmètres :
#  ce montage était écrit **deux fois** à l'identique (`test_perimetres_arbre.py`
#  et `test_perimetres_router.py`), et un troisième fichier venait d'en avoir
#  besoin (14/08/2026). Une fixture recopiée diverge comme n'importe quel autre
#  code — les deux `_vider` avaient d'ailleurs déjà divergé sur les modèles
#  qu'ils purgent.
#
#  Les imports sont **différés dans le corps** et non en tête de ce fichier :
#  `conftest.py` est chargé avant tous les tests, y compris ceux qui ne touchent
#  jamais la base, et importer l'application ici changerait leur ordre d'import.


#  Les helpers de purge vivent dans `tests/aides_purge.py` : un conftest n'est pas
#  importable par un test, et un fichier qui en avait besoin en gardait une COPIE
#  divergente (#546, 28/08/2026). Réexportés ici pour les fixtures ci-dessous.
from tests.aides_purge import (  # noqa: E402,F401
    delier_references,
    purger_referentiellement,
    vider_patrimoine,
)


@pytest.fixture()
def session():
    """Une base de test, schéma posé, propre à chaque test (#1495).

    Elle était recopiée dans trente-quatre fichiers. Un test qui a besoin d'une
    AUTRE session (la base de l'application, un `TestClient`) définit la sienne
    sous le même nom : la définition locale prime.
    """
    from sqlmodel import Session

    from tests.aides_base import moteur_de_test

    with Session(moteur_de_test()) as s:
        yield s


@pytest.fixture()
def batiments() -> list[int]:
    """Arbre semé sur quatre bâtiments réels. Renvoie leurs identifiants."""
    from sqlmodel import Session, SQLModel, select

    from app.database import engine
    from app.models.core import Batiment, Copropriete
    from app.seed.patrimoine import poser_arborescence
    from app.utils import perimetres as P

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        vider_patrimoine(session)
        copro = Copropriete(nom="Test", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        for numero in ("1", "2", "3", "4"):
            session.add(Batiment(copropriete_id=copro.id, numero=numero))
        session.commit()
        ids = list(session.exec(select(Batiment.id).order_by(Batiment.id)).all())
        poser_arborescence(session)
        session.commit()
    P.invalider_cache()
    yield ids
    #  Le patrimoine repart AUSSI à la sortie. Il ne partait qu'à l'entrée, si
    #  bien que la copropriété et ses quatre bâtiments survivaient au test et
    #  attendaient le suivant : `test_copropriete_fiche.py` supprime toutes les
    #  copropriétés dans sa propre fixture, et SQLAlchemy dénoue alors les
    #  bâtiments orphelins (`UPDATE batiment SET copropriete_id = NULL`) — la
    #  colonne est NOT NULL, six tests tombaient en erreur de montage.
    #  Le défaut ne s'est vu qu'en ajoutant un fichier qui trie AVANT
    #  `test_copropriete_fiche` (15/08/2026) : jusque-là, les deux seuls usagers
    #  de cette fixture passaient après lui. Un test dont le résultat dépend de
    #  l'ordre alphabétique des fichiers n'est pas un test.
    with Session(engine) as session:
        vider_patrimoine(session)
    P.invalider_cache()


@pytest.fixture()
def disque_jetable(monkeypatch, tmp_path):
    """Le stockage de la copropriété servie, posé sur `tmp_path` — rendu.

    Un fichier que l'application lit ou efface vit sous SA racine : `stockage()`
    refuse tout chemin hors d'elle (#1748, #1816). La racine se demande au
    contexte de copropriété, qui la lit dans la configuration (#1744). Écrite
    ici : sept fichiers de tests recopiaient la ligne.
    """
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


@pytest.fixture()
def lots_jetables():
    """Les lots qu'un test COMMET repartent à sa sortie (#2212).

    `vider_patrimoine` délie les lots de leurs bâtiments sans les effacer : un lot
    laissé par un test faisait « lot absent de l'état descriptif » au suivant, qui
    confronte un fichier à TOUS les lots en base."""
    from sqlmodel import Session

    from app.database import engine
    from app.models.copropriete import Lot

    yield
    with Session(engine) as session:
        purger_referentiellement(session, Lot)
        session.commit()


@pytest.fixture()
def arbre_vide():
    """Aucun périmètre configuré — l'état d'une copropriété qui n'a rien saisi.

    C'est un état **valide** et non une panne : le produit doit servir une
    copropriété qui n'a ni AFUL, ni quatre bâtiments. Tout ce qui lit l'arbre doit
    donc se comporter correctement quand il est vide.
    """
    from sqlmodel import Session, SQLModel

    from app.database import engine
    from app.utils import perimetres as P

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        vider_patrimoine(session)
    P.invalider_cache()
    yield
    P.invalider_cache()


# ── Où vivent les scripts versionnés ─────────────────────────────────────────
#
#  Quatre tests scannaient les scripts, chacun avec son propre `RACINE.glob("*.sh")`.
#  Le rangement du 15/08/2026 (#337) a déplacé l'outillage du poste dans
#  `scripts/poste/` : les quatre globs ont cessé de le voir **en même temps**, et
#  trois d'entre eux sont devenus faux sans rien dire de compréhensible — « aucun
#  script ne poste export_hors_site », « endpoint orphelin ».
#
#  La leçon n'est pas « corriger quatre chemins » mais « il n'y en avait pas un
#  seul » (`standards/02-factorisation.md`). La portée du scan est une notion :
#  elle s'écrit ici, et les tests la lisent.


def racine_depot():
    from pathlib import Path

    return Path(__file__).resolve().parents[2]


def scripts_shell_versionnes() -> list:
    """Tous les `.sh` du dépôt, où qu'ils soient rangés — plus les hooks git.

    Ce que git suit ou suivrait (`--others --exclude-standard` : un script neuf
    est contrôlé avant son premier commit), donc ni `node_modules` ni un fichier
    ignoré. 🔴 Jusqu'au 14/10/2026 (#1965), la liste se lisait par trois motifs
    — racine, `scripts/**`, `.githooks/` — et huit scripts y échappaient, dont
    ceux que chaque réplique exécute (`deploiement/standard/`) et `api/start.sh`.
    La docstring promettait déjà « où qu'ils soient rangés ».
    🔒 `test_releve_scripts_complet.py`.
    """
    import subprocess

    racine = racine_depot()
    suivis = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.sh"],
        cwd=racine,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    trouves = [racine / s for s in suivis if (racine / s).is_file()]
    trouves += [p for p in racine.glob(".githooks/*") if p.is_file()]
    return sorted(set(trouves))


# ── Une vraie requête, pour les routes limitées en débit ─────────────────────
#
#  Les routes d'authentification portent toutes un `@limiter.limit` (#1027), et
#  slowapi lit l'adresse du client dans une `starlette.requests.Request`. Un
#  objet imitateur ne suffit donc pas, et retirer le décorateur reviendrait à
#  tester une fonction que la production n'exécute pas.
#
#  Cette fabrique vivait en double — `_Requete` dans les tests de mot de passe —
#  au moment où un deuxième fichier en a eu besoin. Elle s'écrit ici une fois.

_compteur_client = itertools.count()


def requete_de_test(chemin: str = "/", methode: str = "POST"):
    """Une requête Starlette minimale, **d'une adresse nouvelle à chaque appel**.

    🔴 L'adresse change à chaque appel parce que les plafonds se comptent PAR
    CLIENT : sans cela, le sixième test d'un fichier recevrait un 429 et
    échouerait pour une raison étrangère à ce qu'il vérifie. On ne désarme pas le
    décorateur — on cesse d'être le même visiteur.
    """
    from starlette.requests import Request

    return Request(
        {
            "type": "http",
            "method": methode,
            "path": chemin,
            "headers": [],
            "query_string": b"",
            "scheme": "https",
            "server": ("test", 443),
            "client": (f"10.0.0.{next(_compteur_client) % 250 + 1}", 51234),
        }
    )


@pytest.fixture()
def utilisateur():
    """Un propriétaire ACTIF, de courriel unique, et ce qu'il laisse derrière lui purgé.

    Elle vivait dans `test_reinitialisation_mot_de_passe.py` ; un second fichier
    en a eu besoin le 27/09/2026 (`test_jeton_rejoue.py`) : elle s'écrit ici une fois.
    """
    import uuid

    from sqlmodel import Session, SQLModel, select

    from app.auth.jwt import hash_password
    from app.database import engine
    from app.models.core import PasswordResetToken, RefreshToken, RoleUtilisateur, Utilisateur
    from tests.aides_purge import purger_ligne

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        u = Utilisateur(
            email=f"reinit-{uuid.uuid4().hex[:8]}@exemple.test",
            hashed_password=hash_password("Ancien-Mdp1"),
            prenom="Reine",
            nom="Ito",
            role=RoleUtilisateur.propriétaire,
            #  `actif` vaut False par défaut : un compte attend sa validation
            #  par le conseil syndical. Un compte de test doit donc l'activer
            #  explicitement, sinon il éprouve le refus, pas la règle.
            actif=True,
        )
        session.add(u)
        session.commit()
        session.refresh(u)
        yield u
        for jeton in session.exec(
            select(PasswordResetToken).where(PasswordResetToken.user_id == u.id)
        ).all():
            session.delete(jeton)
        for rt in session.exec(select(RefreshToken).where(RefreshToken.user_id == u.id)).all():
            session.delete(rt)
        session.commit()
        purger_ligne(session, Utilisateur, u.id)
        session.commit()


@pytest.fixture(scope="module", autouse=True)
def _base_du_processus_neuve():
    """Chaque FICHIER de tests trouve la base partagée du processus neuve (#2223).

    Elle est la seule que voient TOUS les tests d'un processus : ce qu'un fichier
    y laissait, le suivant le trouvait — et lequel est le suivant dépend de la
    répartition entre workers. Le 24/10/2026, des bâtiments laissés là ont fait
    tomber `test_copropriete_fiche.py` sur un lot qui n'y touchait pas. Démarrer
    l'application (`TestClient`, donc `lifespan`) y sème aussi toute la
    copropriété d'essai.

    Neuve comme en production : toutes les tables, aucune ligne, les compteurs à
    1 (`aides_purge.remettre_a_neuf`). Les états de copropriété tenus en mémoire
    (`contexte.etat` : arbre des périmètres, bâtiments de chacun…) partent avec,
    sans quoi ils parleraient de lignes qui n'existent plus. Dans un même fichier, l'ordre est tiré au
    sort (`pytest-randomly`) : une dépendance entre ses tests sort là, au lot
    qui l'écrit.
    """
    import sys

    if _SCHEMA_DU_PROCESSUS is not None:
        from tests.aides_purge import remettre_a_neuf

        remettre_a_neuf(os.environ["DATABASE_URL"])
        contexte = sys.modules.get("app.contexte")
        if contexte is not None:
            #  Le registre des états (`contexte.etat`) : la seule porte, et elle
            #  n'a pas de geste « tout oublier » — que les tests seuls emploieraient.
            contexte._etats.clear()
    yield


@pytest.fixture(autouse=True)
def _retirer_schemas_du_test():
    """Les schémas d'un test partent avec lui (`tests/aides_base`)."""
    yield
    from tests.aides_base import retirer_schemas_du_test

    retirer_schemas_du_test()


def pytest_sessionfinish(session, exitstatus):
    """Le schéma du moteur de l'application part avec la session."""
    import sys

    if _SCHEMA_DU_PROCESSUS is None:
        return
    base = sys.modules.get("app.database")
    if base is not None:
        base.engine.dispose()
    from app.dialecte import retirer_schema

    try:
        retirer_schema(_URL_TESTS, _SCHEMA_DU_PROCESSUS)
    except Exception as exc:  # noqa: BLE001 — un retrait manqué ne change pas le verdict
        print(f"schéma {_SCHEMA_DU_PROCESSUS} non retiré : {exc}")


def pytest_runtest_logreport(report):
    """Les tests sautés, consignés pour le rejeu local de la CI (#1734).

    Sans `REJEU_SAUTS`, ne fait rien — la CI n'en sait rien. Le pourquoi :
    `tests/aides_rejeu.py`.
    """
    from tests.aides_rejeu import consigner_saut

    consigner_saut(report)
