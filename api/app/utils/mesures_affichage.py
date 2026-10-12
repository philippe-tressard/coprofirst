"""Combien de temps les résidents attendent un écran — mesuré chez eux (#1632).

## Pourquoi (03/10/2026)

« Le site rame » se diagnostiquait à la main, mesure par mesure (origine,
chemin, poste). Rien ne disait combien de temps un résident attend réellement
un écran, ni sur quelles pages.

## Ce qui est mesuré

Le navigateur (`mesurerNavigation`, `front/src/lib/telemetry.ts`) poste, par la
file de la mesure d'audience, un événement `action = ACTION_MESURE` dont
`detail` vaut `<indicateur>:<millisecondes>` :

- `chargement` — de l'ouverture de l'onglet à l'écran prêt (application
  hydratée), à la première page seulement ;
- `navigation` — d'un écran au suivant, dans l'application ;
- `donnees` (#1846) — du même début jusqu'aux données principales de l'écran
  affichées, que l'écran déclare (`marquerDonneesAffichees`). Les deux premiers
  s'arrêtent à l'hydratation : ils ne voyaient que la moitié de l'attente.

Mesuré partout de la même façon — le LCP des navigateurs Chromium
n'existe pas sous Safari, et une moitié de téléphones manquerait.

## Ce qui est stocké

Une ligne par mesure — un centile ne se calcule pas sur des compteurs —, au
jour près, sans identifiant de compte, la page aux identifiants masqués
(`/tickets/#`) pour que mille affaires fassent une ligne de synthèse. Une
valeur hors de `[0, DUREE_MAX_MS]` ou un indicateur inconnu ne s'enregistre
pas : le client du site n'en envoie pas.

## Durée

`CONSERVATION_JOURS`, purgées par l'agrégation quotidienne — ce que dit la
politique de confidentialité (`seed/contenus_legaux.TELEMETRIE_PERFORMANCE`).
"""

import math
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlmodel import Session, delete, select

from app.models.telemetrie import MesureAffichage
from app.utils import horloge

#  `CONSERVATION_JOURS` : celle des erreurs, et pas une seconde valeur — la
#  politique de confidentialité et le tableau de bord (`_depuis`) les disent ensemble.
from app.utils.erreurs_navigateur import CONSERVATION_JOURS

#: L'action d'une mesure. ⚠️ Tenue à la main avec `ACTION_MESURE` de
#: `front/src/lib/telemetry.ts` : le front et l'API ne partagent aucun fichier.
ACTION_MESURE = "perf"

#: Les indicateurs reconnus — ⚠️ même liste qu'`INDICATEURS` de
#: `front/src/lib/telemetry.ts`, que `test_mesures_affichage.py` compare.
INDICATEURS = ("chargement", "navigation", "donnees")

#: Au-delà, ce n'est plus un écran lent, c'est un onglet laissé en arrière-plan.
DUREE_MAX_MS = 60_000

#: Les pages rendues au tableau de bord, les plus lentes d'abord.
PAGES_AFFICHEES = 20


def lire_mesure(detail: str | None) -> tuple[str, int] | None:
    """« navigation:340 » → (« navigation », 340) ; `None` pour tout le reste."""
    indicateur, _, brut = (detail or "").partition(":")
    if indicateur not in INDICATEURS or not brut.isdigit():
        return None
    duree = int(brut)
    return (indicateur, duree) if duree <= DUREE_MAX_MS else None


def enregistrer_mesure(session: Session, page: str, detail: str | None, instant: datetime) -> None:
    """Enregistre une mesure valide — sans `commit`, que fait l'appelant pour tout son lot."""
    mesure = lire_mesure(detail)
    if mesure is None:
        return
    indicateur, duree = mesure
    session.add(
        MesureAffichage(
            jour=horloge.jour_civil(instant).isoformat(),
            page=page,
            indicateur=indicateur,
            duree_ms=duree,
        )
    )


def centile(valeurs: list[int], q: float) -> int:
    """Le centile `q` (0 < q ≤ 1) au RANG le plus proche — une valeur mesurée,
    jamais une interpolation : « 75 % des écrans en moins de 1 200 ms » doit
    désigner un écran qui a vraiment mis 1 200 ms."""
    triees = sorted(valeurs)
    return triees[max(0, math.ceil(q * len(triees)) - 1)]


def _resume(valeurs: list[int]) -> dict:
    return {
        "mesures": len(valeurs),
        "mediane": centile(valeurs, 0.5),
        "p75": centile(valeurs, 0.75),
    }


def synthese_mesures(session: Session, depuis: date) -> dict:
    """Médiane et 75ᵉ centile depuis `depuis` (inclus) : par indicateur, puis par
    page et indicateur, les plus lentes (75ᵉ centile) d'abord."""
    lignes = session.exec(
        select(MesureAffichage.page, MesureAffichage.indicateur, MesureAffichage.duree_ms).where(
            MesureAffichage.jour >= depuis.isoformat()
        )
    ).all()
    par_indicateur: dict[str, list[int]] = defaultdict(list)
    par_page: dict[tuple[str, str], list[int]] = defaultdict(list)
    for page, indicateur, duree in lignes:
        par_indicateur[indicateur].append(duree)
        par_page[(page, indicateur)].append(duree)
    pages = [
        {"page": page, "indicateur": indicateur, **_resume(valeurs)}
        for (page, indicateur), valeurs in par_page.items()
    ]
    pages.sort(key=lambda p: (-p["p75"], p["page"], p["indicateur"]))
    return {
        "indicateurs": [
            {"indicateur": i, **_resume(par_indicateur[i])}
            for i in INDICATEURS
            if par_indicateur[i]
        ],
        "pages": pages[:PAGES_AFFICHEES],
    }


def purger_mesures(session: Session, aujourd_hui: date) -> int:
    """Retire les mesures de plus de `CONSERVATION_JOURS` ; rend leur nombre."""
    limite = (aujourd_hui - timedelta(days=CONSERVATION_JOURS)).isoformat()
    resultat = session.exec(delete(MesureAffichage).where(MesureAffichage.jour < limite))
    session.commit()
    return resultat.rowcount
