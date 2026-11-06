"""Admin › Audit des lots : le type d'un lot se lit en clair (#2562).

## Le défaut (06/11/2026)

`GET /admin/audit/user-lots` ne rendait que `lot_type`, le code de
l'énumération, et l'écran l'affichait tel quel : « appartement », « parking ».
`lint:categorie-brute` ne le voyait pas, le champ étant COMPOSÉ (`lot_type`).
La route sert désormais le libellé (`lot_libelle_type`, par `libelle_type_lot`
— la règle que lisent déjà les lots du site et l'app iOS, #2507) ; le code
reste, pour qui le compare.
"""

from __future__ import annotations

from app.routers.admin.acces import audit_user_lots
from app.utils.types_acces import TELECOMMANDE
from tests.aides_badges import _compte, _lier, _lot


def test_le_type_du_lot_est_servi_en_clair(session):
    lot = _lot(session, TELECOMMANDE, numero="12")
    _lier(session, _compte(session, "Durand"), lot)

    (ligne,) = audit_user_lots(session=session, _=None)

    assert ligne["lot_type"] == "parking"
    assert ligne["lot_libelle_type"] == "Parking"
    #  Le lien reste un code : l'écran le rend par `#lib/liens-lot`.
    assert ligne["type_lien"] == "propriétaire"
