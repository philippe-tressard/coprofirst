"""La SOURCE du tarif d'un modèle : la grille publiée par son fournisseur.

## Pourquoi le serveur lit lui-même (30/09/2026)

Demandé : *« l'appel à l'IA de ce use case recherche le prix sur l'opérateur
concerné du modèle du use case concerné, remplit les prix et enregistre »*.

Un modèle interrogé « de mémoire » rend le tarif de son apprentissage, et
aucun des trois fournisseurs n'offre la même recherche web par la même API.
Les deux grands publient en revanche leur grille en **Markdown** (OpenAI
~22 Ko, Anthropic ~48 Ko) : le serveur la lit à l'adresse que le code nomme
(`Fournisseur.page_tarifs`), et l'assistant n'a plus qu'à y trouver la ligne.

Les grilles sont en **dollars**, et les prix se saisissent en dollars
(arbitré le 30/09/2026) : rien à convertir. Une conversion au taux BCE a
existé une heure — elle rendait le chiffre enregistré invérifiable contre la
grille qu'on a sous les yeux.

## Ce qui ne part pas

Aucune donnée du site : un GET vers une adresse fixe, sans cookie ni clé.
"""

from __future__ import annotations

from app.utils.demo import MESSAGE, est_demo
from app.utils.plateforme import NOM_PLATEFORME

DELAI_S = 20
#: Une grille au-delà de cette taille n'est plus une grille : on la tronque
#: plutôt que de payer des dizaines de milliers de jetons pour la lire.
MAX_CARACTERES_GRILLE = 80_000


class SourceIndisponible(Exception):
    """La grille n'a pas pu être lue — l'appelant en fait une `ErreurLLM`."""


async def _lire(url: str) -> str:
    import httpx

    if est_demo():
        raise SourceIndisponible(MESSAGE)  # rien ne part de la démo publique (#1902)

    try:
        async with httpx.AsyncClient(timeout=DELAI_S, follow_redirects=True) as client:
            #  ⚠️ En ASCII : un en-tête HTTP n'admet pas d'accent, et httpx lève
            #  avant même d'envoyer (constaté au premier essai réel).
            entetes = {"User-Agent": f"{NOM_PLATEFORME} (tarif-modele)"}
            r = await client.get(url, headers=entetes)
    except httpx.HTTPError as exc:
        raise SourceIndisponible(f"« {url} » n'a pas pu être lue.") from exc
    if r.status_code != 200:
        raise SourceIndisponible(f"« {url} » a répondu {r.status_code}.")
    return r.text


async def lire_grille(url: str) -> str:
    """La grille tarifaire du fournisseur, bornée."""
    if not url:
        raise SourceIndisponible("Ce fournisseur ne publie pas de grille lisible.")
    return (await _lire(url))[:MAX_CARACTERES_GRILLE]


__all__ = ["SourceIndisponible", "lire_grille"]
