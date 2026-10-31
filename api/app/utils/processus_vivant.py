"""« Ce processus de CET hôte vit-il encore ? » — la question posée une fois (#2399).

Un schéma jetable inscrit son créateur (`dialecte.poser_schema`) : la purge retire
celui dont le créateur est mort, sans attendre qu'il ait vieilli d'une heure.

🔴 Sous Windows, jamais `os.kill(pid, 0)` : le signal 0 n'y existe pas, et Python
appelle alors `TerminateProcess` — la question tuerait le processus qu'elle
interroge. On ouvre le processus en lecture et on lit son code de sortie.

Dans le doute — accès refusé, appel qui échoue —, le processus est dit VIVANT :
garder un schéma de trop ne coûte qu'un peu de catalogue, en retirer un vivant
casse la suite d'une autre session.
"""

from __future__ import annotations

import os

_ACCES_LECTURE_LIMITEE = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
_TOUJOURS_ACTIF = 259  # STILL_ACTIVE
_PARAMETRE_INVALIDE = 87  # ERROR_INVALID_PARAMETER : aucun processus de ce numéro


def processus_vivant(pid: int) -> bool:
    """Vrai si le processus `pid` de cet hôte existe encore, ou si on ne sait pas le dire."""
    if pid <= 0:
        return True
    if os.name == "nt":
        return _vivant_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _vivant_windows(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    noyau = ctypes.WinDLL("kernel32", use_last_error=True)
    noyau.OpenProcess.restype = wintypes.HANDLE
    poignee = noyau.OpenProcess(_ACCES_LECTURE_LIMITEE, False, pid)
    if not poignee:
        return ctypes.get_last_error() != _PARAMETRE_INVALIDE
    try:
        code = wintypes.DWORD()
        if not noyau.GetExitCodeProcess(poignee, ctypes.byref(code)):
            return True
        return code.value == _TOUJOURS_ACTIF
    finally:
        noyau.CloseHandle(poignee)
