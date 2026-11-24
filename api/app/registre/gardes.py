"""Les gardes communes à tout envoi d'une installation — écrites ICI, appelées ailleurs (#2953).

Trois points reçoivent un envoi signé : l'inscription et le bail (`routeur._lire_signee`),
le rapport nocturne (`routeur.recevoir_rapport`) et la notification relayée
(`relais.relayer`). Chacun appelle, dans l'ordre que sa spécification fixe :

1. `lire_contrat` — taille (413), contrat de données (422), version du contrat (400) ;
2. ses gardes propres — le relais croit le bail AVANT la signature, le rapport retrouve
   l'installation dont il vérifie la clé ENREGISTRÉE ;
3. `exiger_signature` — la signature de la clé, sur les octets REÇUS (401).

Le refus dit quelle garde a manqué, jamais ce qu'il a lu.
🔒 `tests/test_signature_registre_source_unique.py` : `signature.verifier` n'a que ses
appelants déclarés, et chaque route du registre atteint `exiger_signature`.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.registre import signature
from app.registre.contrat import EN_TETE_SIGNATURE, VERSION_CONTRAT

#: Une demande d'inscription pèse moins d'un kilo-octet ; au-delà de 16, ce n'en est pas une.
TAILLE_MAX = 16 * 1024

#: Ce que reçoit le point, et ses deux refus : les messages servis restent ceux d'avant.
_REFUS = {
    "demande": (
        "Demande trop volumineuse.",
        "Demande illisible : elle ne suit pas le contrat de données.",
    ),
    "rapport": (
        "Rapport trop volumineux.",
        "Rapport illisible : il ne suit pas le contrat de données.",
    ),
}


def lire_contrat(corps: bytes, schema, objet: str = "demande"):
    """L'envoi que portent les octets reçus, au contrat et à sa version — ou 413, 422, 400."""
    trop_gros, illisible = _REFUS[objet]
    if len(corps) > TAILLE_MAX:
        raise HTTPException(413, trop_gros)
    try:
        envoi = schema.model_validate_json(corps)
    except ValidationError:
        raise HTTPException(422, illisible) from None
    if envoi.version_contrat != VERSION_CONTRAT:
        raise HTTPException(400, f"Version du contrat de données attendue : {VERSION_CONTRAT}.")
    return envoi


def exiger_signature(cle_publique: str, corps: bytes, request: Request) -> None:
    """401 si les octets reçus ne sont pas signés par `cle_publique`.

    `signature.verifier` rend `False` pour une clé mal formée : la vérifier à part
    (`cle_publique_valide`) n'ajoutait rien au refus.
    """
    if not signature.verifier(cle_publique, corps, request.headers.get(EN_TETE_SIGNATURE, "")):
        raise HTTPException(401, "Signature de l'installation absente ou invalide.")
