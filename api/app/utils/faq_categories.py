"""Les catégories de la FAQ : leur libellé, et qui les lit (#2506).

## Pourquoi ce module (04/11/2026)

Les deux règles vivaient dans le front seulement (`#lib/faq.ts`,
`normalizeCategorieLabel` et `categoriesPourStatut`). L'app iOS, qui ne parle
qu'au contrat de l'API, montrait donc **toutes** les catégories à tous, sous
leur nom brut. Une règle d'affichage que deux clients montrent se calcule au
serveur (`standards/09` §8, règle 1) : `GET /faq` filtre, et chaque entrée porte
son `categorie_libelle`. Le front lit les deux.

⚠️ Les catégories sont du TEXTE administrable, pas une énumération : on les
reconnaît par les mots qu'elles portent, accents et casse repliés — exactement
comme le faisait l'écran, pour que rien ne change à ce qu'il montre.

⚠️ Ce n'est PAS une règle d'accès : une question de FAQ n'a rien de confidentiel,
et le conseil lit tout (`/faq/all`). C'est un tri de pertinence — un locataire ne
lit pas ce qui ne parle qu'aux copropriétaires.
"""

from __future__ import annotations

from typing import Optional

from app.utils.recherche_affaires import replier
from app.utils.valeurs import valeur

#: La catégorie d'une entrée sans catégorie — celle que l'écran affichait.
CATEGORIE_PAR_DEFAUT = "Général"

#: Le libellé d'une catégorie qui nomme les copropriétaires ET les mandataires.
LIBELLE_COPRO_BAILLEUR = "📋 Copropriétaire bailleur"


def _plie(texte: Optional[str]) -> str:
    """Minuscules, sans accents, bords rognés : le `replier` du front."""
    return replier(texte).strip()


def libelle_categorie_faq(categorie: Optional[str]) -> str:
    """Le libellé affiché d'une catégorie — « copropriétaire » + « mandataire »
    se lisent « 📋 Copropriétaire bailleur » ; les autres, telles que saisies."""
    original = categorie or CATEGORIE_PAR_DEFAUT
    n = _plie(original)
    if "coproprietaire" in n and "mandataire" in n:
        return LIBELLE_COPRO_BAILLEUR
    return original


def _categorie_locataire(n: str) -> bool:
    return "locataire" in n


def _categorie_bailleur(n: str) -> bool:
    return "coproprietaire" in n and ("bailleur" in n or "mandataire" in n)


def _categorie_resident(n: str) -> bool:
    return "coproprietaire" in n and "resident" in n


def categorie_lue_par(categorie: Optional[str], statut) -> bool:
    """Le lecteur de ce statut lit-il cette catégorie ?

    Un locataire ne lit pas celles des copropriétaires, un résident pas celles
    des bailleurs ni des locataires, un bailleur pas celles des résidents ni des
    locataires. Sans statut connu, tout reste lisible. Le test porte sur le
    LIBELLÉ (« 📋 Copropriétaire bailleur » compris), comme le faisait l'écran.
    """
    s = _plie(valeur(statut) if statut is not None else "")
    if not s:
        return True
    n = _plie(libelle_categorie_faq(categorie))
    if s == "locataire":
        return not (_categorie_resident(n) or _categorie_bailleur(n))
    copro = "coproprietaire" in s
    if copro and "resident" in s:
        return not (_categorie_locataire(n) or _categorie_bailleur(n))
    if copro and ("bailleur" in s or "mandataire" in s):
        return not (_categorie_locataire(n) or _categorie_resident(n))
    if copro:
        return not _categorie_locataire(n)
    return True
