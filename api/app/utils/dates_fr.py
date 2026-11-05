"""Formatage des dates en français, indépendant de la locale du système.

`strftime('%B')` (mois) et `%A` (jour) traduisent selon `LC_TIME`. L'image
`python:3.12-slim` ne génère **aucune** locale au-delà de C/POSIX : en production
le mois sortait donc en anglais — « Voté en AG 2026 — 12 June 2026 » sur la fiche
arrivant, un document destiné aux résidents et intégralement en français.

Générer une locale `fr_FR.UTF-8` dans le Dockerfile serait un correctif fragile :
il se reperdrait au premier changement d'image de base, ne protégerait pas les
tests lancés hors conteneur, et laisserait le piège en place pour le prochain
`%B` écrit ailleurs. On formate donc depuis une table explicite — le résultat ne
dépend plus de l'environnement d'exécution.

**Ne jamais utiliser `%B`, `%b`, `%A` ni `%a` dans ce projet** : passer par
`date_longue()` / `datetime_longue()`. `tests/test_dates_fr.py` échoue si un
format dépendant de la locale réapparaît dans `app/`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from app.utils import horloge

MOIS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)

JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def libelle_exercice(mois_debut: int | None) -> str:
    """L'exercice comptable d'une copropriété, d'après son mois de début (#1643).

    « année civile », « de juillet à juin ». `None` (ou un mois hors de 1 à 12)
    vaut janvier, comme partout au serveur (`synthese_affaire.metriques`).

    Servi par `CoproprieteRead.exercice_libelle` (#2505) : la fiche du site et
    celle de l'app iOS le LISENT — le front le composait seul (`libelleExercice`).
    """
    m = mois_debut if mois_debut and 1 <= mois_debut <= 12 else 1
    if m == 1:
        return "année civile"
    return f"de {MOIS[m - 1]} à {MOIS[(m - 2) % 12]}"


def date_longue(d: date | datetime) -> str:
    """`date(2026, 7, 25)` → `25 juillet 2026`."""
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def datetime_longue(dt: datetime) -> str:
    """`datetime(2026, 7, 25, 9, 5)` → `25 juillet 2026 à 09:05`.

    Remplace `strftime('%-d %B %Y à %H:%M')` (mois anglais hors locale fr, et
    `%-d` est une extension glibc absente sous Windows).
    """
    return f"{date_longue(dt)} à {dt:%H:%M}"


def jour_longue(d: date | datetime) -> str:
    """`date(2026, 7, 25)` → `samedi 25 juillet 2026`."""
    return f"{JOURS[d.weekday()]} {date_longue(d)}"


def date_courte(d: date | datetime) -> str:
    """`date(2026, 7, 25)` → `25/07/2026`.

    Format numérique pour les tableaux et documents denses (historiques de
    tickets). Indépendant de la locale — aucun nom de mois — mais centralisé ici
    pour que tout formatage de date destiné à l'affichage passe par ce module.
    """
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def datetime_longue_paris(dt: datetime) -> str:
    """Horodatage **naïf UTC** (tel que stocké en base) → texte français heure de Paris.

    `datetime(2026, 7, 25, 8, 5)` → `25 juillet 2026 à 10:05`.

    Était dupliqué à l'identique sous le nom `_fmt_paris` dans `routers/tickets.py`
    et `routers/publications.py` (corps des e-mails). Les horodatages de la base
    sont naïfs et en UTC : la conversion vit dans `horloge.a_paris` (#1565), pour
    que le décalage ne soit pas réécrit à chaque point d'appel.
    """
    return datetime_longue(horloge.a_paris(dt))


def mois_ecoules(depuis: datetime, maintenant: datetime | None = None) -> int:
    """Nombre de mois **entiers** écoulés depuis `depuis` (horodatage naïf UTC).

    Compte des mois calendaires, pas des tranches de 30 jours : entre le 31/01 et
    le 28/02 il s'est écoulé un mois, ce qu'une division par 30 jours nierait.
    """
    ref = maintenant or horloge.maintenant()
    mois = (ref.year - depuis.year) * 12 + (ref.month - depuis.month)
    if (ref.day, ref.hour, ref.minute) < (depuis.day, depuis.hour, depuis.minute):
        mois -= 1
    return max(0, mois)


def formule_anciennete(mois: list[int]) -> str:
    """Formule française décrivant l'ancienneté d'un lot de dossiers.

    `[1]` → « plus d'un mois » · `[4, 4]` → « plus de 4 mois » · `[1, 5]` → « un à 5 mois »

    Sert le préambule de la relance syndic : un chiffre exact se conteste mal,
    alors qu'un « depuis un certain temps » s'ignore sans effort. La forme au
    pluriel n'est employée que si elle est vraie — annoncer « 3 à 3 mois » ou
    « plus de 1 mois » décrédibiliserait le reste du courrier.

    Volontairement brève : la même formule alimente le corps ET l'objet du mail,
    que les clients de messagerie tronquent vers 70 caractères. Une seule
    formule, donc, plutôt qu'une version longue et une version courte à tenir
    d'accord.
    """
    if not mois:
        return "plus d'un mois"
    mini, maxi = min(mois), max(mois)
    if maxi < 2:
        return "plus d'un mois"
    if mini == maxi:
        return f"plus de {maxi} mois"
    if mini < 2:
        return f"un à {maxi} mois"
    return f"{mini} à {maxi} mois"


def duree_jhm(ecart: timedelta) -> str | None:
    """Une durée écoulée, en `00j23h54'`. `None` si elle n'a pas de sens.

    >>> duree_jhm(timedelta(hours=23, minutes=54))
    "00j23h54'"
    >>> duree_jhm(timedelta(days=2, hours=3, minutes=15))
    "02j03h15'"

    🔴 POURQUOI CE FORMAT (01/09/2026, demandé à l'écran). Le fil affichait
    « Résolu en 23.9h » : un arrondi décimal d'heures, qui n'a de sens nulle part
    ailleurs sur le site et qu'il faut convertir de tête pour savoir qu'il s'agit
    de 23 h 54. Le point décimal était en prime un point, pas une virgule, sur un
    site intégralement en français.

    ⚠️ **Les UNITÉS sont portées, pas devinées** — `00j23h54'` et non
    `00:23:54` (demandé le 01/09/2026, peu après le premier format). Trois
    nombres séparés par des deux-points se lisent spontanément `hh:mm:ss` :
    « 00:00:30 » voulait dire trente MINUTES et se lisait trente secondes. Les
    unités lèvent l'ambiguïté sans allonger.

    ⚠️ Écrit ICI et non dans le routeur qui l'affiche : une durée est un format,
    et un format réimplémenté dans une page est ce que `test_dates_fr.py` et
    `npm run lint:dates` existent pour empêcher. Deux endroits calculent déjà une
    durée de résolution (`flux/tickets.py` et `flux/sante.py`) — le second n'a
    pas encore de lecteur, mais le jour où il en aura un, le format sera le même.

    ## Ce qu'elle rend `None`, et pourquoi ce n'est pas zéro

    Une durée **négative** (fermeture antérieure à la création) est une donnée
    incohérente : l'afficher « -1j00h00' » habillerait le défaut au lieu de le
    taire. L'appelant décide alors de ne rien montrer.

    ⚠️ Zéro, en revanche, est une durée VALIDE — un ticket résolu dans la minute.
    Elle rend donc `"00j00h00'"`, et pas `None` : c'est le cas zéro de cette
    fonction, et le distinguer de l'incohérence est tout son objet. L'ancien code
    écrivait `if duree`, ce qui traitait les deux pareil et faisait disparaître
    la mention pour une résolution immédiate.
    """
    secondes = int(ecart.total_seconds())
    if secondes < 0:
        return None
    jours, reste = divmod(secondes, 86400)
    heures, reste = divmod(reste, 3600)
    minutes = reste // 60
    return f"{jours:02d}j{heures:02d}h{minutes:02d}'"
