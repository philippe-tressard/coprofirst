"""Ce dont les tests de rendu PDF ont besoin des deux côtés.

Ces trois objets existaient dans `test_documents_pdf.py` seulement. Le jour où
un second fichier de test a eu besoin du même garde (`test_pdf_hors_process.py`,
16/09/2026), les recopier aurait fabriqué la duplication que ce dépôt refuse —
et, plus concrètement, deux définitions de « WeasyPrint est-il là ? » qui
divergeraient au premier changement d'image.

⚠️ `EN_INTEGRATION_CONTINUE` n'est pas une commodité : c'est ce qui empêche
l'abstention d'être silencieuse. Sur un poste Windows, WeasyPrint n'a pas ses
bibliothèques système (pango, cairo) et sauter est légitime ; en CI, sauter
signifierait que le rendu n'est contrôlé **nulle part**. Un seul test le
vérifie, pour tous les fichiers qui se servent de `besoin_weasyprint` :
`test_documents_pdf.py::test_weasyprint_present_en_ci`. `DISPONIBLE` est le même
pour toute la session de tests, donc un second exemplaire ne pourrait échouer
que là où le premier échoue déjà — il y en a eu trois, identiques, jusqu'au
30/09/2026. La raison de saut de `besoin_weasyprint` renvoie à ce test.
Un contrôle qui s'abstient partout est un contrôle absent
(`standards/04-fiabilite-des-controles.md` §1).
"""

import os

import pytest


def weasyprint_disponible() -> bool:
    try:
        import weasyprint  # noqa: F401
    except Exception:  # noqa: BLE001 — toute erreur d'import vaut « weasyprint indisponible »
        return False
    return True


DISPONIBLE = weasyprint_disponible()
EN_INTEGRATION_CONTINUE = os.getenv("CI", "").lower() in ("1", "true", "yes")

besoin_weasyprint = pytest.mark.skipif(
    not DISPONIBLE,
    reason=(
        "WeasyPrint absent (bibliothèques système) — voir "
        "test_documents_pdf.py::test_weasyprint_present_en_ci"
    ),
)


def exiger_weasyprint_en_ci() -> None:
    """Le test de portée, appelé par `test_documents_pdf.py` seul, pour tous."""
    if not EN_INTEGRATION_CONTINUE:
        pytest.skip("hors intégration continue — abstention légitime")
    assert DISPONIBLE, (
        "WeasyPrint indisponible en intégration continue : le rendu des documents "
        "n'est vérifié nulle part. Installer libpango/libcairo dans le job."
    )
