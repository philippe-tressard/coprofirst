"""Périmètres — l'arborescence qui dit OÙ se situe une demande.

Module à part, et non une classe de plus dans `core.py` : ce fichier passait
1 506 lignes avant ce lot, et la règle de modularité — rang 1, sans exception —
refuse qu'un fichier au-delà de 500 lignes grossisse pour une nouvelle
fonctionnalité. Le pré-check l'a refusé, à juste titre.

`Perimetre` est réexporté par `app.models.core`, si bien que les imports
existants (`from app.models.core import Perimetre`) continuent de fonctionner —
et surtout que la table reste enregistrée auprès de SQLModel au moment du
`create_all`, ce qu'un module jamais importé ne garantirait pas.
"""

from app.utils import horloge
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint
from pydantic import NaiveDatetime


class DessertePerimetre(str, Enum):
    """Ce qu'un nœud dessert — voir `Perimetre.desserte`."""

    circulation = "circulation"
    caves = "caves"
    stationnement = "stationnement"


class RelationLotPerimetre(str, Enum):
    """Les deux rattachements d'un lot à l'arbre (spec `lots-et-perimetres.md` §1)."""

    situe_dans = "situe_dans"
    desservi_par = "desservi_par"


class Perimetre(SQLModel, table=True):
    """Arborescence des périmètres — **où** se situe une demande.

    Remplace la table de libellés qui était écrite en dur à deux endroits, avec
    deux contenus différents : `utils/perimetres.py` couvrait `bat:1` à `bat:9`,
    `front/src/lib/utils.ts` s'arrêtait à `bat:4`. Un cinquième bâtiment
    s'affichait donc « Bât. 5 » côté API et `bat:5` brut à l'écran.

    **Aucun code de périmètre n'existe plus dans le code.** Le produit doit servir
    une autre copropriété, qui n'a ni AFUL, ni quatre bâtiments, ni forcément de
    caves : cet arbre est intégralement reconstructible depuis l'administration, et
    le vider ne doit rien casser (un périmètre vide vaut « concerne tout le monde »,
    comme aujourd'hui).

    À ne pas confondre avec `Document.perimetre` / `CategorieDocument.perimetre_defaut`
    (`résidence` / `bâtiment` / `lot`), qui portent le même nom mais répondent à une
    autre question : non pas *où* se passe une demande, mais *qui a le droit de lire*
    un fichier. Les deux axes restent distincts — le glossaire nomme le second
    « granularité documentaire ».
    """

    __tablename__ = "perimetre"
    id: Optional[int] = Field(default=None, primary_key=True)

    #: Ce qui est stocké dans les contenus (`ticket.perimetre_cible`,
    #: `evenement.perimetre`…). **Immuable après création** : le changer
    #: orphelinerait les tickets déjà publiés.
    code: str = Field(unique=True, index=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="perimetre.id")

    libelle: str
    libelle_court: Optional[str] = None
    description: str = ""
    icone: Optional[str] = None  # nom d'icône Lucide, rendu par Icon.svelte

    #: Rattachement réel au bâtiment, en clé étrangère — remplace le préfixe
    #: textuel `bat:` qui était analysé à sept endroits du dépôt. Les descendants
    #: d'un nœud de bâtiment en héritent par remontée d'arbre.
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")

    #: ⚠️ Décision de sécurité. Remplace la liste `SCOPES_RESIDENCE`, qui existait
    #: en trois exemplaires. Un nœud à portée globale, ou dont un ancêtre l'est,
    #: est visible de tous les résidents et notifie l'ensemble du conseil syndical.
    portee_globale: bool = Field(default=False)

    #: Un nœud de regroupement (« Bâtiments ») ne se cible pas. Sert aussi à
    #: retirer un périmètre de la saisie sans casser l'historique : `cave` reste
    #: affiché sur les contenus déjà publiés, sans être proposé aux nouveaux.
    selectionnable: bool = Field(default=True)
    #: Ce nœud désigne-t-il un espace **PRIVATIF** — un logement, une cave, une
    #: place de parking attribuée — par opposition aux parties communes ?
    #:
    #: Demandé le 31/08/2026. La copropriété n'a pas de mot pour cette
    #: distinction dans l'arborescence : « Logement » y voisine « Hall d'entrée »
    #: sans que rien ne dise que l'un est chez quelqu'un et l'autre à tout le
    #: monde. Or c'est la question qu'on se pose en premier devant une demande.
    #:
    #: ⚠️ **Purement visuel pour l'instant**, et c'est délibéré : la pastille se
    #: distingue, rien d'autre ne change. Le jour où il faudra en tirer un droit
    #: — qui voit, qui est notifié — la donnée sera là, et la décision sera
    #: prise pour elle-même plutôt que découverte dans un effet de bord.
    #:
    #: Administré depuis Admin → Patrimoine, comme `selectionnable`.
    privatif: bool = Field(default=False)

    #: Ce nœud appartient-il à **quelqu'un d'autre** que la copropriété ?
    #:
    #: L'AFUL — association foncière urbaine libre — en est le cas type : le
    #: parking qu'elle gère est traversé par les résidents et la copropriété
    #: participe à son assemblée, mais il **n'est pas à elle**. Une voie communale,
    #: un terrain mitoyen conventionné relèvent de la même catégorie.
    #:
    #: 🔴 Conséquence, et c'est le défaut qui l'a fait naître (13/09/2026, #943) :
    #: ce qui couvre « toute la copropriété » ne couvre PAS ce nœud. Un contrat de
    #: nettoyage de la résidence entretient le parking de la résidence ; il
    #: n'entretient pas celui de l'AFUL. Le filtre « AFUL » du carnet d'entretien
    #: remontait pourtant toutes les lignes « Copropriété entière » — il ne
    #: filtrait donc presque rien.
    #:
    #: ⚠️ **Distinct de `portee_globale`, et les deux coexistent sur l'AFUL** :
    #: « concerne tous les résidents » (qui VOIT) et « appartient à la
    #: copropriété » (ce qui le COUVRE) sont deux questions. L'AFUL répond oui à
    #: la première et non à la seconde.
    #:
    #: ⚠️ Administré depuis Admin → Patrimoine : une autre copropriété n'a pas
    #: d'AFUL, et le code ne doit connaître aucun nœud par son nom.
    hors_copropriete: bool = Field(default=False)

    #: Ce nœud DESSERT-il des lots, et comment ? (#2212, spec `lots-et-perimetres.md` §4)
    #:
    #: Un parking ou une cave est rattaché à la circulation qui le dessert, pas au
    #: bâtiment de son propriétaire. Le lot désigne le nœud de cette circulation
    #: (`Lot.circulation_perimetre_id`, le bâtiment) ; ce drapeau dit lesquels de
    #: ses enfants en relèvent — l'ascenseur et les escaliers (`circulation`), les
    #: caves (`caves`) — et quel nœud porte les places (`stationnement`).
    #:
    #: ⚠️ Administré, comme `privatif` : aucun code ne connaît « ascenseur » par son
    #: nom, une autre copropriété a peut-être deux escaliers ou aucun ascenseur.
    desserte: Optional[DessertePerimetre] = None

    ordre: int = Field(default=0)
    actif: bool = Field(default=True)

    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    modifie_le: Optional[NaiveDatetime] = None
    modifie_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")


class LotPerimetre(SQLModel, table=True):
    """Les périmètres qui concernent un lot — DÉRIVÉS, jamais saisis deux fois (#2212).

    *Situé dans* : le nœud de son bâtiment (le stationnement pour une place sans
    bâtiment). *Desservi par* : les nœuds de sa circulation qui desservent
    (`Perimetre.desserte`). La dérivation est une fonction pure,
    `utils/perimetres/lots.deriver` ; `derive = False` marque une ligne posée à la
    main dans l'administration, qu'une re-dérivation laisse en place.

    ⚠️ `derive` n'est pas un `actif` : il ne fait rien disparaître, il dit qui a
    écrit la ligne (`test_archivage_colonnes_booleennes`).
    """

    __tablename__ = "lot_perimetre"
    __table_args__ = (
        UniqueConstraint("lot_id", "perimetre_id", "relation", name="uq_lot_perimetre"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    lot_id: int = Field(foreign_key="lot.id", index=True)
    perimetre_id: int = Field(foreign_key="perimetre.id")
    relation: RelationLotPerimetre
    derive: bool = Field(default=True)
