"""Les gestes propres au moteur de la base, PostgreSQL — écrits ici, et nulle part ailleurs.

Ce qui s'exprime dans la langue du serveur — intégrité, compactage, clés
différées, format SQL d'une date, base de travail jetable — vit ICI, derrière un
nom qui dit la QUESTION posée (« la base est-elle saine ? », « le mois de cette
date »), jamais la commande du moteur.
"""

from __future__ import annotations

import os
import re
import socket
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import Interval, String, cast, func, literal, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

# ── Les gestes d'exploitation ────────────────────────────────────────────────


def verifier_integrite(conn) -> str:
    """Le verdict d'intégrité de la base : « ok » si saine, sinon ce qu'elle signale.

    Les SOMMES DE CONTRÔLE de pages (`--data-checksums`, posé à l'initialisation
    par docker-compose.yml) : chaque page lue est vérifiée, et
    `pg_stat_database.checksum_failures` compte les échecs depuis l'origine.
    Zéro, sommes actives : « ok ». Sommes absentes : la base ne SAIT pas
    détecter une page abîmée — le verdict le dit, il n'est pas vert
    (`standards/04` §1).
    """
    actives = conn.execute(text("SHOW data_checksums")).scalar()
    if actives != "on":
        return "sommes de contrôle de pages désactivées — corruption non détectable"
    echecs = conn.execute(
        text("SELECT coalesce(sum(checksum_failures), 0) FROM pg_stat_database")
    ).scalar()
    return "ok" if not echecs else f"{echecs} page(s) en échec de somme de contrôle"


def compacter(conn) -> None:
    """Rend l'espace des lignes supprimées et rafraîchit les statistiques.

    `conn` doit être en AUTOCOMMIT : le serveur ne compacte pas dans une transaction.
    """
    conn.execute(text("VACUUM ANALYZE"))


def taille_base(conn) -> int:
    """La place qu'occupe la base sur le disque du serveur, en octets."""
    return int(conn.execute(text("SELECT pg_database_size(current_database())")).scalar())


# ── Les clés étrangères ──────────────────────────────────────────────────────


def differer_cles_etrangeres(conn) -> None:
    """Les clés ne se vérifient plus pendant cette TRANSACTION.

    Pour une écriture en bloc (l'import d'une archive) : des tables qui se citent
    en cycle n'ont aucun ordre d'écriture qui satisfasse toutes leurs clés —
    `batiment` est refusé avant `copropriete`. Les clés n'étant pas `DEFERRABLE`,
    `session_replication_role = replica` suspend leurs déclencheurs le temps de la
    transaction : l'appelant DOIT relever lui-même les orphelins avant de valider
    (`import_copropriete.lignes_sans_parent`).
    ⚠️ Exige un rôle superutilisateur — celui de l'image l'est.
    """
    conn.execute(text("SET LOCAL session_replication_role = replica"))


# ── Une base de travail jetable ──────────────────────────────────────────────


#: Le nom d'un schéma jetable porte l'heure de sa CRÉATION (UTC) : un schéma
#: resté derrière un processus interrompu se reconnaît alors à son âge (#2223).
#: Sans elle, 1 447 schémas orphelins s'étaient accumulés sur la base d'essai du
#: poste — 128 000 tables au catalogue, et chaque `create_all` y prenait 1,85 s
#: au lieu de 0,39 s (24/10/2026).
_FORMAT_HEURE_SCHEMA = "%Y%m%d%H%M%S"
_NOM_SCHEMA_JETABLE = re.compile(r"^t_(\d{14})_[0-9a-f]{12}$")

#: …et son CRÉATEUR, en commentaire : `createur=<pid>@<hôte>` (#2399). Un schéma
#: dont le créateur est mort est abandonné quel que soit son âge — les restes de
#: plusieurs suites coupées dans la même heure ne s'accumulent plus (140 schémas,
#: 52 000 relations au catalogue le 31/10/2026 : un DDL y prenait 396 ms au lieu de
#: 16). L'hôte, parce qu'un pid ne se juge que sur la machine qui l'a donné.
_COMMENTAIRE_CREATEUR = re.compile(r"^createur=(\d+)@([A-Za-z0-9._-]+)$")


def _hote() -> str:
    """Le nom de cet hôte, réduit à ce qu'un littéral SQL porte sans échappement."""
    return re.sub(r"[^A-Za-z0-9._-]", "", socket.gethostname()) or "inconnu"


def _heure_du_serveur(c) -> datetime:
    """L'heure du SERVEUR (UTC naïf) : l'âge d'un schéma se mesure à elle seule.

    🔴 Jamais `horloge.maintenant()`, que les tests figent : un schéma posé sous
    une horloge figée au passé naissait « périmé », et la purge d'un autre
    processus le retirait en plein usage — une sauvegarde se disait alors
    « échouée » (#2350). Le serveur est la seule horloge que tous partagent.
    """
    return c.execute(text("SELECT clock_timestamp() AT TIME ZONE 'UTC'")).scalar_one()


def poser_schema(url) -> str:
    """Crée un SCHÉMA neuf sur le serveur de `url` ; rend son nom."""
    admin = _creer_moteur(url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        with admin.connect() as c:
            heure = _heure_du_serveur(c)
            nom = f"t_{heure:{_FORMAT_HEURE_SCHEMA}}_{uuid.uuid4().hex[:12]}"
            c.execute(text(f'CREATE SCHEMA "{nom}"'))  # noqa: S608 — identifiant généré ici
            #  Un COMMENT ne prend pas de paramètre lié : le littéral n'est fait que d'un
            #  entier et d'un nom d'hôte réduit à [A-Za-z0-9._-] (`_hote`).
            createur = f"createur={os.getpid()}@{_hote()}"
            c.execute(text(f"COMMENT ON SCHEMA \"{nom}\" IS '{createur}'"))  # noqa: S608
    finally:
        admin.dispose()
    return nom


def url_dans_schema(url, nom: str, *, cles_etrangeres: bool = True) -> URL:
    """L'adresse de `url` réglée pour ne voir que le schéma `nom` (`search_path`).

    `cles_etrangeres=False` suspend la vérification des clés sur chaque
    connexion (`session_replication_role = replica`, rôle superutilisateur).

    Chaque connexion se NOMME du schéma (`application_name`) : la purge ne retire
    jamais le schéma d'une connexion ouverte (#2399).
    """
    options = f"-csearch_path={nom} -capplication_name={nom}"
    if not cles_etrangeres:
        options += " -csession_replication_role=replica"
    return make_url(url).update_query_dict({"options": options})


#: Tables retirées ou créées par instruction. 🔴 Un verrou se prend par table ET par
#: index, et se garde jusqu'à la fin de la TRANSACTION : `DROP SCHEMA … CASCADE` d'un
#: schéma de 94 tables en tenait 1 655 d'un coup, `create_all` dans une transaction
#: 1 465 — mesuré le 29/10/2026 (#2279). La table des verrous du serveur est PARTAGÉE
#: (`max_locks_per_transaction` × connexions = 6 400 par défaut) : quatre workers qui
#: retiraient un schéma au même instant l'épuisaient, « mémoire partagée épuisée ».
#: Dix tables par instruction, chacune dans sa transaction (AUTOCOMMIT) : ~170 verrous.
TABLES_PAR_LOT = 10


def par_lots(elements, taille: int = TABLES_PAR_LOT) -> list[list]:
    """`elements` coupés en lots de `taille` au plus, dans l'ordre. PURE."""
    elements = list(elements)
    return [elements[i : i + taille] for i in range(0, len(elements), taille)]


def instructions_de_retrait(nom: str, tables) -> list[str]:
    """Les instructions qui retirent le schéma `nom`, chacune à passer SEULE. PURE.

    Les tables d'abord, par lots (`CASCADE` : une clé qui pointe hors du lot tombe
    avec elle), puis le schéma — qui ne porte plus que ses types et ses séquences.
    """
    lots = [
        "DROP TABLE IF EXISTS " + ", ".join(f'"{nom}"."{t}"' for t in lot) + " CASCADE"
        for lot in par_lots(sorted(tables))
    ]
    return [*lots, f'DROP SCHEMA IF EXISTS "{nom}" CASCADE']


def _retirer_schema_en_lots(c, nom: str) -> None:
    """Retire `nom` par `instructions_de_retrait`. `c` DOIT être en AUTOCOMMIT : une
    seule transaction autour des lots rendrait la table des verrous à ce qu'elle était."""
    #  Une connexion restée ouverte bloquerait le retrait : 10 s, puis
    #  l'appelant apprend l'échec plutôt que de figer.
    c.execute(text("SET lock_timeout = '10s'"))
    tables = (
        c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = :s"), {"s": nom})
        .scalars()
        .all()
    )
    for instruction in instructions_de_retrait(nom, tables):
        c.execute(text(instruction))  # noqa: S608 — identifiants relus au catalogue


def retirer_schema(url, nom: str) -> None:
    """Retire le schéma `nom` et tout ce qu'il contient."""
    admin = _creer_moteur(url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        with admin.connect() as c:
            _retirer_schema_en_lots(c, nom)
    finally:
        admin.dispose()


def heure_du_schema_jetable(nom: str) -> datetime | None:
    """L'heure de création (UTC naïf) inscrite dans le nom d'un schéma jetable. PURE.

    `None` pour tout autre nom — un schéma qui n'est pas jetable, ou nommé avant
    que son nom ne porte son heure : on ne sait pas son âge, on n'y touche pas.
    """
    trouve = _NOM_SCHEMA_JETABLE.match(nom)
    if not trouve:
        return None
    try:
        return datetime.strptime(trouve.group(1), _FORMAT_HEURE_SCHEMA)
    except ValueError:
        return None


def schemas_jetables_a_retirer(
    schemas: dict[str, str | None],
    *,
    maintenant: datetime,
    plus_vieux_que: timedelta,
    tenus: set[str],
    hote: str,
    vivant: Callable[[int], bool],
) -> list[str]:
    """Les schémas jetables abandonnés, parmi `schemas` (nom → commentaire). PURE.

    - tenu par une connexion ouverte (`application_name`) : jamais ;
    - plus vieux que `plus_vieux_que` : abandonné (le plafond d'avant #2399) ;
    - créateur inscrit, sur CET hôte, et mort : abandonné, quel que soit son âge ;
    - créateur inconnu (nom d'avant, autre hôte, conteneur) : le plafond seul.
    Un schéma sans heure lisible n'est pas jetable : il reste.
    """
    a_retirer = []
    for nom, commentaire in schemas.items():
        heure = heure_du_schema_jetable(nom)
        if heure is None or nom in tenus:
            continue
        createur = _COMMENTAIRE_CREATEUR.match(commentaire or "")
        if heure < maintenant - plus_vieux_que or (
            createur and createur.group(2) == hote and not vivant(int(createur.group(1)))
        ):
            a_retirer.append(nom)
    return sorted(a_retirer)


def retirer_schemas_jetables_perimes(url, *, plus_vieux_que: timedelta) -> int:
    """Retire les schémas jetables abandonnés (`schemas_jetables_a_retirer`) ; rend leur nombre.

    Le geste qui borne ce qu'un processus interrompu laisse derrière lui. L'âge se
    mesure à l'heure du serveur qui a écrit le nom ; un schéma qu'une connexion
    retient encore (verrou au-delà de 10 s) est passé, pas attendu.
    """
    from app.utils.processus_vivant import processus_vivant

    admin = _creer_moteur(url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    retires = 0
    try:
        with admin.connect() as c:
            maintenant = _heure_du_serveur(c)
            schemas = dict(
                c.execute(
                    text("SELECT nspname, obj_description(oid, 'pg_namespace') FROM pg_namespace")
                ).all()
            )
            tenus = set(
                c.execute(
                    text(
                        "SELECT application_name FROM pg_stat_activity"
                        " WHERE datname = current_database() AND pid <> pg_backend_pid()"
                    )
                ).scalars()
            )
            for nom in schemas_jetables_a_retirer(
                schemas,
                maintenant=maintenant,
                plus_vieux_que=plus_vieux_que,
                tenus=tenus,
                hote=_hote(),
                vivant=processus_vivant,
            ):
                try:
                    _retirer_schema_en_lots(c, nom)  # nom relu au motif
                except DBAPIError:
                    continue
                retires += 1
    finally:
        admin.dispose()
    return retires


def schema_jetable(url, *, cles_etrangeres: bool = True) -> tuple[object, Callable[[], None]]:
    """Un moteur sur un SCHÉMA neuf du serveur de `url`, et le geste qui le retire.

    Le schéma est seul visible : le moteur voit une base vide, sans jamais
    toucher aux tables de la base qui sert.

    🔴 `NullPool` : une connexion se FERME dès qu'elle est rendue — sinon le
    retrait du schéma attendrait des connexions gardées par le pool.
    """
    nom = poser_schema(url)
    moteur = _creer_moteur(
        url_dans_schema(url, nom, cles_etrangeres=cles_etrangeres), poolclass=NullPool
    )

    def retirer() -> None:
        moteur.dispose()
        retirer_schema(url, nom)

    return moteur, retirer


@contextmanager
def base_jetable(url) -> Iterator[object]:
    """`schema_jetable` le temps d'un bloc : le schéma est retiré à la sortie, quoi qu'il arrive."""
    moteur, retirer = schema_jetable(url)
    try:
        yield moteur
    finally:
        retirer()


def _creer_moteur(url, **options):
    from sqlmodel import create_engine

    return create_engine(url, **options)


# ── Le jour et le mois d'une date, en SQL ────────────────────────────────────


def _en_texte(colonne, motif: str, decalage: str | None):
    if decalage:
        colonne = colonne + cast(literal(decalage), Interval)
    return func.to_char(colonne, motif, type_=String)


def jour(colonne, decalage: str | None = None):
    """Le jour d'un horodatage, « AAAA-MM-JJ » ; `decalage` : « +2 hours »."""
    return _en_texte(colonne, "YYYY-MM-DD", decalage)


def mois(colonne, decalage: str | None = None):
    """Le mois d'un horodatage, « AAAA-MM » ; `decalage` : « +2 hours »."""
    return _en_texte(colonne, "YYYY-MM", decalage)
