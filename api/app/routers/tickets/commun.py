"""Tickets — notions partagées par les cinq sous-domaines.

Extrait de `tickets.py` (1238 lignes) le 08/08/2026. Voir `__init__.py` pour la
règle de découpage.

Trois duplications que le fichier long avait fabriquées vivent désormais ici :

- **la liste des destinataires syndic / CS**, écrite à l'identique **trois fois**
  (création d'un ticket, relance syndic, ajout d'une évolution). Trois blocs de
  vingt lignes qui déduplicaient les adresses chacun dans leur coin — le jour où
  la règle change, il fallait la corriger trois fois et personne ne l'aurait su ;
- **la lecture de `site_nom` / `site_url`**, refaite **quatre fois** ;
- **le libellé d'une évolution**, écrit deux fois avec deux résultats différents
  (« Commentaire CS » d'un côté, « Commentaire : … » de l'autre).
"""

import json
import random
import string
from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.deps import est_moderateur
from app.utils.affaires_liees import liees_lisibles
from app.utils.fusion_affaires import principale_lue
from app.utils.nature_affaire import natures
from app.utils.batiments import libelle_batiment_ou
from app.utils.perimetres import parse_json_perimetres
from app.utils.visibility import concerne
from app.models.core import (
    Batiment,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.models.prestataires import ContratEntretien, Prestataire
from app.utils.recuperer import ou_rien
from app.schemas import AffaireLieeLue, ContratDeLAffaire, TicketEvolutionRead, TicketRead
from app.utils.archivage import est_archivable, perime_le
from app.utils.lecture import lire_objet
from app.utils.corrections_texte import expliciter_ancienne
from app.utils.photos import parse_photos
from .lecture_groupee import LectureGroupee, lecture_groupee

#: Libellé lisible de chaque état — e-mails, notifications, fil d'évolutions.
#:
#: Les quatre premières clés sont les états du workflow (`StatutTicket`) ;
#: `fermé` n'en est plus un depuis le 17/08/2026 (#415, migration 0149) mais
#: reste **affichable** : le fil de tickets anciens raconte « Ouvert → Fermé »,
#: et une ligne d'histoire ne se réécrit pas. Sans ce libellé, ces évolutions
#: afficheraient la valeur brute.
#:
#: Un couvercle vérifie que ce dictionnaire couvre l'énumération et rien de
#: fantaisiste : `api/tests/test_statuts_tickets.py`.
STATUT_LABELS = {
    "ouvert": "Ouvert",
    "en_ag": "À l’AG",
    "en_cours": "Chez le syndic",
    "chez_prestataire": "Chez le prestataire",
    "résolu": "Résolu",
    "annulé": "Annulé",
    "fermé": "Fermé",  # historique seulement — cf. STATUTS_TICKET_HISTORIQUES
    "publie": "Publiée",  # sans cycle — une actualité (#1091)
}


def pieces_du_ticket(ticket) -> list[str]:
    """Toutes les pièces jointes PROPRES d'un ticket — photos puis documents.

    🔴 Écrite trois fois : ici, et deux fois dans `crud.py` pour composer les
    pièces d'un courriel. L'ordre compte — la galerie d'abord, les documents
    ensuite — et trois écritures d'un ordre, c'est deux occasions de l'inverser
    sans que rien ne le dise : un courriel dont la première pièce change de
    nature ne lève aucune erreur.

    ⚠️ « Propres » au sens de : celles du ticket lui-même, par opposition à
    celles de ses évolutions — que `lecture_groupee.pieces_du_fil` va chercher quand
    l'objet n'en porte aucune.
    """
    return parse_photos(ticket.photos_urls) + parse_photos(ticket.fichiers_urls)


#: Tirages avant de renoncer. Avec n affaires, un tirage tombe sur un numéro pris
#: avec la chance n/10⁶ : vingt échecs de suite n'arrivent pas avant que l'espace
#: des numéros soit presque plein — et ce jour-là, il faut le DIRE.
ESSAIS_NUMERO = 20


def generer_numero(session: Session) -> str:
    """Un numéro `TK-` + six chiffres, LIBRE dans la base (#1802).

    La colonne `ticket.numero` est unique : un tirage sans vérification faisait
    échouer la création d'une affaire en 500 à chaque collision. La question se
    pose ici, pour les cinq créations qui l'appellent. Les affaires ajoutées mais
    pas encore écrites (une création en lot) sont vues, la requête vidant la
    session d'abord. Deux créations simultanées tirant le même numéro libre
    restent possibles ; c'est la contrainte unique qui les départage.
    """
    for _ in range(ESSAIS_NUMERO):
        numero = "TK-" + "".join(random.choices(string.digits, k=6))
        if session.exec(select(Ticket.id).where(Ticket.numero == numero)).first() is None:
            return numero
    raise RuntimeError(f"Aucun numéro d'affaire libre en {ESSAIS_NUMERO} tirages.")


# ── Configuration du site ────────────────────────────────────────────────────
#
# 🔴 LA LECTURE A DÉMÉNAGÉ le 18/09/2026, et ces deux noms n'en sont plus que
# des renvois. Elle vivait ici, c'est-à-dire chez un APPELANT, et dans le
# module d'un domaine qui n'a rien à voir avec la configuration : le
# démarrage de l'application l'importait au milieu d'une fonction pour
# éviter le cycle, et `routers/annonces_hall.py` avait fini par recopier la
# requête — avec un écart, `""` au lieu de `None`.
#
# Le corps vit dans `app/utils/config_site.py`. Les alias restent parce que
# quatre modules de ce paquet les nomment, et que la documentation du paquet
# les désigne : les supprimer serait un second lot, qui n'apporterait que du
# renommage (même parti que les destinataires, ci-dessous).
from app.utils.config_site import (  # noqa: F401  (ré-export volontaire)
    config_site,
    contexte_site,
)


# ── Destinataires ────────────────────────────────────────────────────────────
#
# 🔴 LA RÈGLE A DÉMÉNAGÉ le 31/08/2026, et ces deux noms n'en sont plus que des
# renvois. Ce fichier portait le corps, avec ce commentaire : *« elle est le seul
# endroit où cette règle s'écrit »*. C'était faux — le calendrier, les
# publications et les sondages en portaient chacun une copie, identique à la
# variable près, et sans un mot d'explication.
#
# ⚠️ C'est la forme la plus coûteuse de la duplication : le seul fichier qui
# parlait du sujet affirmait que le problème n'existait pas. Une relecture qui
# ouvrait celui-ci en repartait rassurée.
#
# Le corps vit dans `app/utils/destinataires.py`, que `CLAUDE.md` désigne comme
# la source unique des destinataires. Les alias restent parce que six modules et
# la documentation du paquet les nomment : les supprimer serait un second lot,
# et il n'apporterait rien de plus que du renommage.
from app.utils.destinataires import (  # noqa: F401  (ré-export volontaire)
    destinataires_syndic_cs,
    syndic_principal,
)
from app.utils.saisi_pour import adresse_lisible, noms_derives
from app.utils.noms import nom_auteur


# ── Libellés d'évolution ─────────────────────────────────────────────────────


def libelle_evolution(e: TicketEvolution, *, avec_extrait: bool = False) -> str:
    """Ligne d'historique décrivant une évolution.

    `avec_extrait` reproduit la nuance qui existait entre les deux écritures
    d'origine : l'e-mail d'évolution montrait un extrait du commentaire, celui de
    relance se contentait de « Commentaire CS ». La différence est voulue — un
    paramètre, pas deux fonctions qui divergeront.
    """
    if e.type == "etat":
        return (
            "Changement d'état : "
            f"{STATUT_LABELS.get(e.ancien_statut or '', e.ancien_statut or '?')} → "
            f"{STATUT_LABELS.get(e.nouveau_statut or '', e.nouveau_statut or '?')}"
        )
    if e.type == "relance":
        return e.contenu or "Relance syndic"
    if e.type == "commentaire":
        return f"Commentaire : {(e.contenu or '')[:100]}" if avec_extrait else "Commentaire CS"
    if e.type == "reponse":
        return "Réponse"
    if e.type == "synthese":  # la Suite porteuse d'une synthèse (#1643) — sans texte
        return "Synthèse de l'affaire"
    return e.type


# ── Sérialisation ────────────────────────────────────────────────────────────


def evol_read(
    e: TicketEvolution, session: Session, statut_avant: Optional[str] = None
) -> TicketEvolutionRead:
    auteur = ou_rien(session, Utilisateur, e.auteur_id)
    #  🔴 Lu sur le modèle depuis le 02/10/2026 (#1563). La recopie colonne par
    #  colonne avait oublié `assiste_ia` et `contenu_origine` : le fil d'une
    #  affaire n'a jamais montré la marque « rédigé avec l'assistant » ni le
    #  « Message d'origine » d'une réponse reçue par courriel. `fichiers_urls`
    #  se désérialise par son type (`ListeJson`).
    return lire_objet(
        TicketEvolutionRead,
        e,
        auteur_nom=nom_auteur(auteur, e.auteur_qualite),
        #  `None` — et non `[]` — quand l'entrée ne parle pas du périmètre : le
        #  front distingue « n'en parle pas » de « plus aucun périmètre » (#497).
        #
        #  🔒 NE PAS remplacer par `parse_json_perimetres` (#789, 06/09/2026) :
        #  elle retombe sur le défaut, ce qui ferait dire à chaque entrée
        #  d'historique qu'elle parle de toute la résidence. Quatre autres sites
        #  ont été ramenés à cette fonction ce jour-là ; celui-ci est resté, et
        #  c'est une décision, pas un oubli.
        perimetre_cible=json.loads(e.perimetre_cible) if e.perimetre_cible else None,
        statut_avant=statut_avant,
        #  Une ancienne correction (« Correction : Date de fin », écrite par le
        #  calendrier avant v2.23.0) le DIT, au lieu de laisser croire que le
        #  détail existe — `utils/corrections_texte.py`.
        contenu=expliciter_ancienne(e.contenu),
    )


def ticket_read(
    ticket: Ticket,
    session: Session,
    lecteur: Utilisateur | None = None,
    *,
    groupe: LectureGroupee | None = None,
) -> TicketRead:
    """`lecteur` : à qui l'on répond. Sans lui, aucune affaire liée n'est rendue
    — un lien ne doit rien révéler à qui on ne sait pas (#1342).

    `groupe` : ce qui se lit autour des affaires d'une LISTE, lu une fois pour
    toutes (`lecture_groupee`, #1838). Sans lui, l'affaire seule passe par le
    même chemin — une seule écriture de chaque lecture."""
    groupe = groupe or lecture_groupee(session, [ticket])
    auteur = ou_rien(session, Utilisateur, ticket.auteur_id)
    #  🔴 LE BÂTIMENT DU DEMANDEUR, ET RIEN D'AUTRE (#653, 30/08/2026).
    #
    #  Cette ligne était :
    #
    #      auteur_batiment_id = ticket.batiment_id or (auteur.batiment_id if auteur else None)
    #
    #  Le champ s'appelle `auteur_batiment_nom`, la carte le rend sous 📍 avec le
    #  commentaire « LE BÂTIMENT DU DEMANDEUR » — et le calcul prenait d'abord
    #  celui du TICKET. Dès qu'un ticket portait un `batiment_id`, le badge
    #  affichait le bâtiment visé sous une étiquette qui annonce celui de la
    #  personne : un membre du CS lisait « Paul DELMAS 📍 Bât. 4 » et en
    #  déduisait où habite Paul. Signalé à l'écran, sur une carte où « Bât. 4 »
    #  apparaissait deux fois — une fois comme périmètre, une fois comme ce badge.
    #
    #  ⚠️ AUCUN REPLI, et c'est le cœur du correctif. Quand l'auteur n'a pas de
    #  bâtiment renseigné, on n'affiche RIEN : retomber sur celui du ticket
    #  remettrait une valeur juste sous une étiquette fausse, ce qui est
    #  exactement le défaut qu'on retire. Le périmètre visé est déjà rendu à côté,
    #  par le badge 🔹 — le taire ici ne perd aucune information.
    #
    #  📖 `ticketScope()` (front) porte le repli, LUI, et l'annonce : « le bâtiment
    #  de l'auteur, à défaut le bâtiment ciblé, à défaut la résidence ». Il devient
    #  juste par ce correctif — il recevait jusqu'ici un premier terme qui pouvait
    #  déjà être le second.
    auteur_batiment_id = auteur.batiment_id if auteur else None
    batiment = session.get(Batiment, auteur_batiment_id) if auteur_batiment_id else None
    #  🔴 Les DEUX noms dérivés, en un seul calcul et une seule écriture de
    #  la règle (`utils/saisi_pour.noms_derives`, #1104). Ils étaient composés
    #  ici en ligne, et autrement dans l'actualité et l'événement — d'où un
    #  `proprietaire_nom` que seul le ticket exposait.
    proprietaire_nom, saisi_pour_affichage = noms_derives(session, ticket)
    #  🔴 PARTIR DU MODÈLE, puis ajouter ce qui se CALCULE (#1092, 23/09/2026).
    #
    #  Cette fonction recopiait les colonnes une par une : tout champ déclaré au
    #  schéma et oublié ici prenait sa valeur par défaut, sans un mot. Le
    #  commentaire qui suivait `confidentiel` le décrivait déjà (« un champ au
    #  schéma et jamais rempli prend sa valeur par défaut »), corrigé à la main
    #  pour ce champ-là — et le même défaut restait entier pour `debut`, `fin`
    #  (la section Quand ne se relisait pas), `suivi_kanban` (kanban vide),
    #  `epingle` et `assiste_ia`. Une liste recopiée se complète une ligne à la
    #  fois ; la lire sur le modèle ne s'oublie pas.
    #  🔒 `test_ticket_read_rend_le_modele.py` : chaque colonne partagée revient.
    #  `lire_objet` depuis #1563 : la même lecture, et les champs dérivés sont
    #  VALIDÉS — `model_copy(update=…)` les posait tels quels, sans contrôle.
    return lire_objet(
        TicketRead,
        ticket,
        auteur_nom=nom_auteur(auteur, ticket.auteur_qualite),
        auteur_batiment_nom=libelle_batiment_ou(batiment, None),
        #  Les pièces de l'affaire, sinon celles de la dernière entrée du fil qui
        #  en porte (#464) — `lecture_groupee.pieces_du_fil` dit pourquoi.
        apercu_pieces=pieces_du_ticket(ticket) or groupe.pieces_du_fil.get(ticket.id, []),
        affaires_liees=[
            AffaireLieeLue(**lue)
            for lue in liees_lisibles(
                session, ticket.id, lecteur, index=groupe.liens, tickets=groupe.tickets
            )
        ],
        fusionnee_dans=principale_lue(session, ticket, lecteur),
        fusionnee=ticket.fusionnee_dans_id is not None,
        saisi_pour_affichage=saisi_pour_affichage,
        proprietaire_nom=proprietaire_nom,
        #  L'adresse d'un tiers, au conseil seul (#2140) — la règle est là-bas.
        saisi_pour_email=adresse_lisible(ticket, lecteur),
        #  Le délai du site, lu une fois par liste et non une fois par affaire.
        archivee=est_archivable("ticket", ticket, seuil_jours=groupe.seuil_jours),
        relance_count=groupe.relances[ticket.id],
        synthese_validee=ticket.id in groupe.syntheses_validees,
        natures=natures(ticket),
        perime_le=perime_le(ticket, "ticket"),
        prestataire_nom=nom_prestataire(session, ticket.prestataire_id),
        contrat=contrat_de_l_affaire(session, ticket.contrat_id, lecteur),
        me_concerne=(
            concerne(lecteur, parse_json_perimetres(ticket.perimetre_cible)) if lecteur else None
        ),
    )


def contrat_de_l_affaire(
    session: Session, contrat_id: Optional[int], lecteur: Utilisateur | None
) -> Optional[ContratDeLAffaire]:
    """Le contrat qui cadre l'intervention (#1445) — lu même archivé, pour que
    l'histoire d'une affaire ne change pas quand le contrat s'arrête.

    Le rythme pour tous ; le libellé et le numéro pour le conseil seul, comme la
    liste des contrats.
    """
    c = session.get(ContratEntretien, contrat_id) if contrat_id else None
    if c is None:
        return None
    conseil = lecteur is not None and est_moderateur(lecteur)
    return ContratDeLAffaire(
        id=c.id,
        libelle=c.libelle if conseil else None,
        numero_contrat=c.numero_contrat if conseil else None,
        frequence_type=c.frequence_type,
        frequence_valeur=c.frequence_valeur,
    )


def nom_prestataire(session: Session, prestataire_id: Optional[int]) -> Optional[str]:
    """Le nom de l'intervenant, ou `None` — une ligne effacée ne casse pas la fiche."""
    p = session.get(Prestataire, prestataire_id) if prestataire_id else None
    return p.nom if p else None


def trier_par_activite(session: Session, tickets: list[Ticket]) -> list[Ticket]:
    """Les tickets, du plus RÉCEMMENT ACTIF au plus ancien.

    🔴 LE TRI SUIT L'ACTIVITÉ, PAS LA DATE DE DÉPÔT (05/09/2026), demandé à
    l'écran : *« s'il y a eu un commentaire sur un ticket, celui-ci remonte
    dans la liste — tri sur mise à jour, sauf édition pour une correction »*.

    Un dossier qui bouge doit se voir. Trié sur `cree_le`, un ticket ouvert il
    y a trois mois et commenté ce matin restait en bas, là où personne ne le
    relit.

    ⚠️ ET SURTOUT PAS SUR `mis_a_jour_le` : cette colonne bouge à CHAQUE
    écriture, y compris une correction de faute de frappe. Corriger un titre
    ferait remonter le ticket en tête sans qu'il se soit rien passé — c'est
    exactement ce que l'utilisateur exclut, et c'est la même distinction que
    l'archivage, qui se mesure sur `statut_change_le` et non sur
    `mis_a_jour_le` (`ux-patterns` §16).

    La date d'activité est donc celle de la dernière ENTRÉE du fil : un
    commentaire, un changement d'état, un message, une relance en créent une ;
    une correction pure n'en crée aucune (voir le `PATCH` de `crud.py`, qui
    n'écrit une entrée que si l'état a changé). Éditer une entrée existante ne
    touche pas son `cree_le` : le fil ne se réordonne pas quand on se relit.

    UNE seule requête groupée, pas une par ticket : la liste charge déjà tous
    les tickets, elle ne doit pas charger tous les fils.
    """
    derniere_activite = dict(
        session.exec(
            select(TicketEvolution.ticket_id, func.max(TicketEvolution.cree_le)).group_by(
                TicketEvolution.ticket_id
            )
        ).all()
    )
    #  📌 LES ÉPINGLÉS D'ABORD (05/09/2026) — c'est le sens même de l'option :
    #  « maintenue en tête ». Un booléen en première clé de tri, l'activité
    #  ensuite : entre deux tickets épinglés, le plus actif reste devant.
    return sorted(
        tickets,
        key=lambda t: (bool(t.epingle), derniere_activite.get(t.id) or t.cree_le),
        reverse=True,
    )


#  Les options d'un ticket vivent dans `options.py` depuis le 10/10/2026 : ce
#  module dépassait le plafond de modularité. Ré-exportées, leurs appelants
#  n'ont pas une ligne à changer.
from .options import (  # noqa: E402, F401  (ré-export volontaire)
    OPTIONS_RESERVEES_AU_CS,
    OPTIONS_TICKET,
    appliquer_options,
    options_du_ticket,
)
