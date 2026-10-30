"""Ce que l'application fait **toute seule** — la liste, et son contrôle.

## Pourquoi cette table (#1047, audit du 19/09/2026)

Sept tâches tournent en permanence dans le process de l'API, enregistrées à
**trois** endroits (`main.py`, `utils/backup.py`, et des tâches de rattrapage
dans `utils/rattrapage.py`). **Aucun test ne citait un seul identifiant** :
`test_taches_planifiees.py`, `test_sante_taches_forme.py` et `test_taches_sante.py`
vérifiaient des formes, jamais la liste.

Conséquence, et c'est la règle de `standards/07` §5 : **une tâche planifiée qui
disparaît ne prévient personne.** Un `add_job` supprimé par mégarde — dans un
refactor, une fusion, un `if` mal placé — laisse l'application démarrer
normalement. La sauvegarde ne se fait plus, la relève des courriels s'arrête, et
on l'apprend le jour où l'on en a besoin.

C'est déjà arrivé au voisinage : la skill `infra-rpi` en listait **quatre sur
six**, parce que personne ne pouvait comparer sa table à la réalité.

## Ce que cette table sert — deux fois, et c'est le point

1. **Au démarrage** (`main.py`), les identifiants réellement enregistrés lui sont
   comparés, et tout écart part en `WARNING` : c'est le seul contrôle qui parle
   de ce qui tourne **vraiment**, dans le process, avec sa configuration.
2. **En CI** (`test_taches_planifiees_declarees.py`), chaque identifiant déclaré
   doit correspondre à un `add_job` du code, et réciproquement — ce qui attrape
   la disparition **avant** le déploiement.

Un seul des deux ne suffirait pas : le test statique ne voit pas un `add_job`
qu'une condition saute à l'exécution, et le contrôle au démarrage ne se lit que
si quelqu'un regarde les journaux.

⚠️ Les tâches de **rattrapage** (`utils/rattrapage.py`) n'y figurent pas : elles
sont de type `date`, posées à chaque démarrage et retirées du planificateur une
fois jouées — ce ne sont pas des tâches permanentes. Le contrôle les exclut par
leur identifiant EXACT, lu dans `rattrapage.identifiants_rattrapage()`, jamais
par un motif : le motif recopié ici (`startswith("rattrapage")`) ne reconnaissait
aucun identifiant réel (`telemetry_rattrapage`, `backup_rattrapage`), et chaque
démarrage journalisait deux faux écarts (#1589).
"""

from app.utils.rattrapage import identifiants_rattrapage

#: Les tâches permanentes, par identifiant — et ce que leur disparition coûte.
#:
#: Le second membre n'est pas une description : c'est **ce qu'on perd** si elle
#: cesse de tourner. C'est ce qui permet de trancher, en cas d'écart, s'il faut
#: intervenir tout de suite ou au prochain lot.
TACHES_PERMANENTES: dict[str, str] = {
    "backup": "la sauvegarde quotidienne de la base — sans elle, plus aucune copie "
    "n'est produite, et on l'apprend le jour d'une restauration",
    "health_check": "le contrôle de santé de 06:00, seul job qui envoie une alerte "
    "de lui-même (WhatsApp déconnecté, sauvegarde > 25 h, disque < 15 %)",
    "whatsapp_scheduled": "la fenêtre d'envoi WhatsApp de 18 h à 21 h 45 — les "
    "messages programmés ne partent plus",
    "telemetry_aggregation": "l'agrégation de la télémétrie à 02:00 ; sans elle, "
    "la table brute gonfle et les écrans de mesure se vident",
    "manuel_pdf_prechauffage": "le rendu du manuel 20 s après le démarrage — sans "
    "lui, le premier lecteur d'après un manuel modifié attend 21 s",
    "manuel_pdf_quotidien": "le même rendu à 00:05, parce que la clé du cache porte "
    "la date : sans lui, le premier lecteur du jour repaie l'attente",
    "courriel_reponses": "la relève IMAP toutes les 10 minutes — les réponses du "
    "syndic par courriel n'entrent plus dans les tickets",
    "synthese_affaires": "la file des synthèses d'affaires closes, toutes les 10 minutes "
    "(#1643) — les affaires du carnet se closent sans synthèse, et le conseil n'est pas "
    "avisé qu'il y en a une à relire",
    "desepinglage_affaires_closes": "le retrait horaire de l'épingle des affaires closes "
    "depuis 24 h (`utils/desepinglage`) — une affaire résolue ou annulée reste en tête de "
    "liste et dans le bandeau « Épinglé » jusqu'à ce que le conseil la désépingle",
    "validation_points_conseil": "la validation d'office, toutes les heures, du compte rendu "
    "d'un point CS / Syndic resté 7 jours sans réponse de tous les présents (#2042) — il reste "
    "« à valider » : ses comptes rendus ne paraissent ni dans les affaires ni au fil",
    "purge_comptes_inactifs": "la purge quotidienne des comptes inactifs (#1580) — plus "
    "aucun avertissement ni aucune suppression : la durée de conservation annoncée par la "
    "politique de confidentialité redevient fictive",
    "sante_plateforme": "le contrôle du disque à partir de la deuxième copropriété "
    "(#1814) — un disque plein n'est plus signalé par l'application ; seule "
    "l'infrastructure le voit encore (`check-reliability.sh`) — et celui de la copie "
    "hors site du registre (#1896) : son oubli ne prévient plus l'opérateur",
    "sauvegarde_plateforme": "la sauvegarde nocturne de la base `plateforme` (#1892) — le "
    "registre des installations n'a plus de copie vérifiée : une erreur répliquée sur les "
    "deux nœuds le perd",
    "bail_installation": "le renouvellement nocturne du bail de l'installation (#1878) — le "
    "bail échoit en 30 jours et l'installation se constate limitée, sans que l'opérateur "
    "soit prévenu",
    "conservation_registre": "l'effacement, à leur échéance, des coordonnées (12 mois) et du "
    "contrat archivé (5 ans) d'une installation résiliée — les durées promises par les "
    "conditions d'inscription (§4) redeviennent fictives",
    "canaux_registre": "la lecture des versions publiées dans le registre (#2210) — les "
    "baux portent alors une version cible figée, et aucune réplique ne reçoit de nouvelle "
    "version",
    "conservation_affaires": "l'archivage, à leur échéance, des pièces jointes des affaires "
    "closes et le détachement de leurs auteurs (#2014), puis le retrait du serveur des "
    "archives copiées sur le PC depuis 30 jours — les durées de conservation redeviennent "
    "fictives, et les archives s'accumulent sur les deux nœuds",
    "transcription_pv": "la transcription quotidienne des PV d'AG récents (29/10/2026) — le "
    "PV de l'année n'est plus proposé à la relecture : les questions au règlement ignorent "
    "ses décisions tant que personne ne le transcrit par le bouton",
}


#: Les tâches qui travaillent pour la PLATEFORME et non pour une copropriété, avec
#: leur raison (#1745, spec §4.6). Toutes les autres s'enregistrent enveloppées par
#: `contexte.pour_chaque_copropriete` : jouées dans le contexte de chaque
#: copropriété, un passage journalisé par copropriété, l'échec de l'une sans effet
#: sur les autres.
#:
#: Vide au 10/10/2026 : chacune des tâches d'aujourd'hui lit ou écrit la base d'une
#: copropriété (sa sauvegarde, sa télémétrie, sa boîte de réception, ses comptes…).
#: Le défaut va dans le sens de l'étanchéité : une tâche oubliée ici tourne PAR
#: copropriété, jamais pour toutes à la fois.
TACHES_DE_LA_PLATEFORME: dict[str, str] = {
    "sante_plateforme": "le disque du serveur et la copie hors site du registre, qui "
    "n'appartiennent à aucune copropriété : jugés une fois, à destination de "
    "l'opérateur (#1814, #1896)",
    "sauvegarde_plateforme": "la base `plateforme` (registre des installations), qui "
    "n'appartient à aucune copropriété (§4.11, règle 7) (#1892)",
    "bail_installation": "le bail de l'INSTALLATION auprès du registre, qui n'appartient à "
    "aucune copropriété (§4.11) (#1878)",
    "conservation_registre": "la base `plateforme` (registre des installations), qui "
    "n'appartient à aucune copropriété (§4.11, règle 7)",
    "canaux_registre": "les versions publiées du registre des installations, relues sur "
    "le dépôt public : elles n'appartiennent à aucune copropriété (§4.11, règle 6) (#2210)",
}


#: Les tâches RETIRÉES du planificateur dans la démo publique (spec `mode-demo.md`
#: §4.4, #1902), avec leur raison. Restent : la télémétrie, le manuel, le disque et
#: le bail du registre — internes, ou voulus par la démo (M11).
TACHES_HORS_DEMO: dict[str, str] = {
    "purge_comptes_inactifs": "supprime des comptes ; la remise à zéro nocturne la remplace",
    "backup": "rien à sauvegarder : la démo se régénère chaque nuit",
    "courriel_reponses": "relève IMAP : un appel sortant",
    "synthese_affaires": "appel à l'IA et courriel au conseil",
    "transcription_pv": "appel à l'IA",
    "whatsapp_scheduled": "messages WhatsApp",
    "health_check": "son seul effet est un courriel d'alerte",
}


def coupee_hors_demo(tache: str) -> bool:
    """Cette tâche est-elle coupée ICI parce que l'installation est la démo ?

    La question que le rapport nocturne pose pour la sauvegarde (#1982) : elle se
    lit dans `TACHES_HORS_DEMO`, la table que `retirer_hors_demo` applique — jamais
    une seconde règle « démo → pas de sauvegarde » écrite à côté.
    """
    from app.utils.demo import est_demo

    return est_demo() and tache in TACHES_HORS_DEMO


def retirer_hors_demo(scheduler) -> list[str]:
    """En démo, retire les tâches de `TACHES_HORS_DEMO`, rattrapages compris. Rend leurs ids."""
    from app.utils.demo import est_demo

    if not est_demo():
        return []
    retirees = sorted(
        job.id
        for job in scheduler.get_jobs()
        if job.id in TACHES_HORS_DEMO or job.id.removesuffix("_rattrapage") in TACHES_HORS_DEMO
    )
    for identifiant in retirees:
        scheduler.remove_job(identifiant)
    return retirees


def enregistrer_taches_de_la_plateforme(scheduler) -> None:
    """Pose les tâches de `TACHES_DE_LA_PLATEFORME`, chacune par SON module.

    `main.py` n'en appelle qu'une : il touchait son plafond de 500 lignes, et la
    liste des tâches de la plateforme se lit ICI, à côté de leur déclaration.
    """
    from app.inscription import client
    from app.registre import canaux, conservation, sauvegarde
    from app.utils import sante_plateforme

    for module in (sante_plateforme, sauvegarde, conservation, canaux, client):
        module.enregistrer(scheduler)


def tache_hors_enveloppe(job) -> bool:
    """Ce job travaille-t-il pour une copropriété sans passer par l'enveloppe ?"""
    return job.id not in TACHES_DE_LA_PLATEFORME and not getattr(job.func, "par_copropriete", False)


def verifier_taches_enregistrees(scheduler, logger) -> list[str]:
    """Comparer ce qui tourne à ce qui est déclaré, et journaliser l'écart.

    Rend la liste des identifiants **manquants** (vide si tout va bien). Ne lève
    jamais : un écart de tâches ne doit pas empêcher l'application de démarrer —
    ce serait échanger une panne silencieuse contre une panne totale.

    ⚠️ En `WARNING`, comme le journal de sécurité et pour la même raison : le
    point 6 du pré-check et `check-reliability.sh` comptent les `ERROR`, et un
    `ERROR` ici ferait sonner le canal d'alerte à chaque démarrage d'une
    installation qui n'a pas encore sa configuration.
    """
    from app.utils.demo import est_demo

    enregistrees = {job.id for job in scheduler.get_jobs()}
    #  En démo, une tâche retirée exprès n'est pas une tâche disparue (#1902).
    attendues = set(TACHES_PERMANENTES) - (set(TACHES_HORS_DEMO) if est_demo() else set())
    manquantes = sorted(attendues - enregistrees)
    for identifiant in manquantes:
        logger.warning(
            "tache planifiee ABSENTE : %s — %s",
            identifiant,
            TACHES_PERMANENTES[identifiant],
        )
    #  L'inverse compte aussi : une tâche qui tourne sans être déclarée n'a pas
    #  de coût écrit, donc personne ne saura quoi faire le jour où elle tombe.
    #  Les rattrapages sont attendus et non déclarés (voir l'en-tête).
    for identifiant in sorted(enregistrees - set(TACHES_PERMANENTES) - identifiants_rattrapage()):
        logger.warning("tache planifiee NON DECLAREE : %s", identifiant)
    #  Et une tâche qui tournerait hors de toute copropriété : elle écrirait dans
    #  la base de celle que le repli désigne, sans que rien le dise (#1745).
    for job in sorted(
        (j for j in scheduler.get_jobs() if tache_hors_enveloppe(j)), key=lambda j: j.id
    ):
        logger.warning("tache planifiee HORS COPROPRIETE : %s", job.id)
    return manquantes
