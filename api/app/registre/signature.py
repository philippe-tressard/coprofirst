"""Les signatures Ed25519 du registre — la seule pièce secrète est une clé privée (§4.11).

Le code est public (AGPL) : rien ne tient sur un secret écrit dans le code. Une
installation prouve qu'elle est elle-même en signant ses envois avec SA clé privée,
générée chez elle ; la référence ne reçoit que la clé publique. Plus tard (R2), la
référence signe les baux de la même façon avec la sienne (`registre/baux`).

Une clé ou une signature mal formée n'est jamais une exception qui remonte : c'est
une vérification qui ÉCHOUE (`verifier` rend `False`).
"""

from __future__ import annotations

import base64
import binascii
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_BRUT = serialization.Encoding.Raw
_PUBLIQUE = serialization.PublicFormat.Raw


def _decoder(valeur: str) -> bytes | None:
    try:
        return base64.b64decode(valeur, validate=True)
    except (binascii.Error, ValueError):
        return None


def cle_publique_valide(cle_b64: str) -> bool:
    """Une clé publique Ed25519 : 32 octets, en base64."""
    brut = _decoder(cle_b64)
    if brut is None or len(brut) != 32:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(brut)
    except ValueError:
        return False
    return True


def verifier(cle_b64: str, message: bytes, signature_b64: str) -> bool:
    """La signature `signature_b64` de `message` est-elle celle de la clé `cle_b64` ?"""
    cle, signature = _decoder(cle_b64), _decoder(signature_b64)
    if cle is None or signature is None or len(cle) != 32:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(cle).verify(signature, message)
    except (InvalidSignature, ValueError):
        return False
    return True


def empreinte(cle_b64: str) -> str:
    """L'empreinte courte d'une clé publique, telle que l'opérateur la lit (16 hexa)."""
    return hashlib.sha256(_decoder(cle_b64) or b"").hexdigest()[:16]


def generer_paire() -> tuple[Ed25519PrivateKey, str]:
    """Une paire neuve : la clé privée, et la publique en base64 (R2, et les tests)."""
    privee = Ed25519PrivateKey.generate()
    return privee, publique_de(privee)


def privee_de(cle_b64: str) -> Ed25519PrivateKey | None:
    """Une clé privée Ed25519 lue de ses 32 octets bruts en base64, ou None si illisible."""
    brut = _decoder(cle_b64.strip())
    if brut is None or len(brut) != 32:
        return None
    return Ed25519PrivateKey.from_private_bytes(brut)


def en_base64(privee: Ed25519PrivateKey) -> str:
    """Les 32 octets bruts d'une clé privée, en base64 — la forme qu'on range."""
    brut = privee.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    return base64.b64encode(brut).decode()


def publique_de(privee: Ed25519PrivateKey) -> str:
    """La clé publique d'une clé privée, en base64."""
    return base64.b64encode(privee.public_key().public_bytes(_BRUT, _PUBLIQUE)).decode()


def signer(privee: Ed25519PrivateKey, message: bytes) -> str:
    """La signature de `message`, en base64."""
    return base64.b64encode(privee.sign(message)).decode()
