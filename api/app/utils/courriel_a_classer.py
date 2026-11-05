"""Un courriel qu'aucune affaire ne désigne attend d'être CLASSÉ par le conseil (#2555).

## Le besoin (05/11/2026)

> « si ticket non raccroché, proposer de créer une nouvelle affaire ou de la
>   raccrocher à une affaire »

Un message authentifié d'un correspondant connu — « Re: Portillon Hostachy » d'un
membre du conseil, alors que l'affaire du portillon est ouverte — était refusé :
« rien ne permet de dire à quel ticket ». Le journal ne garde pas le corps : le
message était perdu pour le site.

## Ce qui attend ici

Un message **authentifié** (DKIM, `courriel_authenticite`) dont l'expéditeur est
**connu** — un compte actif, ou un membre de la fiche du syndic — et qui ne
désigne ni affaire ni relance. Un inconnu reste refusé ou ignoré : la file n'est
pas une boîte de réception, et un prospectus n'y entre pas.

## Les trois gestes — Espace CS › Courriels

- **Rattacher** à une affaire ouverte : le message entre au fil comme un
  transfert (« Mail reçu de X …, transféré par Y »), pièces jointes comprises ;
- **Créer une affaire** : celle d'un transfert — Étude & travaux, conseil seul,
  au nom de l'expéditeur (`courriel_affaire_du_fil`) ;
- **Écarter** : rien n'est écrit.

🔴 **Jamais de rattachement automatique** : les `suggestions` (mots de l'objet en
commun avec le titre d'une affaire ouverte, affaires de l'expéditeur) se
proposent, elles ne décident pas — la règle de `courriel_numero`, qui DIT un
numéro voisin sans rattacher de lui-même.

Le message entier (`brut`) s'efface au classement ; la ligne, à 90 jours.
"""

from __future__ import annotations

import email
import re
from email.utils import parseaddr

from sqlmodel import Session, select

from app.models.core import Ticket, Utilisateur
from app.models.courriel import CourrielAClasser, CourrielReleve
from app.models.tickets import STATUTS_TICKET_CLOS
from app.utils import horloge
from app.utils.courriel_affaire_du_fil import compte_a_l_adresse, creer_affaire_du_fil
from app.utils.courriel_decodage import _corps_lisible, _sans_citation
from app.utils.courriel_fil import _sans_accent, titre_du_fil
from app.utils.config_site import config_site
from app.utils.destinataires import membre_syndic_a_l_adresse
from app.utils.liens import nom_site
from app.utils.noms import nom_affiche
from app.utils.valeurs import valeur

A_CLASSER = "a_classer"
RATTACHE = "rattache"
CREE = "cree"
ECARTE = "ecarte"
STATUTS = (A_CLASSER, RATTACHE, CREE, ECARTE)

#: Le motif du journal — écrit pour le conseil, qui le lit dans l'onglet.
MOTIF = "aucune affaire n'est désignée : le message attend d'être classé ci-dessous"

#: Combien d'affaires se proposent, au plus.
SUGGESTIONS_MAX = 3

#: Les mots qui ne disent rien d'un sujet : ils ne rapprochent pas deux titres.
_MOTS_VIDES = frozenset(
    "les des une pour par sur dans avec sans aux est sont pas que qui son ses leur "
    "vos votre nos notre affaire courriel message residence".split()
)


def correspondant_connu(session: Session, expediteur: str) -> bool:
    """Un compte actif à cette adresse, ou un membre de la fiche du syndic."""
    adresse = parseaddr(expediteur or "")[1]
    return (
        compte_a_l_adresse(session, adresse) is not None
        or membre_syndic_a_l_adresse(session, adresse) is not None
    )


def retenir(
    session: Session, releve: CourrielReleve, entetes: dict, brut: bytes | None, envoye_le
) -> CourrielAClasser:
    """Met le message en attente, à côté de sa ligne du journal (même transaction)."""
    lire = {k.lower(): v for k, v in entetes.items()}
    session.flush()  # l'identifiant de la ligne du journal
    item = CourrielAClasser(
        releve_id=releve.id,
        envoye_le=envoye_le,
        expediteur=(lire.get("from") or "")[:300],
        objet=(lire.get("subject") or "")[:300],
        brut=brut,
    )
    session.add(item)
    return item


def en_attente(session: Session, releve_ids: list[int]) -> dict[int, CourrielAClasser]:
    """Les messages à classer de ces lignes du journal, par ligne."""
    if not releve_ids:
        return {}
    lignes = session.exec(
        select(CourrielAClasser).where(CourrielAClasser.releve_id.in_(releve_ids))
    ).all()
    return {item.releve_id: item for item in lignes}


def _mots(texte: str) -> set[str]:
    propre = re.sub(r"[^0-9a-z]+", " ", _sans_accent(texte or "").lower())
    return {m for m in propre.split() if len(m) >= 3 and m not in _MOTS_VIDES}


def suggestions(session: Session, item: CourrielAClasser) -> list[Ticket]:
    """Les affaires OUVERTES les plus proches : mots de l'objet en commun avec leur
    titre, puis celles de l'expéditeur. Jamais une décision — une proposition."""
    #  Le nom de la résidence est dans la moitié des titres : il ne rapproche rien.
    mots = _mots(titre_du_fil(item.objet)) - _mots(nom_site(config_site(session).get("site_nom")))
    auteur = compte_a_l_adresse(session, item.expediteur)
    ouvertes = session.exec(
        select(Ticket).where(
            Ticket.fusionnee_dans_id.is_(None),
            Ticket.statut.not_in(list(STATUTS_TICKET_CLOS)),
        )
    ).all()
    notes = []
    for t in ouvertes:
        score = 2 * len(mots & _mots(t.titre))
        if auteur is not None and auteur.id in (t.auteur_id, t.saisi_pour_user_id):
            score += 1
        if score:
            notes.append((score, t.mis_a_jour_le or t.cree_le, t))
    notes.sort(key=lambda n: (n[0], n[1]), reverse=True)
    return [t for _s, _d, t in notes[:SUGGESTIONS_MAX]]


def apercu(item: CourrielAClasser, longueur: int = 400) -> str:
    """Le début du texte, sans citation — de quoi décider sans ouvrir la boîte."""
    if not item.brut:
        return ""
    texte = _sans_citation(_corps_lisible(email.message_from_bytes(item.brut)))
    texte = re.sub(r"\s+", " ", texte).strip()
    return texte if len(texte) <= longueur else texte[:longueur].rstrip() + "…"


class NonClassable(Exception):
    """Le geste ne peut pas avoir lieu — le motif est écrit pour l'écran."""


def _exiger_a_classer(item: CourrielAClasser) -> None:
    if item.statut != A_CLASSER:
        raise NonClassable("ce message a déjà été classé")
    if not item.brut:
        raise NonClassable("le message n'est plus disponible : il reste dans la boîte de réception")


def _nom(session: Session, item: CourrielAClasser) -> tuple[str, str]:
    """(nom affiché, adresse) de l'expéditeur : celui du courriel, sinon du compte."""
    nom, adresse = parseaddr(item.expediteur or "")
    if not nom:
        qui = compte_a_l_adresse(session, adresse) or membre_syndic_a_l_adresse(session, adresse)
        nom = nom_affiche(qui.prenom, qui.nom) if qui else adresse
    return nom, adresse


def _classer(session, item: CourrielAClasser, statut: str, qui: Utilisateur, ticket, motif):
    """Le message est classé : son contenu s'efface, sa ligne du journal le dit."""
    item.statut = statut
    item.classe_le = horloge.maintenant()
    item.classe_par_id = qui.id
    item.ticket_id = ticket.id if ticket else None
    item.brut = None
    session.add(item)
    releve = session.get(CourrielReleve, item.releve_id)
    if releve is not None:
        releve.motif = motif
        if ticket is not None:
            releve.ticket_id, releve.affaire = ticket.id, ticket.numero
        session.add(releve)


def rattacher(session: Session, item: CourrielAClasser, ticket: Ticket, qui: Utilisateur) -> str:
    """Verse le message au fil de `ticket`, comme un transfert de `qui`. Rend le bilan."""
    from app.utils import courriel_pieces_jointes as pj
    from app.utils.reponse_courriel import suite_d_un_message

    _exiger_a_classer(item)
    if valeur(ticket.statut) in STATUTS_TICKET_CLOS:
        raise NonClassable(f"l'affaire #{ticket.numero} est close")
    message = email.message_from_bytes(item.brut)
    corps = _corps_lisible(message)
    nom, _adresse = _nom(session, item)
    classe_par = nom_affiche(qui.prenom, qui.nom)
    suite = suite_d_un_message(
        session,
        ticket,
        qui,
        expediteur=item.expediteur,
        nom=nom,
        texte=_sans_citation(corps),
        recu=corps,
        envoye_le=item.envoye_le,
        transfere_par=classe_par,
    )
    suite = pj.joindre(
        session,
        ticket,
        qui,
        suite,
        pj.trier(message),
        expediteur=item.expediteur,
        envoye_le=item.envoye_le,
    )
    if suite is not None:
        session.add(suite)
        if suite.nouveau_statut:
            ticket.statut = suite.nouveau_statut
    ticket.mis_a_jour_le = horloge.maintenant()
    session.add(ticket)
    bilan = f"rattaché à l'affaire #{ticket.numero} par {classe_par}"
    _classer(session, item, RATTACHE, qui, ticket, bilan)
    return bilan


def creer(session: Session, item: CourrielAClasser, qui: Utilisateur) -> Ticket:
    """Une affaire neuve, décrite par le message — celle d'un transfert."""
    from app.utils import courriel_pieces_jointes as pj
    from app.utils.reponse_courriel import (
        contenu_de_la_suite,
        mettre_en_forme,
        moment_de_la_suite,
    )

    _exiger_a_classer(item)
    message = email.message_from_bytes(item.brut)
    corps = _corps_lisible(message)
    texte = _sans_citation(corps)
    mis = mettre_en_forme(session, texte, corps)
    nom, adresse = _nom(session, item)
    classe_par = nom_affiche(qui.prenom, qui.nom)
    quand = moment_de_la_suite(item.envoye_le)
    ticket = creer_affaire_du_fil(
        session,
        qui,
        nom=nom,
        adresse=adresse,
        description=contenu_de_la_suite(
            item.expediteur, nom, quand, mis.contenu or texte, classe_par
        ),
        quand=quand,
        assiste=mis.assiste,
        titre=titre_du_fil(item.objet) or f"Courriel de {nom}",
    )
    pieces = pj.joindre(
        session,
        ticket,
        qui,
        None,
        pj.trier(message),
        expediteur=item.expediteur,
        envoye_le=item.envoye_le,
    )
    if pieces is not None:
        session.add(pieces)
    _classer(session, item, CREE, qui, ticket, f"affaire #{ticket.numero} créée par {classe_par}")
    return ticket


def ecarter(session: Session, item: CourrielAClasser, qui: Utilisateur) -> None:
    """Rien n'est écrit — le conseil a jugé que le message n'appelait pas de suite."""
    _exiger_a_classer(item)
    _classer(session, item, ECARTE, qui, None, f"écarté par {nom_affiche(qui.prenom, qui.nom)}")
