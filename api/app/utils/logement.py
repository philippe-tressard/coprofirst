"""« Bât. 4, T4, 2ème » — où habite un compte, tel que l'accueil le dit (#2500).

## Pourquoi côté serveur (03/11/2026)

La règle vivait dans le front (`libelleLogement`, `front/src/lib/utils.ts`), et
seul le site savait nommer le logement de quelqu'un. L'app iOS, qui lit la même
API, n'avait que deux choix : recopier la règle — une seconde écriture, libre de
diverger — ou ne rien afficher. Elle n'affichait rien. Arbitré par Philippe :
« Oui, côté serveur » — une seule source, que le site et l'app lisent dans
`GET /auth/me` (`libelle_logement`).

Elle est transposée À L'IDENTIQUE : le premier appartement rattaché, par ordre
d'identifiant (l'ordre de `GET /lots/mes-lots`), fait le libellé ; sans
appartement, le compte prend le relais.

🔴 Le repli sur le COMPTE n'est pas un détail (09/09/2026) : la règle rendait une
chaîne vide dès qu'un compte n'avait aucun lot, et un résident inscrit la veille
lisait « Bonsoir Thomas · Copropriétaire résident » quand son voisin lisait son
bâtiment, son type et son étage — alors que son bâtiment ET son étage étaient
saisis à l'inscription.
"""

from __future__ import annotations

from typing import Optional

from app.utils.batiments import libelle_batiment
from app.utils.etages import etage_label, type_de_lot


def libelle_logement(lots, batiment_du_compte: str, etage_du_compte: Optional[int]) -> str:
    """Le libellé du logement — une chaîne VIDE quand il n'y a rien à dire.

    `lots` : les lots activement rattachés au compte (`lots_rattaches.lots_de`).
    `batiment_du_compte` : son libellé (« Bât. A »), vide s'il n'en a pas.
    """
    appartement = next((lot for lot in lots if type_de_lot(lot) == "appartement"), None)
    if appartement is not None:
        parts: list[str] = []
        batiment = libelle_batiment(getattr(appartement, "batiment", None))
        if batiment:
            parts.append(batiment)
        elif batiment_du_compte:
            parts.append(batiment_du_compte)
        if appartement.type_appartement:
            parts.append(appartement.type_appartement)
        #  ⚠️ `is not None` : `0` est le rez-de-chaussée.
        if appartement.etage is not None:
            parts.append(etage_label(appartement.etage))
        return ", ".join(parts)
    #  Le repli sur le COMPTE. Le séparateur diffère exprès de celui du cas
    #  nominal : ce n'est pas la même phrase — elle porte un ÉTAT en son milieu, et
    #  « Bât. 3, sans lot, RDC » se lirait comme une énumération de trois choses de
    #  même nature.
    parts = []
    if batiment_du_compte:
        parts.append(batiment_du_compte)
    parts.append("sans lot")
    #  Rien n'est écrit quand l'étage n'a pas été saisi — une mention « étage
    #  inconnu » n'apprendrait rien à qui la lit sur SON écran.
    if etage_du_compte is not None:
        parts.append(etage_label(etage_du_compte))
    #  Ni bâtiment ni étage : « sans lot » tout seul est un reproche, pas une
    #  information. Mieux vaut ne rien dire.
    return " — ".join(parts) if len(parts) > 1 else ""
