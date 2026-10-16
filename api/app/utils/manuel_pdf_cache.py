"""Le manuel PDF, gardé SUR DISQUE — il survit au redémarrage (#1071).

## 🔴 Pourquoi (25/09/2026, arbitré par Philippe : « visualisation instantanée »)

Le cache en mémoire de `manuel_pdf` repartait vide à chaque mise en
production, et le premier lecteur d'après — celui qui vient voir ce qui a
changé — payait le rendu entier : 21 s mesurées sur le Raspberry Pi.

⚠️ Ce cache n'a AUCUNE invalidation à écrire, et c'est ce qui lève la réserve
d'origine (« pas d'invalidation à écrire, donc à oublier ») : le nom du fichier
EST l'empreinte de la clé — manuel, site, date. Un manuel modifié donne un autre
nom, donc un rendu neuf ; seul un PDF identique au caractère près est resservi.

## Où il vit, et pourquoi pas ailleurs

Dans le volume `app_data` (`CACHE_MANUEL_DIR`, `/app/data/cache-manuel-pdf`) :

- pas dans le volume `uploads` : il est servi en statique, un PDF posé là
  serait public ;
- la sauvegarde ne prend que la base et `uploads` — un cache n'a rien à y
  faire, et il n'y entre pas.

Aucune fonction d'ici ne lève : un disque plein ou en lecture seule coûte le
cache de demain, jamais le document d'aujourd'hui.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

_logger = logging.getLogger("hostachy.manuel")


def dossier_par_defaut() -> Path | None:
    """Le dossier du cache ; `None` quand `CACHE_MANUEL_DIR` est vide (pas de cache)."""
    from app.config import get_settings

    dossier = get_settings().cache_manuel_dir
    return Path(dossier) if dossier else None


def _fichier(dossier: Path, cle: tuple[str, ...]) -> Path:
    return dossier / (hashlib.sha256("\x1f".join(cle).encode("utf-8")).hexdigest() + ".pdf")


def lire(cle: tuple[str, ...], dossier: Path | None) -> bytes | None:
    """Le PDF déjà rendu pour cette clé, ou `None`."""
    if dossier is None:
        return None
    try:
        return _fichier(dossier, cle).read_bytes()
    except OSError:
        return None


def ecrire(cle: tuple[str, ...], pdf: bytes, dossier: Path | None, *, garder: int) -> None:
    """Écrit le PDF d'un bloc (fichier provisoire puis `replace`), garde les `garder` plus récents.

    ⚠️ D'un bloc : un lecteur qui tomberait sur un fichier à moitié écrit
    servirait un PDF tronqué — et le resservirait jusqu'à minuit.
    """
    if dossier is None:
        return
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        cible = _fichier(dossier, cle)
        provisoire = cible.with_suffix(".tmp")
        provisoire.write_bytes(pdf)
        provisoire.replace(cible)
        recents = sorted(dossier.glob("*.pdf"), key=lambda f: f.stat().st_mtime, reverse=True)
        for f in recents[garder:]:
            f.unlink(missing_ok=True)
    except OSError as exc:
        _logger.warning("Cache disque du manuel PDF inutilisable : %s", exc)
