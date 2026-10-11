"""Les fichiers d'une FICHE de « Ma résidence » — son fichier principal et ses annexes.

## Ce qu'est une fiche, et pourquoi elle a des annexes (migration 0276)

Les fiches de Ma résidence sont un plan, un règlement, un CR d'AG (`Document`
d'une catégorie), un rapport de diagnostic (`DiagnosticRapport`) et une règle
(`RegleResidence`). Les quatre premières ÉTAIENT leur fichier, la dernière n'en
portait aucun : leur édition n'offrait donc pas la section « Pièces jointes »
du cadre, et un CR d'AG ne pouvait pas porter sa feuille de présence.

Une annexe est un `Document` SANS catégorie, rattaché à sa fiche par l'une des
colonnes de `PORTEURS` — la forme des pièces jointes d'affaire et d'événement
(#390). Elle hérite ainsi de tout ce que le `Document` sait déjà faire : la
porte unique de téléversement, le téléchargement authentifié, la visibilité
(`utils/visibility/documents` : une annexe se lit EXACTEMENT comme sa fiche).

⚠️ Le fichier PRINCIPAL ne devient pas une annexe : il se REMPLACE, il ne se
retire pas — une fiche sans fichier n'existe pas. `remplacer_fichier` vaut pour
le document comme pour le rapport, qui portent les quatre mêmes colonnes.

## Ce que ce module garde

- `PORTEURS` est la SEULE table « fiche → colonne » : le routeur, la
  visibilité et les suppressions la lisent, aucun ne la recopie.
- Une annexe n'a qu'UN porteur, et jamais d'annexe : la visibilité remonte
  d'un cran, pas davantage.
- Une fiche supprimée emporte ses annexes, fichiers compris : une annexe sans
  porteur n'aurait plus de règle de lecture, donc ne se lirait plus jamais.
"""

from __future__ import annotations

import os

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.core import DiagnosticRapport, Document, RegleResidence
from app.utils.fichiers import enregistrer_televersement
from app.utils.recuperer import ou_404
from app.utils.stockage import stockage

#: Ce qui porte des annexes, et la colonne de `document` qui les y rattache.
PORTEURS: dict[str, str] = {
    "document": "document_parent_id",
    "diagnostic": "diagnostic_rapport_id",
    "regle": "regle_residence_id",
}

#: Le plafond d'une fiche — celui de la section « Pièces jointes » de tout le
#: site (`MAX_FICHIERS`, `front/src/lib/fichiers.ts`). Tenu ICI aussi : l'écran
#: dit ce que le serveur fait, et un appel direct ne passe pas par l'écran.
MAX_ANNEXES = 10


def porteurs_demandes(**colonnes: int | None) -> dict[str, int]:
    """Les fiches qu'une requête nomme par leurs colonnes, rendues `{porteur: id}`."""
    return {p: colonnes[c] for p, c in PORTEURS.items() if colonnes.get(c)}


def porteur_de(doc: Document) -> tuple[str, int] | None:
    """La fiche qui porte cette annexe, ou None si ce n'en est pas une."""
    for porteur, colonne in PORTEURS.items():
        porteur_id = getattr(doc, colonne)
        if porteur_id:
            return porteur, porteur_id
    return None


def annexes_de(session: Session, porteur: str, porteur_id: int) -> list[Document]:
    colonne = getattr(Document, PORTEURS[porteur])
    return list(
        session.exec(select(Document).where(colonne == porteur_id).order_by(Document.id)).all()
    )


def verifier_porteur(session: Session, porteur: str, porteur_id: int) -> None:
    """Refuse une annexe que sa fiche ne peut pas recevoir — 404 si elle n'existe pas."""
    if porteur == "document":
        parent = ou_404(session, Document, porteur_id, "Document")
        #  Ni un document de contrat ou d'affaire, ni une annexe : seule une fiche
        #  de la bibliothèque porte des annexes, et la visibilité ne remonte
        #  qu'un cran.
        if not parent.categorie_id or porteur_de(parent):
            raise HTTPException(400, "Seul un document de Ma résidence porte des annexes")
    elif porteur == "diagnostic":
        ou_404(session, DiagnosticRapport, porteur_id, "Rapport")
    else:
        ou_404(session, RegleResidence, porteur_id, "Règle")
    if len(annexes_de(session, porteur, porteur_id)) >= MAX_ANNEXES:
        raise HTTPException(400, f"Une fiche porte au plus {MAX_ANNEXES} pièces jointes")


def supprimer_annexes(session: Session, porteur: str, porteur_id: int) -> None:
    """Retire les annexes d'une fiche qu'on supprime — l'appelant valide la transaction."""
    for annexe in annexes_de(session, porteur, porteur_id):
        stockage().supprimer_chemin(annexe.fichier_chemin)
        session.delete(annexe)


def remplacer_fichier(fiche: Document | DiagnosticRapport, file, user) -> str:
    """Pose un nouveau fichier principal sur la fiche ; rend le chemin de l'ancien.

    ⚠️ L'ancien ne s'efface qu'APRÈS l'écriture en base, par l'appelant : effacé
    avant, un échec de la transaction laisserait la fiche pointer un fichier
    disparu.
    """
    raw_name = file.filename or "document"
    dest = enregistrer_televersement(file, raw_name, user)
    ancien = fiche.fichier_chemin
    fiche.fichier_nom = raw_name
    fiche.fichier_chemin = dest
    fiche.taille_octets = os.path.getsize(dest)
    fiche.mime_type = file.content_type or "application/octet-stream"
    return ancien
