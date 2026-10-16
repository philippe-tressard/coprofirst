"""Les lots d'un compte : ceux qu'un lien ACTIF lui rattache, et rien d'autre.

## 🔴 Pourquoi aucun repli « tous les lots »

`GET /lots/mes-lots` rendait jusqu'au 16/10/2026 TOUS les lots de la résidence
à un administrateur, un conseiller ou un opérateur sans lot propre — « pour
consulter le patrimoine ». Les écrans, eux, y lisent « mes lots » : le profil
proposait l'étage de trente logements à un compte qui n'en habite aucun,
l'accueil lui attribuait l'étage du premier appartement venu, et les accès lui
offraient de commander un badge pour des lots où la commande est refusée
(`est_rattache_au_lot`). Consulter tout le patrimoine a sa route,
`GET /lots/admin/tous`, réservée au conseil et à l'administration.

La même requête était écrite ici ET dans `utils/alerte_etage` — qui, elle,
refusait le repli : deux écritures d'une notion divergent sur le cas limite.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.core import Lot, UserLot, Utilisateur


def rattachements_actifs(session: Session, user: Utilisateur) -> list[tuple[Lot, UserLot]]:
    """Chaque lot rattaché à ce compte par un lien actif, avec ce lien — un lot une fois."""
    lignes = session.exec(
        select(Lot, UserLot)
        .join(UserLot, UserLot.lot_id == Lot.id)
        .where(UserLot.user_id == user.id, UserLot.actif == True)  # noqa: E712
        .order_by(Lot.id)
    ).all()
    par_lot: dict[int, tuple[Lot, UserLot]] = {}
    for lot, lien in lignes:
        par_lot.setdefault(lot.id, (lot, lien))
    return list(par_lot.values())


def lots_de(session: Session, user: Utilisateur) -> list[Lot]:
    """Les lots activement rattachés à ce compte — vide s'il n'en a aucun, quel que soit son rôle."""
    return [lot for lot, _ in rattachements_actifs(session, user)]
