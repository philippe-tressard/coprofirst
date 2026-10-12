"""Configuration pytest — variables d'environnement minimales avant import de l'app.

L'import de `app.config` exige un SECRET_KEY ≥ 32 caractères et `app.database`
instancie un engine depuis `database_url`. On fournit des valeurs neutres pour
que les tests s'exécutent sans .env ni base réelle (aucun test ici ne se
connecte à la base : ils lisent les templates et la chaîne de migrations).
"""

import itertools
import os
import tempfile

os.environ.setdefault("SECRET_KEY", "x" * 40)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENABLE_API_DOCS", "false")
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
#  Les clés étrangères sont actives en production comme ici : `app/database.py`
#  les pose sur son moteur (`activer_cles_etrangeres`, depuis le 30/08/2026, #546),
#  et `test_integrite_referentielle.py` vérifie qu'elles le sont. Ce fichier n'en
#  garde aucune copie — ni écouteur, ni porte pour les désactiver (#1496).


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
from tests.aides_purge import delier_references, vider_patrimoine  # noqa: E402,F401


@pytest.fixture()
def session():
    """Une base SQLite en mémoire, schéma posé, propre à chaque test (#1495).

    Elle était recopiée dans trente-quatre fichiers. Un test qui a besoin d'une
    AUTRE session (la base de l'application, un `TestClient`) définit la sienne
    sous le même nom : la définition locale prime.
    """
    from sqlmodel import Session

    from tests.aides_base import moteur_memoire

    with Session(moteur_memoire()) as s:
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

    Les scripts d'exploitation (cron) sont restés à la racine : leurs chemins
    absolus vivent dans des crontabs non versionnés, que ce dépôt ne peut pas
    mettre à jour tout seul. Cette fonction ne fait aucune hypothèse là-dessus,
    et c'est le but : elle survivra au jour où ils bougeront.
    """
    racine = racine_depot()
    trouves = list(racine.glob("*.sh"))
    trouves += list(racine.glob("scripts/**/*.sh"))
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


def pytest_collection_modifyitems(config, items):
    """Sur PostgreSQL, les tests des migrations HISTORIQUES sont sautés, et le disent (#1747).

    Elles sont écrites pour SQLite (`DATETIME`, mode `batch`, `PRAGMA`) et ne
    s'exécutent jamais sur PostgreSQL : une base y naît du schéma initial (spec
    §4.3). Une migration POSTÉRIEURE à l'historique, elle, doit passer sur les
    deux — son test n'est pas sauté. La tête est jugée de même par
    `test_migration_de_tete`.
    """
    import re

    if not os.environ.get("TESTS_BASE_URL"):
        return
    from tests.aides_migrations import DERNIERE_HISTORIQUE, VERSIONS

    for item in items:
        marque = item.get_closest_marker("sqlite_seulement")
        if marque:
            assert marque.args, f"{item.nodeid} : `sqlite_seulement` exige sa raison"
            item.add_marker(pytest.mark.skip(reason=f"propre à SQLite — {marque.args[0]}"))

    tete = max(int(p.name[:4]) for p in VERSIONS.glob("[0-9][0-9][0-9][0-9]_*.py"))
    saut = pytest.mark.skip(
        reason="migration historique écrite pour SQLite — sur PostgreSQL, le schéma initial (#1747)"
    )
    for item in items:
        numero = re.match(r"test_migration_(\d{4})_", item.path.name)
        de_tete = item.path.name == "test_migration_de_tete.py" and tete <= DERNIERE_HISTORIQUE
        if de_tete or (numero and int(numero.group(1)) <= DERNIERE_HISTORIQUE):
            item.add_marker(saut)


@pytest.fixture(autouse=True)
def _retirer_schemas_postgresql():
    """Sur PostgreSQL, les schémas d'un test partent avec lui (`tests/aides_base`)."""
    yield
    from tests.aides_base import retirer_schemas_postgresql

    retirer_schemas_postgresql()


def pytest_runtest_logreport(report):
    """Les tests sautés, consignés pour le rejeu local de la CI (#1734).

    Sans `REJEU_SAUTS`, ne fait rien — la CI n'en sait rien. Le pourquoi :
    `tests/aides_rejeu.py`.
    """
    from tests.aides_rejeu import consigner_saut

    consigner_saut(report)
