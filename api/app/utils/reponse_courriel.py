"""Ce que devient le TEXTE d'une réponse reçue par courriel sur une affaire (#1322).

La relève (`courriel_boite`) décide si un message rejoint un fil ; ce module dit
**ce qui y entre** : le texte, sa date, et ce que l'assistant en a fait.

## Demandé le 25/09/2026

> « que le mail soit bien formaté, daté, […] avec les lignes inutiles du message
>   d'origine retirées, les lignes blanches etc… juste la réponse utile »

Arbitré : la mise en forme est **automatique** à la relève, le **texte reçu est
conservé** (« Message d'origine » dans la Suite), et la Suite est **datée de
l'envoi** du courriel.

## Ce qui ne se perd jamais

`_sans_citation` retire d'abord, sans IA, le message cité. L'assistant ne voit
que ce reste — ce qu'il faut pour le mettre en forme, et rien de plus : le fil
cité porte souvent les données d'autres personnes. Si l'usage est coupé, non
réglé, en échec, ou s'il rend quelque chose de suspect (vide, plus long que ce
qu'on lui a donné, ou un mot qui n'y était pas : il n'a rien à ajouter), le texte
nettoyé sans IA entre dans le fil. **Une réponse du syndic n'est jamais perdue à
cause de l'assistant.**

Le courriel est un contenu NON FIABLE : il n'atteint le modèle que cadré, par
`ia_courriel.lire_un_courriel`, et sa sortie se juge par `sortie_conforme` (#2369).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime
from typing import TYPE_CHECKING

from sqlmodel import Session

from app.utils import horloge

if TYPE_CHECKING:  # pragma: no cover - `ia_courriel` importe ce module
    from app.utils.ia_courriel import Conformite

logger = logging.getLogger(__name__)

USAGE_REPONSE_COURRIEL = "reponse_courriel"

#: Le prompt d'origine de l'usage — modifiable depuis l'administration.
CONSIGNE = (
    "Tu reçois le texte d'une réponse envoyée par courriel sur une affaire de "
    "copropriété, le plus souvent par le syndic. Rends UNIQUEMENT la réponse utile, "
    "mise en forme :\n"
    "- retire la signature, les coordonnées, les mentions légales ou de "
    "confidentialité, les formules automatiques et tout reste du message cité ;\n"
    "- retire les lignes vides superflues ; garde les paragraphes et les listes de "
    "l'auteur ;\n"
    "- ne résume pas, ne reformule pas, n'ajoute rien : les mots sont ceux de "
    "l'auteur, seule la présentation change ;\n"
    "- rends du texte simple, sans balises ni Markdown, sans introduction ni "
    "commentaire.\n"
    "Si rien d'utile ne reste, rends une réponse vide."
)

#: Le texte reçu conservé, borné : un fil transféré peut peser des centaines de
#: kilo-octets, et ce n'est pas la base qui doit en porter l'historique entier.
MAX_ORIGINE = 20_000

#: Une date d'envoi plus loin dans le futur est une horloge fausse chez
#: l'expéditeur : on date alors de la relève.
TOLERANCE_FUTUR = timedelta(minutes=5)


def date_d_envoi(entete: str | None) -> datetime | None:
    """L'en-tête `Date` en UTC NAÏF — la forme des dates en base — ou None.

    🔴 La relève faisait `parsedate_to_datetime(...).replace(tzinfo=None)` : elle
    JETAIT le fuseau sans convertir. « 18:00 +0200 » devenait 18:00 UTC, deux
    heures trop tard — et le plancher de la relève se comparait à cette date
    fausse. Un en-tête sans fuseau est pris pour de l'UTC (RFC 5322 : `-0000`).
    """
    try:
        d = parsedate_to_datetime(entete or "")
    except (TypeError, ValueError, IndexError):
        return None
    if d is None:
        return None
    if d.tzinfo is not None:
        d = d.astimezone(timezone.utc).replace(tzinfo=None)
    return d


def moment_de_la_suite(envoye_le: datetime | None, maintenant: datetime | None = None) -> datetime:
    """La date de la Suite : celle de l'envoi, sauf si elle est absente ou future."""
    maintenant = maintenant or horloge.maintenant()
    if envoye_le is None or envoye_le > maintenant + TOLERANCE_FUTUR:
        return maintenant
    return envoye_le


@dataclass(frozen=True)
class Texte:
    """Ce qui entre dans le fil."""

    contenu: str
    #: Le texte reçu, quand l'assistant l'a mis en forme ; None sinon.
    origine: str | None
    assiste: bool
    #: L'assistant a jugé qu'il ne restait RIEN d'utile. Le texte nettoyé entre
    #: quand même par défaut — sauf pour qui peut être écarté (`suite_de_reponse`).
    vide_selon_assistant: bool = False


def mettre_en_forme(session: Session, nettoye: str, recu: str) -> Texte:
    """La réponse utile, mise en forme par l'assistant si l'usage est prêt.

    `nettoye` : le texte sans citation (`_sans_citation`), seul envoyé au modèle.
    `recu` : le texte lisible du courriel, conservé quand l'assistant a travaillé.

    ⚠️ Synchrone : la relève tourne sous `BackgroundScheduler`, sans boucle
    d'événements — `asyncio.run` y est sûr (`health_monitor` fait de même).
    """
    repli = Texte(contenu=nettoye, origine=None, assiste=False)
    if not nettoye:
        return repli
    from app.utils.llm import ErreurLLM

    try:
        lecture = lire_et_juger(session, nettoye)
    except ErreurLLM as exc:
        #  Usage coupé ou non réglé : le cas nominal tant que l'administration ne
        #  l'a pas activé. Une ligne d'information, pas une alerte.
        logger.info("Réponse par courriel : mise en forme non appliquée (%s)", exc)
        return repli
    except Exception as exc:  # noqa: BLE001 — la relève ne doit jamais perdre la réponse
        logger.warning("Réponse par courriel : mise en forme en échec (%s)", type(exc).__name__)
        return repli
    if lecture.conformite is not None and not lecture.conformite.conforme:
        #  Il a écrit autre chose qu'une mise en forme : plus long, un mot qui
        #  n'est pas dans le courriel, une marque du cadre (#2369). Le motif part
        #  au journal ; le texte du courriel, jamais.
        logger.warning(
            "Réponse par courriel : mise en forme écartée (%s)", lecture.conformite.motif
        )
    return texte_retenu(lecture, nettoye, recu)


@dataclass(frozen=True)
class Lecture:
    """Ce que l'assistant a rendu d'un courriel, et le jugement du contrat."""

    #: Sa sortie, sans blancs autour — vide : « rien d'utile » selon lui.
    brut: str
    #: `ia_courriel.sortie_conforme` sur `brut` ; None quand il est vide.
    conformite: Conformite | None


def lire_et_juger(session: Session, nettoye: str) -> Lecture:
    """Fait lire `nettoye` par la porte du courriel (#2369), et juge la sortie.

    Partagée par la relève (`mettre_en_forme`) et par le canari nocturne
    (`utils/canari_ia`) : le canari éprouve ainsi le chemin même de la relève, pas
    une copie. Lève ce que lève l'appel au modèle (`ErreurLLM` d'abord).
    """
    from app.utils.ia_courriel import lire_un_courriel, sortie_conforme

    #  Le courriel est un contenu NON FIABLE : il passe par la porte qui le
    #  cadre dans l'invite, jamais par `demander` directement.
    reponse = asyncio.run(lire_un_courriel(session, usage=USAGE_REPONSE_COURRIEL, texte=nettoye))
    brut = (reponse.texte or "").strip()
    return Lecture(brut=brut, conformite=sortie_conforme(nettoye, brut) if brut else None)


def texte_retenu(lecture: Lecture, nettoye: str, recu: str) -> Texte:
    """Ce qui entre dans le fil après une lecture : la sortie si elle est conforme,
    le texte nettoyé sans IA sinon."""
    if not lecture.brut:
        return Texte(contenu=nettoye, origine=None, assiste=False, vide_selon_assistant=True)
    if lecture.conformite is None or not lecture.conformite.conforme:
        return Texte(contenu=nettoye, origine=None, assiste=False)
    return Texte(contenu=lecture.brut, origine=(recu or nettoye)[:MAX_ORIGINE], assiste=True)


def contenu_de_la_suite(
    expediteur: str,
    nom_du_compte: str,
    envoye_le: datetime,
    texte: str,
    transfere_par: str | None = None,
) -> str:
    """Le HTML de la Suite : « Mail reçu de … le … » en italique, puis le texte.

    Libellé demandé le 28/09/2026 (« Réponse de » jusque-là). Un message du syndic
    TRANSFÉRÉ par un membre du conseil nomme le syndic, puis qui l'a transféré.

    La ligne d'en-tête est écrite par le CODE, jamais par le modèle (arbitré le
    25/09/2026) : un nom et une date lus dans l'en-tête ne s'inventent pas. Le nom
    est celui que le courriel affiche (« Jean Martin <jm@…> »), à défaut celui du
    compte ; la date, l'envoi en heure de Paris.

    🔴 Le texte est ÉCHAPPÉ : c'est un courriel reçu, et `safeDescription` ne
    ré-échappe pas une chaîne qui commence par une balise.
    """
    from html import escape

    from app.utils.dates_fr import datetime_longue_paris

    nom = parseaddr(expediteur or "")[0].strip() or nom_du_compte
    par = f", transféré par {escape(transfere_par, quote=False)}" if transfere_par else ""
    entete = (
        f"<p><em>Mail reçu de {escape(nom, quote=False)} le "
        f"{datetime_longue_paris(envoye_le)}{par}</em></p>"
    )
    paragraphes = [p.strip() for p in re.split(r"\n\s*\n", texte) if p.strip()]
    corps = "".join(
        "<p>" + "<br>".join(escape(ligne.strip(), quote=False) for ligne in p.splitlines()) + "</p>"
        for p in paragraphes
    )
    return entete + corps


def suite_de_reponse(session: Session, ticket, auteur, expediteur: str, corps: str, envoye_le):
    """La Suite d'une réponse DIRECTE, ou None si elle n'a rien à apporter au fil.

    Le message d'un fil TRANSFÉRÉ ne passe plus par ici depuis le 29/09/2026 :
    `courriel_transfert` le découpe et appelle `suite_d_un_message` pour chacun.
    """
    from app.auth.deps import est_moderateur
    from app.utils.courriel_decodage import _sans_citation
    from app.utils.noms import nom_affiche

    return suite_d_un_message(
        session,
        ticket,
        auteur,
        expediteur=expediteur,
        nom=nom_affiche(auteur.prenom, auteur.nom),
        texte=_sans_citation(corps),
        recu=corps,
        envoye_le=envoye_le,
        ecartable=est_moderateur(auteur),
    )


def suite_d_un_message(
    session: Session,
    ticket,
    signataire,
    *,
    expediteur: str,
    nom: str,
    texte: str,
    recu: str,
    envoye_le,
    transfere_par: str | None = None,
    ecartable: bool = False,
):
    """La Suite d'UN message — réponse directe ou message d'un fil transféré —,
    ou None s'il n'a rien à apporter au fil.

    `signataire` est le compte qui signe la Suite (qui a répondu, ou qui a
    transféré) ; `expediteur` et `nom` disent qui a ÉCRIT le message, et c'est
    lui que la ligne d'en-tête nomme. `texte` est déjà sans citation.

    Deux règles demandées le 28/09/2026 :

    - **le syndic fait avancer le dossier** : un message du syndic — reconnu à
      son adresse dans la fiche du cabinet — fait passer une affaire encore
      « Ouvert » à « Chez le syndic » (`en_cours`). La Suite est alors une entrée
      d'ÉTAT, comme au formulaire ;
    - **un simple merci du conseil n'entre pas** (`ecartable`) : quand
      l'assistant ne trouve rien d'utile dans le message d'un membre du conseil,
      rien n'est écrit. Un message du syndic ou d'un résident entre toujours —
      l'assistant n'a pas à décider qu'une réponse sollicitée ne comptait pas.
    """
    return suite_mise_en_forme(
        session,
        ticket,
        signataire,
        mettre_en_forme(session, texte, recu),
        expediteur=expediteur,
        nom=nom,
        envoye_le=envoye_le,
        transfere_par=transfere_par,
        ecartable=ecartable,
    )


def suite_mise_en_forme(
    session: Session,
    ticket,
    signataire,
    mis: Texte,
    *,
    expediteur: str,
    nom: str,
    envoye_le,
    transfere_par: str | None = None,
    ecartable: bool = False,
):
    """`suite_d_un_message`, le texte déjà mis en forme — sans appel à l'assistant.

    🔴 Séparée le 30/09/2026 (#1469) : un fil transféré met en forme TOUS ses
    messages avant la première écriture. L'appel à l'assistant écrit son journal
    dans sa propre transaction (`llm_journal.journaliser`), et une écriture en
    cours dans celle de la relève le verrouillait : « database is locked », et la
    consommation n'était pas comptée.
    """
    from app.models.core import TicketEvolution
    from app.models.tickets import StatutTicket
    from app.utils.destinataires import est_adresse_syndic
    from app.utils.nature_affaire import est_actualite
    from app.utils.valeurs import valeur

    syndic = est_adresse_syndic(session, parseaddr(expediteur or "")[1])
    if not mis.contenu:
        return None
    if mis.vide_selon_assistant and ecartable and not syndic:
        return None
    quand = moment_de_la_suite(envoye_le)
    contenu = contenu_de_la_suite(expediteur, nom, quand, mis.contenu, transfere_par)
    etat = valeur(ticket.statut)
    avance = syndic and etat == StatutTicket.ouvert.value and not est_actualite(ticket)
    return TicketEvolution(
        ticket_id=ticket.id,
        type="etat" if avance else "commentaire",
        ancien_statut=etat if avance else None,
        nouveau_statut=StatutTicket.en_cours.value if avance else None,
        contenu=contenu,
        contenu_origine=mis.origine,
        assiste_ia=mis.assiste,
        auteur_id=signataire.id,
        cree_le=quand,
    )
