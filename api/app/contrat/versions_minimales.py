"""La version minimale de chaque app, SERVIE — et ce qu'elle prouve pour la sortie (#2994).

## Pourquoi

Une version d'app publiée contraint le contrat tant qu'elle circule
(`circulation.py`). Rien ne disait qu'elle ne circulait plus : la télémétrie ne
retient pas la version de l'app, et l'en doter collecterait une donnée de plus
(contrat, fiches de confidentialité des magasins). L'option la plus sûre, tranchée
le 24/11/2026 par délégation : le serveur SERT une version minimale par app ; une
app qui la lit invite à se mettre à jour en dessous. Une fois servie assez
longtemps, la version d'en dessous peut sortir — si elle la lisait.

## Ce qui est servi

`GET /config` → `version_minimale_<app>` (`coprofirst-ios`, `coprofirst-android`) :
l'étiquette `vX.Y.Z` en dessous de laquelle l'app invite à la mise à jour, ou `""`
quand aucune n'est imposée. Calculée, jamais saisie (`PUT /config` n'écrit que les
clés déclarées, `utils/reglages`).

Monter une version minimale est une DÉCISION (elle invite des gens à mettre à jour) :
une entrée datée ici, dans la PR qui la pose.
🔒 `tests/test_versions_minimales.py`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

#: app → (étiquette minimale, posée le « JJ/MM/AAAA »). Absente : aucune minimale.
VERSIONS_MINIMALES: dict[str, tuple[str, str]] = {}

#: Combien de jours la version minimale doit avoir été servie avant qu'une version
#: de production d'en dessous sorte : le temps qu'une app ouverte de loin en loin
#: l'ait lue.
DELAI_SORTIE_JOURS = 90

MOTIF_TEST = "piste de test fermée"
MOTIF_MINIMALE = "sous la version minimale servie"
MOTIFS = (MOTIF_TEST, MOTIF_MINIMALE)


def cle_publique(app: str) -> str:
    return f"version_minimale_{app}"


def cles_publiques(apps: tuple[str, ...]) -> dict[str, str]:
    """Les clés de `GET /config` : une par app, `""` sans version minimale."""
    return {cle_publique(a): VERSIONS_MINIMALES.get(a, ("", ""))[0] for a in apps}


def _rang(etiquette: str) -> tuple[int, ...]:
    return tuple(int(x) for x in etiquette.removeprefix("v").split("."))


def _jour(texte: str) -> date:
    return datetime.strptime(texte, "%d/%m/%Y").date()


def sorties_non_prouvees(sorties, minimales: dict[str, tuple[str, str]] | None = None) -> list[str]:
    """PURE. Les sorties que leur motif ne prouve pas. Vide = conforme."""
    minimales = VERSIONS_MINIMALES if minimales is None else minimales
    messages = []
    for s in sorties:
        nom = f"{s.app} {s.etiquette}"
        if s.motif not in MOTIFS:
            messages.append(f"{nom} : motif « {s.motif} » inconnu ({' / '.join(MOTIFS)})")
        elif s.motif == MOTIF_MINIMALE:
            minimale = minimales.get(s.app)
            if not s.lisait_version_minimale:
                messages.append(f"{nom} : ne lisait pas la version minimale — elle ne sort pas")
            elif minimale is None or _rang(s.etiquette) >= _rang(minimale[0]):
                messages.append(f"{nom} : n'est pas sous la version minimale servie")
            elif _jour(s.le) < _jour(minimale[1]) + timedelta(days=DELAI_SORTIE_JOURS):
                messages.append(
                    f"{nom} : la version minimale n'est servie que depuis le {minimale[1]} "
                    f"({DELAI_SORTIE_JOURS} jours exigés)"
                )
    return messages
