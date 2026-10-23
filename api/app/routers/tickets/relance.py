"""Tickets — relance groupée du syndic.

Extrait de `tickets.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.

Domaine à part entière : c'est le seul endroit qui écrit au syndic **au nom du
conseil syndical**, avec sa civilité, l'ancienneté réelle des dossiers et
l'historique de chaque ticket.
"""

import json
from app.utils import horloge

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import (
    GenreCivilite,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.utils.dates_fr import date_courte, formule_anciennete, mois_ecoules
from app.models.courriel import RelanceCourriel
from app.utils.courriel_entrant import nouveau_jeton
from app.utils.destinataires import formule_appel, interlocuteurs_syndic
from app.utils.perimetres import perimetre_label_json
from app.utils.preferences_mail import Designe
from app.utils.relance_syndic import ids_relancables
from app.utils.html_sur import html_riche

from .commun import (
    STATUT_LABELS,
    config_site,
    destinataires_syndic_cs,
    libelle_evolution,
    syndic_principal,
)
from .lecture_groupee import relances_par_affaire
from app.utils.noms import nom_affiche
from app.utils.liens import nom_site
from app.utils.recuperer import ou_404

router = APIRouter()


class RelanceSyndicRequest(BaseModel):
    ticket_ids: list[int]


#  🔴 La LISTE des affaires à relancer n'a plus de route ici depuis #2035 : elle
#  est celle du Suivi des affaires (`GET /suivi-affaires`, mode « Relancer le
#  syndic »), qui lit la même règle (`utils/relance_syndic`). Deux routes pour une
#  liste, c'était deux écrans pour une liste — et ils comptaient différemment.


def _contexte_ticket(session: Session, ticket: Ticket) -> dict:
    """Un ticket tel que le tableau de l'e-mail de relance l'affiche."""
    evols = session.exec(
        select(TicketEvolution)
        .where(TicketEvolution.ticket_id == ticket.id)
        .order_by(TicketEvolution.cree_le)
    ).all()
    historique = [
        {
            "date": date_courte(ticket.cree_le),
            "label": f"Création du ticket (statut : {STATUT_LABELS.get(ticket.statut, ticket.statut)})",
        }
    ]
    historique += [{"date": date_courte(e.cree_le), "label": libelle_evolution(e)} for e in evols]
    return {
        "numero": ticket.numero,
        "titre": ticket.titre,
        "categorie": ticket.categorie,
        "priorite": ticket.priorite,
        #  `vide=""` : un ticket sans périmètre n'affiche aucune ligne, là où le
        #  fil d'activité afficherait « Copropriété entière ». Cf. utils/perimetres.
        "perimetre": perimetre_label_json(ticket.perimetre_cible),
        "description": html_riche(ticket.description),
        #  Le résumé de l'assistant, montré dans l'aperçu avant l'envoi (#2035).
        "resume": (ticket.resume_ia or "").strip(),
        # La relance qui vient d'être enregistrée ne se compte pas elle-même.
        "relance_count": relances_par_affaire(session, [ticket.id])[ticket.id] - 1,
        "historique": historique,
    }


@router.get("/relance-syndic/reponses")
def list_reponses_relance(
    session: Session = Depends(get_session),
    _user: Utilisateur = Depends(require_cs_or_admin),
):
    """Les réponses du syndic aux relances, de la plus récente à la plus ancienne.

    🔴 POURQUOI CET ÉCRAN EXISTE. La réponse était captée et notifiée, jamais
    CONSERVÉE à un endroit qu'on rouvre. Une notification se lit une fois puis
    descend dans la pile — passé quelques jours, la réponse du syndic était en
    base et introuvable. C'est le défaut que tout ce chantier corrige, déplacé de
    la boîte aux lettres vers une table de notifications (04/09/2026).

    ⚠️ Chaque réponse porte les tickets que la RELANCE contenait, pas ceux qu'elle
    mentionne : aucune machine ne sait à quel dossier chaque phrase se rapporte —
    c'est précisément pourquoi on ne la ventile pas. La liste sert de contexte au
    lecteur, jamais de rattachement.
    """
    from app.models.courriel import RelanceCourriel, ReponseRelance

    reponses = session.exec(
        select(ReponseRelance).order_by(ReponseRelance.recue_le.desc()).limit(50)
    ).all()
    if not reponses:
        return {"reponses": []}

    relances = {
        r.id: r
        for r in session.exec(
            select(RelanceCourriel).where(RelanceCourriel.id.in_({x.relance_id for x in reponses}))
        ).all()
    }
    #  Les numéros sont résolus ICI, une fois : le front n'a pas à savoir que la
    #  relance stocke des identifiants en JSON.
    ids_tous = set()
    for rel in relances.values():
        try:
            ids_tous.update(int(i) for i in json.loads(rel.tickets_json or "[]"))
        except (ValueError, TypeError):
            pass
    #  Seules les affaires ENCORE SUIVIES sont citées : une affaire résolue,
    #  annulée, archivée ou absorbée n'a plus rien à recevoir de la réponse, et
    #  une affaire supprimée n'est plus en base (09/10/2026).
    suivies = ids_relancables(session, ids_tous)
    numeros = {
        t.id: t.numero
        for t in (
            session.exec(select(Ticket).where(Ticket.id.in_(suivies))).all() if suivies else []
        )
    }

    sortie = []
    for rep in reponses:
        rel = relances.get(rep.relance_id)
        try:
            ids = [int(i) for i in json.loads(rel.tickets_json or "[]")] if rel else []
        except (ValueError, TypeError):
            ids = []
        #  Une réponse dont TOUTES les affaires sont closes n'a plus rien à
        #  reporter : elle quitte la liste avec elles. Une réponse sans affaire
        #  connue (relance illisible) reste, faute de pouvoir en juger.
        if ids and not any(i in numeros for i in ids):
            continue
        sortie.append(
            {
                "id": rep.id,
                "expediteur": rep.expediteur,
                "contenu": rep.contenu,
                "recue_le": rep.recue_le,
                "relance_le": rel.cree_le if rel else None,
                "tickets": [numeros[i] for i in ids if i in numeros],
            }
        )
    return {"reponses": sortie}


@router.post("/relance-syndic", status_code=200)
def envoyer_relance_syndic(
    body: RelanceSyndicRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Mail de relance groupé au syndic principal, en copie des membres du CS.

    Chaque ticket relancé reçoit une évolution « relance », ce qui le date et le
    rend traçable.
    """
    from app.utils.email import send_email_group

    if not body.ticket_ids:
        raise HTTPException(422, "Aucun ticket sélectionné")

    tickets_relance = [ou_404(session, Ticket, tid, f"Ticket {tid}") for tid in body.ticket_ids]
    #  La MÊME règle que la liste : un écran resté ouvert pendant qu'une affaire
    #  se résolvait relancerait sinon le syndic sur un dossier clos.
    admis = ids_relancables(session, {t.id for t in tickets_relance})
    refuses = [t.numero for t in tickets_relance if t.id not in admis]
    if refuses:
        raise HTTPException(
            422,
            f"Plus à relancer : {', '.join(refuses)} (résolue, annulée, archivée ou fusionnée)."
            " Rafraîchissez la liste.",
        )

    now = horloge.maintenant()
    for ticket in tickets_relance:
        session.add(
            TicketEvolution(
                ticket_id=ticket.id,
                type="relance",
                contenu=f"Relance syndic n°{relances_par_affaire(session, [ticket.id])[ticket.id] + 1}",
                auteur_id=user.id,
                cree_le=now,
            )
        )
        ticket.mis_a_jour_le = now
        #  Relancer un ticket l'escalade au syndic (utile pour ceux pas encore
        #  explicitement adressés au syndic) → cohérence avec le mail envoyé.
        ticket.destinataire_syndic = True
        session.add(ticket)

    session.flush()

    principal = syndic_principal(session)
    if not principal or not principal.email:
        raise HTTPException(422, "Aucun gestionnaire syndic principal avec email configuré")

    cfg = config_site(session)

    #  Ancienneté réelle des dossiers relancés : le préambule annonçait « plus
    #  d'un mois » quelle que soit la situation, y compris pour des tickets en
    #  souffrance depuis cinq mois. Mesurée sur `mis_a_jour_le`, c'est-à-dire sur
    #  la dernière avancée — le même repère que celui qui rend un ticket
    #  relançable.
    anciennete = formule_anciennete(
        [mois_ecoules(t.mis_a_jour_le or t.cree_le, now) for t in tickets_relance]
    )

    ctx = {
        #  La formule d'appel s'adresse à la gestionnaire ET à l'assistante de
        #  gestion : le cabinet fonctionne en binôme, l'une supplée l'autre en son
        #  absence. Les personnes viennent de l'annuaire, choisies par leur
        #  FONCTION — écrire les noms en dur ne survivrait pas au premier
        #  changement de personnel.
        "interlocuteurs": formule_appel(interlocuteurs_syndic(session)),
        #  Les deux variables historiques restent fournies : le modèle déjà en
        #  base les utilise encore tant que la migration 0127 n'a pas tourné, et
        #  une variable absente rend une chaîne vide sans rien signaler.
        "civilite": "Monsieur" if principal.genre == GenreCivilite.mr else "Madame",
        "nom_gestionnaire": nom_affiche(principal.prenom, principal.nom),
        "residence": {"nom": nom_site(cfg.get("site_nom"))},
        "anciennete": anciennete,
        "tickets": [_contexte_ticket(session, t) for t in tickets_relance],
    }

    #  🔴 L'ADRESSE DE RÉPONSE D'UN ENVOI GROUPÉ (#703, 03/09/2026).
    #
    #  Ce message porte N tickets : il n'a pas de jeton de ticket, et il n'en
    #  aura jamais. Sans celui-ci, la réponse du syndic arrivait dans la boîte
    #  sans rien pour la rattacher — ignorée EN SILENCE, alors qu'on venait de
    #  la solliciter.
    #
    #  ⚠️ Le jeton rattache à la RELANCE, pas à un ticket : la réponse ira au
    #  conseil syndical avec la liste des dossiers concernés, jamais recopiée
    #  dans les N fils. Voir `models.RelanceCourriel`.
    relance = RelanceCourriel(
        jeton=nouveau_jeton(),
        tickets_json=json.dumps([t.id for t in tickets_relance]),
        cree_le=now,
    )
    session.add(relance)

    #  Désigné : la relance s'adresse au syndic, sa préférence ne l'écarte pas (#2006).
    to_recipients = [Designe(principal.user_id, principal.email)]
    #  Le CS passe en copie, sans le syndic qui est déjà destinataire principal.
    cc_recipients = destinataires_syndic_cs(
        session, syndic=False, cs=True, deja_vus={principal.email.lower()}
    )

    session.commit()

    #  Pas de session= : la tâche de fond crée sa propre session (celle de
    #  l'endpoint est fermée une fois la réponse envoyée).
    background_tasks.add_task(
        send_email_group,
        code="relance_syndic",
        to_recipients=to_recipients,
        context=ctx,
        cc_recipients=cc_recipients or None,
        jeton_reponse=relance.jeton,
    )

    return {"sent": len(tickets_relance), "relance_to": principal.email}
