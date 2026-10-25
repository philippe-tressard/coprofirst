"""Les périmètres d'un lot — DÉRIVÉS de sa désignation, jamais saisis deux fois (#2212).

Un lot a trois rattachements indépendants (spec `lots-et-perimetres.md` §1) : le
bâtiment où il est *situé*, la circulation qui le *dessert*, les clés de charges
auxquelles il contribue. Les deux premiers se traduisent en nœuds de l'arbre des
périmètres, rangés dans `lot_perimetre` :

| Relation | Nœuds |
|---|---|
| `situe_dans` | le nœud de son bâtiment ; pour une place sans bâtiment, le nœud qui porte le stationnement |
| `desservi_par` | les enfants de sa circulation qui desservent (`desserte = circulation`) ; une cave y ajoute les caves de sa circulation, une place le stationnement |

🔴 **Le nœud du bâtiment desservant n'en fait PAS partie**, seulement ses espaces de
circulation. Arbitré le 24/10/2026 (coordination, sur délégation de Philippe du
17/10) : détenir une place desservie par le bâtiment 3 ouvre son ascenseur et son
escalier, jamais un contenu ciblé « Bâtiment 3 » en entier — ses actualités
confidentielles, son hall, son toit.

**Aucun code de nœud n'est écrit ici** : tout se lit sur l'arbre (`desserte`,
`parent`, `batiment_id`), administré. Une copropriété sans ascenseur ni caves n'a
simplement pas ces nœuds, et la dérivation n'en pose pas.
"""

from __future__ import annotations

from typing import Iterable, Optional

from app.models.copropriete import NatureLot
from app.models.perimetre import DessertePerimetre, RelationLotPerimetre
from app.utils.designation_lot import nature_du_lot
from app.utils.perimetres.arbre import Noeud, arbre, perimetre_du_batiment

_SITUE = RelationLotPerimetre.situe_dans
_DESSERVI = RelationLotPerimetre.desservi_par


def _dessertes(noeuds: dict[str, Noeud], desserte: DessertePerimetre, parent: Optional[str]):
    """Les nœuds actifs qui portent cette desserte — sous `parent`, ou partout."""
    return [
        n.code
        for n in noeuds.values()
        if n.actif
        and n.desserte == desserte.value
        and (parent is None or (n.parent or "") == parent.lower())
    ]


def deriver(
    nature: Optional[NatureLot],
    batiment: Optional[str],
    circulation: Optional[str],
    noeuds: dict[str, Noeud],
) -> set[tuple[str, RelationLotPerimetre]]:
    """Les `(code, relation)` d'un lot — fonction PURE, l'arbre est passé en argument.

    `batiment` est le code du nœud de son bâtiment, `circulation` celui du nœud qui
    le dessert (le bâtiment desservant). Un logement ou un commerce sans circulation
    déclarée est desservi par son propre bâtiment ; une annexe sans circulation est
    à accès direct.
    """
    paires: set[tuple[str, RelationLotPerimetre]] = set()
    stationnement = _dessertes(noeuds, DessertePerimetre.stationnement, None)

    if batiment:
        paires.add((batiment, _SITUE))
    elif nature == NatureLot.parking:
        paires.update((code, _SITUE) for code in stationnement)

    if circulation is None and nature not in (NatureLot.cave, NatureLot.parking):
        circulation = batiment
    if circulation:
        paires.update(
            (code, _DESSERVI)
            for code in _dessertes(noeuds, DessertePerimetre.circulation, circulation)
        )
        if nature == NatureLot.cave:
            paires.update(
                (code, _DESSERVI)
                for code in _dessertes(noeuds, DessertePerimetre.caves, circulation)
            )
    if nature == NatureLot.parking:
        paires.update((code, _DESSERVI) for code in stationnement)
    return paires


def _code_de(noeuds_par_id: dict[int, Noeud], perimetre_id: Optional[int]) -> Optional[str]:
    noeud = noeuds_par_id.get(perimetre_id) if perimetre_id is not None else None
    return noeud.code if noeud is not None else None


def rederiver(session, lots: Iterable) -> int:
    """Réécrit les lignes DÉRIVÉES de ces lots ; une ligne posée à la main reste.

    Renvoie le nombre de lignes ajoutées ou retirées. N'écrit rien si l'arbre est
    vide — une copropriété sans arbre n'a rien à dériver. L'appelant valide la
    transaction ; « mes bâtiments » et « mes périmètres » sont invalidés ici, parce
    qu'ils en dépendent.
    """
    from sqlmodel import select

    from app.models.perimetre import LotPerimetre
    from app.utils import mes_batiments

    noeuds = arbre()
    if not noeuds:
        return 0
    noeuds_par_id = {n.id: n for n in noeuds.values() if n.id is not None}
    id_par_code = {n.code.lower(): n.id for n in noeuds.values()}
    lots = list(lots)
    existantes: dict[int, list[LotPerimetre]] = {}
    for ligne in session.exec(
        select(LotPerimetre).where(LotPerimetre.lot_id.in_([lot.id for lot in lots]))  # type: ignore[union-attr]
    ).all():
        existantes.setdefault(ligne.lot_id, []).append(ligne)

    ecrites = 0
    for lot in lots:
        noeud_bat = perimetre_du_batiment(lot.batiment_id)
        voulues = {
            (id_par_code[code.lower()], relation)
            for code, relation in deriver(
                nature_du_lot(lot),
                noeud_bat.code if noeud_bat else None,
                _code_de(noeuds_par_id, lot.circulation_perimetre_id),
                noeuds,
            )
        }
        presentes = set()
        for ligne in existantes.get(lot.id, []):
            cle = (ligne.perimetre_id, RelationLotPerimetre(ligne.relation))
            if ligne.derive and cle not in voulues:
                session.delete(ligne)
                ecrites += 1
            else:
                presentes.add(cle)
        for perimetre_id, relation in voulues - presentes:
            session.add(LotPerimetre(lot_id=lot.id, perimetre_id=perimetre_id, relation=relation))
            ecrites += 1
    mes_batiments.invalider_cache()
    return ecrites
