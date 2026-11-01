"""Exécuter une fonction **hors du process de l'API**, dans un enfant jetable.

Deux moteurs de ce dépôt lisent ce que d'autres ont écrit, par des bibliothèques C
dont l'historique compte des corruptions de mémoire : WeasyPrint (le rendu des
documents, 16/09/2026) et Pillow (les images reçues, #2396 — libtiff, libwebp,
libavif, libheif…). Un fichier piégé qui fait planter le décodeur, boucler le
moteur ou épuiser la mémoire du RPi n'emporte ainsi que l'enfant : l'API répond
toujours, et l'appelant reçoit une erreur franche.

Ce module porte la mécanique, une fois : démarrer l'enfant, attendre un délai
borné, distinguer « trop long » de « mort en route », abattre ce qui traîne. Elle
était écrite dans `pdf_rendu` ; la recopier pour les images aurait fait deux
attentes libres de diverger sur le cas qui compte — l'enfant qui meurt
(`standards/02-factorisation.md`).

## 🔴 SPAWN, JAMAIS FORK

Le défaut de Python 3.12 sous Linux est `fork`. Un enfant **forké** hérite des
descripteurs du parent, **y compris les connexions** du pool SQLAlchemy : en se
terminant, il peut fermer côté serveur une session que l'API croit ouverte.
`spawn` démarre un interpréteur neuf qui ne partage aucun descripteur ; le prix
est l'import de la bibliothèque dans l'enfant, à chaque appel.

C'est vérifié par le **comportement** : l'enfant rapporte un TÉMOIN — son pid, et
s'il a `app.database` en mémoire —, que `test_pdf_hors_process.py` et
`test_images_hors_process.py` confrontent au parent.

⚠️ Corollaire de `spawn` : le module principal de l'appelant est réimporté dans
l'enfant. Il doit porter un garde `if __name__ == "__main__"`, sans quoi il se
rejoue en entier (uvicorn et pytest l'ont ; un script maison, pas toujours).

## La fonction est NOMMÉE, jamais passée

L'enfant reçoit `module` et `fonction` en texte, et les importe lui-même. Le
parent n'a donc jamais à importer le moteur : `utils/images` n'importe pas
Pillow, et `test_images_hors_process.py` exige qu'aucun module de l'API n'importe
`utils/images_moteur` — la seule porte vers lui est celle-ci.

## Le plafond de mémoire

`memoire_max_octets` borne l'espace d'adressage de l'enfant (`RLIMIT_AS`), là où
le système le permet (Linux : le RPi, la CI). Un décodeur qui s'emballe y
rencontre un `MemoryError` ou meurt — lui seul, jamais le RPi entier. Hors de
Linux, le plafond ne s'applique pas, et le témoin le dit (`plafond_memoire`) :
sous Windows, `resource` n'existe pas ; sous macOS (le poste depuis le 01/11/2026,
#2419), le noyau refuse un `RLIMIT_AS` sous l'espace déjà réservé et ne le ferait
pas respecter — chaque décodage échouait sur « current limit exceeds maximum limit ».
"""

from __future__ import annotations

import importlib
import multiprocessing
import os
import sys


class EchecIsole(RuntimeError):
    """L'enfant n'a rien rendu : délai dépassé, mort en route, ou exception levée.

    `temoin` porte ce que l'enfant a dit de lui-même, quand il a pu le dire.
    """

    def __init__(self, message: str, temoin: dict | None = None):
        super().__init__(message)
        self.temoin = temoin


def _plafonner_la_memoire(octets: int | None) -> bool:
    """Pose `RLIMIT_AS` dans l'enfant. Rend True si le plafond est en place."""
    if not octets or not sys.platform.startswith("linux"):  # Windows, macOS : le poste
        return False
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (octets, octets))
    return True


def _dans_l_enfant(tube, module: str, fonction: str, args: tuple, memoire_max: int | None):
    """Exécute `module.fonction(*args)` et renvoie son résultat. **Dans l'enfant.**

    🔴 Le témoin voyage DANS le message, jamais par le journal : sa remontée
    dépendrait sinon de la configuration du logging des deux process — c'est ce
    qui a rendu le contrôle de `pdf_rendu` vert sur le poste et rouge en CI.
    """
    temoin = {
        "pid": os.getpid(),
        "base_chargee": "app.database" in sys.modules,
        "plafond_memoire": False,
    }
    try:
        temoin["plafond_memoire"] = _plafonner_la_memoire(memoire_max)
        cible = getattr(importlib.import_module(module), fonction)
        valeur = cible(*args)
    except BaseException as exc:  # noqa: BLE001 — tout est remonté au parent
        tube.send(("erreur", f"{type(exc).__name__}: {exc}", temoin))
    else:
        tube.send(("ok", valeur, temoin))
    finally:
        tube.close()


def executer_isole(
    module: str,
    fonction: str,
    *args,
    delai_s: float,
    nom: str,
    memoire_max_octets: int | None = None,
) -> tuple[object, dict]:
    """`module.fonction(*args)` exécutée dans un enfant `spawn`. Rend `(valeur, témoin)`.

    Les arguments et la valeur traversent un tube : ils doivent être sérialisables
    (des octets, des nombres, des tuples). Lève `EchecIsole` si l'enfant dépasse
    `delai_s`, meurt sans répondre (mémoire, plantage du moteur), ou lève.
    """
    contexte = multiprocessing.get_context("spawn")
    lecture, ecriture = contexte.Pipe(duplex=False)
    enfant = contexte.Process(
        target=_dans_l_enfant,
        args=(ecriture, module, fonction, args, memoire_max_octets),
        name=nom,
        daemon=True,
    )
    enfant.start()
    #  ⚠️ Fermer NOTRE copie de l'extrémité d'écriture, sinon le tube n'atteint
    #  jamais EOF quand l'enfant meurt : `poll()` attendrait le délai complet au
    #  lieu de signaler la mort immédiatement.
    ecriture.close()

    repondu = False
    try:
        if not lecture.poll(delai_s):
            raise EchecIsole(f"{nom} abandonné après {delai_s:.0f} s — moteur bloqué ou trop lent")
        try:
            message = lecture.recv()
        except EOFError as exc:
            #  ⚠️ Deux causes très différentes, et les nommer toutes les deux évite
            #  l'heure perdue au mauvais endroit : la première est plausible en
            #  production (mémoire, fichier piégé), la seconde apparaît dès qu'on
            #  appelle ce module depuis un script sans garde `__main__`.
            raise EchecIsole(
                f"le process {nom} est mort sans rien produire (code de sortie "
                f"{enfant.exitcode}) — plantage du moteur, mémoire insuffisante, ou "
                'module principal sans garde `if __name__ == "__main__"`'
            ) from exc
        repondu = True
    finally:
        lecture.close()
        #  Un enfant qui a répondu se termine seul ; celui qui a dépassé son délai
        #  s'abat tout de suite — l'attendre encore ne ferait que tenir l'appelant.
        enfant.join(5 if repondu else 0)
        if enfant.is_alive():
            enfant.terminate()
            enfant.join(5)
        if enfant.is_alive():
            enfant.kill()
            enfant.join()

    etat, charge, temoin = message
    if etat == "erreur":
        raise EchecIsole(charge, temoin)
    return charge, temoin
