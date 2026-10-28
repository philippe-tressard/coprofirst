"""Le fil d'activité ne rend pas l'équipement d'un prestataire en valeur brute.

Signalé à l'écran le 26/09/2026 : « DBI — interphone_digicode », deux fois
(détail et pastille). Le serveur n'a pas la table des libellés d'équipement —
elle vit côté écran (`#lib/prestataires`, `EQUIPEMENTS`) — : il envoie la
VALEUR dans `meta`, et `badgesDuFlux` (`front/src/lib/flux.ts`) la traduit.
"""

from __future__ import annotations

import inspect

from app.routers.flux import prestataires


def test_la_specialite_ne_sort_qu_en_meta():
    source = inspect.getsource(prestataires._collecter_fiches)
    assert "detail=pr.specialite" not in source
    assert "badges=[pr.specialite]" not in source
    assert '"specialite": pr.specialite' in source, "l'écran la lit dans `meta`"
