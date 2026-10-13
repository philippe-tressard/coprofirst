"""La sauvegarde de la base `plateforme` — le registre des installations (#1892, §4.9).

Ni la sauvegarde de la résidence (son export ne lit que les tables d'une
copropriété) ni la copie hors site ne la couvraient. La réplication en continu la
protège d'une panne de NŒUD (D16), pas d'une erreur : une suppression, une
migration fautive se répliquent comme le reste.

## Ce qu'elle fait

Une tâche de la PLATEFORME (`sauvegarde_plateforme`, déclarée dans
`utils/taches`), chaque nuit, éteinte hors de la référence dont le registre est
déclaré (`base.registre_actif`). Même format et même preuve que la résidence :
l'export neutre (`export_copropriete`, sur les métadonnées du registre), RÉIMPORTÉ
dans une base jetable avant d'être gardé — une archive qui ne se restaure pas
n'est pas une sauvegarde.

- Archives : `<BACKUP_DIR>/plateforme/plateforme_backup_<AAAAMMJJ_HHMMSS>_paris.tar.gz`,
  à part de celles de la résidence (rien ne les mêle : rotation, contrôle de
  fraîcheur et copie hors site lisent `hostachy_backup_*` à la racine).
- On en garde `BACKUP_KEEP_VERSIONS`.
- Un échec prévient l'OPÉRATEUR (`sante_plateforme.alerter`, #1814) — jamais une
  copropriété : le registre n'est pas une donnée de la résidence (§4.11, règle 7).

🔴 Comme le registre lui-même, elle ne doit JAMAIS gêner la résidence : elle ne
lit que la base `plateforme`, et une exception s'arrête ici.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

from app.config import get_settings
from app.registre.base import moteur, registre_actif
from app.registre.modeles import registre_plateforme
from app.utils import horloge
from app.utils.backup import garder_les_dernieres, nom_archive

logger = logging.getLogger("hostachy.registre")

#: Le préfixe des archives du registre — distinct de `backup.PREFIXE_ARCHIVE`.
PREFIXE = "plateforme_backup_"

#: L'identifiant de la tâche — déclaré dans `utils/taches`.
TACHE = "sauvegarde_plateforme"


def dossier() -> Path:
    """Le dossier des archives du registre, sous celui des sauvegardes."""
    return Path(get_settings().backup_dir) / "plateforme"


def sauvegarder() -> Path:
    """Exporte la base `plateforme`, la vérifie par réimport, la range ; rend l'archive.

    Lève si l'export ou sa vérification échoue (`ImportRefuse` compris) : rien
    n'est alors rangé, et la rotation n'a pas lieu.
    """
    from app.utils.export_copropriete import exporter
    from app.utils.import_copropriete import verifier_archive

    metadata = registre_plateforme.metadata
    destination = dossier()
    destination.mkdir(parents=True, exist_ok=True)
    nom = nom_archive(horloge.maintenant(), PREFIXE)
    with tempfile.TemporaryDirectory() as travail:
        export = Path(travail) / nom
        exporter(moteur(), export, metadata=metadata)
        verifier_archive(export, Path(travail), metadata=metadata)
        archive = destination / nom
        shutil.move(export, archive)
    garder_les_dernieres(
        os.path.join(destination, f"{PREFIXE}*.tar.gz"), get_settings().backup_keep_versions
    )
    return archive


def run_sauvegarde_plateforme() -> None:
    """Tâche de la plateforme : la sauvegarde du registre, ou l'alerte qui dit son échec."""
    if not registre_actif():
        return
    try:
        archive = sauvegarder()
    except Exception as exc:  # noqa: BLE001 — l'échec se dit, la résidence n'en sait rien
        from app.utils.sante_plateforme import alerter

        logger.warning("registre : sauvegarde de la base plateforme en échec (%s)", exc)
        alerter([f"Sauvegarde de la base « plateforme » (registre) en échec : {exc}"])
        return
    logger.info("registre : base plateforme sauvegardée (%s)", archive.name)


def enregistrer(scheduler) -> None:
    """Pose la tâche dans le planificateur — appelé par `main.py`, à 03:30.

    Après la sauvegarde de la résidence (03:00, `BACKUP_HOUR`) : les deux ne se
    disputent pas le disque du nœud.
    """
    scheduler.add_job(
        run_sauvegarde_plateforme, "cron", hour=3, minute=30, id="sauvegarde_plateforme"
    )
