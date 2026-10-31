"""La relève de la boîte des réponses — le TUYAU, et rien que le tuyau (#703).

## Ce fichier ne décide de rien

Il ouvre la boîte, lit les messages non traités, appelle
`courriel_ingestion.examiner`, et applique le verdict. La décision est ailleurs,
et c'est délibéré : elle s'y éprouve sur des messages écrits à la main, y compris
hostiles, sans réseau ni base.

## Ce qui se passe pour chaque message

    IGNORE   → marqué lu, rien d'autre. Un prospectus ne doit produire aucun bruit.
    REFUSE   → NOTIFICATION au conseil syndical, rien dans le ticket.
    ACCEPTE  → une entrée dans le fil du ticket, signée du compte de l'expéditeur.

🔴 **Un message accepté dont l'expéditeur n'a pas de compte est REFUSÉ.**
Écrire quand même aurait demandé un compte de service — qui signerait
« 5Hostachy » un texte écrit par un tiers. `TicketEvolution.auteur_id` est
facultatif depuis #1688, mais un auteur vide y veut dire « compte supprimé » et
s'affiche « Ancien résident » : y ranger un tiers mentirait sur qui a écrit. Le conseil syndical est prévenu, et recopie s'il le veut : c'est un
clic de plus, pas une donnée perdue.

## Le silence est ce qui rend un filtre dangereux

Chaque refus produit une notification nommant le ticket et **la raison**. Un
filtre qu'on n'entend jamais finit par être cru parfait, et il l'est d'autant
moins que personne ne le regarde.

## La configuration

Tout vit dans `ConfigSite`, administrable, et **rien n'est activé par défaut** :
`imap_enabled` à faux, la relève ne tourne pas. Les identifiants sont ceux de la
boîte d'envoi — c'est le même compte chez l'hébergeur —, mais le serveur IMAP est
distinct du SMTP et se déclare à part.
"""

from __future__ import annotations

import email
import imaplib
import logging
from datetime import datetime
from app.utils import horloge

from sqlalchemy import func
from sqlmodel import Session, select

from app.utils.liens import LIEN_COURRIELS_AFFAIRES, lien_ticket
from app.auth.deps import peut_commenter
from app.models.core import ConfigSite, Ticket, Utilisateur
from app.models.tickets import STATUTS_TICKET_CLOS
from app.utils.destinataires import est_adresse_syndic
from app.utils.courriel_authenticite import VerificationReportee, verifier_expediteur
from app.utils.courriel_decodage import _corps_lisible, _texte
from app.utils import courriel_pieces_jointes
from app.utils.courriel_journal import journaliser_releve
from app.utils.demo import exiger_hors_demo
from app.utils.courriel_transfert import compte_a_l_adresse, decider_transfert
from app.utils.courriel_relance import reponse_a_une_relance, relance_de
from app.utils.echecs_repetes import CompteurEchecs
from app.utils.courriel_ingestion import (
    ACCEPTE,
    IGNORE,
    REFUSE,
    RELANCE,
    examiner,
)
from app.utils.cloche import sonner_systeme
from app.utils.reponse_courriel import date_d_envoi, suite_de_reponse
from app.utils.services import SERVICE_REPONSES_COURRIEL, cle_actif, service_actif
from app.utils.valeurs import valeur
from app.utils.config_site import ecrire_cle

logger = logging.getLogger(__name__)

#: Combien de relèves ont échoué D'AFFILÉE (#858) — voir `utils/echecs_repetes`.
_ECHECS_RELEVE = CompteurEchecs("relève de la boîte des réponses")

#: Les clés lues dans `ConfigSite`. L'activation d'abord : sans elle, rien.
_CLES = {
    cle_actif(SERVICE_REPONSES_COURRIEL),
    "imap_server",
    "imap_port",
    "imap_username",
    "imap_password",
    "imap_dossier",
    "imap_plancher",
}


def config_imap(session: Session) -> dict:
    lignes = session.exec(select(ConfigSite).where(ConfigSite.cle.in_(_CLES))).all()
    return {r.cle: r.valeur for r in lignes}


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


def _prevenir_le_cs(session: Session, ticket: Ticket | None, verdict) -> None:
    """Une notification par membre du conseil syndical — jamais un silence."""
    #  🔴 `membres_cs_ou_admin` et non `membres_cs_avec_email` : c'est une
    #  notification IN-APP. L'autre vise la boîte aux lettres et exige une
    #  adresse — ici elle priverait d'alerte un membre du CS qui n'en a pas.
    from app.utils.destinataires import membres_cs_ou_admin

    ou = f"le ticket #{ticket.numero}" if ticket else "un ticket"
    for membre in membres_cs_ou_admin(session):
        sonner_systeme(
            session,
            "tache_du_conseil",
            destinataire_id=membre.id,
            type="ticket_update",
            titre=f"Réponse par courriel non prise en compte sur {ou}",
            corps=(
                f"Un message de « {verdict.expediteur} » est arrivé en réponse à {ou}, "
                f"mais il n'a pas été ajouté au fil : {verdict.motif}. "
                "Le message reste consultable dans la boîte de réception."
            ),
            lien=lien_ticket(ticket.id) if ticket else LIEN_COURRIELS_AFFAIRES,
        )


def traiter(
    session: Session,
    entetes: dict,
    corps: str,
    recu_le: datetime | None,
    plancher: datetime | None = None,
    authentification: tuple[bool, str] | None = None,
    pieces: courriel_pieces_jointes.Tri | None = None,
) -> str:
    """Applique le verdict d'UN message. Rend la décision prise, pour le journal.

    Séparée de la connexion IMAP pour être éprouvable : un test lui passe des
    en-têtes et vérifie ce qui est écrit en base, sans boîte aux lettres.

    🔴 Chaque verdict laisse sa ligne au journal des relèves (#1447), validée
    dans la MÊME transaction que lui : un IGNORE n'est plus muet, et un message
    acquitté a toujours la sienne.
    """
    decision, motif, ticket = _decider(
        session, entetes, corps, recu_le, plancher, authentification, pieces
    )
    journaliser_releve(session, entetes, recu_le, decision, motif, ticket)
    session.commit()
    return decision


def _refus(verdict, motif: str, *, jeton=None, numero=None):
    """Le verdict d'un refus décidé ICI, après l'examen — avec son propre motif."""
    return verdict.__class__(
        decision=REFUSE,
        jeton=jeton,
        reference=verdict.reference,
        numero=numero,
        expediteur=verdict.expediteur,
        motif=motif,
    )


def _decider(session, entetes, corps, recu_le, plancher, authentification, pieces=None):
    """`(décision, motif, affaire)` — écrit ce que le verdict demande, sans valider."""
    #  Un fil TRANSFÉRÉ (29/09/2026) : découpé et versé par `courriel_transfert`,
    #  qui rend None quand le message n'est pas pour lui.
    issue = decider_transfert(session, entetes, corps, recu_le, plancher, authentification)
    if issue is not None:
        decision, _motif, ticket = issue
        if decision == ACCEPTE and ticket is not None:
            #  Les pièces du transfert : une suite à elles, signée de qui a transféré.
            de = next((v for k, v in entetes.items() if k.lower() == "from"), "")
            qui = compte_a_l_adresse(session, de)
            suite = courriel_pieces_jointes.joindre(
                session, ticket, qui, None, pieces, expediteur=de, envoye_le=recu_le
            )
            if suite is not None:
                session.add(suite)
        return issue
    verdict = examiner(
        entetes, recu_le=recu_le, plancher=plancher, authentification=authentification
    )
    if verdict.decision == IGNORE:
        return IGNORE, verdict.motif, None

    ticket = _ticket_de(session, verdict)
    #  🔀 Une affaire absorbée (#1704) : la réponse rejoint le fil là où il vit.
    if ticket is not None and ticket.fusionnee_dans_id is not None:
        ticket = session.get(Ticket, ticket.fusionnee_dans_id) or ticket
    if ticket is None:
        #  Pas un ticket : peut-être une RELANCE GROUPÉE (#703). Un envoi qui
        #  porte N dossiers n'a pas de jeton de ticket, et n'en aura jamais.
        relance = relance_de(session, verdict)
        if relance is not None:
            if verdict.decision == REFUSE:
                _prevenir_le_cs(session, None, verdict)
                return REFUSE, verdict.motif, None
            reponse_a_une_relance(session, relance, verdict, corps)
            return RELANCE, "réponse à une relance groupée, transmise au conseil syndical", None

        #  Ni ticket ni relance. Deux situations très différentes :
        if verdict.decision == ACCEPTE and verdict.reference:
            #  🔴 Un message AUTHENTIFIÉ qui répond visiblement à un envoi du
            #  site, sans qu'on sache à quoi. Le taire, c'est perdre une réponse
            #  qu'on a sollicitée — le défaut même que le jeton de relance vient
            #  corriger, et il en resterait d'autres formes (un fil transféré,
            #  un client qui réécrit le destinataire).
            refus = _refus(
                verdict,
                "ce message répond à un envoi du site, mais rien ne permet de dire à quel ticket",
                jeton=verdict.jeton,
            )
            _prevenir_le_cs(session, None, refus)
            return REFUSE, refus.motif, None

        #  Jeton forgé, ou message sans rapport : rien à écrire, et personne de
        #  légitime à prévenir — prévenir ici ferait du bruit sur des tentatives.
        return IGNORE, "aucune affaire ni relance ne correspond à ce message", None

    #  Une affaire close ne reçoit plus rien, pas même une alerte (28/09/2026).
    if valeur(ticket.statut) in STATUTS_TICKET_CLOS:
        return IGNORE, f"l'affaire #{ticket.numero} est close : elle ne reçoit plus rien", ticket
    if verdict.decision == REFUSE:
        _prevenir_le_cs(session, ticket, verdict)
        return REFUSE, verdict.motif, ticket

    auteur = compte_a_l_adresse(session, verdict.expediteur)
    if auteur is None:
        #  Voir l'en-tête : pas de compte, pas d'écriture — mais on le DIT.
        refus = _refus(
            verdict,
            "cet expéditeur, pourtant authentifié, n'a pas de compte sur le site",
            jeton=verdict.jeton,
        )
        _prevenir_le_cs(session, ticket, refus)
        return REFUSE, refus.motif, ticket

    #  🔴 SEULS L'AUTEUR, LE CONSEIL ET LE SYNDIC ÉCRIVENT AU FIL — quel que soit
    #  le chemin. Le contrôle ne valait que pour le repli par le sujet (05/09/2026) :
    #  on tenait que le jeton prouvait que l'expéditeur avait reçu un message du
    #  site sur CE ticket. Il prouve qu'il a reçu l'ADRESSE — qu'un courriel
    #  transféré à un voisin transporte avec lui. Vérifié le 31/10/2026 : un tiers
    #  qui avait un compte et l'ancienne adresse à jeton écrivait au fil.
    if not correspondant_du_ticket(session, ticket, auteur):
        par = "son numéro dans le sujet" if verdict.jeton is None else "son adresse de réponse"
        refus = _refus(
            verdict,
            f"ce message désigne un ticket par {par}, mais son expéditeur "
            "n'est ni l'auteur du ticket, ni le conseil syndical, ni le syndic",
            jeton=verdict.jeton,
            numero=verdict.numero,
        )
        _prevenir_le_cs(session, ticket, refus)
        return REFUSE, refus.motif, ticket

    #  Texte nettoyé, mis en forme par l'assistant si l'usage est prêt, et daté
    #  de l'envoi — `utils/reponse_courriel` (#1322).
    suite = suite_de_reponse(session, ticket, auteur, verdict.expediteur, corps, recu_le)
    #  Les pièces jointes (31/10/2026) : une réponse sans mot qui porte un devis
    #  entre au fil quand même.
    suite = courriel_pieces_jointes.joindre(
        session, ticket, auteur, suite, pieces, expediteur=verdict.expediteur, envoye_le=recu_le
    )
    if suite is None:
        return IGNORE, _RIEN_A_AJOUTER, ticket
    session.add(suite)
    if suite.nouveau_statut:  # le syndic a répondu : l'affaire est chez lui
        ticket.statut = suite.nouveau_statut
    ticket.mis_a_jour_le = horloge.maintenant()
    session.add(ticket)
    return ACCEPTE, f"ajouté au fil de l'affaire — {verdict.motif}", ticket


#: `suite_de_reponse` rend None dans deux cas, qu'elle ne distingue pas.
_RIEN_A_AJOUTER = (
    "rien à ajouter au fil : le message est vide une fois la citation retirée, ou "
    "l'assistant n'y a rien trouvé d'utile (message du conseil)"
)


def plancher_de_releve(session: Session, cfg: dict) -> datetime:
    """La date avant laquelle un message relevé est ignoré.

    🔴 Son défaut était une date écrite dans le code, le 02/09/2026 — celle de la
    mise en service de 5Hostachy (#2060). Pour toute autre copropriété, la première
    relève aurait rejoué des mois d'archives dans ses affaires. Absente, la relève
    commence **aujourd'hui**, et la date est posée en base : l'écran la montre, et
    elle ne bouge plus d'une relève à l'autre. (La migration 0297 a posé l'ancienne
    date chez les installations qui relevaient déjà.)
    """
    valeur_lue = cfg.get("imap_plancher") or ""
    if valeur_lue:
        try:
            return datetime.fromisoformat(valeur_lue)
        except ValueError:
            logger.warning("imap_plancher illisible (%s) — reposé à aujourd'hui", valeur_lue)
    jour = horloge.aujourd_hui().isoformat()
    ecrire_cle(session, "imap_plancher", jour)
    session.commit()
    return datetime.fromisoformat(jour)


def relever() -> dict[str, int]:
    """Relève la boîte et traite ce qui s'y trouve. Rend le compte par décision.

    ⚠️ N'échoue jamais bruyamment : elle tourne sous le planificateur, et une
    exception y tuerait le job pour de bon. Elle journalise, et rend un compte
    que le journal montre — un tuyau muet est un tuyau qu'on croit vivant.
    """
    from app import contexte

    comptes = {ACCEPTE: 0, RELANCE: 0, REFUSE: 0, IGNORE: 0}
    #: Vrai si la relève n'a PAS pu avoir lieu — à distinguer d'une boîte vide.
    echec = False
    derniere_erreur: Exception | None = None
    session = contexte.nouvelle_session()
    try:
        cfg = config_imap(session)
        if not service_actif(cfg, SERVICE_REPONSES_COURRIEL):
            #  🔴 UNE TRACE MÊME QUAND ON NE FAIT RIEN (04/09/2026) : sans elle,
            #  « désactivée » et « boîte vide » rendaient le même silence — le
            #  CONTRAT DE BATTEMENT d'`auto-deploy.sh` (C14). En `info` et non en
            #  `debug` (05/09) : la production n'émet pas `debug`, et un battement
            #  qu'on ne peut pas entendre n'est pas un battement.
            logger.info("Réponses par courriel : relève DÉSACTIVÉE (imap_enabled≠1)")
            return comptes

        plancher = plancher_de_releve(session, cfg)

        exiger_hors_demo("Relève des courriels")  # (#1902)
        boite = imaplib.IMAP4_SSL(cfg.get("imap_server", ""), int(cfg.get("imap_port") or 993))
        try:
            boite.login(cfg.get("imap_username", ""), cfg.get("imap_password", ""))
            boite.select(cfg.get("imap_dossier") or "INBOX")
            _statut, donnees = boite.search(None, "UNSEEN")
            for numero in donnees[0].split() if donnees and donnees[0] else []:
                #  🔴 `BODY.PEEK[]` ET NON `RFC822` (05/09/2026). En IMAP, lire un
                #  message avec `RFC822` pose `\Seen` **au moment de la lecture** :
                #  le message était donc acquitté avant qu'on ait décidé quoi que ce
                #  soit. Si le traitement échouait ensuite — exception, base
                #  indisponible — la réponse du syndic était perdue pour de bon, et
                #  la relève suivante ne la voyait plus.
                #
                #  C'est la classe de défaut du triple envoi WhatsApp, à l'envers :
                #  on acquittait le TRANSPORT au lieu du FAIT. `PEEK` lit sans
                #  marquer ; le marquage vient après, et seulement si le traitement
                #  a abouti.
                _st, brut = boite.fetch(numero, "(BODY.PEEK[])")
                if not brut or not brut[0]:
                    continue
                message = email.message_from_bytes(brut[0][1])
                entetes = {cle: _texte(val) for cle, val in message.items()}
                recu_le = date_d_envoi(message.get("Date"))  # UTC, fuseau converti (#1322)
                try:
                    #  DKIM vérifié ICI, sur les octets reçus (28/09/2026) — jamais lu
                    #  dans un en-tête que l'expéditeur aurait pu écrire.
                    auth = verifier_expediteur(brut[0][1], entetes.get("From", ""))
                    decision = traiter(
                        session,
                        entetes,
                        _corps_lisible(message),
                        recu_le,
                        plancher,
                        auth,
                        pieces=courriel_pieces_jointes.trier(message),
                    )
                except VerificationReportee as exc:
                    #  INCONNU, pas un refus : le message reste non lu, repris ensuite.
                    logger.warning("Réponse par courriel : vérification reportée (%s)", exc)
                    continue
                except Exception as exc:
                    #  Le message reste NON LU : il sera repris dans dix minutes. Et
                    #  l'échec est journalisé en ERROR, donc visible du point 6 du
                    #  pré-check et de l'alerte quotidienne — un message qui
                    #  échouerait indéfiniment se signale au lieu de tourner en
                    #  silence. Une erreur qui se répète est un appel, pas du bruit.
                    logger.error(
                        "Réponse par courriel non traitée (laissée non lue) — de %s, objet %r : %s",
                        entetes.get("From", "?"),
                        entetes.get("Subject", "?"),
                        exc,
                    )
                    session.rollback()
                    continue
                comptes[decision] += 1
                #  L'acquittement vient APRÈS le fait, et lui seul.
                boite.store(numero, "+FLAGS", "\\Seen")
        finally:
            try:
                boite.logout()
            except Exception:
                pass
    except Exception as exc:  # noqa: BLE001  (le tuyau, pas la décision)
        derniere_erreur = exc
        #  🔴 CE PASSAGE N'A RIEN CONSTATÉ, et il ne doit pas dire le contraire.
        #  Sans ce drapeau, la ligne de fin annonçait « relève effectuée, aucun
        #  message non lu » APRÈS l'échec — un commentaire affirmait même qu'elle
        #  « prouve que la relève est vivante », alors qu'elle s'imprimait sur le
        #  passage exact où la relève était morte. Une boîte injoignable et une
        #  boîte vide rendaient le même journal, et une réponse de résident perdue
        #  pendant une panne se lisait comme une absence de réponse.
        echec = True
    finally:
        session.close()

    #  Le succès REMET LE DÉCOMPTE À ZÉRO : sans lui, trois secousses en trois
    #  semaines finiraient par crier.
    if not echec:
        _ECHECS_RELEVE.succes()

    #  Un passage sans message est un fait, pas un non-événement : c'est ce qui
    #  prouve que la relève est vivante et que la boîte est simplement vide.
    if echec:
        #  🔴 WARNING d'abord, ERROR au bout de trois échecs D'AFFILÉE — le motif
        #  et l'incident du 09/09/2026 sont dans `utils/echecs_repetes` (#858).
        #  Rien à AFFIRMER pour autant : aucune ligne rassurante ne recouvre
        #  l'échec.
        _ECHECS_RELEVE.echec(logger, "Relève de la boîte des réponses : %s", derniere_erreur)
    elif any(comptes.values()):
        logger.info(
            "Réponses par courriel — écrites=%d relances=%d refusées=%d ignorées=%d",
            comptes[ACCEPTE],
            comptes[RELANCE],
            comptes[REFUSE],
            comptes[IGNORE],
        )
    else:
        #  Même raison : c'est CE passage-là qui prouve que la relève est vivante
        #  et que la boîte est simplement vide. Une ligne toutes les dix minutes
        #  dans un journal qui en compte des milliers par heure est un prix
        #  dérisoire devant une fonction qu'on croit morte.
        logger.info("Réponses par courriel : relève effectuée, aucun message non lu")
    return comptes
