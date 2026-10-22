"""Flux — rubrique Communauté : sondages, petites annonces, boîte à idées.

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.

Les trois sources sont les trois onglets d'une même page. C'est aussi ce qui
oblige leurs liens à porter `?onglet=` : sans lui, « Voir l'annonce → » ouvrait
l'onglet Sondages (signalé le 26/07/2026). `lien_element` s'en charge.
"""

from sqlalchemy import func
from sqlmodel import select

from app.models.core import Idee, OptionSondage, PetiteAnnonce, Sondage, VoteIdee, VoteSondage
from app.utils.liens import lien_element, lien_sondage
from app.utils.montants import montant_fr
from app.utils.photos import parse_photos
from app.utils.visibility import annonce_visible, idee_visible, sondage_accessible, sondage_clos

from .commun import ContexteFlux, auteur_nom, strip_html
from .schemas import FluxItem

_ANN_ICONS = {"vente": "🏷️", "don": "🎁", "recherche": "🔍"}
_ANN_TYPE_LABELS = {"vente": "Vente", "don": "Don", "recherche": "Recherche"}
_ANN_STATUT_BADGES = {"disponible": "Disponible", "reserve": "Réservé", "vendu": "Vendu"}
_IDEE_STATUT_BADGES = {
    "ouverte": "Ouverte",
    "retenue": "Retenue",
    "rejetee": "Rejetée",
    "realisee": "Réalisée",
}


def _pluriel_votes(n: int) -> str:
    """« 0 vote », « 3 votes » — une seule écriture pour les sondages et les idées.

    ⚠️ Seul changement de rendu du découpage, assumé : les deux rubriques
    écrivaient la même formule avec **deux espaces différentes** — une espace
    ordinaire pour les sondages, une fine insécable (U+202F) pour les idées,
    invisible à la relecture. L'unification retient l'espace ordinaire : U+202F
    n'apparaît que deux fois dans tout le dépôt, et uniquement dans le formatage
    des montants (`app/utils/montants.py`), où elle est voulue. Ici c'était un
    accident de saisie, pas une règle typographique.
    """
    return f"{n} vote{'s' if n > 1 else ''}"


def _collecter_sondages(ctx: ContexteFlux) -> list[FluxItem]:
    sondages = ctx.session.exec(
        select(Sondage).where(Sondage.cree_le >= ctx.since).order_by(Sondage.cree_le.desc())
    ).all()

    cartes: list[FluxItem] = []
    for s in sondages:
        if not sondage_accessible(s, ctx.user):
            continue
        cloture = sondage_clos(s, ctx.now)
        nb_votants = ctx.session.exec(
            select(func.count(func.distinct(VoteSondage.user_id))).where(
                VoteSondage.sondage_id == s.id
            )
        ).one()

        if not cloture:
            echeance = f" · Clôture le {s.cloture_le.strftime('%d/%m')}" if s.cloture_le else ""
            cartes.append(
                FluxItem(
                    id=f"sond_{s.id}",
                    type="sondage_ouvert",
                    date=s.cree_le,
                    cree_le=s.cree_le,
                    titre=s.question,
                    detail=_pluriel_votes(nb_votants) + echeance,
                    icon="📊",
                    badges=["En cours"],
                    lien=lien_sondage(s.id),
                    meta={
                        "sondage_id": s.id,
                        "nb_votants": nb_votants,
                        "full_html": s.description,
                        "assiste_ia": s.assiste_ia,
                    },
                )
            )
            continue

        # Sondage clos : afficher l'option gagnante.
        top_option = ctx.session.exec(
            select(OptionSondage.libelle, func.count(VoteSondage.id).label("cnt"))
            .join(VoteSondage, VoteSondage.option_id == OptionSondage.id)
            .where(OptionSondage.sondage_id == s.id)
            .group_by(OptionSondage.libelle)
            .order_by(func.count(VoteSondage.id).desc())
        ).first()
        gagnant = top_option[0] if top_option else None
        cartes.append(
            FluxItem(
                id=f"sond_{s.id}",
                type="sondage_clos",
                date=s.cloture_le or s.cree_le,
                cree_le=s.cree_le,
                titre=s.question,
                detail=f"Clos · {_pluriel_votes(nb_votants)}"
                + (f" · Résultat : {gagnant}" if gagnant else ""),
                icon="🗳️",
                badges=["Clôturé"],
                lien=lien_sondage(s.id),
                meta={
                    "sondage_id": s.id,
                    "nb_votants": nb_votants,
                    "gagnant": gagnant,
                    "full_html": s.description,
                    "assiste_ia": s.assiste_ia,
                },
            )
        )
    return cartes


def _collecter_annonces(ctx: ContexteFlux) -> list[FluxItem]:
    annonces = ctx.session.exec(
        select(PetiteAnnonce)
        .where(PetiteAnnonce.cree_le >= ctx.since)
        .order_by(PetiteAnnonce.cree_le.desc())
    ).all()

    cartes: list[FluxItem] = []
    for a in annonces:
        #  Le fil lit ce que la rubrique lit (22/10/2026, #2141) : il servait
        #  toutes les annonces, Destinataires ignorés, quand la liste les filtrait.
        if not annonce_visible(a, ctx.user):
            continue
        detail_parts = [_ANN_TYPE_LABELS.get(a.type_annonce, a.type_annonce)]
        if a.prix and a.type_annonce == "vente":
            detail_parts.append(montant_fr(a.prix))
        if a.negotiable:
            detail_parts.append("négociable")
        cartes.append(
            FluxItem(
                id=f"ann_{a.id}",
                type="annonce",
                #  🔴 PAS `mis_a_jour_le` — signalé le 01/09/2026 : *« l'édition ne
                #  change pas la date de modification (correction d'erreurs) »* et
                #  *« ne modifie pas la mise à jour dans le fil d'actualité »*.
                #
                #  Corriger une faute de frappe sur une annonce la remontait en tête
                #  du fil, à la date du jour, pastille NEW comprise — comme s'il
                #  s'était passé quelque chose.
                #
                #  ⚠️ La leçon était DÉJÀ écrite, dans `flux/publications.py`, mot
                #  pour mot, depuis le 01/08/2026 : elle avait été appliquée là où
                #  le défaut avait été vu, et pas chez le voisin qui faisait la même
                #  chose. Des quinze sources du fil, celle-ci était la seule à
                #  employer `mis_a_jour_le`.
                date=a.cree_le,
                cree_le=a.cree_le,
                titre=a.titre,
                detail=" · ".join(detail_parts),
                badges=[_ANN_STATUT_BADGES.get(a.statut, a.statut)],
                icon=_ANN_ICONS.get(a.type_annonce, "🏷️"),
                lien=lien_element("annonce", a.id),
                meta={
                    "annonce_id": a.id,
                    "type_annonce": a.type_annonce,
                    "statut": a.statut,
                    "prix": a.prix,
                    "auteur": auteur_nom(ctx.session, a.auteur_id) if a.contact_visible else None,
                    "assiste_ia": a.assiste_ia,
                    "resume": strip_html(a.description),
                    #  Même clé que partout ailleurs : la vignette du fil (FluxVignette)
                    #  ne connaît que `photos_urls` et `image_url`. Une rubrique qui
                    #  stocke ses photos sous un autre nom doit les exposer ici sous
                    #  ce nom-là, sinon elle est la seule à ne pas avoir d'aperçu.
                    "photos_urls": parse_photos(a.photos_json),
                },
            )
        )
    return cartes


def _collecter_idees(ctx: ContexteFlux) -> list[FluxItem]:
    idees = ctx.session.exec(
        select(Idee).where(Idee.cree_le >= ctx.since).order_by(Idee.cree_le.desc())
    ).all()

    cartes: list[FluxItem] = []
    for idee in idees:
        if not idee_visible(idee, ctx.user):
            continue
        nb_votes = ctx.session.exec(
            select(func.count(VoteIdee.id)).where(VoteIdee.idee_id == idee.id)
        ).one()
        cartes.append(
            FluxItem(
                id=f"idee_{idee.id}",
                type="idee",
                date=idee.cree_le,
                cree_le=idee.cree_le,
                titre=idee.titre,
                detail=_pluriel_votes(nb_votes),
                badges=[_IDEE_STATUT_BADGES.get(idee.statut, idee.statut)],
                icon="💡",
                lien=lien_element("idee", idee.id),
                meta={
                    "idee_id": idee.id,
                    "statut": idee.statut,
                    "assiste_ia": idee.assiste_ia,
                    "nb_votes": nb_votes,
                    "resume": strip_html(idee.description),
                },
            )
        )
    return cartes


def collecter(ctx: ContexteFlux) -> list[FluxItem]:
    return _collecter_sondages(ctx) + _collecter_annonces(ctx) + _collecter_idees(ctx)
