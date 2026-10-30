"""La PALETTE de la copropriété — ses couleurs sur le site, les courriels et les affiches.

## Ce qu'elle est (#2379, 30/10/2026)

L'administration choisit, à côté du logo, une palette parmi celles de ce registre
(clé `site_palette`, onglet Copropriété › Identité). Le style ne change pas —
polices, formes, en-tête restent ceux de la charte — : seules les couleurs
suivent. La palette par défaut est la charte elle-même (`seine`).

## Une seule liste, trois rendus

- le **site** lit ses jetons dans `front/src/styles/palettes.css`, l'attribut
  `data-palette` posé par le serveur (`#lib/palettes.ts`) ;
- un **courriel** et un **document PDF** sont composés aux couleurs de la charte,
  puis `recolorer` y substitue celles de la palette — UN geste, au point où
  chacun se termine (`composer_email`, `html_to_pdf`), plutôt qu'une palette lue
  dans chacun des modèles : ceux des courriels vivent en base et l'administration
  les édite, un modèle réécrit à la main garderait ses couleurs.

Le front et l'API ne partagent aucun fichier (contextes de build distincts) : les
valeurs claires sont donc écrites deux fois, ici et dans `palettes.css`.
🔒 `test_palettes.py` les confronte, code par code et couleur par couleur.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: La clé de configuration — écrite par l'onglet Identité, lue par le serveur du front.
CLE_PALETTE = "site_palette"


@dataclass(frozen=True)
class Palette:
    nom: str
    primaire: str
    primaire_fonce: str
    primaire_clair: str
    accent: str
    fond: str


#: Le registre — l'ordre est celui de l'écran. Les valeurs sont celles du thème CLAIR.
PALETTES: dict[str, Palette] = {
    "seine": Palette("Seine (charte)", "#1e3a5f", "#16304f", "#eef2f7", "#bd8c2c", "#f2efe9"),
    "bordeaux": Palette("Bordeaux & or", "#651d28", "#51171f", "#f5ecec", "#aa7d30", "#f4efe8"),
    "bouteille": Palette(
        "Vert bouteille & laiton", "#1b4232", "#143327", "#eaf1ed", "#a1813a", "#eef1ec"
    ),
    "cuivre": Palette("Bleu nuit & cuivre", "#1b2a41", "#131f31", "#edf0f5", "#bc734c", "#f1f0ee"),
    "roi": Palette("Bleu roi & moutarde", "#13376f", "#0f2c5a", "#ecf1fa", "#ab7e16", "#f3f2ee"),
    "prune": Palette("Prune & rose poudré", "#4a2540", "#3b1d33", "#f4edf2", "#b27670", "#f6f0ef"),
}

PALETTE_PAR_DEFAUT = "seine"

#: Les couleurs de la CHARTE telles que les courriels et les PDF les écrivent, et le
#: rôle qu'elles y jouent. L'or est celui d'origine (#C9983A) : c'est lui que les
#: modèles portent, l'or assombri du site (#2296) n'y figure pas.
_ROLES_CHARTE = {
    "#1e3a5f": "primaire",
    "#16304f": "primaire_fonce",
    "#eef2f7": "primaire_clair",
    "#c9983a": "accent",
    "#f2efe9": "fond",
}
_MOTIF_CHARTE = re.compile("|".join(_ROLES_CHARTE), re.IGNORECASE)


def code_palette(valeur: str | None) -> str:
    """Le code d'une valeur de configuration — liste blanche : inconnue ou absente → défaut."""
    v = (valeur or "").strip()
    return v if v in PALETTES else PALETTE_PAR_DEFAUT


def recolorer(html: str, valeur: str | None) -> str:
    """Le document aux couleurs de la palette `valeur`. PURE.

    La palette par défaut le rend tel quel : la charte est déjà la sienne.
    """
    code = code_palette(valeur)
    if code == PALETTE_PAR_DEFAUT:
        return html
    palette = PALETTES[code]
    return _MOTIF_CHARTE.sub(lambda m: getattr(palette, _ROLES_CHARTE[m.group(0).lower()]), html)


__all__ = ["CLE_PALETTE", "PALETTES", "PALETTE_PAR_DEFAUT", "Palette", "code_palette", "recolorer"]
