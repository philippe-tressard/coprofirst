"""Les CONSÉQUENCES d'un geste sur un accès — déduire, tracer, prévenir.

## Pourquoi ce module (14/09/2026, #953)

Ce ne sont pas des routes : ce sont les trois choses qui arrivent quand on
enregistre ou corrige un badge. Le plafond de modularité a refusé `acces/parc.py`
à 507 lignes pour un fichier neuf, et il désignait cette césure — un routeur dit
QUI a le droit et QUOI répondre ; ce qui suit dit ce que le geste entraîne.

C'est le même raisonnement que `utils/telemetrie_calculs` : ce qui n'est pas du
routage se relit mieux ailleurs, et devient éprouvable sans monter une requête.
"""

from __future__ import annotations

import json
from typing import Optional

from sqlmodel import Session, select

from app.models.copropriete import Lot
from app.models.core import TicketEvolution, UserLot, Utilisateur
from app.utils.acces_choix import acces_par_defaut
from app.utils.acces_perimetre import acces_deduit
from app.utils.perimetres import parse_json_perimetres, perimetre_label
from app.utils.types_acces import TypeAcces
from app.utils.cloche import sonner_systeme
from app.utils.journal_securite import journaliser_securite


#  ── Ce que le badge ouvre, et ce qui en découle ────────────────────────────


def _acces_json(
    session: Session,
    type_acces: TypeAcces,
    donne: Optional[list[str]],
    lot_id: Optional[int],
    porteur_id: Optional[int],
) -> Optional[str]:
    """Le périmètre à enregistrer : celui qu'on a saisi, sinon celui qu'on déduit.

    ⚠️ **Une liste VIDE est une décision**, pas une absence : elle dit « on ne
    sait pas », et on n'essaie alors pas de deviner à la place de qui l'a
    effacée. Seul `None` — le champ non transmis — déclenche la déduction.

    🔴 **La déduction dépend du TYPE** (14/09/2026, signalé à l'écran) : un vigik
    ouvre le bâtiment où l'on habite, une télécommande ouvre des portails —
    toujours les mêmes. C'est le descripteur qui le dit (`acces_suit_le_lot`), et
    `utils/acces_choix` qui sait où sont ces portails.

    La règle de déduction vit dans `utils/acces_perimetre` : le bâtiment du lot,
    ou celui des lots du porteur s'ils sont tous dans le même. La migration 0190
    en porte l'équivalent SQL, la 0191 la corrige pour les télécommandes, et
    `test_acces_perimetre.py` vérifie que les deux disent la même chose.
    """
    if donne is not None:
        return json.dumps(donne, ensure_ascii=False) if donne else None

    if not type_acces.acces_suit_le_lot:
        fixe = acces_par_defaut(session, type_acces)
        return json.dumps(fixe, ensure_ascii=False) if fixe else None

    batiments: list = []
    if lot_id:
        lot = session.get(Lot, lot_id)
        if lot:
            batiments.append(lot.batiment_id)
    if not batiments:
        batiments = [
            lot.batiment_id
            for lot in session.exec(
                select(Lot)
                .join(UserLot, UserLot.lot_id == Lot.id)
                .where(UserLot.user_id == porteur_id, UserLot.actif == True)  # noqa: E712
            ).all()
        ]
    deduit = acces_deduit(batiments)
    return json.dumps(deduit, ensure_ascii=False) if deduit else None


def _tracer_sur_ticket(
    session: Session, ticket, auteur: Utilisateur, type_acces: TypeAcces, objet, verbe: str
) -> None:
    """Le geste s'inscrit dans le fil du ticket dont le numéro a été saisi.

    ⚠️ Par une **entrée d'historique**, comme n'importe quel commentaire — pas
    par une écriture directe dans le ticket. Le fil est la mémoire de l'objet, et
    une ligne qui n'y passerait pas serait invisible de l'écran qui le lit.

    ⚠️ Le type est `commentaire` : ce geste ne fait pas avancer le ticket, il
    raconte ce qui a été fait. Choisir `etat` inscrirait une transition qui n'a
    pas eu lieu.
    """
    if ticket is None:
        return
    perimetre = parse_json_perimetres(objet.perimetre_cible)
    portee = perimetre_label(perimetre) if perimetre else "non précisé"
    session.add(
        TicketEvolution(
            ticket_id=ticket.id,
            type="commentaire",
            contenu=(f"{type_acces.libelle} {objet.code} {verbe} — accès : {portee}."),
            auteur_id=auteur.id,
        )
    )
    session.commit()


def _prevenir_porteur(session: Session, porteur: Utilisateur, type_acces: TypeAcces, objet) -> None:
    """Le porteur apprend qu'un accès est enregistré à son nom.

    ⚠️ **Une notification dans l'application, pas un courriel** — et c'est une
    limite que je nomme plutôt que de la masquer. Le ticket demande « un mail
    notifie le demandeur s'il a un mail » ; l'envoi passe par un MODÈLE stocké en
    base, et en créer un demande une migration qui le pose (sans quoi il part
    vide : c'est l'incident du modèle BOUCHON, 09/09/2026). Ce lot livre donc la
    notification, et le courriel suit avec son modèle.

    ⚠️ Rien n'est envoyé si le porteur n'a pas d'adresse — la demande le dit
    (« s'il a un mail »), et une notification sans destinataire n'est pas une
    notification.
    """
    perimetre = parse_json_perimetres(objet.perimetre_cible)
    portee = perimetre_label(perimetre) if perimetre else "non précisé"
    sonner_systeme(
        session,
        "sa_demande",
        destinataire_id=porteur.id,
        type=type_acces.cle,
        titre=f"{type_acces.libelle} enregistré à votre nom",
        corps=f"{objet.code} — accès : {portee}.",
        lien="/mon-lot",
    )
    session.commit()


def journaliser_acces(
    acteur: Utilisateur, type_acces: TypeAcces, objet, avant: Optional[str]
) -> None:
    """Le conseil a posé ou changé ce qu'un badge OUVRE : la trace de qui, et sur quoi (#2217).

    Une porte physique ne s'ajoute pas sans laisser de ligne — c'est le pendant de
    « proposer, jamais poser » (`utils/acces_portes`). Rien n'est écrit si l'accès
    n'a pas changé. 🔴 Sans donnée personnelle : des identifiants et des codes de
    périmètre, jamais un nom.
    """
    if objet.perimetre_cible == avant:
        return
    journaliser_securite(
        "acces_perimetre_pose",
        acteur_id=acteur.id,
        cible_id=objet.user_id,
        detail=(
            f"type={type_acces.cle} objet={objet.id} "
            f"avant={','.join(json.loads(avant)) if avant else '-'} "
            f"apres={','.join(json.loads(objet.perimetre_cible)) if objet.perimetre_cible else '-'}"
        ),
    )
