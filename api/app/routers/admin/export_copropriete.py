"""Admin — l'export neutre de la copropriété, et la preuve qu'elle se restaure (#1749).

La règle vit dans `utils/export_copropriete.py`. Ces routes la servent DANS le
processus de l'API : c'est ce qui rend l'export sûr pendant que le site tourne
(règle d'or, CLAUDE.md) — jamais un `docker exec` qui ouvrirait la base à côté.
"""

import json
import os
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel

from app.auth.deps import require_admin
from app.config import get_settings
from app.models.core import Utilisateur
from app.utils import export_copropriete as ex
from app.utils import import_copropriete as im
from app.utils import horloge

router = APIRouter()

#: Préfixe des archives d'export : distinct de celui des sauvegardes
#: (`hostachy_backup_`), que leur rotation ne doit ni compter ni effacer.
PREFIXE = "export_copropriete_"
#: Les exports gardés dans le volume des sauvegardes — les plus récents.
GARDER = 3


class VerificationRestauration(BaseModel):
    restaurable: bool
    tables: int
    lignes: int
    revision: Optional[str] = None
    ignorees: list[str] = []
    ecarts: list[str] = []
    duree_secondes: float


@router.post("/export-copropriete/verifier", response_model=VerificationRestauration)
def verifier_restauration(_: Utilisateur = Depends(require_admin)):
    """Exporte la base et la réimporte dans une base jetable : se restaure-t-elle ?"""
    from app import contexte

    debut = time.monotonic()
    with tempfile.TemporaryDirectory() as dossier:
        try:
            manifeste, bilan = im.verifier_restauration(contexte.moteur(), Path(dossier))
            ecarts, restaurable = bilan.ecarts, True
        except im.ImportRefuse as refus:
            manifeste = {"tables": {}, "ignorees": [], "revision": None}
            ecarts, restaurable = [str(refus)], False
    tables = manifeste["tables"]
    return VerificationRestauration(
        restaurable=restaurable,
        tables=len(tables),
        lignes=sum(t["lignes"] for t in tables.values()),
        revision=manifeste.get("revision"),
        ignorees=manifeste.get("ignorees", []),
        ecarts=ecarts,
        duree_secondes=round(time.monotonic() - debut, 1),
    )


class ExportLance(BaseModel):
    archive: str


def _exporter(chemin: Path) -> None:
    from app import contexte
    from app.utils.stockage import stockage

    partiel = chemin.with_suffix(".partiel")
    ex.exporter(contexte.moteur(), partiel, fichiers=stockage().racine)
    os.replace(partiel, chemin)  # l'archive n'existe sous son nom qu'entière
    anciennes = sorted(chemin.parent.glob(f"{PREFIXE}*.tar.gz"))[:-GARDER]
    for vieille in anciennes:
        vieille.unlink(missing_ok=True)


@router.post("/export-copropriete", response_model=ExportLance, status_code=202)
def lancer_export(background_tasks: BackgroundTasks, _: Utilisateur = Depends(require_admin)):
    """Écrit l'archive complète — tables ET fichiers — dans le volume des sauvegardes."""
    dossier = Path(get_settings().backup_dir)
    dossier.mkdir(parents=True, exist_ok=True)
    nom = f"{PREFIXE}{horloge.a_paris(horloge.maintenant()):%Y%m%d_%H%M%S}_paris.tar.gz"
    background_tasks.add_task(_exporter, dossier / nom)
    return ExportLance(archive=nom)


class DernierExport(BaseModel):
    archive: Optional[str] = None
    octets: int = 0
    cree_le: Optional[str] = None
    tables: int = 0
    lignes: int = 0
    fichiers: int = 0


@router.get("/export-copropriete/dernier", response_model=DernierExport)
def dernier_export(_: Utilisateur = Depends(require_admin)):
    """Le dernier export ENTIER du volume des sauvegardes, lu dans son manifeste."""
    archives = sorted(Path(get_settings().backup_dir).glob(f"{PREFIXE}*.tar.gz"))
    if not archives:
        return DernierExport()
    derniere = archives[-1]
    with tarfile.open(derniere, "r:gz") as a:
        manifeste = json.loads(a.extractfile("manifeste.json").read())
    return DernierExport(
        archive=derniere.name,
        octets=derniere.stat().st_size,
        cree_le=manifeste.get("cree_le"),
        tables=len(manifeste["tables"]),
        lignes=sum(t["lignes"] for t in manifeste["tables"].values()),
        fichiers=len(manifeste.get("fichiers", [])),
    )
