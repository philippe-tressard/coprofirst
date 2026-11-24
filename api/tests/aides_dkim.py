"""Une clé DKIM tirée pour les tests de l'authenticité d'un courriel (#2950).

`test_courriel_authenticite.py` et `test_courriel_delegation.py` portaient la même
fixture `cle`, au corps identique. Elle vit ici ; c'est une fixture : un fichier de
tests l'IMPORTE pour que pytest la trouve (même forme qu'`aides_fil.cs`).
"""

from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


@pytest.fixture(scope="module")
def cle() -> tuple[bytes, bytes]:
    """Une paire de clés tirée pour ce module — jamais écrite dans le dépôt.

    Rend `(clé privée PEM, enregistrement DNS « v=DKIM1 » qui publie la clé publique)`.
    """
    privee = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = privee.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    publique = privee.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem, b"v=DKIM1; k=rsa; p=" + base64.b64encode(publique)
