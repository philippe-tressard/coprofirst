"""À quelle affaire un courriel reçu répond-il, et son expéditeur peut-il y écrire ?

Sorti de `courriel_boite` le 05/11/2026 (#2555), sur refus du contrôle de
modularité : la file « à classer » faisait passer la relève au-delà de 500 lignes.
La coupure suit une question : la relève applique un verdict, ce module dit QUEL
dossier il vise et QUI peut y écrire — la relève ordinaire et le transfert
(`courriel_transfert`) le demandent tous deux ici.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.deps import peut_commenter
from app.models.core import Ticket, Utilisateur
from app.utils.destinataires import est_adresse_syndic


def _ticket_de(session: Session, verdict) -> Ticket | None:
    """Le ticket visé : le jeton d'abord, le numéro du sujet en REPLI (05/09/2026).

    L'ordre porte la sécurité. Le jeton est opaque et non devinable : le tenir
    prouve qu'on a reçu un message du site à propos de CE ticket. Le numéro, lui,
    figure dans tous les courriels déjà envoyés — il désigne, il ne prouve pas.
    C'est pourquoi le repli ne donne pas le même droit : voir
    `correspondant_du_ticket`, qui n'est exigé QUE sur ce chemin.
    """
    if verdict.jeton:
        return session.exec(select(Ticket).where(Ticket.jeton_courriel == verdict.jeton)).first()
    if verdict.numero:
        #  Comparaison insensible à la casse : un client de messagerie peut
        #  remettre le sujet en capitales, et le numéro y perdrait sa forme.
        return session.exec(
            select(Ticket).where(func.lower(Ticket.numero) == verdict.numero.lower())
        ).first()
    return None


def correspondant_du_ticket(session: Session, ticket: Ticket, auteur: Utilisateur) -> bool:
    """Le site aurait-il ÉCRIT à cette personne à propos de ce ticket ?

    C'est le prix du repli par le sujet, et il est calculé sur ce que le jeton
    prouvait tout seul : *avoir reçu un message du site sur ce dossier*. Sans lui,
    n'importe quel titulaire de compte pourrait commenter n'importe quel ticket
    en écrivant son numéro dans un sujet — un droit que l'écran ne donne pas.

    Quatre cas, et ce sont exactement ceux à qui l'application envoie les
    courriels d'un ticket :

    - son **auteur**, et la personne pour qui il a été saisi ;
    - un membre du **conseil syndical**, qui suit tous les dossiers ;
    - un **administrateur** ;
    - le **syndic**, reconnu à son adresse dans la fiche du cabinet — il n'a
      souvent pas d'autre lien avec le site, et c'est POUR LUI que ce repli a été
      demandé.

    ⚠️ Le syndic est cherché par l'ADRESSE, pas par un rôle : `RoleUtilisateur`
    n'en a pas, et le gestionnaire vit dans `MembreSyndic`.
    """
    return peut_commenter(ticket, auteur) or est_adresse_syndic(session, auteur.email)
