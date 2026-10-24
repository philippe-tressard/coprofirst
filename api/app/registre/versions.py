"""Quelle version publiée retenir — PUR, sans rien du projet (#2210).

Deux lecteurs, une seule règle :
- `registre/canaux` en tire la version cible de chaque vague et la liste proposée ;
- `scripts/ci/purge-paquets.sh` l'exécute comme un script (`python3 -I
  api/app/registre/versions.py garder`) pour savoir quelles releases et quelles
  images GHCR GARDER — tout ce qu'une vague peut encore servir.

Une version est tout objet qui porte `version` (« X.Y.Z ») et `publiee_le` (la date
de son tag, UTC naïf) : la ligne `VersionDisponible`, ou une `Publication` lue.
C'est pourquoi le module n'importe que la bibliothèque standard : un script de la CI
le lit sans installer l'application.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Protocol, TypeVar

#: Une version : `X.Y.Z`, celle d'un tag de `main` — jamais un commit.
MOTIF_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
#: L'attente standard : Pilote, Standard et Fixe ne reçoivent qu'une version de 7 jours.
ATTENTE_STANDARD = timedelta(days=7)
#: Le nombre de mineures proposées à l'opérateur, chacune à son dernier correctif.
VERSIONS_PROPOSEES = 5
#: Une version plus jeune se garde : elle sera la cible de Pilote ou de Standard
#: quand elle aura ses 7 jours. Le jour de plus couvre l'écart entre la lecture
#: nocturne des versions et la purge.
FENETRE_DE_GARDE = ATTENTE_STANDARD + timedelta(days=1)


class Versionnee(Protocol):
    version: str
    publiee_le: datetime


V = TypeVar("V", bound=Versionnee)


def semver(texte: Optional[str]) -> Optional[tuple[int, int, int]]:
    m = MOTIF_VERSION.match((texte or "").strip())
    if not m:
        return None
    majeure, mineure, correctif = m[0].split(".")
    return int(majeure), int(mineure), int(correctif)


def version_valide(texte: Optional[str]) -> bool:
    return semver(texte) is not None


def plus_recente(versions: Iterable[str]) -> Optional[str]:
    return max((v for v in versions if version_valide(v)), key=semver, default=None)


def derniere(versions: Iterable[V]) -> Optional[V]:
    """La dernière version publiée — la cible de la vague Urgence."""
    return max(
        (v for v in versions if version_valide(v.version)),
        key=lambda v: semver(v.version),
        default=None,
    )


def derniere_rodee(versions: Iterable[V], maintenant: datetime) -> Optional[V]:
    """La dernière version publiée depuis l'attente standard — la cible de Pilote."""
    return derniere(v for v in versions if maintenant - v.publiee_le >= ATTENTE_STANDARD)


def derniere_standard(versions: Iterable[V], maintenant: datetime) -> Optional[V]:
    """La cible de Standard : le dernier correctif, publié depuis l'attente standard, de
    la mineure qui précède la dernière mineure publiée (y-1 ; la dernière mineure de la
    majeure précédente quand y vaut 0).

    Si y-1 n'a encore aucun correctif de 7 jours — plusieurs mineures sortent parfois
    dans la semaine —, la dernière version rodée d'une mineure ANTÉRIEURE : sans ce
    repli, Standard ne trouverait rien tant que les mineures se suivent, et
    l'installation ne se mettrait plus jamais à jour."""
    versions = list(versions)
    mineures = sorted({s[:2] for s in map(semver, (v.version for v in versions)) if s})
    if len(mineures) < 2:
        return None
    visee = mineures[-2]
    return derniere_rodee(
        (v for v in versions if (semver(v.version) or (0, 0))[:2] <= visee), maintenant
    )


def versions_proposees(versions: Iterable[V]) -> list[V]:
    """Les `VERSIONS_PROPOSEES` dernières mineures, à leur dernier correctif, la plus
    récente en tête."""
    par_mineure: dict[tuple[int, int], V] = {}
    for v in versions:
        s = semver(v.version)
        if s is None:
            continue
        tenue = par_mineure.get(s[:2])
        if tenue is None or semver(tenue.version) < s:
            par_mineure[s[:2]] = v
    tries = sorted(par_mineure.values(), key=lambda v: semver(v.version), reverse=True)
    return tries[:VERSIONS_PROPOSEES]


def versions_a_garder(versions: Iterable[V], maintenant: datetime) -> set[str]:
    """Ce qu'une vague peut encore servir : la liste proposée, la cible de chaque vague
    du canal Urgence, et toute version plus jeune que `FENETRE_DE_GARDE`."""
    versions = [v for v in versions if version_valide(v.version)]
    gardees = {v.version for v in versions_proposees(versions)}
    for cible in (
        derniere(versions),
        derniere_rodee(versions, maintenant),
        derniere_standard(versions, maintenant),
    ):
        if cible is not None:
            gardees.add(cible.version)
    gardees |= {v.version for v in versions if maintenant - v.publiee_le < FENETRE_DE_GARDE}
    return gardees


# ── Le script de la purge ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Lue:
    version: str
    publiee_le: datetime


def date_utc(texte: str) -> datetime:
    """Une date ISO (« …Z » compris) en UTC naïf."""
    instant = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    if instant.tzinfo is not None:
        instant = instant.astimezone(timezone.utc).replace(tzinfo=None)
    return instant


def main(argv: list[str]) -> int:
    """`garder` : lit `[{"version", "publiee_le"}]` sur l'entrée, écrit une version à
    garder par ligne. Une entrée vide ou illisible échoue : ne rien garder purgerait tout.
    `fenetre` : la fenêtre de garde, en jours — celle des images sans version."""
    if argv == ["fenetre"]:
        print(FENETRE_DE_GARDE.days)
        return 0
    if argv != ["garder"]:
        print("usage : versions.py garder < versions.json | versions.py fenetre", file=sys.stderr)
        return 2
    lues = [Lue(e["version"], date_utc(e["publiee_le"])) for e in json.load(sys.stdin)]
    maintenant = datetime.now(timezone.utc).replace(tzinfo=None)
    gardees = versions_a_garder(lues, maintenant)
    if not gardees:
        print("aucune version à garder : la purge s'arrête", file=sys.stderr)
        return 1
    print("\n".join(sorted(gardees, key=semver)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
