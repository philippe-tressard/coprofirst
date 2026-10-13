"""Les clés publiques de la référence — DANS L'IMAGE, par époque (R2 #1878, D24).

Une installation ne croit un bail que s'il est signé par la clé de l'époque qu'il
annonce, et refuse toute époque inférieure à la plus haute qu'elle a reçue
(§4.11, règle 11 : jamais deux références).

La clé de l'époque 1 se crée sur le Raspberry Pi actif de la référence
(`scripts/exploitation/creer-cle-baux.sh`, arbitrage du 13/10/2026) : la clé
privée ne quitte pas les deux nœuds, la publique s'écrit ICI. Tant qu'elle n'y
est pas, aucun bail n'est cru et toute installation se constate « limitée ».

Un transfert du rôle de référence (R8, #1884) AJOUTE l'époque suivante, et la clé
qu'il remplace entre dans `REVOQUEES` — jamais une clé n'est réécrite.
"""

from __future__ import annotations

#: époque → clé publique Ed25519 (32 octets, base64).
CLES_REFERENCE: dict[int, str] = {}

#: Les clés publiques révoquées : un bail qu'elles signent n'est jamais cru.
REVOQUEES: frozenset[str] = frozenset()
