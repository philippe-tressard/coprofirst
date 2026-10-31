"""Flux — indicateurs « santé résidence » et agenda des prochaines échéances.

Extrait de `flux.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.

Ce module ne produit **aucune** ligne de fil : il répond à l'autre question du
tableau de bord — « où en est-on ? » et « quoi ensuite ? ». C'est pour cela qu'il
date les événements sur `debut` là où le fil les date sur `cree_le`
(cf. `evenements.py`).
"""

from datetime import timedelta

from sqlalchemy import func
from sqlmodel import select

from app.models.core import (
    STATUTS_TICKET_ACTIFS,
    CommandeAcces,
    ContratEntretien,
    Copropriete,
    DemandeModificationProfil,
    Prestataire,
    RoleUtilisateur,
    Sondage,
    StatutCommande,
    StatutDemandeProfil,
    StatutTicket,
    Ticket,
)
from app.routers.copropriete import contrat_de_reference
from app.utils.comptes import nb_comptes_en_attente
from app.utils.echeance_contrat import echeance_du_contrat
from app.utils.relance_syndic import conditions_relancable, delai_relance_jours
from app.utils.visibility import (
    sondage_accessible,
    sondage_clos,
    ticket_visible,
)

from .commun import ContexteFlux
from .schemas import FluxSante, RendezVous
from app.utils.categories_ticket import ticket_urgent
from app.auth.deps import est_moderateur

#: Bornes de l'agenda : par source, puis au total.
_MAX_VISITES = 5
_MAX_PROCHAINS = 12


def _prochains(ctx: ContexteFlux) -> list[dict]:
    """Agenda « Prochaines échéances » : visites de contrat, assurance."""
    prochains: list[dict] = []

    #  Les événements du calendrier sont des affaires depuis le lot 5 (#1092) :
    #  cet agenda ne les lit plus. Il n'est d'ailleurs affiché par aucun écran
    #  (relevé le 23/09/2026) — ce qui reste sert l'API, sans consommateur.
    visites = ctx.session.exec(
        select(ContratEntretien, Prestataire)
        .join(Prestataire, ContratEntretien.prestataire_id == Prestataire.id)
        .where(ContratEntretien.actif, ContratEntretien.prochaine_visite.is_not(None))
        .order_by(ContratEntretien.prochaine_visite.asc())
    ).all()
    for ct, prest in visites[:_MAX_VISITES]:
        prochains.append(
            {
                "id": f"ct_{ct.id}",
                "date": ct.prochaine_visite.isoformat() if ct.prochaine_visite else "",
                "titre": f"{ct.libelle} — {prest.nom}",
                "type": "contrat",
                "icon": "🔧",
                "description": ct.notes,
                "prestataire": prest.nom,
            }
        )

    #  🔴 L'échéance d'assurance venait de `Copropriete.assurance_echeance` — la
    #  COLONNE HÉRITÉE, hors du circuit depuis #490. `copropriete_lue` l'efface
    #  précisément pour que l'ancienne saisie libre ne réapparaisse pas derrière
    #  le contrat ; la relance, elle, continuait de la lire. Le tableau de bord
    #  annonçait donc une échéance que plus aucun écran n'affiche et que
    #  personne ne met à jour — trouvé le 29/08/2026 en instruisant la remarque
    #  de l'utilisateur sur la reconduction tacite.
    #
    #  Elle se déduit désormais du CONTRAT, par la même fonction que la fiche
    #  (`utils/echeance_contrat.py`), et elle se reporte donc d'elle-même.
    copro = ctx.session.exec(select(Copropriete)).first()
    if copro:
        for section, icone in (("assurance", "🛡️"), ("syndic", "🏢")):
            contrat = contrat_de_reference(ctx.session, copro, section)
            e = echeance_du_contrat(contrat) if contrat else None
            if not e:
                continue
            presta = ctx.session.get(Prestataire, contrat.prestataire_id)
            #  ⚠️ « reconduit tacitement » se dit ICI aussi : une échéance de
            #  reconduction ne se relance pas comme un terme négocié, et le
            #  taire donnerait au CS deux lignes qu'il ne saurait pas départager.
            #  ⚠️ TROIS états, pas deux. « Échu » n'est pas une échéance à
            #  venir : c'est un mandat qui a CESSÉ, et la copropriété doit voter.
            #  Le confondre avec une reconduction — ce que faisait la première
            #  version — supprimait le seul signal qui appelle une AG (#628).
            if e.echu:
                suffixe = " — MANDAT ÉCHU, à renouveler en AG"
            elif e.reconduit:
                suffixe = " (reconduction tacite)"
            else:
                suffixe = ""
            prochains.append(
                {
                    "id": section,
                    "date": e.date.isoformat(),
                    "titre": f"Échéance {section} {presta.nom if presta else ''}".strip() + suffixe,
                    "type": section,
                    "icon": icone,
                }
            )

    prochains.sort(key=lambda x: x.get("date", ""))
    return prochains[:_MAX_PROCHAINS]


def _rendez_vous(ctx: ContexteFlux, visibles: list[Ticket]) -> RendezVous | None:
    """Le prochain rendez-vous : l'affaire datée la plus proche qui n'est pas passée.

    « Pas passée » : elle commence maintenant ou plus tard, ou elle est EN COURS
    (une fin encore à venir) — une AG commencée il y a une heure reste le
    rendez-vous du jour. Une affaire annulée n'en est plus un. La lecture suit
    `ticket_visible`, déjà appliqué par l'appelant : la pastille ne nomme jamais
    une affaire que l'écran ne montrerait pas.
    """
    a_venir = [
        t
        for t in visibles
        if t.debut is not None
        and t.statut != StatutTicket.annulé
        and max(t.debut, t.fin or t.debut) >= ctx.now
    ]
    if not a_venir:
        return None
    t = min(a_venir, key=lambda x: x.debut)
    return RendezVous(id=t.id, titre=t.titre, debut=t.debut, fin=t.fin)


def _nb_commandes_acces(ctx: ContexteFlux) -> int:
    """Commandes d'accès (vigik, télécommande) en attente de traitement."""
    return (
        ctx.session.exec(
            select(func.count(CommandeAcces.id)).where(
                CommandeAcces.statut == StatutCommande.en_attente
            )
        ).one()
        or 0
    )


def _nb_demandes_profil(ctx: ContexteFlux) -> int:
    """Demandes de modification de profil en attente.

    Troisième tâche de la file d'administration, et la seule que l'Espace CS ne
    montre pas : elle ne se traite que depuis `/admin`. Elle n'était comptée
    **nulle part** avant #399 — l'admin ne pouvait l'apprendre qu'en ouvrant
    l'écran.
    """
    return (
        ctx.session.exec(
            select(func.count(DemandeModificationProfil.id)).where(
                DemandeModificationProfil.statut_demande == StatutDemandeProfil.en_attente
            )
        ).one()
        or 0
    )


def _validations_cs(ctx: ContexteFlux) -> int:
    """Ce que la pastille « Espace CS » annonce — et rien d'autre.

    Exactement les deux sections de son onglet « ✅ Comptes & accès » : comptes en
    attente de validation, et demandes d'accès. Un compteur ne se prouve que d'une
    façon — ouvrir l'écran de destination et compter ce qu'on y voit (#399).

    Le CS **a** le droit de traiter ces deux files : les trois endpoints
    `/admin/*` correspondants sont protégés par `require_cs_or_admin`, et l'écran
    existe. Ce n'est donc pas un décompte d'actions interdites, contrairement à ce
    que laissait craindre la lecture des seules conditions du tableau de bord.
    """
    if not est_moderateur(ctx.user):
        return 0
    return nb_comptes_en_attente(ctx.session) + _nb_commandes_acces(ctx)


def _validations_admin(ctx: ContexteFlux) -> int:
    """Ce que la pastille « Admin » annonce — les trois files de son écran.

    Elle recouvre `validations_cs` de deux tiers, et c'est voulu : les deux écrans
    montrent réellement ces éléments, chacun annonce donc son propre contenu. Un
    admin voit les deux pastilles, chacune fidèle à sa destination.

    Réservé aux admins, comme la pastille : `/admin` est fermé au CS non-admin par
    son layout. Calculer ce nombre pour quelqu'un qui ne voit pas la pastille
    serait du travail serveur inutile — et l'afficher sans pouvoir le calculer
    serait un mensonge à l'écran.
    """
    if not ctx.user.has_role(RoleUtilisateur.admin):
        return 0
    return nb_comptes_en_attente(ctx.session) + _nb_commandes_acces(ctx) + _nb_demandes_profil(ctx)


def _relances_syndic(ctx: ContexteFlux) -> int:
    """Affaires éligibles à la relance du syndic (pas de modification depuis > délai)."""
    if not est_moderateur(ctx.user):
        return 0

    seuil = ctx.now - timedelta(days=delai_relance_jours(ctx.session))
    return (
        ctx.session.exec(
            select(func.count(Ticket.id)).where(
                #  La règle de la liste, qu'il annonce : `utils/relance_syndic`. Il
                #  ne retenait que les affaires déjà adressées au syndic ; la liste
                #  les propose toutes, et l'envoi les lui adresse (10/10/2026).
                *conditions_relancable(),
                Ticket.mis_a_jour_le < seuil,
            )
        ).one()
        or 0
    )


def calculer(ctx: ContexteFlux) -> FluxSante:
    #  `ticket_visible` AVANT tout décompte : `select(Ticket)` ramenait toute la
    #  résidence, si bien qu'un indicateur du tableau de bord *personnel*
    #  annonçait à un résident des tickets qu'il n'a pas le droit d'ouvrir. C'est
    #  pour cette raison que la pastille comptait côté client sur le fil déjà
    #  filtré — mais elle bougeait alors avec les filtres de l'utilisateur, seule
    #  de la rangée à le faire (#399).
    tous = [t for t in ctx.session.exec(select(Ticket)).all() if ticket_visible(t, ctx.user)]
    ouverts = [t for t in tous if t.statut in STATUTS_TICKET_ACTIFS]
    urgents = [t for t in ouverts if ticket_urgent(t)]

    # Temps moyen de résolution sur les 30 derniers jours
    depuis_30j = ctx.now - timedelta(days=30)
    resolus = [
        t
        for t in tous
        if t.statut == "résolu" and t.ferme_le and t.cree_le and t.ferme_le >= depuis_30j
    ]
    resolution_moy = None
    if resolus:
        durees = [(t.ferme_le - t.cree_le).total_seconds() / 3600 for t in resolus]
        resolution_moy = round(sum(durees) / len(durees), 1)

    #  Deux filtres, tous deux absents avant #399, et le compteur était faux pour
    #  chacun séparément :
    #    • `sondage_accessible` — le décompte ignorait le ciblage (périmètre ET
    #      public cible), donc la pastille pouvait annoncer « Sondages 2 » à un
    #      résident dont l'écran /sondages n'en montre aucun ;
    #    • `sondage_clos` — `~cloture_forcee` n'exclut que la clôture manuelle. Un
    #      sondage dont l'échéance est passée est clos partout ailleurs, et resté
    #      « actif » ici : la plus permissive des deux définitions alimentait la
    #      pastille. Il n'y en a plus qu'une, dans `utils/visibility.py`.
    sondages_actifs = sum(
        1
        for s in ctx.session.exec(select(Sondage)).all()
        if not sondage_clos(s, ctx.now) and sondage_accessible(s, ctx.user)
    )

    return FluxSante(
        tickets_ouverts=len(ouverts),
        tickets_urgents=len(urgents),
        resolution_moyenne_heures=resolution_moy,
        sondages_actifs=sondages_actifs,
        validations_cs=_validations_cs(ctx),
        validations_admin=_validations_admin(ctx),
        tickets_relance_syndic=_relances_syndic(ctx),
        prochains=_prochains(ctx),
        rendez_vous=_rendez_vous(ctx, tous),
    )
