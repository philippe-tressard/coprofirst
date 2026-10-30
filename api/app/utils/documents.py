"""Où vit un document — la seule réponse, pour tous ceux qui y renvoient.

## 🔴 Elle était donnée DEUX fois, et les deux ne disaient pas la même chose

Le fil d'actualité savait qu'un document n'est pas toujours affiché là où on
croit : une pièce jointe d'actualité s'ouvre sur **sa publication**, un document
de contrat vit dans la fiche de **son prestataire** — et seulement pour le conseil
et l'administration —, et un document dont la catégorie n'a pas de rubrique
dédiée n'est affiché **nulle part**, donc n'a pas de lien.

La notification et le courriel de publication, eux, écrivaient
`lien_element("doc", doc.id)` **sans condition** : /residence#doc-N, pour tout
document. Un document de contrat partait donc avec un lien vers une page où il
n'apparaît pas, et un résident qui cliquait arrivait sur une liste où rien ne
s'allumait.

C'est la version la plus disante qui est retenue (`standards/02` §4 bis) : celle
du fil, qui connaît les trois cas.

⚠️ La page était bonne, l'élément invisible — exactement le défaut du 28/07/2026
qui a fait naître `utils/liens`, un cran plus loin : là c'était l'onglet qui
manquait, ici c'est l'écran qui ne montre pas ce document-là.

## Pourquoi ici et pas dans `utils/liens`

`liens` ne connaît que des préfixes et des identifiants — aucun modèle, aucune
session. Il reste ainsi éprouvable seul, et `test_liens_front` peut confronter sa
table aux onglets du front. Cette fonction-ci a besoin du document, de la session
et de **qui regarde** : elle a sa propre place.
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from app.models.core import ContratEntretien, Document, Utilisateur
from app.utils.liens import lien_element, lien_ticket, page_element
from app.utils.question_reglement.texte import CODE_CATEGORIE as CODE_TEXTE_REGLEMENT
from app.utils.question_reglement.texte import CODE_CATEGORIE_AG as CODE_DECISIONS_AG
from app.auth.deps import est_moderateur

#: Où un document d'une catégorie s'affiche : l'onglet, tel que le menu le nomme,
#: et la rubrique — ce que le fil d'activité DIT sous le titre (11/10/2026).
#: Signalé à l'écran : « Nouveau document » ne disait pas où le trouver.
#: ⚠️ Les noms suivent `front/src/lib/pages.ts` (onglets) et les titres des
#: rubriques de `/residence` : renommer l'un, c'est renommer l'autre.
RUBRIQUES: dict[str, tuple[str, str]] = {
    "plan_residence": ("Résidence › Fiche", "rubrique Plans"),
    "reglement_copropriete": ("Résidence › Fiche", "rubrique Règlement de copropriété"),
    "pv_ag": ("Résidence › Fiche", "rubrique Comptes-rendus d'AG"),
    CODE_TEXTE_REGLEMENT: ("Résidence › Règlement", "parmi les textes lus par l'assistant"),
    CODE_DECISIONS_AG: ("Résidence › Règlement", "parmi les décisions d'AG lues par l'assistant"),
}

#: Les catégories qui ont une rubrique à elles sur la Fiche de /residence, où le
#: document est listé avec son ancre. Un document d'une autre catégorie n'y est
#: pas : lui fabriquer un lien enverrait sur une page où rien ne s'allume.
CATEGORIES_AVEC_LIEN = {code for code, (onglet, _) in RUBRIQUES.items() if onglet.endswith("Fiche")}


def _code(doc: Document) -> Optional[str]:
    return doc.categorie.code if doc.categorie else None


def lien_document(doc: Document, user: Utilisateur, session: Session) -> Optional[str]:
    """L'endroit exact où CE document est affiché pour CET utilisateur, ou None.

    L'ancre (`#doc-<id>`, `#presta-<id>`) compte autant que la page :
    /residence enchaîne plans, règlement, PV d'AG et diagnostics — y arriver sans
    viser le document oblige à le chercher dans la bonne section.

    ⚠️ Le résultat dépend de `user` : un document de contrat n'est visible que du
    conseil et de l'administration. Il se calcule donc PAR DESTINATAIRE, jamais
    une fois pour toute une liste d'envoi.
    """
    if doc.ticket_id:
        # Pièce jointe d'une affaire — actualités comprises depuis le 23/09/2026
        # (#1091) : c'est sa fiche qu'on ouvre. La 0210 y a rattaché les
        # documents des anciennes publications.
        return lien_ticket(doc.ticket_id)

    if doc.contrat_id:
        # Les documents de contrat ne sont visibles que dans /prestataires, page
        # réservée au CS et aux admins : pour les autres, pas de lien.
        if not est_moderateur(user):
            return None
        contrat = session.get(ContratEntretien, doc.contrat_id)
        # Les documents d'un contrat sont listés dans la fiche de son prestataire.
        return lien_element("presta", contrat.prestataire_id) if contrat else page_element("presta")

    code = _code(doc)
    if code in (CODE_TEXTE_REGLEMENT, CODE_DECISIONS_AG):
        #  L'onglet où il est joint, sans ancre : il n'y est pas listé en carte.
        #  `document_visible` l'a déjà réservé à l'administration.
        return page_element("question-reglement")
    return lien_element("doc", doc.id) if code in CATEGORIES_AVEC_LIEN else None


def endroit_document(doc: Document, user: Utilisateur) -> str:
    """Ce que le fil dit sous le titre d'un document : OÙ il a été ajouté.

    Suit les mêmes cas que `lien_document`, pour que la phrase et le lien ne se
    contredisent pas. Le fil ne voit que les AJOUTS (il trie par `publie_le`) :
    la phrase ne dit jamais « modifié ».
    """
    if doc.ticket_id:
        return "Pièce jointe ajoutée à une affaire"
    if doc.contrat_id:
        if est_moderateur(user):
            return "Document ajouté à la fiche d'un prestataire"
        return "Nouveau document"
    rubrique = RUBRIQUES.get(_code(doc) or "")
    if rubrique is None:
        return "Nouveau document"
    onglet, precision = rubrique
    return f"Document ajouté dans {onglet}, {precision}"


__all__ = ["CATEGORIES_AVEC_LIEN", "RUBRIQUES", "endroit_document", "lien_document"]
