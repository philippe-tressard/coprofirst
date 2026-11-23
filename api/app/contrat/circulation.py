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
que cette version circule. Le jugement est celui du contrat lui-même
(`inventaire.comparer`), contre le contrat FIGÉ de chaque version :
`circulation/<app>-<version>.json`, la référence du serveur à son plancher, à l'octet
(`git show <plancher>:api/app/contrat/reference.json`). Ce que ce juge ne voit pas
est déclaré, et vérifié aveugle : `inventaire.LIMITES` (#2970).

## Ce qui est « publié » (#2919, tranché le 23/11/2026)

Toute version qu'un magasin distribue hors du poste de développement : la production
(App Store, Google Play), et AUSSI une piste de test fermée — ses testeurs ont l'app
installée et ne la mettent pas à jour à volonté. Chaque version distribuée porte dans
le dépôt de son app une étiquette `vX.Y.Z` ; une étiquette sans entrée ici (ni dans
`SORTIES`) fait échouer la CI : `api/scripts/check_versions_en_circulation.py`, qui
vérifie aussi que chaque contrat figé est bien la référence de son plancher.

## Quand une version sort (#2970)

Aucune mesure ne dit aujourd'hui qu'une version n'est plus employée : la télémétrie
par canal (#2726) ne retient pas la version de l'app, et le serveur n'impose aucune
version minimale. Une version de PRODUCTION ne sort donc pas. Seule une version de
TEST sort, quand sa piste ne la distribue plus (testeurs passés à la suivante) : une
entrée dans `SORTIES`, datée, avec sa preuve — comme `preuve` à l'ajout. Le jour où
une mesure existera (version de l'app dans le lot d'audience, ou version minimale
servie par `GET /config`), elle deviendra la preuve admise pour la production.

Une dérogation se DÉCLARE, datée, avec sa raison et son échéance — jamais à la main
dans une PR. Une dérogation qui ne sert plus, ou échue, fait échouer le contrôle.
🔒 `tests/test_contrat_versions_en_circulation.py`, dans la suite pytest (requise).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.contrat import inventaire as inv
from app.utils import horloge

DOSSIER = Path(__file__).with_name("circulation")

#: Les dépôts des apps qui lisent le contrat — ceux dont les étiquettes se relisent.
APPS = ("coprofirst-ios", "coprofirst-android")

#: Une étiquette de version distribuée ; les autres (`archive/…`) ne disent rien.
ETIQUETTE_VERSION = re.compile(r"^v\d+\.\d+\.\d+$")


@dataclass(frozen=True)
class VersionPubliee:
    app: str  #: le dépôt de l'app
    version: str  #: sa version publiée
    plancher: str  #: la version du serveur sur laquelle elle s'est générée
    preuve: str  #: où se lit ce plancher
    etiquette: str  #: l'étiquette `vX.Y.Z` qui la marque dans le dépôt de l'app
    canal: str  #: le magasin et la piste qui la distribuent

    @property
    def nom(self) -> str:
        return f"{self.app} {self.version}"

    @property
    def fichier(self) -> Path:
        return DOSSIER / f"{self.app}-{self.version}.json"


@dataclass(frozen=True)
class VersionSortie:
    app: str
    etiquette: str
    le: str  #: « JJ/MM/AAAA »
    preuve: str  #: ce qui montre qu'elle n'est plus distribuée ni employée


EN_CIRCULATION: tuple[VersionPubliee, ...] = (
    VersionPubliee(
        "coprofirst-ios",
        "1.0",
        "v3.89.0",
        "`scripts/generateurs/_plancher.py` de coprofirst-ios au commit f8bba99, qui "
        "constate la publication de la 1.0 (App Store)",
        "v1.0.0",
        "App Store",
    ),
    VersionPubliee(
        "coprofirst-ios",
        "1.1",
        "v3.103.0",
        "`scripts/generateurs/_plancher.py` à l'étiquette v1.1.0 de coprofirst-ios "
        '(`VERSION = "v3.103.0"`, contrat 2.0.0) ; en ligne sur l\'App Store le '
        "18/11/2026 (coprofirst-ios#263)",
        "v1.1.0",
        "App Store",
    ),
    VersionPubliee(
        "coprofirst-android",
        "0.8.173",
        "v3.109.0",
        "`contrat/plancher.env` à l'étiquette v0.8.173 de coprofirst-android "
        "(`PLANCHER=v3.109.0`, contrat 2.4.0), « soumise au Play Store »",
        "v0.8.173",
        "Google Play, test fermé",
    ),
)

#: Les versions qui ne circulent plus, et la preuve qui l'établit (voir « Quand une
#: version sort »). Son étiquette reste dans le dépôt de l'app : elle se lit ici.
SORTIES: tuple[VersionSortie, ...] = ()

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


def etiquettes_non_declarees(
    etiquettes: dict[str, list[str]],
    versions: tuple[VersionPubliee, ...] | None = None,
    sorties: tuple[VersionSortie, ...] | None = None,
) -> list[str]:
    """PURE. `etiquettes` : les étiquettes lues dans le dépôt de chaque app de `APPS`.

    Rend les écarts : une étiquette de version sans entrée (ni en circulation, ni
    sortie) ; une entrée dont l'étiquette n'existe pas (déclaration inventée ou
    mal recopiée) ; une version déclarée deux fois. Vide = conforme.
    """
    versions = EN_CIRCULATION if versions is None else versions
    sorties = SORTIES if sorties is None else sorties
    declarees = [(v.app, v.etiquette) for v in versions] + [(s.app, s.etiquette) for s in sorties]
    messages = [
        f"{a} {e} : déclarée deux fois"
        for a, e in sorted(set(declarees))
        if declarees.count((a, e)) > 1
    ]
    for app in APPS:
        lues = {e for e in etiquettes.get(app, []) if ETIQUETTE_VERSION.match(e)}
        connues = {e for a, e in declarees if a == app}
        messages += [
            f"{app} {e} : étiquette d'une version distribuée, sans entrée dans "
            "EN_CIRCULATION ni SORTIES (app/contrat/circulation.py)"
            for e in sorted(lues - connues)
        ]
        messages += [
            f"{app} {e} : déclarée, mais aucune étiquette ne la porte"
            for e in sorted(connues - lues)
        ]
    return messages
