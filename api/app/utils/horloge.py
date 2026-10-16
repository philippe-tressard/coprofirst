"""**L'heure du serveur, écrite une fois.**

## Pourquoi ce module (#1047, 25/09/2026)

`datetime.utcnow()` était appelé **114 fois** dans `app/` — dont 51 en
`default_factory` de modèle —, sans helper. Il est **déprécié depuis Python
3.12**, l'image de l'API (`python:3.12-slim`), et chaque appel émet un
`DeprecationWarning` : le jour où il disparaîtra, ce sont 114 lignes à
reprendre, et on en manquera.

## 🔴 UTC NAÏF — et c'est voulu

Le ticket proposait `datetime.now(timezone.utc)`. Ce n'est **pas** un
remplacement : `utcnow()` rend une date **naïve** (sans fuseau), `now(utc)` une
date **consciente**, et Python refuse de comparer les deux (`TypeError`).

Or tout ce que la base rend est naïf — ses colonnes sont sans fuseau —, et le
dépôt entier tient cette convention : `whatsapp_scheduler`,
`telemetry_aggregation`, `courriel_boite` et `telemetry` ramènent explicitement
leurs dates à l'UTC naïf par `.replace(tzinfo=None)`. Passer d'un coup à des
dates conscientes aurait fait lever chaque comparaison entre « maintenant » et
une date lue en base.

`maintenant()` rend donc **exactement** ce que rendait `utcnow()`, sans
l'avertissement. Passer aux dates conscientes serait une autre décision — base,
modèles et comparaisons ensemble —, pas un remplacement de fonction.

🔒 Ruff `DTZ003` refuse `utcnow()` dans `api/app/` (CI, job `lint-backend`).

⚠️ **S'appelle par son module** — `horloge.maintenant()`, jamais importée seule :
treize fichiers ont déjà une variable ou un paramètre nommé `maintenant`
(`maintenant = maintenant or …`), qu'une fonction du même nom aurait masqué.

## Une question, une fonction (#1565, 02/10/2026)

| La question | La réponse |
|---|---|
| quel **instant**, pour la base ? | `maintenant()` — UTC naïf |
| quel **jour** est-on pour le résident ? (calendrier, échéance, date affichée) | `aujourd_hui()` — le jour de Paris |
| quel jour était-ce, à Paris, à cet instant de la base ? | `jour_civil(instant)` |
| quelle heure est-il / était-il à Paris ? (fenêtre d'envoi, minuit, libellé) | `a_paris(instant)` — conscient |
| quelle borne UTC pour « depuis le début du jour » à Paris ? (requête sur `_le`) | `debut_du_jour_utc(jour=None)` — UTC naïf (#1617) |

Deux « aujourd'hui » coexistaient : `date.today()` (dix fois — le jour du
**conteneur**, parisien en production par `TZ=Europe/Paris` et UTC sur un poste
ou une CI qui ne le pose pas) et `maintenant().date()` (le jour **UTC**). Entre
minuit et deux heures à Paris, ils diffèrent d'un jour : une délégation commencée
« aujourd'hui » se comparait au jour UTC, une actualité périmait à 02:00.

Le jour du résident est celui de Paris, et il se calcule depuis `maintenant()` :
il ne dépend plus du fuseau du conteneur, et figer `maintenant` dans un test
fige aussi le jour. `TZ_PARIS` est le seul endroit où le fuseau se nomme — le
planificateur (`backup.setup_scheduler`) compris.

🔒 `test_horloge.py` refuse, hors de ce module, `date.today`, `datetime.today`,
`datetime.now` sans fuseau — appelés **ou** référencés, la forme
`default_factory` qu'aucune règle Ruff ne voit — et `maintenant.date()` ; et
« Europe/Paris » écrit ailleurs qu'ici — et, depuis #1617, un minuit recomposé
(`replace(hour=0…)`) puis converti de fuseau dans une même fonction.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

#: Le fuseau du résident — et du planificateur. Nommé ici, et nulle part ailleurs.
TZ_PARIS = ZoneInfo("Europe/Paris")


def maintenant() -> datetime:
    """L'instant présent, en **UTC naïf** — la forme de toutes les dates en base.

    Sert aussi de `default_factory` : `Field(default_factory=horloge.maintenant)`.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def a_paris(instant: datetime) -> datetime:
    """Un instant — UTC naïf comme en base, ou conscient — à l'heure de Paris (conscient).

    Conscient à dessein : rendu naïf, il serait repris pour de l'UTC à la
    première comparaison avec une date de la base, deux heures plus loin.
    """
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(TZ_PARIS)


def de_paris(heure_murale: datetime) -> datetime:
    """Une heure MURALE de Paris (naïve, lue dans un nom de fichier) en UTC naïf.

    Le sens inverse de `a_paris` : ce qu'on écrit à l'heure de Paris se relit
    pour être comparé à une date de la base. Pendant l'heure répétée du passage à
    l'heure d'hiver, la première occurrence est retenue (`fold=0`).
    """
    return heure_murale.replace(tzinfo=TZ_PARIS).astimezone(timezone.utc).replace(tzinfo=None)


def jour_civil(instant: date | datetime) -> date:
    """Le jour qu'il était **à Paris** à cet instant de la base (UTC naïf).

    Une `date` est déjà un jour civil : elle est rendue telle quelle — ce qui
    laisse un appelant accepter l'un ou l'autre (« affiché le », nom de fichier).
    ⚠️ `datetime` hérite de `date` : c'est lui qu'on teste.
    """
    if not isinstance(instant, datetime):
        return instant
    return a_paris(instant).date()


def aujourd_hui() -> date:
    """Le jour qu'il est pour le résident — celui de Paris, quel que soit le conteneur.

    Sert aussi de `default_factory` : `Field(default_factory=horloge.aujourd_hui)`.
    Tiré de `maintenant()` (cherché à l'appel) : figer l'un fige l'autre.
    """
    return jour_civil(maintenant())


def debut_du_jour_utc(jour: date | datetime | None = None) -> datetime:
    """Minuit **de Paris** du jour demandé, en **UTC naïf** — la borne d'une requête sur `_le`.

    Les colonnes de date sont en UTC naïf ; « depuis le début du jour » pour le
    résident est minuit à Paris, soit 22 h ou 23 h UTC la veille selon la saison.
    Comparer à `maintenant().replace(hour=0…)` serait la borne du jour UTC (#1617).

    `jour` : un `datetime` — UTC naïf comme en base, ou conscient — se lit au jour
    qu'il était à Paris (`jour_civil`) ; une `date` est ce jour-là ; rien, c'est
    aujourd'hui (`aujourd_hui`). Un jour de changement d'heure est traité par le
    fuseau : minuit n'y est jamais ambigu, la bascule a lieu la nuit, à 2 h ou 3 h.
    """
    jour = aujourd_hui() if jour is None else jour_civil(jour)
    minuit = datetime(jour.year, jour.month, jour.day, tzinfo=TZ_PARIS)
    return minuit.astimezone(timezone.utc).replace(tzinfo=None)
