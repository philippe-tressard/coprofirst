"""La fréquence d'un contrat en une expression courte — « ↺ Mensuel », « ↺ 2×/an ».

## Pourquoi ici (#2507, 04/11/2026)

Elle se composait dans le front (`frequenceLabel`, `prestataires.ts`). L'app iOS ne
recopie aucune règle du site : elle ne montrait rien. Le serveur la SERT
(`ContratRead.frequence_libelle`), le site la lit (`standards/09` §8, règle 1).

⚠️ Une chaîne VIDE sans fréquence : l'appelant n'affiche alors pas de pastille,
plutôt qu'une pastille vide.
"""

from __future__ import annotations

from typing import Optional


def frequence_libelle(frequence_type: Optional[str], frequence_valeur: Optional[int]) -> str:
    """« ↺ 3 sem. », « ↺ Mensuel », « ↺ 4×/an », « ↺ tous les 2 ans » — ou ``""``."""
    n = frequence_valeur or 0
    if frequence_type == "semaines":
        return f"↺ {n} sem."
    if frequence_type == "mois":
        return "↺ Mensuel"
    if frequence_type == "fois_par_an":
        return f"↺ {n}×/an"
    if frequence_type == "ans":
        return f"↺ tous les {n} an{'s' if n > 1 else ''}"
    return ""


__all__ = ["frequence_libelle"]
