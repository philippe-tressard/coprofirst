"""Produire une synthèse : métriques, appel à l'assistant, Suite, avis (#1643).

## Une production, quatre portes

| Porte | Qui | Ce qu'elle fait de plus |
|---|---|---|
| la file (`file.traiter_file`) | la tâche permanente, 30 min après la clôture | crée la Suite, avise le gestionnaire et le conseil |
| « Produire la synthèse » | le conseil, sur une affaire close d'avant la MEP | idem |
| « Relancer » | le conseil, sur un brouillon | PROPOSE, avec un complément ajouté au prompt |
| « Recommencer » | le conseil, sur un brouillon | PROPOSE, sans complément |

Une relance ne remplace rien : elle propose une rédaction, que le conseil
applique (`appliquer_tentative` — le complément suit) ou annule.

Chaque production est journalisée deux fois : ses compteurs dans `appel_ia`
(par `llm.demander`, comme tout appel), son texte, son complément et son coût
dans `tentative_synthese` — l'historique que « Recommencer » ne touche pas.

## 🔴 Sans assistant, la Suite naît quand même

IA coupée, plafond atteint, réponse illisible : la première production crée la
Suite **vide, en brouillon**, avec son motif (bandeau « Synthèse à rédiger »),
et l'avis part — le conseil rédige à la main. Une relance qui échoue, elle,
garde le texte en place et le dit à qui l'a demandée.

## L'ordre des écritures

L'appel à l'assistant se fait AVANT toute écriture dans la session : le journal
des appels écrit dans sa propre transaction, et une écriture en cours dans
celle de l'appelant le verrouillerait (« database is locked », #1469).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session, col, select

from app.models.core import Ticket, TicketEvolution
from app.models.synthese import (
    A_PRODUIRE,
    ANNULEE,
    BROUILLON,
    STATUTS_VIVANTS,
    SyntheseAffaire,
    TentativeSynthese,
)
from app.models.tickets import STATUTS_TICKET_CLOS
from app.utils import horloge
from app.utils.description_format import ReponseIllisible
from app.utils.synthese_affaire.format import (
    USAGE_SYNTHESE_AFFAIRE,
    consigne_complete,
    lire_reponse,
)
from app.utils.synthese_affaire.lecture import TYPE_SYNTHESE
from app.utils.synthese_affaire.rassemblement import construire_message, metriques_de
from app.utils.valeurs import valeur

logger = logging.getLogger("hostachy.synthese")


@dataclass
class Resultat:
    """Ce qu'une production a donné."""

    #: La synthèse a été produite (avec ou sans texte) — `False` : demande périmée.
    produite: bool
    #: L'assistant a rendu un texte.
    redigee: bool = False
    #: Pourquoi il n'en a pas rendu — l'écran le dit, le bandeau aussi.
    motif: Optional[str] = None
    #: La première production d'une demande : l'avis est à envoyer.
    a_aviser: bool = False
    #: La tentative écrite — sur une relance, c'est la PROPOSITION à appliquer.
    tentative_id: Optional[int] = None


def peut_etre_produite(ticket: Ticket) -> bool:
    """Close et non absorbée — la condition commune à la file et au bouton. Une
    absorbée est couverte par la synthèse de sa principale (#1704).

    Toute catégorie : arbitré le 21/10/2026, à la place de « uniquement les
    affaires du carnet » (03/10) — une question close au point CS / Syndic n'avait
    pas de synthèse, et l'utilisateur l'a lu comme une anomalie. Le carnet, lui,
    ne range toujours que les siennes (`carnet_entretien.contribue_au_carnet`)."""
    return (
        valeur(ticket.statut) in STATUTS_TICKET_CLOS
        and bool(ticket.ferme_le)
        and ticket.fusionnee_dans_id is None
    )


async def _rediger(
    session: Session, message: str, complement: Optional[str], demandeur: Optional[int]
):
    """L'appel à l'assistant — (champs, réponse, statut, motif). Ne lève jamais.

    `demandeur` : le membre du conseil qui relance, ou `None` pour la file
    automatique — que seule la limite du mois borne."""
    from app.utils.llm import ErreurLLM, RefusLimite, config_llm, demander

    cfg = config_llm(session, USAGE_SYNTHESE_AFFAIRE)
    if not cfg.pret:
        try:
            cfg.verifier()
        except ErreurLLM as exc:
            return None, None, "indisponible", str(exc)
    try:
        rep = await demander(
            session,
            usage=USAGE_SYNTHESE_AFFAIRE,
            message=message,
            consigne=consigne_complete(cfg.prompt, complement),
            demandeur=demandeur,
        )
        return lire_reponse(rep.texte), rep, "succes", None
    except RefusLimite as exc:
        return None, None, "indisponible", str(exc)
    except ErreurLLM as exc:
        return None, None, "erreur", str(exc)
    except ReponseIllisible as exc:
        return None, None, "erreur", f"Réponse de l'assistant illisible : {exc}"


def _auteur_de_la_suite(
    session: Session, ticket: Ticket, auteur_id: Optional[int]
) -> Optional[int]:
    """Qui signe la Suite : qui a demandé la production, sinon qui a clos l'affaire.

    Vide seulement si ces comptes ont été supprimés (#1688) : la Suite se lit
    alors « Ancien résident », comme le reste de leur fil. Pour la production automatique,
    la Suite est signée de la dernière transition qui a clos l'affaire, à défaut
    de son auteur — jamais d'un compte de service, qui signerait un texte qu'il
    n'a pas relu.
    """
    if auteur_id:
        return auteur_id
    cloture = session.exec(
        select(TicketEvolution)
        .where(
            TicketEvolution.ticket_id == ticket.id,
            TicketEvolution.type == "etat",
            col(TicketEvolution.nouveau_statut).in_(STATUTS_TICKET_CLOS),
        )
        .order_by(col(TicketEvolution.cree_le).desc())
    ).first()
    return cloture.auteur_id if cloture else ticket.auteur_id


def _remplacer_les_precedentes(session: Session, synthese: SyntheseAffaire) -> None:
    """Arbitré : une nouvelle production remplace la précédente, même validée."""
    for ancienne in session.exec(
        select(SyntheseAffaire).where(
            SyntheseAffaire.ticket_id == synthese.ticket_id,
            SyntheseAffaire.id != synthese.id,
            col(SyntheseAffaire.statut).in_(STATUTS_VIVANTS),
        )
    ).all():
        ancienne.statut = ANNULEE
        ancienne.mis_a_jour_le = horloge.maintenant()
        session.add(ancienne)


async def produire(
    session: Session,
    synthese: SyntheseAffaire,
    *,
    auteur_id: Optional[int] = None,
    complement: Optional[str] = None,
) -> Resultat:
    """Produit (ou reproduit) la synthèse — puis valide la session.

    Une demande en file dont l'affaire a été rouverte, ou close à nouveau
    depuis, est PÉRIMÉE : elle passe `annulee` sans appel (une autre demande
    porte la nouvelle clôture).
    """
    from app.routers.tickets.commun import STATUT_LABELS

    ticket = session.get(Ticket, synthese.ticket_id)
    premiere = synthese.statut == A_PRODUIRE
    if (
        ticket is None
        or not peut_etre_produite(ticket)
        or (premiere and synthese.cloture_le and ticket.ferme_le != synthese.cloture_le)
    ):
        synthese.statut = ANNULEE
        synthese.mis_a_jour_le = horloge.maintenant()
        session.add(synthese)
        session.commit()
        return Resultat(produite=False)

    cloture_le = ticket.ferme_le
    met = metriques_de(session, ticket, cloture_le)
    message = construire_message(session, ticket, met, STATUT_LABELS)
    champs, rep, statut, motif = await _rediger(session, message, complement, auteur_id)

    from app.utils.llm_journal import cout_appel

    maintenant = horloge.maintenant()
    tentative = TentativeSynthese(
        synthese_id=synthese.id,
        auteur_id=auteur_id,
        statut=statut,
        prompt_complement=complement or None,
        jetons_entree=rep.jetons_entree if rep else None,
        jetons_sortie=rep.jetons_sortie if rep else None,
        cout_usd=(
            cout_appel(
                session,
                USAGE_SYNTHESE_AFFAIRE,
                rep.jetons_entree,
                rep.jetons_sortie,
                rep.jetons_cache,
            )
            if rep
            else None
        ),
        cree_le=maintenant,
        **(champs or {}),
    )
    session.add(tentative)
    session.flush()
    synthese.metriques_json = json.dumps(met, ensure_ascii=False)
    if not premiere:
        #  🔴 Une relance PROPOSE, elle ne remplace pas (03/10/2026, demandé à
        #  l'écran : « il manque une option Annuler si on veut sortir sans
        #  sauvegarder »). Le texte relu reste en place ; la rédaction neuve est
        #  dans la tentative, que le conseil applique (`appliquer_tentative`) ou
        #  laisse. Les métriques, elles, sont du code : recalculées, elles valent.
        synthese.mis_a_jour_le = maintenant
        session.add(synthese)
        session.commit()
        return Resultat(
            produite=True, redigee=champs is not None, motif=motif, tentative_id=tentative.id
        )

    synthese.prompt_complement = complement or None
    synthese.produite_le = maintenant
    synthese.mis_a_jour_le = maintenant
    if champs is not None:
        synthese.synthese = champs["synthese"]
        synthese.difficultes = champs["difficultes"]
        synthese.amelioration = champs["amelioration"]
        synthese.assiste_ia = True
        synthese.motif_vide = None
    else:
        synthese.motif_vide = motif
    if premiere:
        synthese.statut = BROUILLON
        synthese.cloture_le = cloture_le
        evol = TicketEvolution(
            ticket_id=ticket.id,
            type=TYPE_SYNTHESE,
            contenu=None,
            auteur_id=_auteur_de_la_suite(session, ticket, auteur_id),
            cree_le=maintenant,
            assiste_ia=champs is not None,
        )
        session.add(evol)
        session.flush()
        synthese.evolution_id = evol.id
        _remplacer_les_precedentes(session, synthese)
    session.add(synthese)
    session.commit()
    return Resultat(
        produite=True,
        redigee=champs is not None,
        motif=motif,
        a_aviser=premiere and synthese.mail_envoye_le is None,
    )


def appliquer_tentative(
    session: Session, synthese: SyntheseAffaire, tentative: TentativeSynthese
) -> None:
    """Le conseil garde la rédaction proposée par une relance — texte, complément.

    « Recommencer » a proposé sans complément : l'appliquer l'efface (arbitré).
    """
    synthese.synthese = tentative.synthese
    synthese.difficultes = tentative.difficultes
    synthese.amelioration = tentative.amelioration
    synthese.prompt_complement = tentative.prompt_complement
    synthese.assiste_ia = True
    synthese.motif_vide = None
    synthese.mis_a_jour_le = horloge.maintenant()
    session.add(synthese)
    evol = session.get(TicketEvolution, synthese.evolution_id) if synthese.evolution_id else None
    if evol is not None:
        evol.assiste_ia = True
        session.add(evol)
    session.commit()


async def envoyer_avis(session: Optional[Session], synthese_id: int) -> bool:
    """Le courriel « Synthèse à valider » — UN envoi par production.

    Marqué `mail_envoye_le` AVANT l'envoi, et validé : une relance, une seconde
    passe de la file ou un double clic ne trouvent plus rien à envoyer. Un envoi
    qui échoue ensuite n'est pas rejoué — mieux vaut un avis manqué, que la
    cloche du conseil rattrape à l'écran, que deux courriels pour un même fait.
    """
    from app import contexte
    from app.utils.config_site import config_site
    from app.utils.destinataires import gestionnaire_puis_cs
    from app.utils.email import send_email_group
    from app.utils.liens import adresse_du_site, nom_site

    propre = session is None
    session = session or contexte.nouvelle_session()
    try:
        synthese = session.get(SyntheseAffaire, synthese_id)
        if synthese is None or synthese.mail_envoye_le is not None:
            return False
        ticket = session.get(Ticket, synthese.ticket_id)
        destinataires = gestionnaire_puis_cs(session)
        synthese.mail_envoye_le = horloge.maintenant()
        session.add(synthese)
        session.commit()
        if ticket is None or not destinataires:
            return False
        cfg = config_site(session, "site_nom")
        await send_email_group(
            code="synthese_a_valider",
            to_recipients=destinataires,
            context={
                "ticket": {"id": ticket.id, "numero": ticket.numero, "titre": ticket.titre},
                "issue": "résolue" if valeur(ticket.statut) == "résolu" else "annulée",
                "synthese": {"vide": not synthese.synthese, "evolution_id": synthese.evolution_id},
                "residence": {"nom": nom_site(cfg.get("site_nom"))},
                "app": {"url": adresse_du_site()},
            },
            session=session,
        )
        return True
    finally:
        if propre:
            session.close()


__all__ = [
    "Resultat",
    "appliquer_tentative",
    "USAGE_SYNTHESE_AFFAIRE",
    "envoyer_avis",
    "peut_etre_produite",
    "produire",
]
