"""Le lieu d'un contenu, SERVI avec lui — le badge 🔹 (#2505, généralisé par #2633).

Le site nommait le périmètre d'un contenu dans son front (`perimetreLabel`) ; l'app
iOS n'avait que les codes. Un schéma qui porte `perimetre_cible` mêle
`AvecPerimetreLibelle` : il sert `perimetre_libelle`, calculé par `perimetre_badge`
— VIDE pour le périmètre par défaut, que le badge tait. Le calcul vit au schéma :
vrai partout où il est rendu, sans qu'un appelant puisse l'oublier.
"""

from __future__ import annotations

from pydantic import BaseModel, computed_field

from app.utils.perimetres.arbre import parse_json_perimetres
from app.utils.perimetres.libelles import perimetre_badge, perimetre_label


def codes_de(perimetre) -> list[str]:
    """Les codes d'un périmètre, en liste ou en chaîne JSON — vide s'il manque."""
    if isinstance(perimetre, list):
        return perimetre
    return parse_json_perimetres(perimetre) if perimetre else []


class AvecPerimetreLibelle(BaseModel):
    """`perimetre_libelle` : le badge 🔹 du contenu (`perimetre_badge`)."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def perimetre_libelle(self) -> str:
        """« Bât. 2 › Toit » — `""` pour le périmètre par défaut, que le badge tait."""
        return perimetre_badge(codes_de(getattr(self, "perimetre_cible", None)))


def libelle_complet(perimetre) -> str:
    """Le lieu, MÊME par défaut — `perimetre_label`, vide sans périmètre."""
    codes = codes_de(perimetre)
    return perimetre_label(codes) if codes else ""


__all__ = ["AvecPerimetreLibelle", "codes_de", "libelle_complet"]
