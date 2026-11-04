"""L'affaire NEUVE qu'ouvre un fil transféré, et le compte d'une adresse (#2515).

Extrait de `courriel_transfert.py` le 04/11/2026 : ce fichier était à 499 lignes
et devait recevoir les pièces jointes d'un transfert. `courriel_transfert`
ré-exporte tout ce qui vit ici — ses lecteurs (`courriel_boite`,
`versement_transfert`) l'y cherchent encore.
"""

from __future__ import annotations

from sqlmodel import Session

from app.auth.adresse_compte import compte_par_adresse
from app.models.core import Ticket, Utilisateur
from app.models.tickets import CategorieTicket
from app.utils import horloge

#: La catégorie d'une affaire créée par transfert — le conseil la corrige ensuite.
CATEGORIE_PAR_DEFAUT = CategorieTicket.etude_travaux
#: « Conseil syndical seul », CHOISI et non hérité de la catégorie : il tient
#: quand le conseil corrige la catégorie.
PUBLIC_CONSEIL_SEUL = '["conseil_syndical"]'
#: Un titre d'affaire reste lisible dans une liste.
LONGUEUR_TITRE = 200


def compte_a_l_adresse(session: Session, adresse: str | None) -> Utilisateur | None:
    """Le compte ACTIF à cette adresse (« Nom <a@b.fr> » accepté), sans égard à la casse.

    Ce module ne fait qu'extraire l'adresse de l'en-tête : la question « quel
    compte ? » est celle de `auth.adresse_compte`, posée partout de la même façon.
    """
    from email.utils import parseaddr

    return compte_par_adresse(session, parseaddr(adresse or "")[1], actif_seulement=True)


def creer_affaire_du_fil(
    session: Session,
    qui: Utilisateur,
    *,
    nom: str,
    adresse: str | None,
    description: str,
    quand,
    assiste: bool,
    titre: str,
) -> Ticket:
    """Une affaire du conseil, au nom de l'auteur du message qui la décrit —
    celle d'un transfert, ou celle qu'on en détache (`versement_transfert`)."""
    from app.routers.tickets.commun import generer_numero
    from app.utils.courriel_entrant import nouveau_jeton
    from app.utils.kanban_tickets import suivi_par_defaut
    from app.models.tickets import StatutTicket
    from app.utils.destinataires import est_adresse_syndic
    from app.utils.nature_affaire import statut_pour

    #  Le syndic a déjà écrit : l'affaire naît chez lui (demandé le 29/09/2026,
    #  même règle que pour une Suite — `suite_d_un_message`).
    demande = StatutTicket.en_cours.value if est_adresse_syndic(session, adresse) else None
    auteur = compte_a_l_adresse(session, adresse)
    if auteur is not None:
        #  « Au nom de » soi-même, c'est « en mon nom » : rien à poser.
        pour = {"saisi_pour_user_id": auteur.id} if auteur.id != qui.id else {}
    else:
        pour = {"saisi_pour_nom": nom, "saisi_pour_email": adresse or None}
    ticket = Ticket(
        numero=generer_numero(session),
        jeton_courriel=nouveau_jeton(),
        titre=titre[:LONGUEUR_TITRE],
        description=description,
        categorie=CATEGORIE_PAR_DEFAUT,
        statut=statut_pour(CATEGORIE_PAR_DEFAUT, demande, est_cs=True),
        priorite="normale",
        auteur_id=qui.id,
        public_cible=PUBLIC_CONSEIL_SEUL,
        suivi_kanban=suivi_par_defaut(CATEGORIE_PAR_DEFAUT),
        assiste_ia=assiste,
        #  Datée du courriel : ses Suites le sont aussi, et le fil doit se lire
        #  dans l'ordre où les choses ont été écrites.
        cree_le=quand,
        mis_a_jour_le=horloge.maintenant(),
        **pour,
    )
    session.add(ticket)
    session.flush()
    return ticket
