"""L'ordre dans lequel une rubrique de Ma résidence montre ses documents (#2505).

Les plans et les comptes-rendus d'AG se lisent dans un ordre qui n'est pas celui
de leur dépôt. Le site les triait dans l'écran (`trierPlans`, `trierCrAg` de
`residence/+page.svelte`) ; l'app iOS, qui ne recopie aucune règle du front,
montrait l'ordre du serveur. `GET /documents?categorie=…` sert donc la liste
déjà rangée, et les deux clients l'affichent telle qu'elle arrive.

- **plans** : ceux de la copropriété d'abord, puis par bâtiment, dans l'ordre de
  son numéro (« A », « B »…) — jamais de son identifiant, qui ne suit pas le nom ;
- **comptes-rendus d'AG** : l'année la plus récente d'abord, puis la date de
  l'assemblée (à défaut, celle du dépôt), la plus récente d'abord.

Une autre catégorie garde l'ordre de la requête : du plus récent dépôt au plus
ancien.
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Optional

from sqlmodel import Session, select

from app.models.core import Batiment, Document
from app.utils.noms import cle_de_classement


def _plans(session: Session, docs: list[Document]) -> list[Document]:
    numeros = {b.id: b.numero for b in session.exec(select(Batiment)).all()}

    def cle(d: Document) -> tuple:
        if not d.batiment_id:
            return (0, cle_de_classement(None, ""))
        return (1, cle_de_classement(None, numeros.get(d.batiment_id, "")))

    return sorted(docs, key=cle)


def _jour_de_l_ag(d: Document) -> date:
    return d.date_ag or d.publie_le.date()


def _comptes_rendus(_session: Session, docs: list[Document]) -> list[Document]:
    return sorted(docs, key=lambda d: (d.annee or 0, _jour_de_l_ag(d)), reverse=True)


#: L'ordre propre à une catégorie, par son CODE (`CategorieDocument.code`).
ORDRES: dict[str, Callable[[Session, list[Document]], list[Document]]] = {
    "plan_residence": _plans,
    "pv_ag": _comptes_rendus,
}


def ordonner(session: Session, categorie: Optional[str], docs: list[Document]) -> list[Document]:
    """Les documents d'une rubrique dans l'ordre où elle les montre."""
    ordre = ORDRES.get(categorie or "")
    return ordre(session, docs) if ordre else docs
