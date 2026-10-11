"""Le LIEN vers le règlement publié, que l'onglet donne à qui n'est pas l'administration.

## Pourquoi (11/10/2026)

Les fichiers que l'assistant lit sont réservés à l'administration
(`texte.CODE_CATEGORIE`). Les autres — conseil syndical compris — lisent une
phrase simple : « Le règlement de copropriété est disponible sur le site », avec
un lien vers le règlement rangé dans la Fiche de Ma résidence.

## Lequel : le plus récent de la catégorie « Règlement de copropriété »

Aucun numéro de document n'est écrit dans le code : l'application sert d'autres
copropriétés. Le plus récent est le recueil consolidé que la copropriété vient de
déposer — chez 5Hostachy, le doc-27 qu'on voulait viser — et un recueil plus
neuf le remplacera de lui-même. Il est montré à chacun s'IL peut le lire
(`document_visible`, puis `lien_document`, les deux règles qui décident partout).
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, col, select

from app.models.core import CategorieDocument, Document, Utilisateur
from app.utils.documents import lien_document
from app.utils.visibility import document_visible

#: La catégorie du règlement publié, celle de la rubrique de la Fiche.
CODE_REGLEMENT_PUBLIE = "reglement_copropriete"


def lien_reglement(session: Session, user: Utilisateur) -> Optional[str]:
    """Le lien vers le règlement le plus récent que `user` peut lire, ou `None`."""
    docs = session.exec(
        select(Document)
        .join(CategorieDocument, col(CategorieDocument.id) == col(Document.categorie_id))
        .where(
            CategorieDocument.code == CODE_REGLEMENT_PUBLIE,
            col(Document.ticket_id).is_(None),
            col(Document.contrat_id).is_(None),
            col(Document.evenement_id).is_(None),
        )
        .order_by(col(Document.publie_le).desc(), col(Document.id).desc())
    ).all()
    for doc in docs:
        if document_visible(user, doc, session):
            lien = lien_document(doc, user, session)
            if lien:
                return lien
    return None


__all__ = ["CODE_REGLEMENT_PUBLIE", "lien_reglement"]
