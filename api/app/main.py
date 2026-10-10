"""
CoproFirst — Application de gestion de copropriétés
API FastAPI v0.1
"""

import logging as _logging
import os as _os
import traceback as _traceback
from contextlib import asynccontextmanager
from app.utils import horloge

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.exc import OperationalError as _SAOperationalError

from app.utils.limiter import limiter

#  🔴 SANS CETTE LIGNE, TOUT `logger.info` DE L'APPLICATION DISPARAÎT (05/09/2026).
#
#  Uvicorn ne configure QUE ses propres journaux (`uvicorn`, `uvicorn.access`,
#  `uvicorn.error`). Un `logging.getLogger(__name__)` applicatif remonte au logger
#  RACINE, qui n'a aucun destinataire : Python se rabat alors sur son handler de
#  dernier recours, lequel n'émet qu'à partir de WARNING. Conséquence : tous les
#  `info` du produit — relève des réponses, checkpoint WAL, sauvegardes
#  orphelines, envois d'e-mails — n'étaient écrits NULLE PART.
#
#  On l'a payé deux fois sur le même sujet : #747 a ajouté un battement à la
#  relève des courriels pour répondre à « est-ce que ça tourne ? », puis on l'a
#  fait passer de `debug` à `info` le 05/09 — les deux invisibles. Le défaut
#  n'était pas le niveau choisi, c'était qu'aucun niveau ne sortait.
#
#  ⚠️ `basicConfig` ne touche que le logger racine : les journaux d'uvicorn ont
#  leurs propres handlers et ne se propagent pas, donc rien n'est dupliqué.
_logging.basicConfig(
    level=_os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

_logger = _logging.getLogger("hostachy.api")


from app.utils.reponse_utc import UTCJSONResponse

from app.database import _run_migrations
from app import contexte
from app.routers import (
    auth,
    auth_mot_de_passe,
    auth_profil,
    auth_telemetrie,
    tickets,
    publications,
    documents,
    lots,
    admin,
    notifications,
    acces,
    calendrier,
    prestataires,
    prestataires_archivage,
    prestataires_metriques,
    compteurs,
    sondages,
    idees,
    copropriete,
    copropriete_patrimoine,
    carnet,
    bailleur,
    config,
    diagnostics,
    annonces,
    regles_residence,
    delegations,
    telemetry,
    telemetry_collecte,
    flux,
)
from app.routers import uploads, faq, signalements, annonces_hall, patrimoine
from app.routers import manuel
from app.routers import courriels_affaires
from app.routers import partage
from app.routers import assistant, config_llm, config_logo, config_services, reglement
from app.seed import seed
from app.utils.backup import setup_scheduler
from app.utils.plateforme import NOM_PLATEFORME


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialisation au démarrage
    # Note : la création des tables est gérée par Alembic (start.sh)
    # _run_migrations() gère uniquement les migrations manuelles SQLite (ALTER TABLE)
    _run_migrations()
    seed()

    # Purge des refresh tokens — les échangés restent jusqu'à leur expiration,
    # c'est par eux qu'un jeton rejoué se reconnaît (`auth/jetons_rafraichissement`).
    from app.auth.jetons_rafraichissement import purger as purger_jetons

    with contexte.nouvelle_session() as _s:
        purger_jetons(_s, horloge.maintenant())
        _s.commit()

    # Nettoyage des sauvegardes orphelines restées "en_cours" suite à un
    # redémarrage/arrêt du conteneur en plein milieu du job (faussait le
    # contrôle de santé "dernière sauvegarde réussie")
    from datetime import timedelta as _timedelta
    from sqlmodel import select as _select
    from app.models.core import HistoriqueSauvegarde, StatutSauvegarde

    with contexte.nouvelle_session() as _s:
        _seuil = horloge.maintenant() - _timedelta(hours=2)
        _orphelines = _s.exec(
            _select(HistoriqueSauvegarde).where(
                (HistoriqueSauvegarde.statut == StatutSauvegarde.en_cours)
                & (HistoriqueSauvegarde.cree_le < _seuil)
            )
        ).all()
        for _b in _orphelines:
            _b.statut = StatutSauvegarde.echouee
            _b.message_erreur = "Interrompue par redémarrage du conteneur"
            _b.terminee_le = horloge.maintenant()
            _s.add(_b)
        if _orphelines:
            _s.commit()
            _logger.info(
                "Sauvegardes orphelines nettoyées : %d marquée(s) en échec.", len(_orphelines)
            )

    scheduler = setup_scheduler()

    #  🏢 CHAQUE TÂCHE TRAVAILLE POUR UNE COPROPRIÉTÉ (#1745, spec §4.6) : elle
    #  s'enregistre enveloppée par `pour_chaque_copropriete`, qui la joue dans le
    #  contexte de chacune, journalise chaque passage et isole l'échec de l'une.
    #  Une tâche de la plateforme se déclare dans `taches.TACHES_DE_LA_PLATEFORME`.

    # Planificateur WhatsApp : fenêtre de rattrapage 18h00 → 21h45 (toutes les
    # 15 min) au lieu d'une tentative unique à 18h00 pile — cf. incident du
    # 24/07/2026 (bridge indisponible à 18h00, message mensuel perdu).
    # La dédup dans whatsapp_scheduler.check_and_send() rend les tentatives
    # répétées sûres (aucun risque de doublon).
    from app.utils.whatsapp_scheduler import check_and_send as _wa_check

    scheduler.add_job(
        contexte.pour_chaque_copropriete(_wa_check, "whatsapp_scheduled"),
        "cron",
        hour="18-21",
        minute="*/15",
        id="whatsapp_scheduled",
    )

    # Agrégation télémétrie : chaque nuit à 2h
    from app.utils.telemetry_aggregation import run_telemetry_aggregation_cron

    scheduler.add_job(
        contexte.pour_chaque_copropriete(run_telemetry_aggregation_cron, "telemetry_aggregation"),
        "cron",
        hour=2,
        minute=0,
        id="telemetry_aggregation",
    )

    #  🔴 LES RATTRAPAGES — et ils ne concernent PLUS que la télémétrie (#876).
    #
    #  Un `cron` d'APScheduler tient ses jobs en MÉMOIRE : un créneau franchi
    #  pendant un arrêt n'est pas rejoué, et le prochain se calcule à partir de
    #  l'instant d'ajout. Le 10/09/2026, un déploiement a redémarré la pile et le
    #  planificateur est reparti à 02:00:13 — treize secondes après le créneau.
    #
    #  ⚠️ Ce commentaire disait déjà, le matin même, que le sujet « ne concerne
    #  pas que la télémétrie » — et le correctif ne couvrait qu'elle. La règle,
    #  la liste des tâches couvertes et surtout le MOTIF des deux qui ne le sont
    #  pas (contrôle santé, WhatsApp) vivent désormais dans `utils/rattrapage.py`,
    #  écrits une seule fois.
    from app.utils.rattrapage import planifier_rattrapages

    planifier_rattrapages(scheduler)

    #  🔴 PRÉCHAUFFAGE DU MANUEL EN PDF (18/09/2026, demandé par Philippe).
    #
    #  Un déploiement qui MODIFIE le manuel change la clé du cache — mémoire et
    #  disque (#1071) — et le premier lecteur d'après payait le rendu complet :
    #  **21,1 s mesurées en production**, contre 0,15 s ensuite. Personne n'a à
    #  attendre cela pour ouvrir un manuel.
    #
    #  Deux déclenchements, et le second n'est pas un luxe : la clé du cache
    #  porte la DATE d'édition, donc le premier lecteur de chaque jour repaierait
    #  les 21 s sans le rendez-vous de 00:05.
    #
    #  ⚠️ En ARRIÈRE-PLAN, jamais dans le démarrage : l'API doit répondre tout de
    #  suite, et le rendu s'exécute de toute façon dans un autre process
    #  (`utils/pdf_rendu`). Un échec ne remonte pas — `prechauffer` ne lève
    #  jamais, il journalise.
    def _prechauffer_manuel() -> None:
        from app.utils.manuel_pdf import identite_du_manuel, prechauffer

        with contexte.nouvelle_session() as _s:
            identite = identite_du_manuel(_s)
        prechauffer(**identite)

    scheduler.add_job(
        contexte.pour_chaque_copropriete(_prechauffer_manuel, "manuel_pdf_prechauffage"),
        "date",
        #  Conscient, donc indépendant du fuseau du planificateur (#1565).
        run_date=horloge.a_paris(horloge.maintenant()) + _timedelta(seconds=20),
        id="manuel_pdf_prechauffage",
    )
    scheduler.add_job(
        contexte.pour_chaque_copropriete(_prechauffer_manuel, "manuel_pdf_quotidien"),
        "cron",
        hour=0,
        minute=5,
        id="manuel_pdf_quotidien",
    )

    # Contrôle santé quotidien : WhatsApp, sauvegardes, disque (06h00)
    from app.utils.health_monitor import run_health_check

    scheduler.add_job(
        contexte.pour_chaque_copropriete(run_health_check, "health_check"),
        "cron",
        hour=6,
        minute=0,
        id="health_check",
    )

    #  Réponses par courriel aux tickets (#703). Toutes les 10 minutes : assez
    #  souvent pour qu'une réponse du syndic paraisse « immédiate » dans le fil,
    #  assez rare pour ne pas marteler la boîte IMAP.
    #
    #  ⚠️ `relever()` ne lève jamais — voir sa docstring : une exception ici
    #  tuerait le job pour de bon, et la relève s'arrêterait en silence. Elle
    #  rend un compte, qu'elle journalise.
    #
    #  Rien ne tourne tant que `imap_enabled` n'est pas posé en administration :
    #  la fonction sort immédiatement.
    from app.utils.courriel_boite import relever as _relever_reponses

    scheduler.add_job(
        contexte.pour_chaque_copropriete(_relever_reponses, "courriel_reponses"),
        "interval",
        minutes=10,
        id="courriel_reponses",
    )

    #  La synthèse d'une affaire close (#1643) : la file se vide toutes les 10
    #  minutes, chaque demande attendant 30 min après la clôture. `traiter_file`
    #  ne lève jamais, et laisse une trace à chaque passage.
    from app.utils.synthese_affaire.file import traiter_file as _syntheses

    scheduler.add_job(
        contexte.pour_chaque_copropriete(_syntheses, "synthese_affaires"),
        "interval",
        minutes=10,
        id="synthese_affaires",
    )

    #  La purge des comptes inactifs (#1580) : chaque jour à 04:30, après la
    #  sauvegarde de la nuit (03:00 par défaut). Elle avertit, puis supprime trente jours plus tard ;
    #  un passage manqué décale d'un jour, dans le sens de la conservation.
    #  `purger_comptes_inactifs` ne lève jamais et laisse une trace à chaque passage.
    from app.utils.purge_comptes.tache import purger_comptes_inactifs as _purge_comptes

    scheduler.add_job(
        contexte.pour_chaque_copropriete(_purge_comptes, "purge_comptes_inactifs"),
        "cron",
        hour=4,
        minute=30,
        id="purge_comptes_inactifs",
    )

    #  🔴 Ce qui tourne VRAIMENT est comparé à ce qui est déclaré (#1047). Un
    #  `add_job` supprimé par mégarde — refactor, fusion, condition mal placée —
    #  laissait jusqu'ici l'application démarrer normalement : la sauvegarde ne se
    #  faisait plus, et on l'apprenait le jour d'une restauration.
    #
    #  L'analyse statique de la CI ne suffit pas : elle voit l'appel dans le code,
    #  pas le fait qu'une condition l'ait sauté. Ce contrôle-ci lit le scheduler.
    from app.utils.taches import verifier_taches_enregistrees

    verifier_taches_enregistrees(scheduler, _logging.getLogger("taches"))

    yield
    # Nettoyage à l'arrêt
    scheduler.shutdown()

    # WAL checkpoint au shutdown : vide le fichier .db-wal avant que Docker tue le process.
    # Sans ça, si un job APScheduler est interrompu par SIGTERM, le WAL reste dans un état
    # intermédiaire → "database disk image is malformed" au prochain démarrage.
    try:
        from app.dialecte import point_de_controle

        with contexte.moteur().connect() as _conn:
            point_de_controle(_conn)
            _conn.commit()
        _logger.info("WAL checkpoint effectué au shutdown.")
    except Exception as _e:
        _logger.warning("WAL checkpoint échoué au shutdown (non bloquant) : %s", _e)


import os as _os

_enable_docs = _os.getenv("ENABLE_API_DOCS", "false").lower() == "true"

#  Version du CONTRAT de l'API, délibérément distincte de celle de l'application
#  (`front/package.json`). Elle était écrite en dur à deux endroits — ici et dans
#  la réponse de `/health` — donc rien ne garantissait qu'ils restent d'accord.
#
#  ⚠️ Ne pas la faire pointer vers la version applicative : `/health` est PUBLIC et
#  non authentifié, la rendre exacte divulguerait la version déployée sans qu'aucun
#  besoin ne l'impose. Le post-check lit la version servie dans le bundle du front,
#  ce qui n'expose rien de plus (décision du 03/08/2026, cf. la skill mep-precheck).
#  Aucun script d'infra ne consomme ce champ — vérifié le 06/08/2026.
API_VERSION = "0.2.0"

app = FastAPI(
    title=f"{NOM_PLATEFORME} API",
    description="API de gestion de copropriétés",
    version=API_VERSION,
    lifespan=lifespan,
    default_response_class=UTCJSONResponse,
    docs_url="/docs" if _enable_docs else None,
    redoc_url="/redoc" if _enable_docs else None,
    #  ⚠️ Le SCHÉMA aussi, pas seulement les deux pages qui l'affichent.
    #  Jusqu'au 08/08/2026 seuls `docs_url` et `redoc_url` étaient fermés :
    #  `openapi_url` gardait sa valeur par défaut, et `/api/openapi.json`
    #  répondait 200 en production. Le document rend l'intégralité de la surface
    #  — 279 routes, leurs paramètres, et tous les modèles avec leurs noms de
    #  champs. Ce n'est pas une ouverture d'accès : les autorisations restaient
    #  intactes. C'est une divulgation de surface d'attaque, qui épargne à un
    #  attaquant tout le travail d'énumération.
    #
    #  Le défaut n'était pas dans le réglage mais dans sa PORTÉE : son nom
    #  (`ENABLE_API_DOCS`) promettait de fermer la documentation, il n'en fermait
    #  que l'affichage. Un réglage doit couvrir tout ce que son nom annonce.
    openapi_url="/openapi.json" if _enable_docs else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ── Gestionnaires d'erreurs globaux ──────────────────────────────────────────


@app.exception_handler(_SAOperationalError)
async def db_operational_error_handler(request: Request, exc: _SAOperationalError):
    """SQLite I/O error, DB locked, pool corrompu → 503 avec log structuré.
    Le pool est purgé ici pour que la prochaine requête reparte sur une connexion saine.
    """

    contexte.moteur().dispose()
    _logger.error(
        "DB OperationalError sur %s %s — pool purgé : %s",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Base de données temporairement indisponible. Veuillez réessayer."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Filet de sécurité : toute exception non gérée → 500 loggué, jamais de crash silencieux."""
    _logger.error(
        "Exception non gérée sur %s %s :\n%s",
        request.method,
        request.url.path,
        _traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Erreur interne du serveur."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://localhost"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Routeurs
app.include_router(auth.router)
#  Même préfixe `/auth`, monté à part : FastAPI additionne les routers, les URL
#  publiques sont donc inchangées (cf. en-tête de `routers/auth_mot_de_passe.py`).
app.include_router(auth_mot_de_passe.router)
#  Idem pour le bloc PROFIL, sorti d'`auth.py` le 09/09/2026 (cf. son en-tête) :
#  même préfixe `/auth`, donc mêmes URL publiques.
app.include_router(auth_profil.router)
#  Idem pour les trois routes RGPD sur la télémétrie, sorties d'`auth.py` le
#  08/09/2026 : elles ne parlent pas d'authentification, seulement d'une donnée
#  que le site collecte.
app.include_router(auth_telemetrie.router)
app.include_router(lots.router)
app.include_router(tickets.router)
app.include_router(partage.router)  # 🔗 → courriel (#1357)
app.include_router(publications.router)
app.include_router(documents.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(acces.router)
#  Le calendrier n'est plus qu'une REDIRECTION des anciens liens (#1092, lot 5) :
#  ses événements sont des affaires, son historique et son aperçu sont partis.
app.include_router(calendrier.router)
app.include_router(prestataires.router)
#  Même préfixe : les relevés de compteurs sont sortis de `prestataires.py`
#  (modularité, 29/08/2026), pas de l'API — les chemins n'ont pas bougé.
app.include_router(compteurs.router)
#  Le geste 📦 des prestataires et des contrats (#1538), même préfixe aussi.
app.include_router(prestataires_archivage.router)
#  Les métriques des affaires d'un prestataire (#1646), même préfixe.
app.include_router(prestataires_metriques.router)
#  Les routeurs sans particularité de montage : un `include_router` chacun.
for _routeur in (sondages, idees, annonces, annonces_hall, courriels_affaires, manuel):
    app.include_router(_routeur.router)
app.include_router(copropriete.router)
#  Les bâtiments et les lots — extraits le 22/09/2026 (modularité, rang 1). Même
#  préfixe `/copropriete`, donc mêmes URL publiques (cf. son en-tête).
app.include_router(copropriete_patrimoine.router)
#  Le carnet d'entretien : une VUE sur les contrats, les interventions et les
#  tickets clos. Router à part parce que `copropriete.py` était à 478 lignes.
app.include_router(carnet.router)
app.include_router(uploads.router)
app.include_router(faq.router)
app.include_router(bailleur.router)
app.include_router(config.router)
#  Même préfixe `/config` : l'assistant IA de l'administration (#984).
app.include_router(config_llm.router)
app.include_router(config_services.router)
app.include_router(config_logo.router)
app.include_router(diagnostics.router)
app.include_router(regles_residence.router)
app.include_router(delegations.router)
app.include_router(telemetry.router)
app.include_router(telemetry_collecte.router)
app.include_router(flux.router)
app.include_router(signalements.router)
app.include_router(patrimoine.router)
#  L'assistant IA des formulaires (#985) : retravailler une description.
app.include_router(assistant.router)
app.include_router(reglement.router)

# Fichiers statiques (photos uploadées)
#  `UPLOADS_DIR` plutôt qu'un chemin figé : le motif existe déjà dans
#  `routers/documents.py` et `utils/fichiers.py`, donc on l'applique à
#  l'identique (CLAUDE.md — un pattern présent ≥ 2 fois fait loi). En
#  production rien ne change, la variable n'étant pas définie.
#  Ce qu'il débloque : importer `app.main` hors conteneur. Le `mkdir` d'un
#  chemin absolu échouait sur un poste de développement et sur un exécuteur
#  d'intégration continue — ce qui rendait l'application intestable dans son
#  ensemble, et laissait passer toute rupture d'assemblage (cf.
#  tests/test_demarrage.py).
uploads_dir = contexte.courante().racine_fichiers
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.get("/health", tags=["system"])
def health():
    """Health check : vérifie aussi la disponibilité de la DB.

    Retourne 503 si la DB est inaccessible. C'est la sonde sur laquelle quatre
    scripts d'exploitation décident — `bascule.sh`, `boot-role-guard.sh`,
    `health-watch.sh` et `check-reliability.sh` interrogent tous `/api/health` —
    donc **un 200 ici autorise un basculement de production**.
    (La docstring nommait `check-stack.sh`, supprimé le 20/09/2026 : elle
    désignait le seul appelant qui ne décidait de rien.)
    """
    from sqlmodel import text as _text

    try:
        with contexte.nouvelle_session() as _s:
            _s.exec(_text("SELECT 1"))  # type: ignore[arg-type]
        return {"status": "ok", "version": API_VERSION}
    except Exception as exc:
        _logger.error("Health check DB failed : %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "db_unavailable", "detail": "Base de données indisponible"},
        )
