"""Le catalogue des modèles que la clé enregistrée peut appeler.

Sorti de `llm.py` le 27/09/2026, sans changement de logique : ce module-là
franchissait 500 lignes en recevant le journal des appels (#1383). Les
appelants importent toujours `modeles_disponibles` depuis `app.utils.llm`.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session

from app.utils.demo import MESSAGE, est_demo

logger = logging.getLogger("hostachy.llm")


async def modeles_disponibles(session: Session) -> dict[str, Any]:
    """Ce que la clé enregistrée peut RÉELLEMENT appeler, demandé au fournisseur.

    🔴 Le fait, pas le catalogue. Le champ « Modèle » était libre et adossé à
    trois exemples écrits en dur, avec le commentaire « le catalogue bouge
    vite » — ce qui est l'aveu même du défaut : un repère recopié propose des
    modèles que la clé ne peut pas appeler et cache ceux qui sont sortis depuis.
    Le gestionnaire découvrait l'écart au test de connexion, une saisie plus
    tard.

    Rend toujours une réponse LISIBLE, jamais une exception :

    | `listable` | Ce que l'écran en fait |
    |---|---|
    | `True` | une liste déroulante, avec le modèle en place toujours proposé |
    | `False` | la saisie libre, et le `motif` dit pourquoi |

    ⚠️ `False` couvre trois cas qu'il ne faut PAS confondre avec une panne :
    Azure (pas d'inventaire par cette porte), une clé restreinte en lecture, et
    un service injoignable. Aucun n'empêche de configurer l'assistant à la main —
    c'est pourquoi l'absence de liste n'est pas une erreur.
    """
    import httpx

    from app.utils.llm import config_llm  # différé : `llm` ré-exporte ce module (#2241)

    if est_demo():
        #  Avant même la configuration : rien ne part de la démo publique (#1902).
        return {"listable": False, "motif": MESSAGE, "modeles": []}
    #  Le catalogue est COMMUN — il dépend de la clé, pas de l'usage : le même
    #  inventaire sert à choisir le modèle de chaque bloc de l'écran.
    cfg = config_llm(session)
    cfg.verifier(exiger_actif=False, exiger_modele=False)
    url = cfg.fournisseur.url_modeles(cfg.base_url, cfg.version_api)
    if url is None:
        return {
            "listable": False,
            "motif": f"{cfg.fournisseur.libelle} n'expose pas la liste de ses déploiements.",
            "modeles": [],
        }
    try:
        async with httpx.AsyncClient(timeout=cfg.delai_s) as client:
            reponse = await client.get(url, headers=cfg.fournisseur.entetes(cfg.cle))
    except httpx.HTTPError:
        return {"listable": False, "motif": "Le service n'a pas pu être joint.", "modeles": []}
    if reponse.status_code in (401, 403):
        #  Le cas le plus fréquent : une clé créée en écriture seule, ou
        #  restreinte à `/chat/completions`. Elle SYNTHÉTISE très bien et ne
        #  peut pas s'inventorier — le dire évite de la croire invalide.
        return {
            "listable": False,
            "motif": "Cette clé n'a pas le droit de lister les modèles (permission « models »).",
            "modeles": [],
        }
    if reponse.status_code >= 400:
        logger.warning("Liste des modèles %s → %s", cfg.fournisseur.code, reponse.status_code)
        return {
            "listable": False,
            "motif": f"Le fournisseur a répondu {reponse.status_code}.",
            "modeles": [],
        }
    try:
        modeles = cfg.fournisseur.lire_modeles(reponse.json())
    except (ValueError, KeyError, TypeError, AttributeError):
        #  `AttributeError` : un JSON VALIDE d'une autre forme (un tableau, ou
        #  `{"data": "texte"}`) fait lever `.get` — c'est « illisible », pas un 500 (#1624).
        return {"listable": False, "motif": "Liste illisible — format inattendu.", "modeles": []}
    #  Une liste VIDE n'est pas une liste : la rendre ferait choisir dans un
    #  menu sans entrée (`standards/04` §2 — le cas zéro).
    if not modeles:
        return {"listable": False, "motif": "Aucun modèle de conversation proposé.", "modeles": []}
    return {"listable": True, "motif": "", "modeles": modeles}
