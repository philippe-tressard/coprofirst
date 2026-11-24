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

from decimal import ROUND_HALF_UP, Decimal

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


# ── Centimes entiers (socle 06 §7 : un montant ne se stocke pas en flottant, #3011) ─


def en_centimes(euros: float | int | None) -> int | None:
    """`19.99` → `1999` · `None` → `None`. PURE.

    Par la décimale ÉCRITE (`repr` du flottant) et un arrondi au plus proche, la
    moitié s'éloignant de zéro — le `ROUND(prix::numeric * 100)` de PostgreSQL, que
    la migration 0348 emploie pour la reprise. `int(19.99 * 100)` rendrait 1998.
    """
    if euros is None:
        return None
    return int((Decimal(repr(float(euros))) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def en_euros(centimes: int | None) -> float | None:
    """`1999` → `19.99` — pour un champ servi en euros, que des clients lisent encore."""
    return None if centimes is None else centimes / 100
