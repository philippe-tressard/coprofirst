"""Les schémas de l'arborescence des périmètres — lecture, création, modification.

Sortis de `routers/patrimoine.py` le 10/11/2026, quand le niveau de chaque nœud
(`utils/perimetres/niveaux`) l'a fait passer au-delà de 500 lignes (`standards/02`
§6). Seuls ses deux routeurs (`patrimoine`, `patrimoine_branche`) les rendent ;
`patrimoine` les ré-exporte, et ses importateurs n'ont pas changé.
"""

from typing import Optional

from pydantic import BaseModel


class PerimetreRead(BaseModel):
    """Un nœud, tel que le front en a besoin pour afficher ET pour faire choisir."""

    id: int
    code: str
    parent: Optional[str]
    libelle: str
    libelle_court: str
    description: str
    icone: Optional[str]
    batiment_id: Optional[int]
    profondeur: int
    #: Le niveau lu par l'administrateur — 1 pour une tête de rangée (« Bâtiment 1 »,
    #: « Parking »), 0 pour un regroupement (« Bâtiments ») — et combien de niveaux
    #: il peut encore porter sous lui (`utils/perimetres/niveaux`, plafond 3).
    #: L'écran retire « Ajouter un sous-périmètre » à 0 et écarte des copies les
    #: parents trop bas : jamais une règle recopiée, toujours ce que le serveur dit.
    niveau: int = 0
    niveaux_libres: int = 0
    #: Combien de niveaux la branche compte SOUS ce nœud (0 pour une feuille).
    hauteur: int = 0
    ordre: int
    actif: bool

    #: Le drapeau porté par ce nœud — ce que l'écran édite.
    portee_globale: bool
    #: Le drapeau **effectif**, héritage compris. C'est lui qui répond à « ce contenu
    #: sera-t-il visible de tous les résidents ? », donc lui que l'aide affiche.
    concerne_tous: bool
    #: Un regroupement ne se cible pas, et un nœud retiré de la saisie non plus. Le
    #: front doit tout de même les connaître pour afficher le libellé des contenus
    #: déjà publiés qui les citent — d'où un seul point de lecture et des drapeaux
    #: plutôt que deux listes.
    selectionnable: bool
    privatif: bool
    #: Ce nœud appartient à un tiers (AFUL, voie communale) : ce qui couvre
    #: « toute la copropriété » ne le couvre pas (#943).
    hors_copropriete: bool
    #: Vrai si un contenu cite ce code : l'écran propose alors de désactiver plutôt
    #: que de supprimer, et dit pourquoi.
    utilise: bool
    #: Combien de nœuds la suppression emporterait avec lui — ce que la
    #: confirmation annonce.
    nb_descendants: int = 0
    #: Le serveur accepterait-il de dupliquer cette branche ? Lu sur la même règle
    #: que le geste qui refuse (`refus_duplication`), jamais recopié à l'écran.
    dupliquable: bool = False
    #: …et de le copier sous d'autres parents (`refus_copie`), et lesquelles des
    #: quatre flèches il accepterait (`sens_admis`) : l'écran grise les autres.
    copiable: bool = False
    deplacements: list[str] = []
    #: Les types d'accès (`types_acces.TYPES_ACCES`) qui ouvrent ce nœud d'office,
    #: sans dépendre d'aucun lot — un portillon, un portail (#2060).
    acces_fixes: list[str] = []
    #: Le SEUL nœud que désigne un contenu sans périmètre explicite — « toute la
    #: copropriété » (`code_par_defaut`). Les clients le présélectionnent et le
    #: taisent en pastille sans refaire le tri (#2514, `standards/09` §8).
    par_defaut: bool = False


class PerimetreCreate(BaseModel):
    code: str
    libelle: str
    parent: Optional[str] = None
    libelle_court: Optional[str] = None
    description: str = ""
    icone: Optional[str] = None
    batiment_id: Optional[int] = None
    portee_globale: bool = False
    selectionnable: bool = True
    privatif: bool = False
    hors_copropriete: bool = False
    ordre: int = 0


class PerimetreUpdate(BaseModel):
    """Tout est optionnel — sauf `code`, qui n'y figure pas du tout."""

    libelle: Optional[str] = None
    parent: Optional[str] = None
    libelle_court: Optional[str] = None
    description: Optional[str] = None
    icone: Optional[str] = None
    batiment_id: Optional[int] = None
    portee_globale: Optional[bool] = None
    selectionnable: Optional[bool] = None
    privatif: Optional[bool] = None
    hors_copropriete: Optional[bool] = None
    ordre: Optional[int] = None
    actif: Optional[bool] = None
    #: Remplace la liste des types d'accès fixes de ce nœud (#2060).
    acces_fixes: Optional[list[str]] = None
