"""La clé et l'état d'inscription de CETTE installation — volume `app_data` (R2 #1878).

Arbitrage du 13/10/2026 : ils appartiennent à l'INSTALLATION, pas à une
copropriété ; ils vivent dans `INSTALLATION_DIR` (`/app/data/installation/`, le
volume persistant de l'API) — jamais dans une image, ni dans une base de
copropriété.

| Fichier | Contenu |
|---|---|
| `cle_privee` | la clé Ed25519 de l'installation, 32 octets en base64, droits 0600 |
| `inscription.json` | identifiant attribué, bail signé, plus haute époque reçue, contact de l'administrateur, dernier renouvellement |

Copier ce dossier copie l'IDENTITÉ de l'installation : deux machines sous une
même clé sont indiscernables pour la référence. Deux clés sous un même
identifiant, elles, sont un clone qu'elle signale (§4.11, règle 1).

Écriture ATOMIQUE (fichier temporaire puis `os.replace`) : un arrêt au milieu ne
laisse jamais un état à moitié écrit. Un état illisible se lit comme « non
inscrite », et se DIT (`illisible`) — jamais une exception qui arrête l'API.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.registre import signature

logger = logging.getLogger("hostachy.inscription")

CLE = "cle_privee"
ETAT = "inscription.json"


class Contact(BaseModel):
    """L'administrateur de l'installation — gardé ici pour l'afficher et le rectifier."""

    prenom: str
    nom: str
    courriel: str
    telephone: Optional[str] = None


class EtatLocal(BaseModel):
    """Ce que l'installation sait d'elle-même — tout est facultatif : rien n'est acquis."""

    identifiant: Optional[str] = None
    etat_inscription: Optional[str] = None  #: ce que la référence a répondu à l'inscription
    bail: Optional[dict] = None  #: le `BailSigne` reçu, tel quel
    plus_haute_epoque: int = 0
    conditions_acceptees: Optional[int] = None
    contact: Optional[Contact] = None
    inscrite_le: Optional[str] = None
    dernier_renouvellement_le: Optional[str] = None
    derniere_erreur: Optional[str] = None
    #: vrai quand le fichier existait mais ne se lisait pas
    illisible: bool = False


def dossier() -> Path:
    return Path(get_settings().installation_dir)


def _ecrire_atomique(chemin: Path, contenu: bytes, mode: int = 0o600) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    provisoire = chemin.with_name(chemin.name + ".provisoire")
    descripteur = os.open(provisoire, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(descripteur, "wb") as f:
        f.write(contenu)
    os.replace(provisoire, chemin)


def cle_privee() -> Ed25519PrivateKey:
    """La clé de l'installation — créée au premier appel, relue ensuite.

    Un fichier présent mais illisible LÈVE : en générer une autre changerait
    l'identité de l'installation sans que personne l'ait décidé.
    """
    chemin = dossier() / CLE
    if chemin.exists():
        cle = signature.privee_de(chemin.read_text(encoding="ascii", errors="replace"))
        if cle is None:
            raise ValueError(f"clé de l'installation illisible : {chemin}")
        return cle
    cle, _ = signature.generer_paire()
    _ecrire_atomique(chemin, signature.en_base64(cle).encode("ascii"))
    logger.info("inscription : clé de l'installation créée")
    return cle


def cle_existe() -> bool:
    return (dossier() / CLE).exists()


def lire() -> EtatLocal:
    """L'état rangé, ou un état vide — `illisible` quand le fichier ne se lit pas."""
    chemin = dossier() / ETAT
    if not chemin.exists():
        return EtatLocal()
    try:
        return EtatLocal.model_validate(json.loads(chemin.read_text(encoding="utf-8")))
    except (OSError, ValueError, ValidationError) as exc:
        logger.warning("inscription : état illisible (%s)", type(exc).__name__)
        return EtatLocal(illisible=True)


def ecrire(etat: EtatLocal) -> None:
    """Range l'état, atomiquement. `illisible` n'est jamais écrit : il se constate."""
    corps = etat.model_dump(mode="json", exclude={"illisible"})
    _ecrire_atomique(
        dossier() / ETAT, json.dumps(corps, ensure_ascii=False, indent=1).encode("utf-8")
    )
