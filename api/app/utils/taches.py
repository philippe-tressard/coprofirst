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
    "purge_comptes_inactifs": "la purge quotidienne des comptes inactifs (#1580) — plus "
    "aucun avertissement ni aucune suppression : la durée de conservation annoncée par la "
    "politique de confidentialité redevient fictive",
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
TACHES_DE_LA_PLATEFORME: dict[str, str] = {}


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
    enregistrees = {job.id for job in scheduler.get_jobs()}
    manquantes = sorted(set(TACHES_PERMANENTES) - enregistrees)
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
