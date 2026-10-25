"""Clés de charges et quotes-parts — ce que le règlement dit qu'un lot paie (#2212).

Un lot contribue à PLUSIEURS répartitions : charges générales, bâtiment, ascenseur,
escalier… chacune avec son dénominateur (10 000, 1 000). `UserLot.quote_part`, unique
et posée sur le LIEN, ne pouvait pas le dire : la quote-part est celle du LOT, quel
que soit son propriétaire (spec `lots-et-perimetres.md` §4).

🔴 **Aucune clé n'est écrite dans le code** : elles viennent de l'état descriptif,
importé par l'atelier (`utils/etat_descriptif`), et ne bougent qu'avec un acte
modificatif. L'application EXPLIQUE une charge par sa clé et sa source ; elle ne la
calcule pas.
"""

from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class CleDeCharges(SQLModel, table=True):
    """Une répartition du règlement : « Charges générales », « Ascenseur A »…"""

    __tablename__ = "cle_de_charges"
    id: Optional[int] = Field(default=None, primary_key=True)
    #: Dérivé du libellé à l'import ; c'est par lui qu'un réimport retrouve la clé.
    code: str = Field(unique=True, index=True)
    libelle: str
    #: Déclaré par l'en-tête du fichier, jamais déduit de la somme des parts : c'est
    #: la somme qu'on CONTRÔLE contre lui.
    denominateur: int
    #: Le périmètre dont cette clé répartit les charges (l'ascenseur d'un bâtiment) —
    #: facultatif, il ne sert qu'à expliquer.
    perimetre_id: Optional[int] = Field(default=None, foreign_key="perimetre.id")
    ordre: int = Field(default=0)
    #: Ce que la clé finance, tel que le règlement le définit (« l'escalier qui dessert
    #: les deux niveaux de sous-sol ») — sans elle, « Escalier A » et « Escalier A' » ne
    #: se distinguent pas (#2251). Entre par l'atelier (feuille « Clés »).
    description: Optional[str] = None


class QuotePartLot(SQLModel, table=True):
    """La part d'un lot dans une clé : `numerateur / cle.denominateur`."""

    __tablename__ = "quote_part_lot"
    __table_args__ = (UniqueConstraint("lot_id", "cle_id", name="uq_quote_part_lot"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    lot_id: int = Field(foreign_key="lot.id", index=True)
    cle_id: int = Field(foreign_key="cle_de_charges.id")
    numerateur: int
