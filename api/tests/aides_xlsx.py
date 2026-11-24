"""Un classeur `.xlsx` en mémoire pour les tests d'import (#2950).

`test_import_xlsx.py` et `test_purge_imports.py` portaient chacun ce `_classeur`,
au corps identique.
"""

from __future__ import annotations

import io

#  Un IMPORT, pas un `importorskip` (#2952) : openpyxl est épinglé dans
#  `requirements.txt` ; s'il disparaît, les tests d'import doivent échouer, pas sauter.
import openpyxl


def classeur(lignes: list[list]) -> bytes:
    """Un vrai fichier .xlsx en mémoire — pas une imitation de `openpyxl`.

    Simuler la bibliothèque aurait testé mon idée de son comportement plutôt que
    le sien : c'est elle qui décide de ce qu'une cellule vide ou un nombre rend.
    """
    wb = openpyxl.Workbook()
    for ligne in lignes:
        wb.active.append(ligne)
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()
