"""Défaire un transfert de courriel versé par erreur — d'un geste (#1482, 30/09/2026).

## Le besoin

> « Si par erreur un fil est versé dans la mauvaise affaire, est-il possible
>   d'annuler ces ajouts en une fois, et/ou de les réaffecter à une autre
>   affaire, et/ou de créer une nouvelle affaire ? »

Un transfert (`courriel_transfert.verser`) écrit une Suite par message, et
parfois l'affaire elle-même. Chaque Suite porte désormais `versement_id`, et la
trace (`VersementCourriel`) garde ce que le versement a changé AUTOUR d'elles :
le statut d'avant, le lien du fil d'avant. Trois gestes :

| Geste | Ce qu'il fait |
|---|---|
| **annuler** | les Suites et leurs empreintes partent ; statut et lien du fil reviennent ; une affaire que le transfert avait créée est **archivée** — jamais supprimée |
| **réaffecter** | les Suites passent dans l'affaire choisie, sans doubler ce qu'elle a déjà ; une affaire créée par le transfert y verse aussi sa description, puis s'archive |
| **détacher** | une affaire neuve, décrite par le premier message, au nom de son auteur — comme à la création par transfert — reçoit les autres |

## Quand ce n'est plus proposé (arbitré le 30/09/2026)

Aucun délai, mais **dès qu'une Suite a été écrite dans l'affaire après le
transfert — par quiconque, celui qui a transféré compris —**, le geste s'éteint :
la suite répond à ce qui a été versé, et défaire la laisserait sans contexte.
Arbitré le 01/10/2026 : la règle exceptait jusque-là les Suites de celui qui a
transféré, et l'annulation restait offerte après sa propre réponse.

Un transfert ne se défait pas non plus tant qu'un transfert SUIVANT a été versé
dans l'affaire : on défait du plus récent au plus ancien, et un seul transfert
à la fois s'offre au geste. Deux transferts du même fil proposaient chacun
« Annuler » (01/10/2026) — le premier aurait rendu le lien du fil sous le second.

## Qui

Celui qui a transféré, et l'administrateur — `auth/appartenance.exiger_auteur_du_versement`.
Déplacer vers une autre affaire exige en plus de modérer : on ne verse pas dans
une affaire qu'on ne peut pas lire.

## Valider (13/10/2026)

> « Il manque Valider ce transfert (si c'est ok et pour faire disparaître ces
>   boutons) »

Un transfert versé au bon endroit gardait ses trois gestes jusqu'à ce qu'une
Suite les éteigne. **Valider** le confirme : il quitte la liste
(`a_proposer`) et ne se défait plus. Il reste EN PLACE — `versements_de` le
compte toujours —, donc un transfert plus ancien reste bloqué sous lui : valider
le plus récent ne rouvre pas le précédent. Même droit qu'annuler.

## Réglé sans geste (14/10/2026)

Un transfert que plus rien ne rouvrira — une Suite écrite depuis, ou un
transfert suivant validé — quitte la liste de lui-même. Il y restait, sous
« Ne peut plus être défait : … annulez-le d'abord », avec pour seul bouton
« Valider » : un geste à faire sur ce qu'on venait de dire impossible, et une
consigne (« annulez-le ») qu'un transfert validé refuse. Seul reste bloqué À
L'ÉCRAN celui qu'un transfert suivant encore défaisable retient.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.models.core import Ticket, TicketEvolution, Utilisateur
from app.models.courriel import FilCourriel, MessageVerse, VersementCourriel
from app.models.tickets import STATUTS_TICKET_CLOS, StatutTicket
from app.utils import horloge
from app.utils.valeurs import valeur


# ── La trace, posée par `courriel_transfert.verser` ─────────────────────────


def etat_avant(session: Session, ticket: Ticket | None, cle: str | None) -> dict:
    """Ce que le versement va changer, lu AVANT d'écrire : ce que l'annulation rétablit."""
    lien = session.exec(select(FilCourriel).where(FilCourriel.cle == cle)).first() if cle else None
    return {
        "statut_avant": valeur(ticket.statut) if ticket is not None else None,
        "cle_fil": cle,
        "fil_avant_id": lien.ticket_id if lien else None,
        "seuil_evolution_id": _derniere_suite(session),
    }


def ouvrir_versement(session, qui, ticket, avant: dict, objet: str, *, creee: bool):
    versement = VersementCourriel(
        ticket_id=ticket.id,
        transfere_par_id=qui.id,
        affaire_creee=creee,
        objet=objet,
        **avant,
    )
    session.add(versement)
    session.flush()
    return versement


def _derniere_suite(session: Session) -> int:
    return session.exec(select(func.max(TicketEvolution.id))).one() or 0


# ── Ce qu'on en lit ─────────────────────────────────────────────────────────


def suites_du(session: Session, v: VersementCourriel) -> list[TicketEvolution]:
    """Les Suites du versement, dans l'ordre où elles ont été écrites."""
    return list(
        session.exec(
            select(TicketEvolution)
            .where(TicketEvolution.versement_id == v.id, TicketEvolution.ticket_id == v.ticket_id)
            .order_by(TicketEvolution.id)
        ).all()
    )


def versements_de(session: Session, ticket_id: int) -> list[VersementCourriel]:
    """Les versements encore en place dans cette affaire — ceux qui ont écrit
    quelque chose : un transfert dont tous les messages ont été écartés n'a
    rien à défaire."""
    actifs = session.exec(
        select(VersementCourriel)
        .where(VersementCourriel.ticket_id == ticket_id, VersementCourriel.annule_le.is_(None))
        .order_by(VersementCourriel.id.desc())
    ).all()
    return [v for v in actifs if v.affaire_creee or suites_du(session, v)]


def a_proposer(session: Session, ticket_id: int) -> list[VersementCourriel]:
    """Les versements que l'affaire montre encore : en place, pas validés, et
    qu'un geste pourra encore défaire — aujourd'hui, ou une fois les transferts
    suivants annulés. Un versement que plus rien ne rouvrira est réglé : le
    montrer n'offrait que « Valider » sous « Ne peut plus être défait »
    (14/10/2026)."""
    return [
        v
        for v in versements_de(session, ticket_id)
        if v.valide_le is None and not _definitivement_bloque(session, v)
    ]


def _suite_ecrite_depuis(session: Session, v: VersementCourriel) -> bool:
    #  Une Suite écrite à la main n'est jamais déplacée : son identifiant dit
    #  bien qu'elle est venue après le seuil. Celles d'un transfert, si — d'où
    #  la comparaison des seuils dans `_suivants`, et non des identifiants.
    return (
        session.exec(
            select(TicketEvolution).where(
                TicketEvolution.ticket_id == v.ticket_id,
                TicketEvolution.id > v.seuil_evolution_id,
                TicketEvolution.versement_id.is_(None),
            )
        ).first()
        is not None
    )


def _suivants(session: Session, v: VersementCourriel) -> list[VersementCourriel]:
    """Les versements en place venus après celui-ci — à défaire avant lui."""
    return [
        w
        for w in versements_de(session, v.ticket_id)
        if w.id != v.id and (v.affaire_creee or w.seuil_evolution_id > v.seuil_evolution_id)
    ]


def _definitivement_bloque(session: Session, v: VersementCourriel) -> bool:
    """Aucun geste ne le rouvrira : une Suite écrite depuis ne part jamais, et un
    transfert suivant validé ne s'annule plus. Une Suite écrite après un
    transfert suivant l'est aussi après celui-ci : elle est vue ici."""
    return _suite_ecrite_depuis(session, v) or any(
        w.valide_le is not None for w in _suivants(session, v)
    )


def motif_bloquant(session: Session, v: VersementCourriel) -> str | None:
    """Pourquoi ce versement ne se défait plus — `None` s'il se défait."""
    if v.annule_le is not None:
        return "ce transfert a déjà été annulé"
    if v.valide_le is not None:
        return "ce transfert a été validé"
    if _suite_ecrite_depuis(session, v):
        return "une suite a été écrite dans cette affaire depuis ce transfert"
    suivants = _suivants(session, v)
    if any(w.valide_le is not None for w in suivants):
        return "un transfert suivant a été validé dans cette affaire"
    if suivants:
        return "un transfert suivant a été versé dans cette affaire : annulez-le d'abord"
    return None


def _exiger_defaisable(session: Session, v: VersementCourriel) -> None:
    motif = motif_bloquant(session, v)
    if motif:
        raise HTTPException(409, f"Ce transfert ne peut plus être défait : {motif}.")


# ── Les gestes ──────────────────────────────────────────────────────────────


def valider(session: Session, v: VersementCourriel, qui: Utilisateur) -> Ticket:
    """Confirme le versement : il reste, et ne s'offre plus au geste."""
    if v.annule_le is not None:
        raise HTTPException(409, "Ce transfert a déjà été annulé.")
    if v.valide_le is None:
        v.valide_le = horloge.maintenant()
        v.valide_par_id = qui.id
        session.add(v)
    return session.get(Ticket, v.ticket_id)


def annuler(session: Session, v: VersementCourriel) -> Ticket:
    """Retire tout ce que le versement a écrit. Rend l'affaire où il était."""
    _exiger_defaisable(session, v)
    ticket = session.get(Ticket, v.ticket_id)
    if v.affaire_creee:
        #  Archiver, jamais supprimer : l'affaire garde sa trace, aux Archives,
        #  où l'administrateur peut l'effacer (`ux-patterns` §8).
        ticket.archive_manuel = True
    else:
        for suite in suites_du(session, v):
            session.delete(suite)
        _rendre_le_statut(ticket, v)
    for marque in _marques(session, v):
        session.delete(marque)
    _rendre_le_fil(session, v, None)
    v.annule_le = horloge.maintenant()
    session.add_all([v, ticket])
    return ticket


def reaffecter(session: Session, v: VersementCourriel, cible: Ticket, qui: Utilisateur) -> Ticket:
    """Verse ailleurs ce que le versement a écrit. Rend l'affaire qui le reçoit."""
    _exiger_defaisable(session, v)
    _exiger_cible(v, cible)
    source = session.get(Ticket, v.ticket_id)
    marques = _marques(session, v)
    suites = suites_du(session, v)
    if v.affaire_creee:
        #  La description de l'affaire créée EST le premier message : elle
        #  devient une Suite de la cible, et c'est la marque sans Suite la plus
        #  ancienne qui la reconnaît — `verser` la pose avant toute autre.
        premiere = _description_en_suite(session, v, source)
        suites.insert(0, premiere)
        sans_suite = [m for m in marques if m.evolution_id is None]
        if sans_suite:
            sans_suite[0].evolution_id = premiere.id
        source.archive_manuel = True
    else:
        _rendre_le_statut(source, v)
    statut_cible = valeur(cible.statut)
    _deplacer(session, v, cible, suites, marques)
    _rendre_le_fil(session, v, cible.id)
    v.ticket_id = cible.id
    v.affaire_creee = False
    v.statut_avant = statut_cible
    v.seuil_evolution_id = _derniere_suite(session)
    cible.mis_a_jour_le = horloge.maintenant()
    session.add_all([v, source, cible])
    return cible


def detacher(session: Session, v: VersementCourriel, qui: Utilisateur) -> Ticket:
    """Une affaire neuve pour ce que le versement a écrit. Rend l'affaire créée."""
    from app.utils.courriel_fil import titre_du_fil
    from app.utils.courriel_transfert import creer_affaire_du_fil

    _exiger_defaisable(session, v)
    if v.affaire_creee:
        raise HTTPException(409, "Ce transfert a déjà créé son affaire.")
    suites = suites_du(session, v)
    if not suites:
        raise HTTPException(409, "Ce transfert n'a écrit aucune suite.")
    premiere = suites[0]
    auteur = session.get(Utilisateur, v.transfere_par_id) or qui
    nouvelle = creer_affaire_du_fil(
        session,
        auteur,
        nom=v.premier_nom or "",
        adresse=v.premier_adresse,
        description=premiere.contenu or "",
        quand=premiere.cree_le,
        assiste=premiere.assiste_ia,
        titre=titre_du_fil(v.objet) or f"Courriel de {v.premier_nom}",
    )
    for marque in _marques(session, v):
        if marque.evolution_id == premiere.id:
            marque.evolution_id = None  # elle décrit l'affaire, comme à la création
    session.delete(premiere)
    session.flush()
    #  Le reste suit le chemin d'une réaffectation — une seule écriture du
    #  déplacement, du statut rendu et du lien du fil.
    reaffecter(session, v, nouvelle, qui)
    v.affaire_creee = True
    v.statut_avant = None
    session.add(v)
    return nouvelle


# ── Ce que les gestes partagent ─────────────────────────────────────────────


def _marques(session: Session, v: VersementCourriel) -> list[MessageVerse]:
    return list(
        session.exec(
            select(MessageVerse).where(MessageVerse.versement_id == v.id).order_by(MessageVerse.id)
        ).all()
    )


def _exiger_cible(v: VersementCourriel, cible: Ticket) -> None:
    if cible.id == v.ticket_id:
        raise HTTPException(422, "Le transfert est déjà dans cette affaire.")
    if valeur(cible.statut) in STATUTS_TICKET_CLOS:
        raise HTTPException(422, f"L'affaire #{cible.numero} est close : elle ne reçoit plus rien.")


def _rendre_le_statut(ticket: Ticket, v: VersementCourriel) -> None:
    """Une réponse du syndic avait fait passer l'affaire « En cours » : elle revient.

    Sûr parce que le geste s'éteint dès qu'une Suite a été écrite : un
    changement d'état fait à la main laisse la sienne, donc bloque avant ici.
    """
    if v.statut_avant and valeur(ticket.statut) != v.statut_avant:
        ticket.statut = v.statut_avant


def _rendre_le_fil(session: Session, v: VersementCourriel, vers: int | None) -> None:
    """Le lien du fil : vers la nouvelle affaire, ou tel qu'il était avant le transfert."""
    if not v.cle_fil:
        return
    lien = session.exec(select(FilCourriel).where(FilCourriel.cle == v.cle_fil)).first()
    if lien is None or lien.ticket_id != v.ticket_id:
        return  # un transfert suivant l'a déjà repris : il n'est plus à nous
    cible = vers if vers is not None else v.fil_avant_id
    if cible is None:
        session.delete(lien)
        return
    lien.ticket_id = cible
    lien.mis_a_jour_le = horloge.maintenant()
    session.add(lien)


def _description_en_suite(session, v: VersementCourriel, source: Ticket) -> TicketEvolution:
    suite = TicketEvolution(
        ticket_id=source.id,
        type="commentaire",
        contenu=source.description,
        auteur_id=v.transfere_par_id,
        assiste_ia=source.assiste_ia,
        cree_le=source.cree_le,
        versement_id=v.id,
    )
    session.add(suite)
    session.flush()
    return suite


def _deplacer(session, v, cible: Ticket, suites, marques) -> None:
    """Chaque Suite passe dans la cible — sauf ce que la cible porte déjà,
    reconnu comme au versement : par l'empreinte, ou par le texte reçu."""
    from app.utils.courriel_fil import texte_normalise
    from app.utils.courriel_transfert import DEBUT_COMPARE, LONGUEUR_COMPARABLE, texte_du_fil
    from app.utils.nature_affaire import est_actualite

    deja = set(
        session.exec(select(MessageVerse.empreinte).where(MessageVerse.ticket_id == cible.id)).all()
    )
    fil = texte_du_fil(session, cible)
    marque_de = {m.evolution_id: m for m in marques if m.evolution_id is not None}
    retirees: set[int] = set()
    for suite in suites:
        marque = marque_de.get(suite.id)
        norme = texte_normalise(suite.contenu_origine or "")
        if (marque is not None and marque.empreinte in deja) or (
            len(norme) >= LONGUEUR_COMPARABLE and norme[:DEBUT_COMPARE] in fil
        ):
            session.delete(suite)
            if marque is not None:
                session.delete(marque)
                retirees.add(marque.id)
            continue
        suite.ticket_id = cible.id
        if suite.type == "etat":
            #  Une réponse du syndic fait avancer l'affaire qui la reçoit, pas
            #  celle qu'elle quitte — même règle qu'au versement
            #  (`reponse_courriel.suite_mise_en_forme`).
            if valeur(cible.statut) == StatutTicket.ouvert.value and not est_actualite(cible):
                suite.ancien_statut = StatutTicket.ouvert.value
                cible.statut = suite.nouveau_statut
            else:
                suite.type, suite.ancien_statut, suite.nouveau_statut = "commentaire", None, None
        session.add(suite)
    for marque in marques:
        if marque.id in retirees:
            continue
        if marque.evolution_id is None and marque.empreinte in deja:
            session.delete(marque)  # un message écarté que la cible a déjà
            continue
        marque.ticket_id = cible.id
        session.add(marque)


__all__ = [
    "annuler",
    "detacher",
    "etat_avant",
    "motif_bloquant",
    "ouvrir_versement",
    "reaffecter",
    "suites_du",
    "versements_de",
]
