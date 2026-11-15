"""Les versions des apps EN CIRCULATION, et le contrat que chacune a compilé (#2744).

## Pourquoi

Le serveur se déploie plusieurs fois par jour ; une app installée ne se met pas à
jour. L'iOS 1.0 restera des mois sur des iPhone : une route ou un champ qu'elle
emploie, retiré ou rendu incompatible, la casse chez les gens — et aucune nouvelle
version de l'app ne le rattrape à temps. `RETRAITS` (`retraits.py`) annonce un retrait
avant de le faire ; il ne sait pas qu'une app publiée s'en sert encore.

## La règle (arbitrée le 15/11/2026, socle `standards/09` §8 règle 4)

Rien de ce que le contrat d'une version publiée promettait ne disparaît ni ne change
de façon incompatible — opération, champ de réponse, entrée requise neuve —, tant
que cette version circule (version minimale imposée, ou part d'usage nulle d'après
la télémétrie par canal, #2726). Le jugement est celui du contrat lui-même
(`inventaire.comparer`), contre le contrat FIGÉ de chaque version :
`circulation/<app>-<version>.json`, la référence du serveur à son plancher.

Ajouter une version publiée : une entrée ici, et la référence de son plancher
recopiée (`git show v<plancher>:api/app/contrat/reference.json`). La retirer : quand
elle ne circule plus, et le dire dans son commit.

Une dérogation se DÉCLARE, datée, avec sa raison et son échéance — jamais à la main
dans une PR. Une dérogation qui ne sert plus, ou échue, fait échouer le contrôle.
🔒 `tests/test_contrat_versions_en_circulation.py`, dans la suite pytest (requise).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.contrat import inventaire as inv
from app.utils import horloge

DOSSIER = Path(__file__).with_name("circulation")


@dataclass(frozen=True)
class VersionPubliee:
    app: str  #: le dépôt de l'app
    version: str  #: sa version publiée
    plancher: str  #: la version du serveur sur laquelle elle s'est générée
    preuve: str  #: où se lit ce plancher

    @property
    def nom(self) -> str:
        return f"{self.app} {self.version}"

    @property
    def fichier(self) -> Path:
        return DOSSIER / f"{self.app}-{self.version}.json"


EN_CIRCULATION: tuple[VersionPubliee, ...] = (
    VersionPubliee(
        "coprofirst-ios",
        "1.0",
        "v3.89.0",
        "`scripts/generateurs/_plancher.py` de coprofirst-ios au commit f8bba99, qui "
        "constate la publication de la 1.0 (App Store)",
    ),
)

#: (nom de la version, cible) → (date, raison, échéance « AAAA-MM-JJ »). Une cible :
#: `GET /x`, `GET /x → $.champ` ou `GET /x ← corps.champ` (`inventaire.comparer`).
DEROGATIONS: dict[tuple[str, str], tuple[str, str, str]] = {}


def contrat_fige(version: VersionPubliee) -> dict:
    return json.loads(version.fichier.read_text(encoding="utf-8"))


def ruptures(
    courant: dict[str, dict],
    versions: tuple[VersionPubliee, ...] = EN_CIRCULATION,
    derogations: dict[tuple[str, str], tuple[str, str, str]] | None = None,
    aujourd_hui: date | None = None,
) -> list[str]:
    """Ce que le contrat courant casse d'une version en circulation, sans dérogation
    valide ; et les dérogations qui ne servent plus ou sont échues. Vide = conforme."""
    derogations = DEROGATIONS if derogations is None else derogations
    aujourd_hui = aujourd_hui or horloge.aujourd_hui()
    messages, servies = [], set()
    for v in versions:
        ecarts = inv.comparer(contrat_fige(v)["operations"], courant)
        for cible in ecarts.retraits + ecarts.exigences:
            cle = (v.nom, cible)
            if cle in derogations:
                servies.add(cle)
            else:
                messages.append(f"{v.nom} : {cible} — la version publiée s'en sert peut-être")
    for cle, (_, _, echeance) in derogations.items():
        if cle not in servies:
            messages.append(f"dérogation {cle} : ne sert plus — la retirer")
        elif date.fromisoformat(echeance) < aujourd_hui:
            messages.append(f"dérogation {cle} : échue le {echeance}")
    return messages
