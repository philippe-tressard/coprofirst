"""Système de sauvegarde — APScheduler + rotation automatique."""

import glob
import os
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from app.utils import horloge

from sqlmodel import Session, select

from app.utils.declenchement import AUTOMATIQUE
from app.config import get_settings
from app import contexte
from app.dialecte import chemin_fichier, point_de_controle, verifier_integrite
from app.models.core import ConfigSauvegarde, HistoriqueSauvegarde, StatutSauvegarde

from app.utils.noeud import noeud_courant

settings = get_settings()

#  Nommage des archives — convention PORTEUSE DE SENS, pas cosmétique.
#  L'horodatage dans le nom est déjà ce sur quoi repose la rotation (tri
#  lexicographique = tri chronologique). `export-hors-site.sh` le remonte à
#  l'API, et `health_monitor` le relit pour distinguer « l'export tourne » de
#  « la copie hors site est fraîche ». Trois lecteurs, donc UN SEUL endroit où
#  la convention est écrite, et un seul parseur.
PREFIXE_ARCHIVE = "hostachy_backup_"
MOTIF_ARCHIVE = f"{PREFIXE_ARCHIVE}*.tar.gz"
_FORMAT_HORODATAGE = "%Y%m%d_%H%M%S"
_SUFFIXE_ARCHIVE = ".tar.gz"
#  🔴 Le nom ÉCRIT son fuseau (#1611). Il portait l'horloge UTC sans le dire :
#  `…_020000` désignait une sauvegarde prise à 04:00, l'heure que le planificateur
#  règle. Il dit désormais l'heure de Paris, et le suffixe distingue une archive
#  nouvelle d'une ancienne (UTC, sans suffixe) — sans lui, rien ne dirait laquelle on
#  lit pendant les `keep` versions où les deux coexistent. Le suffixe vient APRÈS les
#  secondes : le tri alphabétique reste le tri chronologique (rotation, export), et les
#  lecteurs par JOUR (`jours_manquants`) lisent la date de Paris, celle du résident.
SUFFIXE_FUSEAU = "_paris"


def nom_archive(instant: datetime) -> str:
    """Le nom d'une archive prise à `instant` (UTC naïf) — à l'heure de Paris."""
    heure = horloge.a_paris(instant).strftime(_FORMAT_HORODATAGE)
    return f"{PREFIXE_ARCHIVE}{heure}{SUFFIXE_FUSEAU}{_SUFFIXE_ARCHIVE}"


def horodatage_archive(nom_fichier: str) -> datetime | None:
    """Date de création (UTC naïf) lue dans le nom d'une archive, ou None si illisible.

    Deux formats coexistent pendant la rétention (#1611) : `…_HHMMSS_paris` (heure de
    Paris, converti ici) et `…_HHMMSS` (l'ancien, déjà en UTC). Un suffixe de fuseau
    inconnu est refusé : lire autre chose en UTC serait deviner.

    Rend None plutôt que de lever : un nom non conforme (fichier déposé à la
    main, archive renommée) ne doit pas faire échouer un contrôle de santé —
    il doit le faire répondre « je ne sais pas », ce que l'appelant traite
    comme une anomalie et non comme un OK (standards/04 §1).
    """
    if not nom_fichier:
        return None
    base = os.path.basename(nom_fichier)
    if not base.startswith(PREFIXE_ARCHIVE) or not base.endswith(_SUFFIXE_ARCHIVE):
        return None
    brut = base[len(PREFIXE_ARCHIVE) : -len(_SUFFIXE_ARCHIVE)]
    paris = brut.endswith(SUFFIXE_FUSEAU)
    if paris:
        brut = brut[: -len(SUFFIXE_FUSEAU)]
    try:
        lu = datetime.strptime(brut, _FORMAT_HORODATAGE)
    except ValueError:
        return None
    return horloge.de_paris(lu) if paris else lu


#: Le nom, DANS l'archive, de l'export vérifié d'une base serveur (DI-7b).
#: `scripts/lib/lib-export-hors-site.sh` le reconnaît : même valeur, tenue par
#: `tests/test_sauvegarde_base_serveur.py`.
NOM_EXPORT_BASE = "base-export.tar.gz"

#: Les fichiers téléversés, sauvegardés avec la base.
UPLOADS = "/app/uploads"


def _integrite() -> str:
    """Le verdict du moteur, « ok » si sain — une erreur de lecture n'est pas « ok »."""
    try:
        with contexte.moteur().connect() as connexion:
            return verifier_integrite(connexion)
    except Exception as exc:
        return f"contrôle d'intégrité en échec : {exc}"


def _annuler(session: Session, entry: HistoriqueSauvegarde, verdict: str) -> None:
    """Ne jamais écraser les sauvegardes saines (rotation) par celle d'une base abîmée.

    Cf. corruption telemetry_event du 17/06/2026 : le backup de 01:00 contenait
    déjà la table malformée, devenu inutilisable.
    """
    entry.statut = StatutSauvegarde.echouee
    entry.message_erreur = (
        f"Sauvegarde annulée — base corrompue ({verdict}). "
        f"Backups sains préservés (pas de rotation)."
    )
    entry.terminee_le = horloge.maintenant()
    session.add(entry)
    session.commit()


def _exporter_et_verifier(export: Path, dossier: Path) -> None:
    """Exporte la base, puis la RÉIMPORTE dans une base jetable : un écart lève.

    `ImportRefuse` (compte ou empreinte d'une table) fait échouer la sauvegarde —
    une archive qui ne se restaure pas n'est pas une sauvegarde.
    """
    from app.utils.export_copropriete import exporter
    from app.utils.import_copropriete import verifier_archive

    exporter(contexte.moteur(), export)
    verifier_archive(export, dossier)


def _reussie(session: Session, entry: HistoriqueSauvegarde, nom: str, chemin: str) -> None:
    entry.statut = StatutSauvegarde.reussie
    entry.fichier_nom = nom
    entry.fichier_chemin = chemin
    entry.taille_octets = os.path.getsize(chemin)
    entry.terminee_le = horloge.maintenant()
    _rotate_backups(session)
    session.add(entry)
    session.commit()


def run_backup(history_id: int | None = None):
    """
    Lance une sauvegarde : la base + le répertoire uploads → .tar.gz.
    Base-fichier : `app.db`, après point de contrôle et `quick_check`. Base
    serveur : son export vérifié (`base-export.tar.gz`), après le contrôle des
    sommes de pages.
    Met à jour l'entrée HistoriqueSauvegarde correspondante.
    """
    with contexte.nouvelle_session() as session:
        entry: HistoriqueSauvegarde | None = None
        if history_id:
            entry = session.get(HistoriqueSauvegarde, history_id)
        if not entry:
            entry = HistoriqueSauvegarde(declenchee_par=AUTOMATIQUE, noeud=noeud_courant())
            session.add(entry)
            session.commit()
            session.refresh(entry)

        try:
            os.makedirs(settings.backup_dir, exist_ok=True)
            filename = nom_archive(horloge.maintenant())
            dest = os.path.join(settings.backup_dir, filename)

            fichier = chemin_fichier(contexte.courante().url_base)
            db_path = str(fichier) if fichier else ""

            #  🔴 Une base SERVEUR (PostgreSQL, DI-7b, #1781) n'a pas de fichier à
            #  copier : sans cette branche, l'archive partait SANS la base et
            #  marquée « réussie ». Elle reçoit l'EXPORT vérifié (P2-7) — format
            #  neutre, réimporté dans une base jetable AVANT d'être déclaré bon.
            if fichier is None:
                verdict = _integrite()
                if verdict != "ok":
                    _annuler(session, entry, verdict)
                    return
                with tempfile.TemporaryDirectory() as dossier:
                    export = Path(dossier) / NOM_EXPORT_BASE
                    _exporter_et_verifier(export, Path(dossier))
                    with tarfile.open(dest, "w:gz") as tar:
                        tar.add(export, arcname=NOM_EXPORT_BASE)
                        if os.path.exists(UPLOADS):
                            tar.add(UPLOADS, arcname="uploads")
                _reussie(session, entry, filename, dest)
                return

            # WAL checkpoint avant copie : garantit que app.db contient
            # toutes les transactions committées (le WAL peut être en avance)
            if os.path.exists(db_path):
                with contexte.moteur().connect() as _conn:
                    point_de_controle(_conn, "FULL")

                # Validation d'intégrité AVANT de sauvegarder : ne jamais écraser
                # les backups sains (rotation) par un snapshot d'une base corrompue.
                # Cf. corruption telemetry_event du 17/06/2026 : le backup de 01:00
                # contenait déjà la table malformée, devenu inutilisable.
                verdict = _integrite()
                if verdict != "ok":
                    _annuler(session, entry, verdict)
                    return

            with tarfile.open(dest, "w:gz") as tar:
                if os.path.exists(db_path):
                    tar.add(db_path, arcname="app.db")
                if os.path.exists(UPLOADS):
                    tar.add(UPLOADS, arcname="uploads")

            _reussie(session, entry, filename, dest)
            return

        except Exception as exc:
            entry.statut = StatutSauvegarde.echouee
            entry.message_erreur = str(exc)
            entry.terminee_le = horloge.maintenant()

        session.add(entry)
        session.commit()


def _rotate_backups(session: Session):
    """Supprime les sauvegardes au-delà du nombre de versions à conserver."""
    cfg: ConfigSauvegarde | None = session.exec(select(ConfigSauvegarde)).first()
    keep = cfg.nb_versions_conservees if cfg else settings.backup_keep_versions

    pattern = os.path.join(settings.backup_dir, MOTIF_ARCHIVE)
    files = sorted(glob.glob(pattern))  # order par date (timestamp dans le nom)

    to_delete = files[: max(0, len(files) - keep)]
    for f in to_delete:
        try:
            os.remove(f)
        except OSError:
            pass

    # Marquer comme supprimées dans l'historique
    all_entries = session.exec(
        select(HistoriqueSauvegarde).where(HistoriqueSauvegarde.statut == StatutSauvegarde.reussie)
    ).all()
    deleted_names = {os.path.basename(f) for f in to_delete}
    for e in all_entries:
        if e.fichier_nom in deleted_names:
            session.delete(e)
    session.commit()


def derniere_sauvegarde_reussie(session):
    """L'horodatage de la dernière sauvegarde qui a ABOUTI, ou `None`.

    Le fait qu'interroge le rattrapage (`utils/rattrapage.py`, #876). On lit
    `terminee_le` et non `cree_le` : une sauvegarde qui commence ne prouve rien,
    c'est celle qui finit qui compte — et une ligne restée `en_cours` est
    justement ce que le nettoyage des orphelines requalifie en échec au
    démarrage suivant.
    """
    ligne = session.exec(
        select(HistoriqueSauvegarde)
        .where(HistoriqueSauvegarde.statut == StatutSauvegarde.reussie)
        .order_by(HistoriqueSauvegarde.terminee_le.desc())
        .limit(1)
    ).first()
    return ligne.terminee_le if ligne else None


def setup_scheduler():
    """Configure APScheduler selon ConfigSauvegarde (ou paramètres .env par défaut)."""
    from apscheduler.schedulers.background import BackgroundScheduler

    #  Les tâches `cron` (heure=2, minute=0…) s'entendent à l'heure de Paris.
    scheduler = BackgroundScheduler(timezone=horloge.TZ_PARIS)

    with contexte.nouvelle_session() as session:
        cfg: ConfigSauvegarde | None = session.exec(select(ConfigSauvegarde)).first()

    # Si la config existe et est désactivée, on ne programme rien
    if cfg is not None and not cfg.active:
        scheduler.start()
        return scheduler

    hour = cfg.heure_execution if cfg else settings.backup_hour

    #  QUOTIDIENNE, et rien d'autre. `frequence` proposait aussi « hebdomadaire »
    #  et « mensuelle », qui ne s'ajoutent pas au quotidien mais le REMPLACENT :
    #  sur une base de quelques mégaoctets, les espacer ne fait que perdre des
    #  jours de données. Le choix est retiré de l'interface, et la migration 0139
    #  ramène les installations existantes au quotidien (13/08/2026).
    #
    #  Une valeur ancienne qui ressurgirait — base non migrée, restauration —
    #  donne donc une sauvegarde quotidienne : le repli va dans le sens de la
    #  sécurité, jamais dans celui de la rareté.
    scheduler.add_job(
        contexte.pour_chaque_copropriete(run_backup, "backup"),
        "cron",
        hour=hour,
        minute=0,
        id="backup",
    )

    scheduler.start()
    return scheduler
