import logging
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlmodel import create_engine, Session, SQLModel
from app.contexte import de_la_configuration

logger = logging.getLogger("hostachy.db")


def creer_moteur(url: str):
    """Le moteur d'UNE base, réglé comme la production (#1746).

    `engine` ci-dessous est celui de l'unique copropriété ; `contexte.moteur()`
    l'appelle aussi pour une autre copropriété — une seule recette, jamais deux
    bases réglées différemment.
    """
    return create_engine(
        url,
        echo=False,
        pool_pre_ping=True,  # Teste chaque connexion avant usage : un serveur redémarré ne laisse pas de connexion morte
    )


#  Le moteur de l'UNIQUE copropriété de la phase 2 : son URL vient du contexte (#1744), jamais
#  de `settings`. Ce module le construit ; le reste de l'application le demande à
#  `contexte.moteur()` / `contexte.nouvelle_session()` — 🔒 test_contexte_source_unique.
engine = creer_moteur(de_la_configuration().url_base)


def get_session():
    """Dépendance FastAPI : session DB avec auto-reconnexion sur OperationalError.

    Si SQLAlchemy perd le serveur (redémarrage, connexion coupée), on purge le
    pool avant de propager l'exception — qui sera capturée par le handler global
    dans main.py.
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
    _run_category_migrations()
