"""Le texte du règlement : l'assembler depuis les fichiers joints, en garder les versions.

## Ce qui entre (11/10/2026 — l'objet Pièces jointes standard)

L'administration joint, dans Ma résidence › Règlement, jusqu'à dix fichiers de
la catégorie `texte_reglement` — par l'objet Pièces jointes de tout le site, le
dépôt des documents et leur croix. Ils sont réservés à l'administration
(`visibility.CATEGORIES_ADMIN_SEUL`) : le texte de travail nomme notaires et
parties. L'assistant lit **tous les fichiers Markdown** joints, mis bout à bout
dans l'ordre d'ajout ; les autres (un PDF d'acte) restent joints sans être lus.

Le chargement d'un fichier Markdown par cet écran seul, qui l'a précédé, a
disparu : il s'écartait du dépôt standard (arbitré à l'écran le 11/10/2026).

## Une version par contenu

Le texte assemblé a une empreinte. La première question posée sur un contenu
neuf en enregistre la VERSION (`TexteReglement`), après la réponse ; chaque question garde la sienne, et
une réponse ancienne se relit donc contre le texte qui l'a fondée. Rejoindre le
même fichier que la version en vigueur ne crée rien.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.models.core import CategorieDocument, Document
from app.models.reglement import TexteReglement
from app.utils.stockage import stockage

#: La catégorie des fichiers du règlement — posée par le seed (`profils_documents`).
CODE_CATEGORIE = "texte_reglement"
#: Les fichiers que l'assistant LIT ; les autres sont joints sans être lus.
EXTENSIONS_LUES = (".md", ".markdown")
#: Environ 250 000 jetons : au-delà, ce n'est plus un règlement, et l'appel
#: dépasserait la fenêtre de la plupart des modèles.
MAX_CARACTERES_TEXTE = 1_000_000
#: En deçà, ce n'est pas un règlement — un fichier vide ou le mauvais fichier.
MIN_CARACTERES_TEXTE = 1_000
#: Le titre de l'en-tête YAML (`title: "…"`), s'il y en a un.
_TITRE_YAML = re.compile(r"\A---\s*\n(?:.*\n)*?title:\s*[\"']?(.+?)[\"']?\s*\n", re.MULTILINE)


@dataclass(frozen=True)
class TexteAssemble:
    contenu: str
    titre: str
    empreinte: str
    noms: str
    auteur_id: Optional[int]


def preparer(contenu: str, nom_fichier: str) -> tuple[str, str, str]:
    """PURE. (contenu normalisé, titre, empreinte) — ou `HTTPException(400|413)`.

    BOM retiré, fins de ligne en LF : le même fichier déposé depuis Windows ou
    depuis macOS doit avoir la même empreinte.
    """
    texte = contenu.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in texte:
        raise HTTPException(400, "Un fichier du règlement n'est pas un texte.")
    if len(texte) > MAX_CARACTERES_TEXTE:
        raise HTTPException(413, "Le texte du règlement dépasse un million de caractères.")
    if len(texte.strip()) < MIN_CARACTERES_TEXTE:
        raise HTTPException(400, "Ce texte est trop court pour être un règlement de copropriété.")
    m = _TITRE_YAML.match(texte)
    titre = (m.group(1).strip() if m else "") or nom_fichier.rsplit(".", 1)[0]
    empreinte = hashlib.sha256(texte.encode("utf-8")).hexdigest()
    return texte, titre[:300], empreinte


def categorie(session: Session) -> Optional[CategorieDocument]:
    return session.exec(
        select(CategorieDocument).where(CategorieDocument.code == CODE_CATEGORIE)
    ).first()


def fichiers_lus(session: Session) -> list[Document]:
    """Les fichiers Markdown joints, dans l'ordre d'ajout — ceux que l'assistant lit."""
    cat = categorie(session)
    if cat is None:
        return []
    docs = session.exec(
        select(Document)
        .where(Document.categorie_id == cat.id)
        .order_by(col(Document.publie_le), col(Document.id))
    ).all()
    return [d for d in docs if (d.fichier_nom or "").lower().endswith(EXTENSIONS_LUES)]


def _lire(doc: Document) -> str:
    st = stockage()
    cle = st.cle_de(doc)
    if cle is None or not st.existe(cle):
        raise HTTPException(400, f"Le fichier « {doc.titre} » est introuvable sur le disque.")
    return st.lire(cle).decode("utf-8", errors="replace")


def assembler(session: Session) -> Optional[TexteAssemble]:
    """Le texte que l'assistant lirait maintenant — `None` sans fichier Markdown joint.

    Lève `HTTPException(400|413)` si l'assemblage n'est pas un règlement lisible.
    """
    docs = fichiers_lus(session)
    if not docs:
        return None
    contenu, titre, empreinte = preparer(
        "\n\n".join(_lire(d) for d in docs), docs[0].fichier_nom or "reglement.md"
    )
    return TexteAssemble(
        contenu=contenu,
        titre=titre,
        empreinte=empreinte,
        noms=", ".join(d.fichier_nom or d.titre for d in docs)[:255],
        auteur_id=docs[-1].publie_par_id,
    )


def version_de(session: Session, assemble: TexteAssemble) -> Optional[TexteReglement]:
    """La version déjà enregistrée pour ce contenu, s'il y en a une."""
    return session.exec(
        select(TexteReglement)
        .where(TexteReglement.empreinte == assemble.empreinte)
        .order_by(col(TexteReglement.cree_le).desc(), col(TexteReglement.id).desc())
    ).first()


def texte_en_vigueur(session: Session) -> Optional[TexteReglement]:
    """La version qui correspond aux fichiers joints AUJOURD'HUI, si une question
    l'a déjà enregistrée — sinon `None`, et les réponses déjà données se disent
    « Texte remplacé depuis ». Lecture seule : un assemblage illisible rend `None`."""
    try:
        assemble = assembler(session)
    except HTTPException:
        return None
    return version_de(session, assemble) if assemble else None


def enregistrer_version(session: Session, assemble: TexteAssemble) -> TexteReglement:
    """La version de ce contenu — enregistrée APRÈS la réponse de l'assistant :
    l'appel part avant toute écriture (`production`, #1469), et un appel en
    échec ne laisse pas de version derrière lui."""
    version = version_de(session, assemble)
    if version is not None:
        return version
    version = TexteReglement(
        titre=assemble.titre,
        nom_fichier=assemble.noms,
        contenu=assemble.contenu,
        empreinte=assemble.empreinte,
        charge_par_id=assemble.auteur_id,
    )
    session.add(version)
    session.flush()
    return version


def texte_disponible(session: Session) -> bool:
    """Un texte lisible est-il joint ? — l'écran ouvre la saisie d'une question."""
    try:
        return assembler(session) is not None
    except HTTPException:
        return False


__all__ = [
    "CODE_CATEGORIE",
    "MAX_CARACTERES_TEXTE",
    "assembler",
    "categorie",
    "enregistrer_version",
    "fichiers_lus",
    "preparer",
    "texte_disponible",
    "texte_en_vigueur",
]
