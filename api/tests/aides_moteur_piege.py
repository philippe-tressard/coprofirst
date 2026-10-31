"""Un moteur d'images qui plante, boucle ou gonfle — pour éprouver l'isolement (#2396).

`test_images_hors_process.py` le NOMME à la place du vrai moteur (`images.MOTEUR`) :
l'enfant l'importe, et ce qui s'y passe doit y rester.
"""

import os
import time


def reencoder(data: bytes, max_dim: int, qualite: int) -> bytes:
    """Un décodeur dont le process meurt sans répondre, comme sur une corruption de
    mémoire (`os._exit` plutôt que `abort` : sous Windows, `abort` ouvre une boîte)."""
    os._exit(134)


def mesurer(images: tuple[bytes, ...]) -> list:
    """Un décodeur qui ne rend jamais la main."""
    time.sleep(600)
    return []


def carres(data: bytes, tailles: tuple[int, ...]) -> dict:
    """Un décodeur qui réclame plus de mémoire que l'enfant n'en a."""
    return {0: bytes(4 * 1024 * 1024 * 1024)}
