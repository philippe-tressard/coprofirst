"""Les DOCUMENTS du règlement que l'onglet montre à côté du texte (11/10/2026).

## Pourquoi

Le texte que l'assistant lit est un texte de TRAVAIL (Markdown) : il ne fait
pas foi, et il ne se montre pas aux copropriétaires. Ce qu'ils doivent pouvoir
ouvrir, ce sont les actes — le règlement numérisé, l'original et ses
modificatifs —, déjà rangés dans la bibliothèque de la résidence.

## Choisis par l'administration, jamais écrits dans le code

Le dépôt est public et l'application sert d'autres copropriétés : un numéro de
document écrit ici serait faux partout ailleurs (arbitré le 11/10/2026).
L'administration coche les documents dans l'onglet ; leur liste, ordonnée, vit
dans la clé `reglement_documents` (JSON).

## Ce qui peut être lié, et ce qui se montre

- **Candidat** : un document qui a une place à lui sur Ma résidence (plans,
  règlement, PV d'AG — `utils/documents.CATEGORIES_AVEC_LIEN`) et aucun porteur
  (affaire, contrat, événement) : c'est là que mène le lien.
- **Montré** : à chacun, ceux qu'IL peut lire — `document_visible` puis
  `lien_document`, les deux règles qui décident partout ailleurs. Un document
  réservé au conseil disparaît de la liste d'un copropriétaire au lieu de le
  mener vers un refus.
"""

from __future__ import annotations

import json

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.models.core import ConfigSite, Utilisateur
from app.models.documents import CategorieDocument, Document
from app.utils.documents import CATEGORIES_AVEC_LIEN, lien_document
from app.utils.visibility import document_visible

#: La clé `ConfigSite` qui porte les identifiants, dans l'ordre d'affichage.
CLE_DOCUMENTS = "reglement_documents"
#: Au-delà, ce n'est plus un renvoi aux actes mais une bibliothèque recopiée.
MAX_DOCUMENTS = 12


def ids_lies(session: Session) -> list[int]:
    """Les identifiants enregistrés — liste vide si rien de lisible : une valeur
    malheureuse ne doit pas rendre l'onglet inutilisable."""
    ligne = session.get(ConfigSite, CLE_DOCUMENTS)
    try:
        ids = json.loads(ligne.valeur) if ligne and ligne.valeur else []
    except ValueError:
        return []
    if not isinstance(ids, list):
        return []
    return [i for i in ids if isinstance(i, int) and not isinstance(i, bool)]


def candidats(session: Session) -> list[Document]:
    """Les documents qu'on peut lier : une rubrique à eux sur Ma résidence, sans porteur."""
    return list(
        session.exec(
            select(Document)
            .join(CategorieDocument, col(CategorieDocument.id) == col(Document.categorie_id))
            .where(
                col(CategorieDocument.code).in_(CATEGORIES_AVEC_LIEN),
                col(Document.ticket_id).is_(None),
                col(Document.contrat_id).is_(None),
                col(Document.evenement_id).is_(None),
            )
            .order_by(col(Document.publie_le).desc(), col(Document.id).desc())
        ).all()
    )


def documents_lies(session: Session, user: Utilisateur) -> list[tuple[Document, str]]:
    """(document, lien) de chaque document lié que `user` peut lire, dans l'ordre choisi.

    Un document supprimé depuis, ou devenu illisible pour lui, est sauté.
    """
    rendu = []
    for doc_id in ids_lies(session):
        doc = session.get(Document, doc_id)
        if doc is None or not document_visible(user, doc, session):
            continue
        lien = lien_document(doc, user, session)
        if lien:
            rendu.append((doc, lien))
    return rendu


def lier(session: Session, ids: list[int]) -> list[int]:
    """Enregistre la liste choisie, dédoublonnée dans l'ordre — 422 si l'un
    d'eux n'est pas un candidat : un lien vers une page où rien ne s'allume ne
    s'enregistre pas."""
    voulus = list(dict.fromkeys(ids))
    if len(voulus) > MAX_DOCUMENTS:
        raise HTTPException(422, f"Au plus {MAX_DOCUMENTS} documents.")
    permis = {d.id for d in candidats(session)}
    if any(i not in permis for i in voulus):
        raise HTTPException(
            422, "Seul un document rangé sur Ma résidence (plans, règlement, PV d'AG) se lie."
        )
    ligne = session.get(ConfigSite, CLE_DOCUMENTS) or ConfigSite(cle=CLE_DOCUMENTS, valeur="")
    ligne.valeur = json.dumps(voulus)
    session.add(ligne)
    session.commit()
    return voulus


__all__ = ["CLE_DOCUMENTS", "MAX_DOCUMENTS", "candidats", "documents_lies", "ids_lies", "lier"]
