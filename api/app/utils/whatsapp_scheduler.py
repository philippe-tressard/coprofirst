"""Planificateur de messages WhatsApp récurrents.

Logique : de 18h00 à 21h45 (toutes les 15 min), vérifie si demain est le Nème
samedi du mois correspondant à une règle cron_rule, et envoie le message.

Fenêtre de rattrapage (depuis l'incident du 24/07/2026) : le job ne tentait
auparavant l'envoi qu'une seule fois, à 18h00 pile — une panne ponctuelle du
bridge WhatsApp à cette seconde précise faisait perdre le message du mois.

⚠️ Ce commentaire affirmait ensuite : « la déduplication rend les tentatives
répétées sûres : aucun risque de doublon ». C'était faux, et le 14/08/2026 le
message « Encombrants (Boulevard Fernand Hostachy) » est parti **trois fois**
dans le groupe. La déduplication n'observait pas ce qu'elle croyait observer :
elle lisait l'acquittement HTTP du bridge — « ai-je reçu une réponse ? » — et
non le fait — « le message est-il parti ? ». Le bridge dépassait le délai
d'attente tout en délivrant : chaque créneau concluait « échec » et renvoyait.
Le remède au « zéro message » avait créé le « seize messages ».

Ce qui protège du doublon depuis :

1. **Le verrou est posé avant l'envoi**, pas après. Une tentative engagée
   interdit la suivante, même si le processus meurt en plein envoi.
2. **On ne rejoue que sur un échec établi** — un résultat inconnu n'est pas un
   échec (`whatsapp.EnvoiIncertain`). Entre un doublon irréversible dans un
   groupe de copropriétaires et un message à renvoyer à la main, on choisit le
   second, et on alerte un humain.

Si la fenêtre se ferme sans envoi réussi, une alerte e-mail est déclenchée.
"""

import calendar
import logging
from datetime import datetime, timedelta
from app.utils import horloge
from app.utils.horloge import TZ_PARIS

from sqlmodel import Session, select

from app import contexte
from app.models.core import WhatsAppScheduled, WhatsAppLog, ConfigSite
from app.utils.services import SERVICE_DIFFUSION, service_actif
from app.utils.whatsapp import (
    STATUT_EN_COURS,
    STATUT_ENVOYE,
    STATUT_INCERTAIN,
    STATUTS_NON_REJOUABLES,
    verdict_envoi,
)
from app.utils.whatsapp_message import pied_whatsapp

logger = logging.getLogger(__name__)

# Dernière tentative de la fenêtre de rattrapage — doit correspondre au dernier
# déclenchement du cron APScheduler (hour='18-21', minute='*/15') dans main.py.
CATCHUP_END_HOUR = 21
CATCHUP_END_MINUTE = 45


def _nth_weekday(year: int, month: int, weekday: int, n: int):
    """Retourne la date du Nème jour de la semaine (0=lun..5=sam) du mois."""
    cal = calendar.monthcalendar(year, month)
    count = 0
    for week in cal:
        if week[weekday] != 0:
            count += 1
            if count == n:
                return week[weekday]
    return None


def _is_friday_before_nth_saturday(dt: datetime, n: int) -> bool:
    """Vérifie si dt est le vendredi 18h avant le Nème samedi du mois."""
    if dt.weekday() != 4:  # 4 = vendredi
        return False
    saturday = dt.date() + timedelta(days=1)
    day = _nth_weekday(saturday.year, saturday.month, calendar.SATURDAY, n)
    return day is not None and saturday.day == day


def check_and_send():
    """Vérifie les messages planifiés et envoie ceux qui correspondent à aujourd'hui."""
    from app.utils.whatsapp import envoyer_whatsapp_raw

    now = datetime.now(TZ_PARIS)
    is_last_attempt = (now.hour, now.minute) == (CATCHUP_END_HOUR, CATCHUP_END_MINUTE)
    logger.info("WhatsApp scheduler check at %s", now.strftime("%Y-%m-%d %H:%M"))

    with contexte.nouvelle_session() as session:
        schedules = session.exec(
            select(WhatsAppScheduled).where(WhatsAppScheduled.enabled == True)  # noqa: E712
        ).all()

        if not schedules:
            return

        # Charger la config WhatsApp
        rows = session.exec(select(ConfigSite)).all()
        config = {r.cle: r.valeur for r in rows}

        if not service_actif(config, SERVICE_DIFFUSION):
            logger.info("WhatsApp désactivé, pas d'envoi planifié.")
            return

        for sched in schedules:
            should_send = False
            if sched.cron_rule == "3eme_samedi":
                should_send = _is_friday_before_nth_saturday(now, 3)
            elif sched.cron_rule == "4eme_samedi":
                should_send = _is_friday_before_nth_saturday(now, 4)

            if not should_send:
                continue

            # Tentatives déjà faites aujourd'hui pour ce message (tout statut)
            today_start = horloge.debut_du_jour_utc(now)
            today_logs = session.exec(
                select(WhatsAppLog)
                .where(
                    WhatsAppLog.scheduled_id == sched.id,
                    WhatsAppLog.envoye_le >= today_start,
                )
                .order_by(WhatsAppLog.envoye_le.desc())
            ).all()

            #  Seul un échec ÉTABLI autorise une nouvelle tentative. Un envoi
            #  réussi, un résultat inconnu ou une tentative dont on n'a pas vu
            #  la fin valent tous « le groupe l'a peut-être déjà reçu ».
            deja = next((log for log in today_logs if log.statut in STATUTS_NON_REJOUABLES), None)
            if deja is not None:
                logger.info(
                    "Message '%s' : tentative du jour au statut « %s », pas de rejeu.",
                    sched.label,
                    deja.statut,
                )
                #  « en cours » = tentative interrompue (redémarrage en plein
                #  envoi) : personne n'a encore été prévenu. « incertain » a
                #  déjà déclenché son alerte au moment du verdict.
                if is_last_attempt and deja.statut == STATUT_EN_COURS:
                    _alerter(session, sched, deja.statut, deja.erreur)
                continue

            footer = pied_whatsapp(config.get("whatsapp_footer"))
            message_complet = f"{sched.message}\n\n{footer}"

            # Réutilise le log d'échec du jour au lieu d'en empiler un nouveau à
            # chaque créneau de 15 min — sinon _prune_logs (qui ne garde que les
            # 6 derniers logs, tous messages confondus) purgerait tout
            # l'historique récent en moins de 2h de tentatives.
            log = (
                today_logs[0]
                if today_logs
                else WhatsAppLog(
                    scheduled_id=sched.id,
                    label=sched.label,
                )
            )
            log.message = message_complet
            log.envoye_le = horloge.maintenant()

            #  ── Verrou, posé AVANT l'envoi ────────────────────────────────
            #  Écrire le log après coup ne protège que des envois dont on a vu
            #  la fin. Committer « en cours » d'abord ferme aussi la porte au
            #  créneau suivant si celui-ci arrive alors que l'envoi dure encore,
            #  et au redémarrage du conteneur en plein appel : dans les deux cas
            #  on ne sait pas ce que le groupe a reçu, donc on ne renvoie pas.
            log.statut = STATUT_EN_COURS
            log.erreur = None
            session.add(log)
            session.commit()

            log.statut, log.erreur = verdict_envoi(
                lambda: envoyer_whatsapp_raw(message_complet, config)
            )
            session.add(log)
            session.commit()

            if log.statut == STATUT_ENVOYE:
                logger.info("Message planifié '%s' envoyé.", sched.label)
            elif log.statut == STATUT_INCERTAIN:
                logger.warning(
                    "Envoi planifié '%s' au résultat inconnu (%s) — pas de rejeu : "
                    "le groupe l'a peut-être reçu.",
                    sched.label,
                    log.erreur,
                )
                _alerter(session, sched, log.statut, log.erreur)
            else:
                logger.warning("Échec envoi planifié '%s': %s", sched.label, log.erreur)
                if is_last_attempt:
                    _alerter(session, sched, log.statut, log.erreur)

            # Garder seulement les 6 derniers logs
            _prune_logs(session)


def _alerter(session: Session, sched: WhatsAppScheduled, statut: str, erreur: str | None) -> None:
    """Alerte : le message PLANIFIÉ du mois n’est pas arrivé.

    La conduite à tenir — et surtout l’interdit de rejeu sur un envoi
    incertain — vit dans `utils/whatsapp_alerte`, avec celle des envois
    déclenchés par un geste. Elle n’était écrite QUE pour le message planifié
    jusqu’au 19/09/2026 : un ticket partagé en échec ne prévenait personne
    (#1057). Ce qui reste ici est la seule chose que ce module sache : la
    fenêtre de rattrapage.
    """
    from app.utils.whatsapp_alerte import alerter_envoi

    alerter_envoi(
        session,
        sched.label,
        statut,
        erreur,
        precision=(
            f" Malgré la fenêtre de rattrapage (18h00 → "
            f"{CATCHUP_END_HOUR:02d}h{CATCHUP_END_MINUTE:02d})."
        ),
    )


#: Un log de message planifié plus récent que ce délai n'est pas de l'historique :
#: c'est le verrou qui dit « une tentative a déjà été engagée aujourd'hui ».
DUREE_VERROU = timedelta(hours=24)


def _prune_logs(session: Session):
    """Conserve les 6 derniers messages — sans jamais retirer un verrou du jour.

    La purge traitait tous les logs pareil, alors que ceux des messages planifiés
    portent la déduplication. Six publications dans la soirée suffisaient à
    évincer le log « envoyé » des encombrants — et le créneau suivant, ne voyant
    plus rien, renvoyait le message.
    """
    all_logs = session.exec(select(WhatsAppLog).order_by(WhatsAppLog.envoye_le.desc())).all()
    if len(all_logs) <= 6:
        return
    seuil_verrou = horloge.maintenant() - DUREE_VERROU
    supprimes = False
    for old in all_logs[6:]:
        if old.scheduled_id is not None and old.envoye_le >= seuil_verrou:
            continue
        session.delete(old)
        supprimes = True
    if supprimes:
        session.commit()
