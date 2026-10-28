"""Formatage des montants en euros, à la française — source unique côté backend.

Le front a `fmtMontant()` (`#lib/utils.ts`) depuis que le rendu de `montant_estime`
avait dérivé en trois écritures différentes sur une même page. Le backend, lui,
n'avait rien : `flux.py` formatait à la main, deux fois, avec `:,.0f` — un
**arrondi à l'entier**.

Conséquence observée le 01/08/2026 : un devis à 1 234,50 € s'affichait
« 1 234 € » dans le fil d'activité (rendu backend) et « 1 234,50 € » sur la page
Prestataires et dans l'Espace CS (rendu front). Même champ, deux vérités, selon
l'écran regardé.

Ce module aligne le backend sur la règle du front : espace fine insécable comme
séparateur de milliers, décimales seulement si elles existent.
"""

from __future__ import annotations

# Espace insécable étroit (U+202F), comme le rendu `Intl.NumberFormat('fr-FR')`
# du front : sans lui, un montant peut se couper en fin de ligne.
_SEPARATEUR = " "


def montant_fr(valeur: float | int | None, devise: str = "€") -> str:
    """`1234.5` → `1 234,50 €` · `1234` → `1 234 €` · `None` → `—`.

    Mêmes conventions que `fmtMontant()` côté front : pas de décimale quand le
    montant est rond (« 1 234 € » et non « 1 234,00 € »), deux sinon.
    """
    if valeur is None:
        return "—"
    arrondi = round(float(valeur), 2)
    if arrondi == int(arrondi):
        corps = f"{int(arrondi):,}".replace(",", _SEPARATEUR)
    else:
        corps = f"{arrondi:,.2f}".replace(",", _SEPARATEUR).replace(".", ",")
    return f"{corps}{_SEPARATEUR}{devise}" if devise else corps
