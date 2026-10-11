import logging
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError
from sqlmodel import create_engine, Session, SQLModel
from app.contexte import courante
from app.dialecte import (
    activer_cles_etrangeres,
    cles_suspendues,
    est_fichier,
    options_connexion,
    regler_moteur,
)

logger = logging.getLogger("hostachy.db")


def creer_moteur(url: str):
    """Le moteur d'UNE base, réglé comme la production (#1746).

    `engine` ci-dessous est celui de l'unique copropriété ; `contexte.moteur()`
    l'appelle aussi pour une autre copropriété — une seule recette, jamais deux
    bases réglées différemment.
    """
    moteur = create_engine(
        url,
        connect_args=options_connexion(url),
        echo=False,
        pool_pre_ping=True,  # Teste chaque connexion avant usage → détecte les inodes orphelins (ex: post-VACUUM)
    )

    #  🔴 LES CLÉS ÉTRANGÈRES SONT ACTIVES — 30/08/2026, fin de #546. Les trois
    #  conditions qui l'ont permis sont dans le docstring ci-dessus.
    #
    #  ⚠️ **CET APPEL EST AVANT LE BLOC D'AMORÇAGE, ET C'EST NÉCESSAIRE.** Placé
    #  après, il ne prenait pas effet — mesuré, pas supposé :
    #
    #      appel APRÈS l'amorçage   → PRAGMA foreign_keys = 0
    #      appel AVANT l'amorçage   → PRAGMA foreign_keys = 1
    #
    #  L'écouteur ne s'exécute qu'à l'ouverture d'une connexion. Le bloc d'amorçage
    #  en ouvre une avant lui ; le `engine.dispose()` de la fonction devrait la
    #  recycler, et ne suffit pas ici. Poser l'écouteur en premier garantit que
    #  **toute** connexion l'obtient, quel que soit le pool.
    #
    #  C'est le piège que le docstring de la fonction décrit — « un écouteur
    #  enregistré six lignes trop bas laisse le relevé dire foreign_keys = 0 » — et
    #  je l'ai refait en la branchant. Il ne se voit qu'en LISANT le PRAGMA sur une
    #  connexion réelle : l'appel est là, la fonction est juste, et le réglage
    #  n'est pas posé.
    #
    #  ⚠️ Vérifié aussi : `synchronous=FULL` et `busy_timeout=5000`, posés par le
    #  bloc ci-dessous, **survivent** au `dispose()` de la fonction (mesurés à 2 et
    #  5000 sur deux connexions successives). La durabilité choisie après les
    #  corruptions de juin n'est pas perdue.
    activer_cles_etrangeres(moteur)

    #  Durabilité de la base-fichier (WAL, synchronous=FULL, busy_timeout) : le
    #  pourquoi de chaque réglage est dans `dialecte.regler_moteur`.
    regler_moteur(moteur)
    return moteur


#  Le moteur de l'UNIQUE copropriété de la phase 2 : son URL vient du contexte (#1744), jamais
#  de `settings`. Ce module le construit ; le reste de l'application le demande à
#  `contexte.moteur()` / `contexte.nouvelle_session()` — 🔒 test_contexte_source_unique.
engine = creer_moteur(courante().url_base)


def get_session():
    """Dépendance FastAPI : session DB avec auto-reconnexion sur OperationalError.

    Si SQLAlchemy détecte un I/O error (pool corrompu, inode obsolète après VACUUM
    ou docker exec concurrent), on purge le pool et on retente une fois avant
    de propager l'exception — qui sera capturée par le handler global dans main.py.
    """
    #  Le moteur de la copropriété que la requête sert (#1746) : posée à l'entrée
    #  par `contexte.ResolutionCopropriete`.
    from app import contexte

    moteur = contexte.moteur()
    try:
        with Session(moteur) as session:
            yield session
    except OperationalError as exc:
        logger.error("DB OperationalError — purge du pool et reconnexion : %s", exc)
        moteur.dispose()  # ferme toutes les connexions, force fresh connections
        # La requête en cours échoue proprement ; le prochain appel repartira sain
        raise


def _run_migrations():
    """Migrations manuelles d'une base-fichier, pour les colonnes ajoutées avant Alembic.

    Une base SERVEUR n'a pas ce passé : son schéma est posé d'un coup par la
    migration initiale (`utils/schema_initial`, #1747), jamais rattrapé ici.
    """
    from app import contexte

    moteur = contexte.moteur()
    if not est_fichier(moteur):
        return
    simple_migrations = [
        "ALTER TABLE utilisateur ADD COLUMN batiment_id INTEGER REFERENCES batiment(id)",
        # Colonnes ajoutées au modèle Ticket sans migration Alembic correspondante
        "ALTER TABLE ticket ADD COLUMN batiment_id INTEGER REFERENCES batiment(id)",
        "ALTER TABLE ticket ADD COLUMN mis_a_jour_le DATETIME",
        "ALTER TABLE ticket ADD COLUMN perimetre_cible TEXT DEFAULT '[\"résidence\"]'",
        # Colonne cree_le de MessageTicket si manquante
        "ALTER TABLE message_ticket ADD COLUMN cree_le DATETIME",
        # Rôles visuels annuaire CS
        "ALTER TABLE membre_cs ADD COLUMN est_gestionnaire_site BOOLEAN DEFAULT 0",
        "ALTER TABLE membre_cs ADD COLUMN est_president BOOLEAN DEFAULT 0",
    ]
    with moteur.connect() as conn:
        for sql in simple_migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # colonne déjà présente

        # Normalisation des valeurs d'enum ticket (anciennes valeurs sans accents)
        #  `ferme` visait `fermé` jusqu'au 17/08/2026 — donc vers une valeur que
        #  l'énumération ne porte plus (#415, migration 0149). Cette ligne aurait
        #  ressuscité l'état supprimé à chaque démarrage : elle vise `résolu`,
        #  comme la migration.
        data_migrations = [
            "UPDATE ticket SET statut = 'résolu' WHERE statut = 'ferme'",
            "UPDATE ticket SET statut = 'résolu' WHERE statut = 'resolu'",
            "UPDATE ticket SET statut = 'ouvert' WHERE statut = 'nouveau'",
            "UPDATE ticket SET statut = 'ouvert' WHERE statut = 'en_attente'",
        ]
        for sql in data_migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass

        # Migration : rendre lot.batiment_id nullable (parkings sans bâtiment)
        # SQLite ne supporte pas ALTER COLUMN → recréation de la table
        try:
            colonnes = {c["name"]: c for c in inspect(conn).get_columns("lot")}
            if "batiment_id" in colonnes:
                # Recréer si la colonne est encore NOT NULL
                if not colonnes["batiment_id"]["nullable"]:
                    with cles_suspendues(conn):
                        conn.execute(
                            text("""
                            CREATE TABLE lot_migration_tmp (
                                id INTEGER PRIMARY KEY,
                                batiment_id INTEGER REFERENCES batiment(id),
                                numero TEXT NOT NULL,
                                type TEXT NOT NULL DEFAULT 'appartement',
                                type_appartement TEXT,
                                etage INTEGER,
                                superficie REAL
                            )
                        """)
                        )
                        conn.execute(
                            text(
                                "INSERT INTO lot_migration_tmp "
                                "SELECT id, batiment_id, numero, type, type_appartement, etage, superficie FROM lot"
                            )
                        )
                        conn.execute(text("DROP TABLE lot"))
                        conn.execute(text("ALTER TABLE lot_migration_tmp RENAME TO lot"))
                        conn.commit()
        except Exception:
            pass  # déjà migré ou erreur non bloquante


def _run_category_migrations():
    """Met à jour les catégories de documents existantes pour aligner les droits."""
    from app import contexte

    with contexte.moteur().connect() as conn:
        try:
            # Supprimer la catégorie Budget / Comptes annuels
            conn.execute(text("DELETE FROM categorie_document WHERE code = 'budget_comptes'"))
            # PV AG : copropriétaires_et_cs + bâtiment
            conn.execute(
                text("""
                UPDATE categorie_document
                SET profil_acces_id = (SELECT id FROM profil_acces_document WHERE code = 'copropriétaires_et_cs'),
                    perimetre_defaut = 'bâtiment',
                    surcharge_autorisee = 1
                WHERE code = 'pv_ag'
            """)
            )
            # Diagnostic : copropriétaires_et_cs + bâtiment (était lot_occupants + lot)
            conn.execute(
                text("""
                UPDATE categorie_document
                SET libelle = 'Diagnostic',
                    profil_acces_id = (SELECT id FROM profil_acces_document WHERE code = 'copropriétaires_et_cs'),
                    perimetre_defaut = 'bâtiment',
                    surcharge_autorisee = 1
                WHERE code = 'diagnostic_lot'
            """)
            )
            # Contrat fournisseur : périmètre bâtiment (était résidence)
            conn.execute(
                text("""
                UPDATE categorie_document
                SET perimetre_defaut = 'bâtiment',
                    surcharge_autorisee = 1
                WHERE code = 'contrat_fournisseur'
            """)
            )
            conn.commit()
        except Exception:
            pass


def create_db_and_tables():
    #  Dans la base de la copropriété servie (#1746), jamais dans celle par défaut.
    from app import contexte

    SQLModel.metadata.create_all(contexte.moteur())
    _run_migrations()
    _run_category_migrations()
