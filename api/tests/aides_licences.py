"""Les licences que le dépôt N'accorde PAS — une liste, lue par deux contrôles (#2916).

`test_gouvernance_depot.py` refuse qu'un fichier de gouvernance les promette ;
`test_notice_et_licence_du_produit.py`, que le code ou la documentation les prête au
produit. Une aide partagée vit ici, jamais dans un fichier de tests
(`test_aides_de_tests_source_unique.py`).
"""

from __future__ import annotations

#: Les licences qu'un fichier de gouvernance ne peut pas promettre, puisque le
#: dépôt ne les accorde pas.
#:
#: `AGPL` n'y est pas : c'est la licence accordée depuis le 08/10/2026 (#1726).
#:
#: ⚠️ Le jour où `NOTICE.md` devrait nommer la licence d'une dépendance tierce,
#: ce test échouerait — et l'exception s'écrirait alors, avec sa raison et sa
#: date (`standards/05` §2). Ce jour est venu : voir `SECTIONS_TIERS`
#: dans `test_gouvernance_depot.py`.
LICENCES_NON_ACCORDEES = (
    "MIT",
    "Apache",
    "BSD",
    "ISC",
    "LGPL",
    "MPL",
    "Unlicense",
    "WTFPL",
    "CC0",
    "Creative Commons",
)
