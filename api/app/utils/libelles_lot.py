"""Le type et le nom d'un lot en clair — « Appartement », « Appartement – T3 », « Place 450 ».

## Pourquoi ici (#2507, 04/11/2026)

Ces libellés se composaient dans le front (`lotTypeLabel`, `lotTypeComplet` dans
`utils.ts`, `nomDuLot` dans `charges-lots.ts`). L'app iOS ne parle qu'au contrat
de l'API et ne recopie aucune règle du site : elle montrait « appartement » brut.
Une règle que deux clients affichent se calcule au serveur (`standards/09` §8,
règle 1) : l'API la SERT, champ par champ (`LotRead.libelle_type`…), et le site
la lit. 🔒 `npm run lint:regles-partagees`.

⚠️ Une valeur inconnue n'est pas remplacée par « — » : un type ajouté doit
s'afficher plutôt que disparaître. Elle est seulement mise en forme — soulignés en
espaces, initiale en majuscule (`local_commercial` → « Local commercial »). Seule
l'absence de type rend « — ».
"""

from __future__ import annotations

from typing import Optional

from app.utils.valeurs import valeur

#: Les types que le règlement nomme autrement que par leur code.
_LIBELLES = {"appartement": "Appartement", "parking": "Parking", "cave": "Cave"}

#: Ce que rend un lot sans type : un tiret, jamais une chaîne vide.
SANS_TYPE = "—"


def libelle_type_lot(code) -> str:
    """« Appartement », « Parking », « Local commercial » — le type d'un lot en clair."""
    brut = str(valeur(code) or "")
    if not brut:
        return SANS_TYPE
    if brut in _LIBELLES:
        return _LIBELLES[brut]
    lisible = brut.replace("_", " ")
    return lisible[:1].upper() + lisible[1:]


def libelle_type_complet(code, type_appartement: Optional[str] = None) -> str:
    """« Appartement – T3 » : le type, et sa précision quand le lot en porte une."""
    base = libelle_type_lot(code)
    return f"{base} – {type_appartement}" if type_appartement else base


def nature_ou_type(lot) -> str:
    """La nature du règlement (`nature`), sinon le type du lot — ce qui NOMME le lot."""
    nature = getattr(lot, "nature", None)
    return str(valeur(nature) or valeur(getattr(lot, "type", None)) or "")


def nom_du_lot(lot) -> str:
    """« Logement 15 », « Cave 417 », « Place 450 » — un lot nommé par sa nature et son numéro.

    « Place » et non « Parking » : c'est ainsi qu'un résident nomme son emplacement.
    """
    nature = nature_ou_type(lot)
    nom = "Place" if nature == "parking" else libelle_type_lot(nature)
    return f"{nom} {getattr(lot, 'numero', '')}".rstrip()


__all__ = [
    "SANS_TYPE",
    "libelle_type_complet",
    "libelle_type_lot",
    "nature_ou_type",
    "nom_du_lot",
]
