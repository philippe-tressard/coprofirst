"""Vérification quotidienne de santé d'une copropriété — WhatsApp, sauvegardes, base.

Le disque est une donnée de la PLATEFORME : `utils/sante_plateforme` (#1814).
"""

import glob
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from app.utils import horloge

from sqlmodel import Session, select

from app.utils.config_site import config_site
from app import contexte
from app.utils.dates_fr import datetime_longue
from app.models.core import (
    ConfigSite,
    HistoriqueMaintenance,
    HistoriqueSauvegarde,
    StatutSauvegarde,
    TachePlanifiee,
    WhatsAppLog,
)

from app.utils.verdict_whatsapp import verdict_whatsapp

logger = logging.getLogger(__name__)

#  Âge au-delà duquel l'archive locale la plus récente est anormale : le cron
#  de sauvegarde tourne à 03:00 et ce contrôle à 06:00, sur le même nœud.
_AGE_MAX_ARCHIVE_LOCALE_H = 25


def _heures_depuis(horodatage: str | None) -> float | None:
    """Les heures écoulées depuis un horodatage ISO du bridge ; `None` s'il manque."""
    if not horodatage:
        return None
    try:
        debut = datetime.fromisoformat(horodatage.replace("Z", "+00:00"))
    except ValueError:
        return None
    #  UTC NAÏF, comme `horloge.maintenant()` : le bridge écrit un ISO en « Z ».
    if debut.tzinfo is not None:
        debut = debut.astimezone(timezone.utc).replace(tzinfo=None)
    return (horloge.maintenant() - debut).total_seconds() / 3600


def _check_whatsapp(session: Session) -> list[str]:
    """Retourne une liste de problèmes WhatsApp détectés."""
    from app.utils.whatsapp import (
        CleBridgeRefusee,
        config_whatsapp,
        get_whatsapp_status,
    )
    from app.utils.services import SERVICE_DIFFUSION, service_actif

    issues = []
    #  Ce contrôle n'a besoin que de trois clés, mais c'est la MÊME notion que
    #  celle des routers : il en gardait sa propre liste, cinquième exemplaire.
    #  Lire l'ensemble complet ne coûte rien et supprime la divergence.
    cfg = config_whatsapp(session)

    if not service_actif(cfg, SERVICE_DIFFUSION):
        return []

    if not cfg.get("whatsapp_api_url", "").strip():
        return []

    # Vérifier le statut du bridge — la requête de l'écran d'administration.
    try:
        statut = get_whatsapp_status(cfg)
        #  Coupure ordinaire ou blocage possible : `utils/verdict_whatsapp` (#1061).
        probleme = verdict_whatsapp(
            statut.get("state", "unknown"),
            _heures_depuis(statut.get("hors_ligne_depuis")),
            statut.get("dernier_code"),
        )
        if probleme:
            issues.append(probleme)
    except CleBridgeRefusee as exc:  # joignable, mais pas avec cette clé (#1596)
        return [str(exc)]
    except Exception as exc:
        issues.append(f"Bridge WhatsApp injoignable : {exc}")
        return issues

    # Vérifier les logs des dernières 24h : >= 3 échecs consécutifs
    # (on ignore les anciens échecs antérieurs à une reconnexion)
    depuis = horloge.maintenant() - timedelta(hours=24)
    logs = session.exec(
        select(WhatsAppLog)
        .where(WhatsAppLog.envoye_le >= depuis)
        .order_by(WhatsAppLog.envoye_le.desc())
        .limit(5)
    ).all()
    if len(logs) >= 3 and all(log.statut == "échec" for log in logs[:3]):
        extrait = "\n".join(
            f"    [{horloge.a_paris(log.envoye_le):%d/%m %H:%M}] "
            f"« {log.label[:40]} » → {log.erreur or 'erreur inconnue'}"
            for log in logs[:3]
        )
        issues.append(
            f"3 derniers envois WhatsApp en échec consécutif (dernières 24h) :\n{extrait}"
        )

    return issues


def _check_backups(session: Session) -> list[str]:
    """Retourne une liste de problèmes de sauvegarde détectés."""
    issues = []
    last_ok = session.exec(
        select(HistoriqueSauvegarde)
        .where(HistoriqueSauvegarde.statut == StatutSauvegarde.reussie)
        .order_by(HistoriqueSauvegarde.terminee_le.desc())
    ).first()

    if not last_ok or not last_ok.terminee_le:
        issues.append("Aucune sauvegarde réussie trouvée dans l'historique.")
        return issues

    age = horloge.maintenant() - last_ok.terminee_le
    if age > timedelta(hours=25):
        heures = int(age.total_seconds() / 3600)
        issues.append(
            f"Dernière sauvegarde réussie il y a {heures}h (> 25h). Vérifier Admin → Sauvegardes."
        )

    # Dernière sauvegarde en échec ?
    last_any = session.exec(
        select(HistoriqueSauvegarde).order_by(HistoriqueSauvegarde.terminee_le.desc())
    ).first()
    if last_any and last_any.statut == StatutSauvegarde.echouee:
        issues.append(
            f"La dernière sauvegarde a échoué : {last_any.message_erreur or 'erreur inconnue'}."
        )

    issues += _check_archive_locale()
    return issues


def _check_archive_locale() -> list[str]:
    """Vérifie qu'une archive RÉELLE et récente existe sur ce nœud.

    POURQUOI ce contrôle s'ajoute à celui de l'historique (04/08/2026) :
    `historique_sauvegarde` vit dans la base, répliquée sur le pair — mais le
    volume Docker `backups`, lui, n'est jamais répliqué. Une
    ligne « réussie » ne prouvait donc PAS qu'un fichier existe : elle prouvait
    qu'une ligne a été écrite. Volume vidé, disque plein, archive tronquée,
    rotation trop agressive — le contrôle restait vert dans tous ces cas.
    C'est « vérifier l'artefact déclaré plutôt que le fait » (standards/04).

    Le contrôle tourne à 06:00 sur le nœud actif, qui a produit la sauvegarde de
    03:00 trois heures plus tôt : en marche nominale, une archive fraîche est
    forcément là. Après un failover survenu entre 03:00 et 06:00, ce nœud n'en a
    effectivement pas — et le signaler est correct, pas excessif : cela veut dire
    que si l'autre nœud est perdu, l'archive la plus récente a deux jours.
    """
    from app.utils.backup import MOTIF_ARCHIVE, horodatage_archive

    repertoire = contexte.dossier_des_sauvegardes()
    try:
        chemins = sorted(glob.glob(os.path.join(repertoire, MOTIF_ARCHIVE)))
    except OSError as exc:
        return [f"Répertoire de sauvegarde illisible ({repertoire}) : {exc}."]

    if not chemins:
        return [
            f"Aucun fichier de sauvegarde présent sur ce nœud ({repertoire}), "
            f"alors que l'historique en annonce. Le volume `backups` n'est pas "
            f"répliqué entre les RPi : vérifier Admin → Sauvegardes."
        ]

    recent = chemins[-1]
    nom = os.path.basename(recent)
    try:
        taille = os.path.getsize(recent)
    except OSError as exc:
        return [f"Archive la plus récente illisible ({nom}) : {exc}."]

    if taille == 0:
        return [f"L'archive la plus récente est VIDE (0 octet) : {nom}."]

    horodatage = horodatage_archive(nom)
    if horodatage is None:
        # Ne pas savoir dater n'est pas un OK : c'est un INCONNU, donc une anomalie.
        return [f"Archive au nom non conforme, impossible d'en vérifier l'âge : {nom}."]

    age = horloge.maintenant() - horodatage
    if age > timedelta(hours=_AGE_MAX_ARCHIVE_LOCALE_H):
        heures = int(age.total_seconds() / 3600)
        return [
            f"L'archive la plus récente présente sur ce nœud date de {heures}h "
            f"({nom}) — au-delà des {_AGE_MAX_ARCHIVE_LOCALE_H}h attendues."
        ]
    return []


def seuil_copie_hors_site_h() -> int:
    """L'âge, en heures, au-delà duquel une copie hors site est périmée.

    Lu là où l'écran de santé le lit déjà : deux constantes séparées divergeraient
    au premier ajustement, et l'e-mail contredirait l'écran. Le contrôle du
    registre (`registre/sauvegarde.probleme_copie_hors_site`) juge au même seuil.
    """
    from app.routers.admin import _PERIODICITE_ATTENDUE_H, _TOLERANCE_H

    return _PERIODICITE_ATTENDUE_H[TachePlanifiee.export_hors_site.value] + _TOLERANCE_H


def derniere_copie_hors_site(session: Session) -> tuple[HistoriqueMaintenance | None, dict]:
    """Le dernier rapport d'export hors site, et ses détails lus (vides si illisibles)."""
    derniere = session.exec(
        select(HistoriqueMaintenance)
        .where(HistoriqueMaintenance.tache == TachePlanifiee.export_hors_site.value)
        .order_by(HistoriqueMaintenance.cree_le.desc())
    ).first()
    details: dict = {}
    if derniere is not None and derniere.details:
        try:
            details = json.loads(derniere.details) or {}
        except ValueError:
            details = {}
    return derniere, details


def copie_hors_site_a_jour(session: Session) -> bool:
    """Oui si la copie hors site est là, réussie, fraîche et saine — le jugement de
    l'écran de santé, sans un mot de plus : le rapport nocturne (#1981) le transmet
    tel quel à la référence, qui n'en a pas de second."""
    return not _check_export_hors_site(session)


def _check_export_hors_site(session: Session) -> list[str]:
    """Vérifie qu'une copie des sauvegardes existe HORS des deux Raspberry Pi.

    POURQUOI (04/08/2026) : jusqu'ici, 100 % des archives vivaient dans des
    volumes Docker sur deux RPi posés au même endroit, sur la même box et la
    même alimentation. Les deux nœuds protègent de la panne d'UN nœud, jamais
    d'un `docker volume rm`, d'un rançongiciel ou d'un sinistre — qui emportent
    la base, les uploads ET toutes les sauvegardes d'un coup.
    `export-hors-site.sh` produit cette copie ; ce contrôle est ce qui empêche
    son oubli de passer inaperçu.

    Deux questions DISTINCTES, et c'est le point important :
      1. l'export a-t-il tourné récemment ?
      2. la copie qu'il a produite est-elle FRAÎCHE ?
    Un export qui s'exécute fidèlement mais recopie chaque fois la même archive
    périmée satisfait (1) et trahit (2). Ne vérifier que (1) fabriquerait
    exactement le faux vert que ce lot corrige ailleurs.
    """
    from app.utils.backup import horodatage_archive

    seuil_h = seuil_copie_hors_site_h()
    jours = int(seuil_h / 24)
    derniere, details = derniere_copie_hors_site(session)

    if derniere is None:
        return [
            "Aucune copie hors site n'a jamais été enregistrée. Les sauvegardes "
            "n'existent que sur les deux RPi : un sinistre au domicile les perd "
            "toutes. Lancer export-hors-site.cmd depuis le poste."
        ]

    issues = []
    if derniere.statut == "erreur":
        issues.append(
            f"Le dernier export hors site a ÉCHOUÉ : {derniere.erreur or 'erreur inconnue'}."
        )

    age_execution = horloge.maintenant() - derniere.cree_le
    if age_execution > timedelta(hours=seuil_h):
        j = int(age_execution.total_seconds() / 86400)
        issues.append(
            f"Aucun export hors site depuis {j} jours (seuil : {jours} jours). "
            f"Lancer export-hors-site.cmd depuis le poste."
        )

    #  Fraîcheur de l'archive RÉELLEMENT copiée — cf. docstring, question (2).
    archive = details.get("archive")
    horodatage = horodatage_archive(archive) if archive else None
    if horodatage is None:
        issues.append(
            "Le dernier export hors site n'indique pas quelle archive il a "
            "copiée — impossible d'en vérifier la fraîcheur."
        )
    else:
        age_copie = horloge.maintenant() - horodatage
        if age_copie > timedelta(hours=seuil_h):
            j = int(age_copie.total_seconds() / 86400)
            issues.append(
                f"La sauvegarde copiée hors site date de {j} jours ({archive}) — "
                f"l'export s'exécute mais recopie une archive périmée."
            )

    if details.get("integrite") and details["integrite"] != "ok":
        issues.append(
            f"La copie hors site n'a pas passé le contrôle d'intégrité ({details['integrite']})."
        )

    return issues


def _check_db_integrity() -> list[str]:
    """Vérifie l'intégrité de la base (`dialecte.verifier_integrite`).

    Détecte tôt une page abîmée au lieu d'attendre un signalement utilisateur.
    """
    from app.dialecte import verifier_integrite

    issues: list[str] = []
    try:
        with contexte.moteur().connect() as conn:
            verdict = verifier_integrite(conn)
        if verdict != "ok":
            issues.append(
                f"Intégrité de la base en défaut (« {verdict} »). "
                f"Restauration à envisager — voir la skill infra-rpi."
            )
    except Exception as exc:
        # Un contrôle qui ne peut pas s'exécuter n'est jamais vert (standards/04 §1)
        issues.append(f"Intégrité de la base : le contrôle a échoué ({exc}).")
    return issues


def _check_reference_copro(session: Session) -> list[str]:
    """La référence de copropriété doit être renseignée : le syndic trie dessus.

    Depuis le 11/08/2026, elle est obligatoire — sans exception — dans l'objet de
    tout message qui lui est adressé. Les six modèles concernés ouvrent donc leur
    objet par `{{ prefixe_copro }}`, composé par `email._prefixe_copro`.

    Ce préfixe rend une chaîne vide quand la clé n'est pas renseignée — il le
    faut, sinon l'objet commencerait par « 🏢  — ». Mais c'est précisément ce qui
    rend ce contrôle nécessaire : une clé vide ne produit alors aucune erreur,
    aucun objet dégradé, aucune trace. La règle serait vérifiée sur les modèles —
    les tests resteraient tous verts — et fausse à chaque envoi. Le seul endroit
    d'où l'écart se voit est ici, sur la configuration réelle de l'installation.
    """
    ligne = session.get(ConfigSite, "reference_copro")
    if (ligne.valeur if ligne else "").strip():
        return []
    return [
        "Référence de copropriété non renseignée : les messages adressés au "
        "syndic partent sans elle.\n"
        "Le syndic identifie ses dossiers par cette référence ; sans elle, tickets "
        "et publications transmis sortent de son tri par affaire.\n"
        "À renseigner dans Admin → Configuration du site → Référence de copropriété."
    ]


from app.utils.sante_modeles_email import controler as controler_modeles_email
from app.utils.etat_taches import problemes_taches
from app.utils.sante_mise_a_jour import problemes_mise_a_jour
from app.utils.sante_correctifs import problemes_correctifs
from app.utils.llm_journal import problemes_ia
from app.utils.conservation_copie import archives_en_retard
from app.utils.liens import adresse_du_site, nom_site
from app.utils.sante_plateforme import disque_par_la_plateforme, probleme_disque


def _en_problemes(issues: list[str]) -> list[dict]:
    """Découpe « titre\\ndétail\\ndétail » en {titre, details} pour le modèle.

    Les `_check_*` rendent des chaînes dont les lignes suivantes sont des
    précisions techniques. Le découpage se fait ici, pas dans le modèle : un
    modèle d'e-mail affiche, il ne défait pas un format.
    """
    problemes = []
    for issue in issues:
        lignes = issue.split("\n")
        problemes.append(
            {
                "titre": lignes[0],
                "details": [ligne.strip() for ligne in lignes[1:] if ligne.strip()],
            }
        )
    return problemes


def _send_alert(to: str, issues: list[str], session: Session) -> None:
    """Envoie l'alerte système par le moteur d'e-mail commun.

    Cette fonction parlait à SMTP en direct et fabriquait son HTML en f-strings,
    doublant un moteur d'envoi qui existait à côté. Quatre conséquences, toutes
    silencieuses : l'alerte n'apparaissait pas dans `historique_email` (donc
    l'envoi le plus critique du système était le seul dont on ne pouvait pas
    vérifier le départ), elle n'était pas modifiable depuis Admin → Emails, elle
    ignorait `smtp_ssl_tls` en ne gérant que STARTTLS, et les deux modèles
    prévus pour elle — `sauvegarde_echec` et `alerte_espace_disque` — dormaient
    en base sans que rien ne les envoie.

    Ces deux modèles sont fusionnés en un seul, `alerte_systeme` : le contrôle
    quotidien découvre les problèmes ensemble et n'envoie qu'un message. Deux
    modèles pour un envoi ne se maintiennent pas — ils divergent.

    `send_email` est une coroutine et ce contrôle tourne dans un fil
    d'APScheduler (`BackgroundScheduler`), sans boucle d'événements : `asyncio.
    run` en ouvre une pour la durée de l'envoi, ce qui est le cas d'usage prévu.
    """
    import asyncio

    from app.utils.email import send_email

    cfg = config_site(session)
    site_nom = nom_site(cfg.get("site_nom"))
    site_url = (adresse_du_site()).rstrip("/")

    contexte = {
        "problemes": _en_problemes(issues),
        "nb_problemes": len(issues),
        # Heure de Paris : ce message est lu par une personne, pas par une
        # machine. `datetime_longue` et non `datetime_longue_paris` — la
        # conversion de fuseau est faite ici, sur un instant réellement daté.
        "date_controle": datetime_longue(horloge.a_paris(horloge.maintenant())),
        "residence": {"nom": site_nom},
        "app": {"url": site_url},
    }

    try:
        asyncio.run(send_email(code="alerte_systeme", to=to, context=contexte))
        logger.info("Alerte santé envoyée à %s (%d problème(s)).", to, len(issues))
    except Exception as exc:
        logger.error("Échec envoi alerte santé : %s", exc)


def collecter_problemes(session: Session) -> list[str]:
    """TOUS les contrôles de santé, en une liste — et cette liste n'existe qu'ICI.

    Extraite de `run_health_check` le 09/09/2026 (#852), quand un second appelant
    est apparu : le bouton « Relancer le contrôle » de l'administration.

    🔴 La recopier dans l'endpoint aurait été le défaut de la journée, une
    troisième fois. Un contrôle ajouté à l'un des deux appelants aurait manqué à
    l'autre — et le plus probable, vu que le job quotidien est le seul dont on
    voit le résultat, est que le bouton se serait tu sur un problème réel, sans
    que rien ne le dise.

    ⚠️ Cette fonction ne journalise rien et n'envoie rien : elle **mesure**. Ce
    qu'on fait du résultat — un e-mail à 06:00, un écran à la demande — est la
    décision de l'appelant.
    """
    problemes: list[str] = []
    problemes += _check_db_integrity()
    problemes += _check_whatsapp(session)
    problemes += _check_backups(session)
    problemes += _check_export_hors_site(session)
    #  Une archive d'affaires échues pas encore copiée sur le PC (#2014, §6).
    problemes += archives_en_retard(session, horloge.maintenant())
    problemes += problemes_mise_a_jour(session)
    #  Les correctifs du SYSTÈME d'une installation standard (rien sur la référence,
    #  qui n'en rend pas compte : ses nœuds ont C30).
    problemes += problemes_correctifs(session)
    #  Le disque est celui de la PLATEFORME : jugé ici tant qu'il n'y a qu'une
    #  copropriété, par `sante_plateforme` à partir de la deuxième (#1814).
    if not disque_par_la_plateforme():
        problemes += probleme_disque()
    problemes += _check_reference_copro(session)
    #  Ce que l'écran « Santé des tâches planifiées » montre en rouge, et que
    #  personne ne recevait (27/09/2026). Sauf ce qu'un autre canal signale déjà :
    #  la table `DEJA_SIGNALE` de `sante_taches.py` le déclare.
    problemes += problemes_taches(session)
    #  Ce que l'installation SERT diffère-t-il de ce que le code dit ?
    #  Une migration dont la clause WHERE ne correspond à rien réussit
    #  en ayant modifié zéro ligne, sans erreur ni trace — et le code
    #  porte alors une version que personne ne reçoit (#850).
    problemes += controler_modeles_email(session)
    #  Un usage de l'assistant IA refusé par sa limite d'appels du mois depuis 24 h :
    #  l'usage automatique s'est arrêté, ou quelqu'un a buté dessus (#1383).
    problemes += problemes_ia(session)
    return problemes


def run_health_check() -> None:
    """Job quotidien : vérifie WhatsApp, sauvegardes, disque — alerte si problème."""
    from app.utils.email import get_site_manager_notification_email

    session = contexte.nouvelle_session()
    try:
        issues = collecter_problemes(session)

        if not issues:
            logger.info("Contrôle santé quotidien : tout est OK.")
            return

        logger.warning("Contrôle santé : %d problème(s) détecté(s).", len(issues))
        for i in issues:
            logger.warning("  • %s", i)

        to, _ = get_site_manager_notification_email(session)
        if to:
            _send_alert(to, issues, session)
        else:
            logger.warning("Alerte santé non envoyée : aucun email admin configuré.")
    except Exception as exc:
        logger.error("Erreur contrôle santé quotidien : %s", exc)
    finally:
        session.close()
