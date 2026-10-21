"""Ce qu'une Suite pose sur l'AFFAIRE — écrit une fois pour l'ajout et la correction.

## Pourquoi ce module (01/10/2026)

L'ajout d'une Suite (`add_evolution`) appliquait à l'affaire la Mise en avant,
le Quand, l'Intervenant, l'Équipement, les Destinataires et l'Accès ; sa
correction (`update_evolution`) n'en appliquait aucun. Demandé à l'écran :
*« l'édition d'une suite doit permettre de modifier toutes les sections
éditables et surtout le suivi »*. Recopier le bloc dans le `PATCH` aurait fait
deux règles du même geste : il vit ici, et les deux routes l'appellent.

Le Suivi suit la même pente : `appliquer_statut` porte ce qu'un changement
d'état fait à l'affaire — clôture datée, lecture par défaut, prochaine visite —,
que l'état vienne d'une Suite neuve ou d'une Suite corrigée (`suivi_fil.py`).

⚠️ Ce module ne décide d'aucun DROIT qui n'existe déjà : `appliquer_options`,
`appliquer_intervenant` et `_appliquer_quand` gardent les leurs, et le conseil
seul pose Destinataires et planification (`est_moderateur`).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth.deps import est_moderateur
from app.models.core import STATUTS_TICKET_CLOS, Ticket, TicketEvolution, Utilisateur
from app.utils import horloge
from app.utils.evolutions import TYPES_SAISIS
from app.utils.intervenant import appliquer_intervenant
from app.utils.nature_affaire import est_actualite
from app.utils import suivi_actualite
from app.utils.prochaine_visite import apres_cloture
from app.utils.synthese_affaire.file import inscrire_si_eligible
from app.utils.valeurs import valeur
from app.utils.suivi_fil import doit_propager_statut, resultat, statuts_avant, suivi_corrige
from app.utils.visibility import destinataires_par_defaut, trace_droits, trace_lecture_par_defaut

from .actualite import appliquer_acces
from .commun import appliquer_options
from .correction import _appliquer_quand


def _tracer(evol: TicketEvolution, lignes: list[str]) -> None:
    """Ce qui a changé s'écrit dans la Suite même : la trace est au fil."""
    if lignes:
        evol.contenu = (evol.contenu or "") + f"<p><em>{' ; '.join(lignes)}</em></p>"


def appliquer_sections_suite(
    session: Session, ticket: Ticket, evol: TicketEvolution, body: Any, user: Utilisateur
) -> None:
    """Mise en avant, Quand, Intervenant, Équipement, Destinataires, Accès."""
    est_cs = est_moderateur(user)
    #  Le formulaire montre le DERNIER état, ce qu'on enregistre DEVIENT l'état
    #  (05/09/2026) — la table et le droit vivent dans `appliquer_options`.
    if appliquer_options(ticket, body, est_cs=est_cs):
        ticket.mis_a_jour_le = horloge.maintenant()
        session.add(ticket)
    #  📅🛠️ Le conseil les pose dans une Suite (#1207) : mêmes règles que la
    #  correction de l'affaire, et ce qui a changé s'écrit dans la Suite.
    if est_cs and not est_actualite(ticket):
        planifie = appliquer_intervenant(ticket, body, session, est_cs=True) + _appliquer_quand(
            body, ticket
        )
        if planifie:
            _tracer(evol, planifie)
            ticket.mis_a_jour_le = horloge.maintenant()
            session.add(ticket)
    #  À qui l'on parle — une actualité (#1091) comme une affaire suivie (#1343) :
    #  `ticket_visible` honore ce choix, et l'Accès. Le conseil seul.
    if est_cs and (body.public_cible is not None or body.reserve_perimetre is not None):
        avant = ticket.public_cible
        reserve_avant = bool(ticket.reserve_perimetre)
        if body.public_cible is not None:
            ticket.public_cible = (
                json.dumps(body.public_cible, ensure_ascii=False) if body.public_cible else None
            )
        if body.reserve_perimetre is not None:
            ticket.reserve_perimetre = body.reserve_perimetre
        #  🔒 Les droits valent pour TOUT le fil, et la Suite le dit (29/09/2026).
        _tracer(
            evol,
            trace_droits(
                avant,
                ticket.public_cible,
                reserve_avant,
                bool(ticket.reserve_perimetre),
                vide="Tous" if est_actualite(ticket) else "par défaut de la catégorie",
            ),
        )
        ticket.mis_a_jour_le = horloge.maintenant()
        session.add(ticket)
    #  L'invariant d'accès : une Suite qui referme l'actualité archive ses affiches.
    if est_actualite(ticket):
        appliquer_acces(ticket, session)


def appliquer_statut(
    session: Session,
    ticket: Ticket,
    evol: TicketEvolution,
    statut: str,
    ferme_le: datetime,
    *,
    synthese: bool = True,
) -> None:
    """L'affaire prend `statut`, avec tout ce qu'un changement d'état emporte.

    `synthese=False` : la clôture n'inscrit pas de synthèse — la seule à le
    demander est l'annexe vide d'un point CS / Syndic, qui n'a rien à raconter.

    Une actualité n'a pas de cycle (#1091) : c'est son SUIVI qui change, s'il
    est activé (10/10/2026) — un repère, qui n'emporte rien d'autre.
    """
    if est_actualite(ticket):
        suivi_actualite.appliquer_etat(ticket, statut, ferme_le)
        session.add(ticket)
        return
    lue_avant = destinataires_par_defaut(ticket)
    statut_avant = ticket.statut
    ticket.statut = statut
    #  🔒 Une Étude & travaux qui passe en AG s'ouvre aux copropriétaires
    #  (standard du 30/09/2026) : tout le fil avec elle, et la Suite le dit.
    _tracer(evol, trace_lecture_par_defaut(ticket, lue_avant))
    #  Une seule liste des états clos — celle du modèle.
    if statut in STATUTS_TICKET_CLOS:
        ticket.ferme_le = ferme_le
    ticket.mis_a_jour_le = horloge.maintenant()
    session.add(ticket)
    apres_cloture(ticket, session)  # la prochaine visite d'un contrat (#1092)
    if synthese:
        inscrire_si_eligible(session, ticket, statut_avant=statut_avant)


def corriger_suivi(
    session: Session, ticket: Ticket, evol: TicketEvolution, body: Any, user: Utilisateur
) -> None:
    """Corrige l'état que porte la Suite — la règle vit dans `utils/suivi_fil.py`.

    La Suite garde sa date : une clôture qu'elle porte est datée d'elle.
    """
    if body.type not in TYPES_SAISIS:
        raise HTTPException(422, "Type invalide (commentaire ou etat)")
    if body.type == "etat":
        if not body.nouveau_statut:
            raise HTTPException(422, "nouveau_statut requis pour un changement d'état")
        suivi_actualite.refuser_etat(ticket, body.nouveau_statut, est_cs=est_moderateur(user))
    fil = session.exec(
        select(TicketEvolution)
        .where(TicketEvolution.ticket_id == ticket.id)
        .order_by(TicketEvolution.cree_le)
    ).all()
    statut_affaire = suivi_actualite.etat_de_la_suite(ticket)
    demande = valeur(body.nouveau_statut) if body.nouveau_statut else None
    avant = statuts_avant(fil, statut_affaire).get(evol.id, statut_affaire)
    resultat_avant = resultat(evol, avant)
    corrige = suivi_corrige(avant, body.type, demande)
    if corrige == (evol.type, evol.ancien_statut, evol.nouveau_statut):
        return  # rien ne change : renvoyer l'état qu'on avait est muet
    evol.type, evol.ancien_statut, evol.nouveau_statut = corrige
    resultat_apres = resultat(evol, avant)
    if resultat_apres != resultat_avant and doit_propager_statut(
        evol.id, resultat_avant, fil, statut_affaire
    ):
        appliquer_statut(session, ticket, evol, resultat_apres, evol.cree_le)
