"""Ce que la synthèse lit d'une affaire : ses faits, ses métriques, et le message (#1643).

## Ce qui part à l'assistant, et ce qui ne part pas

Envoyé : le titre, la description, les Suites (réponses du syndic par courriel
comprises), les relances, les états datés, les messages qui ne sont pas
internes au conseil, les métriques calculées et la mention d'une réouverture.

**Exclus** : les messages internes (`MessageTicket.interne`) et toutes les
pièces jointes. Les personnes sont désignées par leur **rôle** (le syndic, le
conseil syndical, l'auteur de l'affaire, un résident), jamais par leur nom : le
modèle n'en a pas besoin pour raconter l'affaire, et la politique de
confidentialité dit ce qui lui est transmis (`seed/contenus_legaux.py`).

## Le syndic

Il se reconnaît à son lien dans la fiche du cabinet (`MembreSyndic.user_id`) ou
à son adresse (`est_adresse_syndic`), jamais à un rôle — `RoleUtilisateur` n'en
a pas. Une Suite venue d'un courriel (texte d'origine conservé, ou versée par un
transfert) compte aussi comme une réponse reçue, arbitré : « 1ʳᵉ Suite d'un
compte syndic ou d'un courriel entrant ».
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Callable, Optional

from sqlmodel import Session, col, select

from app.models.copropriete import Copropriete
from app.models.core import MessageTicket, Ticket, TicketEvolution, Utilisateur
from app.models.gouvernance import MembreSyndic
from app.models.prestataires import Prestataire
from app.models.roles import RoleUtilisateur
from app.models.tickets import STATUTS_TICKET_CLOS
from app.utils import horloge
from app.utils.affaire_absorbee import ouverture_effective, pas_absorbee
from app.utils.annonce_hall import texte_brut
from app.utils.categories_ticket import libelle_categorie
from app.utils.corrections import est_correction
from app.utils.dates_fr import date_courte
from app.utils.destinataires import est_adresse_syndic
from app.utils.jours_ouvres import libelle_jours
from app.utils.synthese_affaire import metriques as m
from app.utils.noms import ANCIEN_RESIDENT
from app.utils.equipements import libelle_equipement
from app.utils.recuperer import ou_rien
from app.utils.synthese_affaire.lecture import TYPE_SYNTHESE
from app.utils.synthese_affaire import recidive as r
from app.utils.valeurs import valeur

#: Une entrée du fil se coupe là : le récit d'une page n'en demande pas plus.
MAX_CARACTERES_ENTREE = 1_500
#: Et le fil entier là — une affaire de deux ans ne doit pas facturer un roman.
MAX_CARACTERES_FIL = 40_000


def reconnaisseur_syndic(session: Session) -> Callable[[int], bool]:
    """« Ce compte est-il celui du syndic ? » — lien dans la fiche du cabinet, ou adresse.

    L'adresse se juge par `est_adresse_syndic`, la règle de la relève des
    courriels : jamais une comparaison recopiée sur `Utilisateur.email`.
    """
    lies = {mb.user_id for mb in session.exec(select(MembreSyndic)).all() if mb.user_id}
    connus: dict[int, bool] = {}

    def est_syndic(user_id: int) -> bool:
        if user_id in lies:
            return True
        if user_id not in connus:
            user = session.get(Utilisateur, user_id)
            connus[user_id] = bool(user and user.email and est_adresse_syndic(session, user.email))
        return connus[user_id]

    return est_syndic


def _evolutions(session: Session, ticket_id: int) -> list[TicketEvolution]:
    """Le fil de l'affaire, sans les Suites de synthèse — elles ne se mesurent pas."""
    return list(
        session.exec(
            select(TicketEvolution)
            .where(TicketEvolution.ticket_id == ticket_id, TicketEvolution.type != TYPE_SYNTHESE)
            .order_by(TicketEvolution.cree_le)
        ).all()
    )


#: « État : Ouvert → Chez le syndic » — ce qu'une CORRECTION écrit quand l'état
#: change par la fiche (`routers/tickets/mise_a_jour`), et non par une Suite.
_ETAT_CORRIGE = re.compile(r"État : (.+?) → (.+?)(?: ; |$)")


def etat_corrige(e: TicketEvolution) -> Optional[tuple[str, str]]:
    """(avant, après) d'un état changé par correction, ou `None`.

    Une correction n'écrit pas d'étape — c'est voulu, elle rectifie — mais elle
    DIT l'état quitté et l'état posé, avec sa date. Sans elle, la frise prêtait
    toute l'attente à l'état d'après (03/10/2026). Les libellés se relisent par
    la table de l'écran (`STATUT_LABELS`), la seule qui les a écrits.
    """
    from app.routers.tickets.commun import STATUT_LABELS

    if not est_correction(e):
        return None
    trouve = _ETAT_CORRIGE.search(texte_brut(e.contenu or ""))
    if not trouve:
        return None
    codes = {libelle: code for code, libelle in STATUT_LABELS.items()}
    avant, apres = (codes.get(x.strip()) for x in trouve.groups())
    return (avant, apres) if avant and apres else None


def _fait(e: TicketEvolution, est_syndic: Callable[[int], bool]) -> m.Fait:
    venue_d_un_courriel = bool(e.contenu_origine) or e.versement_id is not None
    corrige = etat_corrige(e)
    return m.Fait(
        quand=e.cree_le,
        type="etat" if corrige else e.type,
        ancien_statut=corrige[0] if corrige else e.ancien_statut,
        nouveau_statut=corrige[1] if corrige else e.nouveau_statut,
        syndic=est_syndic(e.auteur_id) or venue_d_un_courriel,
    )


def faits_de(session: Session, ticket_id: int, est_syndic: Callable[[int], bool]) -> list[m.Fait]:
    """Les faits mesurables d'une affaire — ce que `metriques` reçoit, et rien d'autre.

    Une lecture, trois lecteurs : la synthèse de l'affaire, la moyenne de sa
    comparaison, et les métriques d'un ensemble d'affaires (`agregats`).
    """
    return [_fait(e, est_syndic) for e in _evolutions(session, ticket_id)]


def mois_debut_exercice(session: Session) -> Optional[int]:
    """Le mois où commence l'exercice comptable — `None` : l'année civile (fiche copropriété)."""
    copro = session.exec(select(Copropriete)).first()
    return copro.mois_debut_exercice if copro else None


def _comparaison(
    session: Session, ticket: Ticket, est_syndic: Callable[[int], bool]
) -> Optional[dict]:
    """La moyenne des autres affaires closes de même catégorie sur l'exercice."""
    debut, fin, libelle = m.bornes_exercice(
        horloge.jour_civil(ticket.ferme_le), mois_debut_exercice(session)
    )
    autres = session.exec(
        select(Ticket).where(
            Ticket.id != ticket.id,
            Ticket.categorie == ticket.categorie,
            col(Ticket.statut).in_(STATUTS_TICKET_CLOS),
            col(Ticket.ferme_le) >= m.debut_utc(debut),
            col(Ticket.ferme_le) < m.debut_utc(fin),
            pas_absorbee(),  # comptée dans sa principale (#1704)
        )
    ).all()
    mesures = [
        m.mesures_de_base(
            ouverture_effective(session, a), a.ferme_le, faits_de(session, a.id, est_syndic)
        )
        for a in autres
    ]
    return m.moyenne(mesures, valeur(ticket.categorie), libelle)


def metriques_de(session: Session, ticket: Ticket, cloture_le: datetime) -> dict:
    """Les métriques de l'affaire, calculées maintenant — ce que la production fige."""
    est_syndic = reconnaisseur_syndic(session)
    faits = faits_de(session, ticket.id, est_syndic)
    met = m.calculer(
        #  Depuis la plus ancienne des affaires fusionnées (#1704).
        cree_le=ouverture_effective(session, ticket),
        cloture_le=cloture_le,
        issue=valeur(ticket.statut),
        faits=faits,
        comparaison=_comparaison(session, ticket, est_syndic),
    )
    #  La récidive d'équipement (#1647) : absente sous le seuil, jamais `None`.
    if (recid := r.recidive_de(session, ticket, cloture_le)) is not None:
        met[r.CLE] = recid
    return met


def _role(user: Optional[Utilisateur], ticket: Ticket, est_syndic: Callable[[int], bool]) -> str:
    if user is None:
        return f"un {ANCIEN_RESIDENT.lower()}"
    if est_syndic(user.id):
        return "le syndic"
    if user.has_role(RoleUtilisateur.conseil_syndical):
        return "le conseil syndical"
    if user.has_role(RoleUtilisateur.admin):
        return "l'administration"
    if user.id in (ticket.auteur_id, ticket.saisi_pour_user_id):
        return "l'auteur de l'affaire"
    return "un résident"


def _texte(html: Optional[str]) -> str:
    return texte_brut(html or "")[:MAX_CARACTERES_ENTREE]


def _lignes_metriques(met: dict, libelles: dict[str, str]) -> list[str]:
    etapes = " · ".join(
        f"{libelles.get(e['statut'], 'Close avant réouverture')} {libelle_jours(e['jours'])}"
        for e in met["etapes"]
    )
    lignes = [
        f"- Durée totale : {libelle_jours(met['duree_totale'])}",
        f"- Temps par étape : {etapes or '—'}",
    ]
    if met["etape_plus_longue"]:
        lignes.append(f"- Étape la plus longue : {libelles.get(met['etape_plus_longue'])}")
    lignes += [
        f"- Suites : {met['suites']} · relances au syndic : {met['relances']}",
        f"- Réaction du syndic après la dernière relance : {libelle_jours(met['reaction_relance'])}",
        "- Première réponse du syndic après l'ouverture : "
        + libelle_jours(met["premiere_reponse_syndic"]),
        f"- Semaines sans aucune suite : {met['semaines_muettes']} sur {len(met['semaines'])}",
    ]
    comp = met.get("comparaison")
    if comp:
        lignes.append(
            f"- Moyenne des {comp['nombre']} autres affaires de la même catégorie closes sur "
            f"l'exercice {comp['exercice']} : durée {libelle_jours(comp['duree_totale'])}, "
            f"première réponse {libelle_jours(comp['premiere_reponse_syndic'])}, "
            f"{comp['relances']} relance(s), {comp['suites']} suite(s)"
        )
    return lignes


def _lignes_recidive(recid: Optional[dict]) -> list[str]:
    """La récidive, dite à l'assistant par NUMÉROS et dates — jamais les titres : ce
    sont d'autres affaires, et il n'en a pas besoin pour la nommer (#1647)."""
    if not recid:
        return []
    autres = ", ".join(
        f"{a['numero']} (close le {date_courte(datetime.fromisoformat(a['ferme_le']).date())})"
        for a in recid["autres"]
    )
    return [
        f"- Récidive : {len(recid['autres'])} autres affaires résolues sur le même équipement "
        f"et le même périmètre dans les {recid['mois']} mois précédents — {autres}"
    ]


def construire_message(
    session: Session, ticket: Ticket, met: dict, libelles: dict[str, str]
) -> str:
    """Le message envoyé à l'assistant — écrit par le code, chiffres compris."""
    est_syndic = reconnaisseur_syndic(session)
    issue = "résolue" if met["issue"] == "résolu" else "annulée"
    prestataire = session.get(Prestataire, ticket.prestataire_id) if ticket.prestataire_id else None
    tete = [
        f"Affaire {ticket.numero} — « {ticket.titre} »",
        f"Catégorie : {libelle_categorie(ticket.categorie)}"
        + (
            f" · équipement : {libelle_equipement(session, ticket.equipement)}"
            if ticket.equipement
            else ""
        ),
        f"Ouverte le {date_courte(horloge.jour_civil(ouverture_effective(session, ticket)))}, "
        f"{issue} le {date_courte(horloge.jour_civil(ticket.ferme_le))}.",
    ]
    #  🔀 Le bilan couvre TOUTES les affaires fusionnées (#1704) : leurs Suites
    #  sont dans le fil, chacune ouverte par sa description.
    absorbees = session.exec(select(Ticket).where(Ticket.fusionnee_dans_id == ticket.id)).all()
    if absorbees:
        tete.append(
            "Elle réunit les affaires fusionnées à sa clôture : "
            + ", ".join(a.numero for a in absorbees)
            + " — le fil daté les couvre toutes."
        )
    if prestataire and prestataire.nom:
        tete.append(f"Intervenant : {prestataire.nom}")
    if met["reouvertures"]:
        tete.append(
            f"L'affaire a été rouverte {met['reouvertures']} fois : la synthèse couvre toute sa vie."
        )
    tete += ["", "Description :", _texte(ticket.description) or "(aucune)", ""]
    tete.append("Métriques calculées (jours ouvrés, 9 h–17 h, hors week-ends et jours fériés) :")
    tete += _lignes_metriques(met, libelles)
    tete += _lignes_recidive(met.get(r.CLE))
    fil = fil_date(session, ticket, libelles, est_syndic)
    return "\n".join([*tete, "", "Fil daté :", fil[:MAX_CARACTERES_FIL] or "(vide)"])


def fil_date(
    session: Session,
    ticket: Ticket,
    libelles: dict[str, str],
    est_syndic: Optional[Callable[[int], bool]] = None,
) -> str:
    """Le fil d'une affaire, une ligne datée par entrée, la plus ancienne en tête.

    États, relances, Suites et messages NON internes ; chaque personne par son
    rôle, jamais son nom. Lu par la synthèse d'une affaire close et par le
    résumé de chaque affaire en cours du Suivi des affaires (#2035) — une seule
    écriture de ce que l'assistant a le droit de lire d'un fil.
    """
    est_syndic = est_syndic or reconnaisseur_syndic(session)
    entrees: list[tuple[datetime, str]] = []
    for e in _evolutions(session, ticket.id):
        qui = _role(ou_rien(session, Utilisateur, e.auteur_id), ticket, est_syndic)
        if e.type == "etat":
            avant, apres = (
                libelles.get(e.ancien_statut or "", "?"),
                libelles.get(e.nouveau_statut, "?"),
            )
            ligne = f"État : {avant} → {apres} ({qui})"
            if e.contenu:
                ligne += f" — {_texte(e.contenu)}"
        elif e.type == "relance":
            ligne = "Relance envoyée au syndic"
        elif e.type == "commentaire" and e.contenu:
            ligne = f"Suite ({qui}) : {_texte(e.contenu)}"
        else:
            continue  # « réponse » : son texte est le message, lu ci-dessous
        entrees.append((e.cree_le, ligne))
    for msg in session.exec(
        select(MessageTicket).where(
            MessageTicket.ticket_id == ticket.id,
            MessageTicket.interne == False,  # noqa: E712
        )
    ).all():
        qui = _role(ou_rien(session, Utilisateur, msg.auteur_id), ticket, est_syndic)
        entrees.append((msg.cree_le, f"Message ({qui}) : {_texte(msg.contenu)}"))
    entrees.sort(key=lambda x: x[0])
    return "\n".join(f"- {date_courte(horloge.jour_civil(q))} — {t}" for q, t in entrees)


__all__ = [
    "construire_message",
    "faits_de",
    "fil_date",
    "metriques_de",
    "mois_debut_exercice",
    "reconnaisseur_syndic",
]
