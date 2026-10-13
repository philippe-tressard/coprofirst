"""Les affaires et les actualités de la résidence fictive (spec §6.2).

Toutes les catégories et tous les états, avec leurs suites et leur fil, datés
RELATIVEMENT au jour du chargement. Les affaires se composent avec les briques du
routeur (`generer_numero`, `nouveau_jeton`, `perimetre_cible_json`,
`suivi_par_defaut`) mais sans `create_ticket` : lui notifie le conseil, met des
courriels en file et force `cree_le` à maintenant — rien de cela n'a de sens pour
un jeu de données.

Une suite qui change l'état écrit l'évolution `etat` (ancien → nouveau), comme
l'écran ; une réponse du fil écrit le message ET son évolution `reponse`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session

from app.demo.dates import dans, il_y_a
from app.demo.patrimoine import Patrimoine
from app.demo.prestataires import Prestataires
from app.models.core import CategorieTicket as C
from app.models.core import MessageTicket, PrioriteTicket, Ticket, Utilisateur
from app.models.core import StatutTicket as S
from app.models.tickets import STATUTS_TICKET_CLOS, TicketEvolution
from app.routers.tickets.commun import generer_numero
from app.utils.courriel_entrant import nouveau_jeton
from app.utils.kanban_tickets import suivi_par_defaut
from app.utils.perimetres import perimetre_cible_json


@dataclass(frozen=True)
class Suite:
    jours: int  #: il y a combien de jours
    auteur: str  #: la clé du compte (`comptes.poser`)
    contenu: str
    statut: Optional[S] = None  #: l'état où elle fait passer l'affaire
    fil: bool = False  #: une réponse du fil plutôt qu'un commentaire de suite


def _poser(
    session: Session,
    comptes: dict[str, Utilisateur],
    *,
    titre: str,
    description: str,
    categorie: C,
    auteur: str,
    jours: int,
    statut: S = S.ouvert,
    priorite: PrioriteTicket = PrioriteTicket.normale,
    codes: Optional[list[str]] = None,
    suites: tuple[Suite, ...] = (),
    **champs,
) -> Ticket:
    cree = il_y_a(jours)
    ticket = Ticket(
        numero=generer_numero(session),
        jeton_courriel=nouveau_jeton(),
        titre=titre,
        description=description,
        categorie=categorie,
        statut=statut,
        priorite=priorite,
        auteur_id=comptes[auteur].id,
        perimetre_cible=perimetre_cible_json(codes),
        suivi_kanban=suivi_par_defaut(categorie.value),
        cree_le=cree,
        mis_a_jour_le=cree,
        **champs,
    )
    session.add(ticket)
    session.flush()
    for suite in suites:
        quand = il_y_a(suite.jours)
        auteur_id = comptes[suite.auteur].id
        if suite.fil:
            session.add(
                MessageTicket(
                    ticket_id=ticket.id, auteur_id=auteur_id, contenu=suite.contenu, cree_le=quand
                )
            )
        evolution = TicketEvolution(
            ticket_id=ticket.id,
            type="reponse" if suite.fil else ("etat" if suite.statut else "commentaire"),
            contenu=suite.contenu,
            auteur_id=auteur_id,
            cree_le=quand,
        )
        if suite.statut and not suite.fil:
            evolution.ancien_statut = ticket.statut.value
            evolution.nouveau_statut = suite.statut.value
        if suite.statut:
            ticket.statut = suite.statut
            ticket.ferme_le = quand if suite.statut in STATUTS_TICKET_CLOS else None
        ticket.mis_a_jour_le = quand
        session.add(evolution)
    session.add(ticket)
    return ticket


def poser(
    session: Session, pat: Patrimoine, comptes: dict[str, Utilisateur], prest: Prestataires
) -> list[Ticket]:
    bat = {lettre: f"bat:{b.id}" for lettre, b in pat.batiments.items()}
    cs = "conseil-syndical"
    p = prest.par_code
    k = prest.contrats
    affaires = [
        _poser(
            session,
            comptes,
            titre="L'ascenseur du bâtiment A est bloqué au 2e étage",
            description="La cabine reste bloquée portes ouvertes au 2e étage depuis ce matin.",
            categorie=C.panne,
            priorite=PrioriteTicket.haute,
            auteur="resident",
            jours=3,
            codes=[f"{bat['A']}/ascenseur"],
            prestataire_id=p["ascenseurs"].id,
            contrat_id=k["ascenseurs"].id,
            suites=(
                Suite(2, cs, "Le prestataire est prévenu : intervention demain matin.", S.en_cours),
                Suite(1, cs, "Pièce commandée, remise en service sous 48 h.", S.chez_prestataire),
            ),
        ),
        _poser(
            session,
            comptes,
            titre="Fuite d'eau au plafond du parking",
            description="Une flaque se forme sous la canalisation, près de la place P03.",
            categorie=C.panne,
            auteur="Christophe",
            jours=26,
            codes=["parking"],
            prestataire_id=p["plomberie"].id,
            suites=(
                Suite(24, cs, "Plombier mandaté.", S.en_cours),
                Suite(19, cs, "Réparé : tronçon de canalisation remplacé.", S.résolu),
            ),
        ),
        _poser(
            session,
            comptes,
            titre="Bruit tard le soir dans la cage d'escalier du bâtiment B",
            description="Des éclats de voix après 23 h, plusieurs soirs cette semaine.",
            categorie=C.nuisance,
            auteur="Camille",
            jours=2,
            codes=[f"{bat['B']}/escaliers"],
            suites=(Suite(1, "locataire", "Même constat au 2e étage.", fil=True),),
        ),
        _poser(
            session,
            comptes,
            titre="Haie à tailler le long de l'allée principale",
            description="La haie déborde sur le cheminement et gêne le passage des poussettes.",
            categorie=C.espaces_verts,
            auteur="Odile",
            jours=6,
            codes=["espaces-verts"],
            prestataire_id=p["jardins"].id,
            contrat_id=k["jardins"].id,
            suites=(Suite(5, cs, "Ajouté à la prochaine visite du jardinier.", S.en_cours),),
        ),
        _poser(
            session,
            comptes,
            titre="Interphone du bâtiment B hors service",
            description="Les visiteurs ne peuvent plus sonner chez nous depuis hier soir.",
            categorie=C.panne,
            priorite=PrioriteTicket.haute,
            auteur="locataire",
            jours=1,
            codes=[f"{bat['B']}/hall"],
        ),
        _poser(
            session,
            comptes,
            titre="Quel jour sortir les encombrants ?",
            description="Je viens d'arriver dans la résidence : quand peut-on déposer les encombrants ?",
            categorie=C.question,
            auteur="Zoé",
            jours=9,
            suites=(
                Suite(
                    8,
                    cs,
                    "Le premier mardi du mois, à déposer la veille après 19 h.",
                    S.résolu,
                    fil=True,
                ),
            ),
        ),
        _poser(
            session,
            comptes,
            titre="Ravalement des façades : trois devis à comparer",
            description="Les façades nord se fissurent ; le conseil a demandé trois devis.",
            categorie=C.etude_travaux,
            auteur=cs,
            jours=40,
            suites=(
                Suite(35, cs, "Trois devis reçus, comparatif au dossier.", S.en_cours),
                Suite(10, cs, "Inscrit à l'ordre du jour de la prochaine AG.", S.en_ag),
            ),
        ),
        _poser(
            session,
            comptes,
            titre="Visite d'entretien des ascenseurs",
            description="Visite mensuelle du contrat de maintenance.",
            categorie=C.entretien,
            auteur=cs,
            jours=5,
            codes=[bat["A"]],
            debut=dans(9, 9),
            fin=dans(9, 11),
            prestataire_id=p["ascenseurs"].id,
            contrat_id=k["ascenseurs"].id,
        ),
        _poser(
            session,
            comptes,
            titre="Dégât des eaux au 2e étage du bâtiment B",
            description="Une tache d'humidité s'étend au plafond de la salle de bain.",
            categorie=C.sinistre,
            priorite=PrioriteTicket.haute,
            auteur="Hélène",
            jours=12,
            codes=[bat["B"]],
            prestataire_id=p["plomberie"].id,
            suites=(
                Suite(11, cs, "Déclaration faite à l'assurance de l'immeuble.", S.en_cours),
                Suite(
                    6, cs, "Expert passé ; recherche de fuite par le plombier.", S.chez_prestataire
                ),
            ),
        ),
        _poser(
            session,
            comptes,
            titre="Badge d'accès perdu",
            description="J'ai perdu mon badge Vigik dans la rue.",
            categorie=C.acces_accueil,
            auteur="Nadia",
            jours=15,
            suites=(Suite(14, cs, "Badge désactivé, nouveau badge remis.", S.résolu),),
        ),
        _poser(
            session,
            comptes,
            titre="Éclairage du hall du bâtiment C en panne",
            description="Le hall reste dans le noir à la tombée de la nuit.",
            categorie=C.panne,
            auteur="Marcel",
            jours=33,
            codes=[f"{bat['C']}/hall"],
            suites=(Suite(31, cs, "Ampoules et détecteur remplacés.", S.résolu),),
        ),
        _poser(
            session,
            comptes,
            titre="Porte du local vélos qui ferme mal",
            description="La gâche ne retient plus la porte, qui reste entrebâillée.",
            categorie=C.panne,
            priorite=PrioriteTicket.basse,
            auteur="resident",
            jours=4,
        ),
    ]
    actualites = [
        _poser(
            session,
            comptes,
            titre="Bienvenue dans la résidence de démonstration",
            description=(
                "Cette résidence est fictive : explorez librement, rien de ce que vous "
                "saisissez n'est envoyé, et tout est remis à zéro chaque nuit."
            ),
            categorie=C.actualite,
            statut=S.publie,
            auteur=cs,
            jours=1,
            epingle=True,
        ),
        _poser(
            session,
            comptes,
            titre="Coupure d'eau jeudi matin au bâtiment C",
            description="Travaux sur la colonne montante : coupure de 8 h à 12 h.",
            categorie=C.actualite,
            statut=S.publie,
            auteur=cs,
            jours=2,
            codes=[bat["C"]],
            debut=dans(3, 8),
            fin=dans(3, 12),
        ),
        _poser(
            session,
            comptes,
            titre="Assemblée générale annuelle",
            description="L'AG se tiendra dans la salle commune ; le ravalement est à l'ordre du jour.",
            categorie=C.actualite,
            statut=S.publie,
            auteur=cs,
            jours=5,
            debut=dans(21, 18),
            fin=dans(21, 21),
        ),
    ]
    session.flush()
    return affaires + actualites
