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

## Sa copie hors site (#1896)

`export-hors-site.sh`, lancé depuis le poste, tire aussi la dernière archive du
registre et rend compte dans le rapport de l'export (`archive_plateforme`,
`integrite_plateforme`). Ce rapport est rangé chez la copropriété servie — c'est
le canal qui existe —, mais il ne la concerne pas : son contrôle de 06:00 ne lit
que `archive` et `integrite`. C'est `probleme_copie_hors_site`, appelé par le
contrôle de la PLATEFORME, qui juge la copie du registre et prévient l'opérateur.
Il ne lit dans la base d'une copropriété que ce rapport technique, sans donnée
personnelle (D5).
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

from app import contexte
from app.config import get_settings
from app.registre import base
from app.registre.modeles import registre_plateforme
from app.utils import horloge
from app.utils.backup import garder_les_dernieres, horodatage_archive, nom_archive

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
        exporter(base.moteur(), export, metadata=metadata)
        verifier_archive(export, Path(travail), metadata=metadata)
        archive = destination / nom
        shutil.move(export, archive)
    garder_les_dernieres(
        os.path.join(destination, f"{PREFIXE}*.tar.gz"), get_settings().backup_keep_versions
    )
    return archive


def run_sauvegarde_plateforme() -> None:
    """Tâche de la plateforme : la sauvegarde du registre, ou l'alerte qui dit son échec."""
    if not base.registre_actif():
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


def probleme_copie_hors_site() -> list[str]:
    """La copie hors site du registre est-elle là, saine et fraîche ? Rien si oui.

    Sans objet hors de la référence dont le registre est allumé. Sinon, le
    dernier rapport d'export de chaque copropriété servie : la plus récente
    archive du registre qu'ils disent avoir copiée, jugée au seuil de la copie
    de la résidence (`health_monitor.seuil_copie_hors_site_h`).
    """
    if not base.registre_actif():
        return []
    from app.utils.health_monitor import derniere_copie_hors_site, seuil_copie_hors_site_h

    retenue: tuple = (None, "", "")  # (horodatage, archive, intégrité)
    for copro in contexte.coproprietes():
        with contexte.dans(copro):
            session = contexte.nouvelle_session()
            try:
                _rapport, details = derniere_copie_hors_site(session)
            finally:
                session.close()
        nom = details.get("archive_plateforme") or ""
        quand = horodatage_archive(nom, PREFIXE) if nom else None
        if quand is not None and (retenue[0] is None or quand > retenue[0]):
            retenue = (quand, nom, details.get("integrite_plateforme") or "")
    quand, nom, integrite = retenue
    if quand is None:
        return [
            "Aucune copie hors site de la base « plateforme » (registre) n'a été "
            "rapportée : elle n'existe que sur les deux nœuds. Lancer "
            "export-hors-site.cmd depuis le poste."
        ]
    problemes = []
    if integrite != "ok":
        problemes.append(
            f"La copie hors site du registre ({nom}) n'a pas passé sa vérification : "
            f"{integrite or 'verdict absent'}."
        )
    seuil_h = seuil_copie_hors_site_h()
    age = horloge.maintenant() - quand
    if age.total_seconds() > seuil_h * 3600:
        problemes.append(
            f"La copie hors site du registre date de {int(age.total_seconds() // 86400)} "
            f"jours ({nom}) — seuil : {seuil_h // 24} jours."
        )
    return problemes


def restaurer(archive: Path, cible):
    """Réimporte une archive du registre dans une base `plateforme` NEUVE (#1972).

    Les deux nœuds perdus : la copie hors site rend l'archive, et rien ne savait
    la réimporter — `export_copropriete importer` ne connaît que les tables d'une
    copropriété. Même règle que `schema_initial` : une base est neuve si elle n'a
    AUCUNE table ; sinon refus, avant tout geste. Puis la chaîne de migrations de
    la plateforme (`alembic_plateforme`, qui la marque à sa tête), puis l'import
    vérifié — transactionnel : un écart laisse la base au schéma seul.

    ⚠️ À faire AVANT que l'API démarre sur cette base : son démarrage y inscrit la
    référence (`migrer.preparer`), et la base ne serait plus neuve.
    Rend le `Bilan` de l'import ; lève `ImportRefuse`.
    """
    from sqlalchemy import inspect

    from app.registre import migrer
    from app.utils.import_copropriete import ImportRefuse, importer

    with cible.connect() as connexion:
        deja = inspect(connexion).get_table_names()
    if deja:
        raise ImportRefuse(
            f"la base cible n'est pas neuve ({len(deja)} table(s), dont {sorted(deja)[0]}) : "
            "le registre ne se restaure que dans une base `plateforme` vide"
        )
    migrer.migrer(cible)
    #  Clés NON différées : ses tables n'ont pas de cycle (toutes visent
    #  `installation`), et son rôle n'est pas superutilisateur — PostgreSQL lui
    #  refuserait le report (`dialecte.differer_cles_etrangeres`).
    return importer(archive, cible, metadata=registre_plateforme.metadata, cles_differees=False)


if __name__ == "__main__":
    import sys

    from sqlmodel import create_engine

    from app.utils.export_copropriete import adresse
    from app.utils.import_copropriete import ImportRefuse, resume

    if len(sys.argv) != 4 or sys.argv[1] != "restaurer":
        sys.exit(
            "usage : python -m app.registre.sauvegarde restaurer <archive> <url-cible>\n"
            "        (l'URL peut s'écrire env:NOM — PLATEFORME_DATABASE_URL, lue dans "
            "l'environnement)"
        )
    _cible = create_engine(adresse(sys.argv[3]))
    try:
        _bilan = restaurer(Path(sys.argv[2]), _cible)
    except ImportRefuse as _refus:
        sys.exit(f"RESTAURATION REFUSÉE : {_refus}")
    finally:
        _cible.dispose()
    print("\n".join(resume(_bilan)))
