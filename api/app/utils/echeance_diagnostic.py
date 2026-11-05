"""Quand un diagnostic réglementaire revient — la règle du relevé des renouvellements.

Elle vivait dans le front (`#lib/reporting.ts` : `diagNextDate`, `diagUrgence`), où
l'app iOS ne la lit pas (`standards/09` §8) ; servie depuis #2525 par
`GET /reporting/renouvellements`.

La périodicité est un TEXTE saisi au référentiel (« 3 ans », « Permanent (révision
si amiante détecté) ») : son premier nombre fait les années. Un diagnostic
PERMANENT n'a pas d'échéance, même quand le texte porte un chiffre. Sans dernier
rapport daté, rien ne se déduit : on n'invente pas une échéance.

L'urgence se juge au JOUR de Paris (`horloge.aujourd_hui`), jamais à l'instant du
navigateur : une échéance qui tombe aujourd'hui est dépassée, comme au site.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal, Optional

from app.utils import horloge
from app.utils.echeance_contrat import ajouter_mois

UrgenceDiagnostic = Literal["depasse", "annee", "futur"]


def est_permanent(frequence: Optional[str]) -> bool:
    """« Permanent (…) » : un diagnostic qu'on ne refait pas à échéance."""
    return bool(frequence) and "permanent" in frequence.lower()


def periodicite_ans(frequence: Optional[str]) -> Optional[int]:
    """Le premier nombre du texte, en années — `None` s'il n'y en a pas."""
    if not frequence or est_permanent(frequence):
        return None
    trouve = re.search(r"\d+", frequence)
    return int(trouve.group()) if trouve else None


def prochaine_echeance(
    frequence: Optional[str], dernier_rapport_le: Optional[date]
) -> Optional[date]:
    """Le dernier rapport plus la périodicité ; un 29 février se ramène au 28."""
    ans = periodicite_ans(frequence)
    if ans is None or dernier_rapport_le is None:
        return None
    return ajouter_mois(dernier_rapport_le, 12 * ans)


def urgence_diagnostic(
    echeance: Optional[date], aujourdhui: Optional[date] = None
) -> Optional[UrgenceDiagnostic]:
    """Dépassée (le jour même compris), cette année, ou plus tard ; `None` sans échéance."""
    if echeance is None:
        return None
    jour = aujourdhui or horloge.aujourd_hui()
    if echeance <= jour:
        return "depasse"
    return "annee" if echeance.year == jour.year else "futur"
