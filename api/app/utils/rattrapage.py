"""Rattraper une tâche planifiée dont le créneau est passé pendant un arrêt.

## L'incident fondateur (10/09/2026, #876)

Le déploiement de 01:58 a redémarré la pile ; le planificateur est reparti à
**02:00:13**, soit treize secondes après le créneau de l'agrégation télémétrie.
APScheduler tient ses jobs en **mémoire** : au redémarrage, il ne sait pas qu'un
passage a été manqué, et calcule le suivant à partir de l'instant d'ajout.
L'agrégation du 10 septembre n'a pas eu lieu, et la suivante était prévue le 11.

🔴 **Ce n'était pas un hasard.** `auto-deploy.sh` tourne toutes les cinq minutes,
et `bascule.sh` redémarre la pile **à 02:00 précises** en cron root — la même
minute que ce job. La collision est structurelle.

## Pourquoi ce module existe séparément

Le premier correctif (10/09, matin) ne couvrait que la télémétrie, et son
commentaire dans `main.py` disait déjà, en toutes lettres, *« il ne concerne pas
que la télémétrie »*. C'est le motif que ce dépôt connaît le mieux : **le seul
fichier qui parle du sujet affirme que le problème est traité ailleurs aussi**.
Il ne l'était pas.

La règle est donc écrite **une fois**, ici, et chaque tâche rattrapable se
déclare dans `TACHES_RATTRAPABLES` — au lieu qu'une deuxième copie de
`rattrapage_necessaire` naisse à côté de la sauvegarde.

## Ce qui N'est PAS rattrapable, et pourquoi

Deux des quatre jobs APScheduler restent volontairement hors de la table, et
c'est une décision, pas un oubli :

| Job | Pourquoi pas |
|---|---|
| `health_check` (06:00) | **il n'enregistre rien**. Il journalise et alerte ; il n'existe aucun fait à interroger, donc rien qui puisse dire « le passage a été manqué ». Lui inventer une table pour le rattraper coûterait plus que le manque : une journée sans contrôle santé, c'est une alerte différée de 24 h, pas une donnée perdue. |
| `whatsapp_scheduled` (18h–21h45, toutes les 15 min) | sa **fenêtre est déjà son rattrapage** — seize créneaux, et une dédup qui lit le fait (#331). Le relancer au démarrage l'enverrait à n'importe quelle heure, alors que la fenêtre du soir est un choix : le message est fait pour être lu le soir. |

`courriel_reponses` est un `interval`, qui repart de zéro au démarrage : il n'a
jamais été concerné.
"""

from datetime import datetime, timedelta
from app.utils import horloge
import logging
from typing import Any, Callable, NamedTuple, Optional

logger = logging.getLogger(__name__)


def rattrapage_necessaire(
    derniere_reussite: Optional[datetime],
    maintenant: datetime,
    periode_h: int = 24,
) -> bool:
    """La tâche a-t-elle MANQUÉ un passage ?

    ## Pourquoi cette fonction plutôt que `misfire_grace_time`

    La grâce d'APScheduler couvre un retard **du processus vivant**, pas un
    arrêt : sans jobstore persistant, il n'y a rien à rattraper au démarrage.
    C'est donc le FAIT qu'on interroge — *quand la tâche a-t-elle réussi pour la
    dernière fois ?* — et non l'horaire. La même réponse couvre alors toutes les
    causes d'arrêt : mise en production, bascule, coupure de courant, panne.

    ⚠️ **Aucune trace du tout ⇒ on rattrape.** Base neuve ou tâche jamais passée,
    les deux méritent une première exécution — et elle est inoffensive.

    ⚠️ La comparaison porte sur la dernière **réussite**, pas sur la dernière
    tentative : une ligne en `erreur` prouve que la tâche a tourné, pas qu'elle a
    produit quoi que ce soit.
    """
    if derniere_reussite is None:
        return True
    return (maintenant - derniere_reussite) > timedelta(hours=periode_h)


def rattraper_si_manquee(
    libelle: str,
    derniere_reussite: Callable[[], Optional[datetime]],
    relancer: Callable[[], Any],
    periode_h: int = 24,
) -> Optional[Any]:
    """Relance `relancer()` si le dernier passage réussi est trop ancien.

    Appelée **au démarrage**, une fois par tâche. Rend `None` quand il n'y a rien
    à rattraper — et c'est le cas nominal, qu'on journalise quand même : un
    chemin muet est un chemin qu'on croit vivant (`standards/07`, le contrat de
    battement).

    ⚠️ Elle ne laisse **jamais** échapper d'exception. Ces appels sont des jobs
    APScheduler : une exception y tuerait le job sans tuer le démarrage, et le
    rattrapage s'arrêterait en silence — exactement le défaut qu'il corrige.
    """
    try:
        derniere = derniere_reussite()
    except Exception as exc:  # noqa: BLE001 — journalisé, jamais propagé
        logger.error(
            "%s : rattrapage impossible, lecture du dernier passage KO (%s).", libelle, exc
        )
        return None

    quand = derniere.isoformat() if derniere else "aucune"
    if not rattrapage_necessaire(derniere, horloge.maintenant(), periode_h):
        logger.info("%s : rien à rattraper (dernière réussite %s).", libelle, quand)
        return None

    logger.warning("%s : passage MANQUÉ (dernière réussite %s) — rattrapage.", libelle, quand)
    try:
        return relancer()
    except Exception as exc:  # noqa: BLE001
        logger.error("%s : le rattrapage a échoué (%s).", libelle, exc)
        return None


class TacheRattrapable(NamedTuple):
    """Une tâche planifiée dont un passage manqué se voit, et se rejoue."""

    libelle: str
    job_id: str
    #: Rend l'horodatage du dernier passage RÉUSSI, ou `None`.
    derniere_reussite: Callable[[], Optional[datetime]]
    #: Relance la tâche. Doit enregistrer son propre passage.
    relancer: Callable[[], Any]
    periode_h: int = 24


def taches_rattrapables() -> tuple[TacheRattrapable, ...]:
    """La table des tâches couvertes — imports différés (cycles au démarrage)."""

    from app import contexte
    from app.utils.backup import derniere_sauvegarde_reussie, run_backup
    from app.utils.telemetry_aggregation import (
        derniere_agregation_ou_rejeu,
        run_telemetry_aggregation_cron,
    )

    def _avec_session(lecture):
        def _lire():
            with contexte.nouvelle_session() as session:
                return lecture(session)

        return _lire

    return (
        TacheRattrapable(
            "Agrégation télémétrie",
            "telemetry_rattrapage",
            _avec_session(derniere_agregation_ou_rejeu),
            run_telemetry_aggregation_cron,
        ),
        TacheRattrapable(
            "Sauvegarde quotidienne",
            "backup_rattrapage",
            _avec_session(derniere_sauvegarde_reussie),
            run_backup,
        ),
    )


def identifiants_rattrapage() -> frozenset[str]:
    """Les identifiants de job que `planifier_rattrapages` pose — et eux seuls.

    Le contrôle des tâches planifiées (`utils/taches`) les exclut de ses écarts.
    Il le faisait par un motif recopié, `startswith("rattrapage")`, qui ne
    correspondait à aucun identifiant réel : deux WARNING « NON DECLAREE » à
    chaque démarrage (#1589). L'ensemble EXACT, lu dans la table, ne peut ni
    diverger d'elle ni avaler une tâche qu'un motif aurait reconnue.
    """
    return frozenset(tache.job_id for tache in taches_rattrapables())


def planifier_rattrapages(scheduler, differe_minutes: int = 1) -> list[str]:
    """Programme un rattrapage par tâche, peu après le démarrage.

    ⚠️ **Différé** : le démarrage doit rendre la main à Caddy avant qu'une
    agrégation ou une sauvegarde ne mobilise la base — le healthcheck n'attend
    pas. Une minute suffit, et rien ne presse : on rattrape un passage vieux de
    plus de vingt-quatre heures.
    """
    from functools import partial

    from app import contexte

    poses = []
    for tache in taches_rattrapables():
        scheduler.add_job(
            contexte.pour_chaque_copropriete(
                partial(
                    rattraper_si_manquee,
                    tache.libelle,
                    tache.derniere_reussite,
                    tache.relancer,
                    tache.periode_h,
                ),
                tache.job_id,
            ),
            "date",
            #  Instant CONSCIENT : un `run_date` naïf est lu dans le fuseau du
            #  planificateur (Paris) — y poser `horloge.maintenant()` (UTC naïf)
            #  le décalerait de deux heures sans un mot (#1565).
            run_date=horloge.a_paris(horloge.maintenant()) + timedelta(minutes=differe_minutes),
            id=tache.job_id,
        )
        poses.append(tache.job_id)
    logger.info("Rattrapages programmés (dans %d min) : %s", differe_minutes, ", ".join(poses))
    return poses
