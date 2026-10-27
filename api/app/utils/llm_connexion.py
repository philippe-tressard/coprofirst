"""Le TEST DE CONNEXION d'un usage de l'assistant IA — une vraie question, une
vraie réponse.

Sorti de `llm.py` le 04/10/2026, sans changement de logique : ce module-là
franchissait 500 lignes en recevant les limites d'appels (`llm_limites`). Les
appelants importent toujours `tester` depuis `app.utils.llm`.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from sqlmodel import Session


async def tester(session: Session, usage: str, *, demandeur: Optional[int]) -> dict[str, Any]:
    """Vérifie que la configuration de cet USAGE parle au modèle — le fait,
    pas le réglage.

    🔴 Un écran qui dit « configuré » parce que trois champs sont remplis ne
    prouve rien : la clé peut être révoquée, le modèle renommé, le point d'accès
    fermé. Ce test envoie une vraie question et attend une vraie réponse
    (`standards/04` — vérifier le comportement, jamais l'artefact).

    Un test PAR usage (17/09/2026) : c'est le modèle de l'usage qui est éprouvé,
    et deux usages n'ont pas le même. Un test sur un modèle commun n'aurait
    prouvé le bon fonctionnement d'aucun des deux.
    """
    #  Différé : `llm` ré-exporte ce module à sa fin, et un import en tête le
    #  rencontrait à moitié chargé quand on entrait par ici (#2241).
    from app.utils.llm import config_llm, demander

    cfg = config_llm(session, usage)
    debut = time.monotonic()
    reponse = await demander(
        session,
        usage=usage,
        consigne="Tu réponds en un seul mot, sans ponctuation.",
        message="Réponds exactement : opérationnel",
        #  🔴 Plus de plafond serré ici (11/09/2026). Il valait 16 jetons — assez
        #  pour un mot, trop peu pour un modèle qui RAISONNE avant de répondre :
        #  il épuisait le plafond sans rien écrire, et le test déclarait en panne
        #  une configuration parfaitement bonne. Un test qui n'éprouve pas la
        #  configuration réelle n'éprouve rien (`standards/04` — vérifier le fait).
        #  Le coût ne change pas : un plafond n'est pas facturé, seuls les jetons
        #  produits le sont, et la réponse attendue fait un mot.
        #  Le test ne demande pas l'activation : il sert à décider de l'activer.
        exiger_actif=False,
        demandeur=demandeur,
        etalon=False,
    )
    return {
        "ok": True,
        "usage": usage,
        "fournisseur": cfg.fournisseur.libelle,
        "modele": cfg.modele,
        "reponse": reponse.texte[:80],
        "duree_ms": int((time.monotonic() - debut) * 1000),
    }
