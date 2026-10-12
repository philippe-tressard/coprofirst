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

## Une seule liste à l'écran, dix fichiers en tout (11/10/2026)

Demandé : *« ne pas mettre Annexes — utilise l'objet PJ standard une seule fois
en principal ; on pourra joindre jusqu'à 10 fichiers »*. L'édition montre donc
UNE section « Pièces jointes », le composant standard du site, où le fichier de
la fiche est la première pastille et ses annexes les suivantes. Le plafond vaut
pour le tout : `MAX_FICHIERS_FICHE`, fichier principal compris.

⚠️ Une fiche sans fichier n'existe pas : retirer la première pastille fait
monter la suivante à sa place (`retirer_fichier_principal`), et refuse quand
elle est seule — on dépose le nouveau fichier, puis on retire l'ancien. Le
document et le rapport portent les quatre mêmes colonnes (`_COLONNES_FICHIER`).

## Ce que ce module garde

- `PORTEURS` est la SEULE table « fiche → colonne » : le routeur, la
  visibilité et les suppressions la lisent, aucun ne la recopie.
- Une annexe n'a qu'UN porteur, et jamais d'annexe : la visibilité remonte
  d'un cran, pas davantage.
- Une fiche supprimée emporte ses annexes, fichiers compris : une annexe sans
  porteur n'aurait plus de règle de lecture, donc ne se lirait plus jamais.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.core import DiagnosticRapport, Document, RegleResidence
from app.utils.recuperer import ou_404
from app.utils.stockage import stockage

#: Ce qui porte des annexes, et la colonne de `document` qui les y rattache.
PORTEURS: dict[str, str] = {
    "document": "document_parent_id",
    "diagnostic": "diagnostic_rapport_id",
    "regle": "regle_residence_id",
}

#: Les fiches qui SONT un fichier — la première pastille de leur liste. Une
#: règle n'en a pas : ses pièces jointes ne sont que des annexes.
PORTEURS_A_FICHIER = frozenset({"document", "diagnostic"})

#: Le plafond d'une fiche, fichier principal COMPRIS — celui de la section
#: « Pièces jointes » de tout le site (`MAX_FICHIERS`, `front/src/lib/fichiers.ts`).
#: Tenu ICI aussi : l'écran dit ce que le serveur fait, et un appel direct ne
#: passe pas par l'écran.
MAX_FICHIERS_FICHE = 10

#: Les colonnes qui décrivent le fichier, communes au document et au rapport.
_COLONNES_FICHIER = ("fichier_nom", "fichier_cle", "taille_octets", "mime_type")


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
    principal = 1 if porteur in PORTEURS_A_FICHIER else 0
    if len(annexes_de(session, porteur, porteur_id)) + principal >= MAX_FICHIERS_FICHE:
        raise HTTPException(400, f"Une fiche porte au plus {MAX_FICHIERS_FICHE} pièces jointes")


def supprimer_annexes(session: Session, porteur: str, porteur_id: int) -> None:
    """Retire les annexes d'une fiche qu'on supprime — l'appelant valide la transaction."""
    for annexe in annexes_de(session, porteur, porteur_id):
        stockage().supprimer_de(annexe)
        session.delete(annexe)


def retirer_fichier_principal(
    session: Session, fiche: Document | DiagnosticRapport, porteur: str
) -> None:
    """Retire le fichier de la fiche : sa première annexe prend sa place.

    L'annexe promue quitte la table — son fichier reste, la fiche le pointe
    désormais. ⚠️ L'ancien fichier ne s'efface qu'APRÈS l'écriture en base :
    effacé avant, un échec de la transaction laisserait la fiche pointer un
    fichier disparu.
    """
    suivante = next(iter(annexes_de(session, porteur, fiche.id)), None)
    if suivante is None:
        raise HTTPException(
            400,
            "Une fiche garde au moins un fichier : déposez le nouveau avant de retirer celui-ci",
        )
    #  La clé de l'ancien fichier, lue AVANT que l'annexe prenne sa place.
    ancien = stockage().cle_de(fiche)
    for colonne in _COLONNES_FICHIER:
        setattr(fiche, colonne, getattr(suivante, colonne))
    session.delete(suivante)
    session.add(fiche)
    session.commit()
    session.refresh(fiche)
    if ancien is not None:
        stockage().supprimer(ancien)
