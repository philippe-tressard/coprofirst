"""Flux — rubrique Ressources : questions fréquentes, documents, diagnostics.

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.

Trois sources, une seule raison de changer : ce sont les **contenus de référence**
que le fil se contente d'annoncer. Aucune ne se vote, ne se commente ni ne change
d'état — elles paraissent, et c'est tout. C'est ce qui les distingue des rubriques
vivantes (tickets, sondages) et ce qui justifie de les tenir ensemble.
"""

from sqlmodel import select

from app.models.core import (
    DiagnosticRapport,
    Document,
    FaqItem,
)
from app.utils.liens import lien_element
from app.utils.visibility import document_visible

from app.utils.documents import endroit_document, lien_document
from .commun import ContexteFlux, auteur_nom, strip_html
from .schemas import FluxItem


# Où un document est-il RÉELLEMENT consultable ? Il n'existe pas de page « tous les
# documents » : chaque document s'affiche là où il est rattaché. Le fil renvoyait vers
# `/documents`, une route qui n'a jamais existé côté front → 404 sur « Voir → »,
# signalé le 26/07/2026 depuis un PV d'AG. Les catégories absentes de cet ensemble ne
# sont affichées nulle part (fiche synthétique, attestation de lot, diagnostic de lot,
# devis travaux, document interne CS) : dans ce cas le fil ne propose aucun lien plutôt qu'un
# lien qui ne mène nulle part. Cf. `api/tests/test_liens_front.py`.
#
# La page et l'onglet, eux, ne sont plus écrits ici : ils viennent de
# `EMPLACEMENTS["doc"]` (app/utils/liens.py), seul endroit du code qui décide où vit
# un élément donné.
def _collecter_faq(ctx: ContexteFlux) -> list[FluxItem]:
    faqs = ctx.session.exec(
        select(FaqItem)
        .where(FaqItem.actif, FaqItem.cree_le >= ctx.since)
        .order_by(FaqItem.cree_le.desc())
    ).all()
    return [
        FluxItem(
            id=f"faq_{f.id}",
            type="faq",
            date=f.cree_le,
            cree_le=f.cree_le,
            titre=f.question,
            detail=strip_html(f.reponse),
            icon="❓",
            badges=[f.categorie] if f.categorie else [],
            lien=lien_element("faq", f.id),
            meta={"faq_id": f.id, "categorie": f.categorie, "resume": strip_html(f.reponse, 400)},
        )
        for f in faqs
    ]


def _collecter_documents(ctx: ContexteFlux) -> list[FluxItem]:
    docs = ctx.session.exec(
        select(Document).where(Document.publie_le >= ctx.since).order_by(Document.publie_le.desc())
    ).all()

    cartes: list[FluxItem] = []
    for d in docs:
        #  Même contrôle d'accès que /documents (profil + périmètre bat/lot) : un
        #  document ciblé bât. 1 ne remonte pas au fil d'un résident du bât. 2.
        if not document_visible(ctx.user, d, ctx.session):
            continue
        cartes.append(
            FluxItem(
                id=f"doc_{d.id}",
                type="document",
                date=d.publie_le,
                cree_le=d.publie_le,
                titre=d.titre,
                #  OÙ il a été ajouté — « Nouveau document » ne le disait pas (11/10/2026).
                detail=endroit_document(d, ctx.user),
                icon="📄",
                badges=[],
                lien=lien_document(d, ctx.user, ctx.session),
                #  Un document EST un fichier : sa carte doit le signaler comme
                #  n'importe quelle pièce jointe (décision du 07/08/2026, « PJ =
                #  fichiers ou photo »). On transmet un DÉCOMPTE et non une URL : la
                #  galerie dépliée afficherait « télécharger », dernier segment de
                #  /documents/{id}/télécharger, au lieu du titre du document — et
                #  ferait doublon avec le lien que la carte porte déjà.
                meta={
                    "document_id": d.id,
                    "auteur": auteur_nom(ctx.session, d.publie_par_id),
                    "fichier_nom": d.fichier_nom,
                    "mime_type": d.mime_type,
                    "pj_compte": 1,
                    #  🔴 La DESCRIPTION, ajoutée au document le 08/09/2026 et restée
                    #  sur le seul écran Résidence — signalé à l'écran le 09/09.
                    #
                    #  Elle passe par `meta` et non par `detail` : `detail` dit ce qui
                    #  s'est PASSÉ (« Document ajouté dans… »), la description dit ce que le
                    #  document COUVRE. La carte affiche « libellé — extrait » depuis
                    #  #531, et se tait d'elle-même si l'un répète l'autre.
                    "description": strip_html(d.description),
                },
            )
        )
    return cartes


def _collecter_diagnostics(ctx: ContexteFlux) -> list[FluxItem]:
    diags = ctx.session.exec(
        select(DiagnosticRapport)
        .where(DiagnosticRapport.publie_le >= ctx.since)
        .order_by(DiagnosticRapport.publie_le.desc())
    ).all()
    return [
        FluxItem(
            id=f"diag_{dg.id}",
            type="diagnostic",
            date=dg.publie_le,
            cree_le=dg.publie_le,
            titre=dg.titre,
            detail=strip_html(dg.synthese) if dg.synthese else "Nouveau rapport de diagnostic",
            icon="🧪",
            badges=["Diagnostic"],
            # Section « Diagnostics et Contrôles Réglementaires » de /residence
            lien=lien_element("diag", dg.id),
            meta={
                "diagnostic_id": dg.id,
                "resume": strip_html(dg.synthese, 400) if dg.synthese else None,
            },
        )
        for dg in diags
    ]


def collecter(ctx: ContexteFlux) -> list[FluxItem]:
    return _collecter_faq(ctx) + _collecter_documents(ctx) + _collecter_diagnostics(ctx)
