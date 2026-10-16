"""Un fil TRANSFÉRÉ par le conseil, versé dans une affaire (29/09/2026).

## Le besoin

> « Je reçois des mails du CS directement dans mon email perso, je dois faire le
>   travail : si c'est relatif à une affaire, recopier le mail […] ; si nouveau,
>   créer une nouvelle affaire […] en mettant l'auteur dans la section AU NOM DE »

Le membre du conseil **transfère** le courriel à l'adresse des affaires. Aucun
mot-clé : le transfert lui-même est le geste (arbitré le 29/09/2026).

## Où va le fil — dans cet ordre

1. **un repère écrit** — « TK-109008 » dans l'objet ou la note, même seul
   (`courriel_fil.repere_ecrit`), ou « Affaire #TK-… » d'un courriel du site ;
2. **un transfert précédent du même fil** (`FilCourriel`), tant que son affaire
   est ouverte ;
3. **sinon, une affaire neuve** : Étude & travaux, **conseil syndical seul**
   (arbitré le 29/09/2026 — ce sont des échanges internes au conseil), titrée de
   l'objet d'origine, décrite par le plus ANCIEN message, au nom de son auteur.

Puis une Suite par message suivant, du plus ancien au plus récent, chacune
ouverte par « *Mail reçu de X le …, transféré par Y* ».

## Ce qui ne se double pas

Un message déjà versé dans CETTE affaire est sauté : par son empreinte
(`MessageVerse`), ou parce que son texte est déjà dans le fil — une copie faite
à la main avant ce lot n'a pas d'empreinte.

## Ce qui n'entre pas

- **la note de qui transfère** : elle porte le repère, pas le suivi (règle du
  28/09/2026 pour un transfert du syndic, étendue à tout transfert) ;
- **les messages du site** et tout ce qu'ils citent : l'affaire les a déjà ;
- **un fil qu'on ne sait pas découper** (`FilIllisible`) : rien, jamais à moitié.

Chaque issue est notifiée à qui a transféré (`sa_demande`) : c'est lui qui
attend de voir son fil dans l'affaire, et lui seul sait s'il manque quelque chose.

## Ce qui se défait (#1482)

Chaque versement laisse sa trace (`VersementCourriel`) et chaque Suite la
sienne (`versement_id`) : le transfert s'annule, se réaffecte ou devient une
affaire neuve d'un geste, depuis l'affaire (`utils/versement_transfert`).

## Qui peut s'en servir

Un **membre du conseil** (ou un administrateur), authentifié — DKIM ou ARC,
comme toute réponse. Un autre correspondant de l'affaire (son auteur, le
syndic) peut transférer dans l'affaire que le courriel DÉSIGNE, sans rien créer
ni rien retenir : c'était déjà le cas pour un message du syndic.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.adresse_compte import compte_par_adresse, normaliser_adresse
from app.auth.deps import est_moderateur
from app.models.core import Ticket, TicketEvolution, Utilisateur
from app.models.courriel import FilCourriel, MessageVerse
from app.models.tickets import STATUTS_TICKET_CLOS, CategorieTicket
from app.utils import horloge
from app.utils.cloche import sonner_systeme
from app.utils.courriel_authenticite import domaine_de
from app.utils.courriel_decodage import (
    Transfert,
    _html_en_texte,
    est_objet_de_transfert,
    transfert_dans,
)
from app.utils.courriel_fil import (
    FilIllisible,
    MessageDuFil,
    cle_du_fil,
    empreinte,
    messages_du_fil,
    repere_ecrit,
    texte_normalise,
    titre_du_fil,
)
from app.utils.courriel_ingestion import (
    ACCEPTE,
    IGNORE,
    PLANCHER_PAR_DEFAUT,
    REFUSE,
    examiner,
)
from app.utils.courriel_numero import aide_au_numero
from app.utils.liens import LIEN_COURRIELS_AFFAIRES, lien_ticket
from app.utils.noms import nom_affiche
from app.utils.reponse_courriel import (
    contenu_de_la_suite,
    mettre_en_forme,
    moment_de_la_suite,
    suite_mise_en_forme,
)
from app.utils.valeurs import valeur
from app.utils.versement_transfert import etat_avant, ouvrir_versement

#: La catégorie d'une affaire créée par transfert — le conseil la corrige ensuite.
CATEGORIE_PAR_DEFAUT = CategorieTicket.etude_travaux
#: « Conseil syndical seul », CHOISI et non hérité de la catégorie : il tient
#: quand le conseil corrige la catégorie.
PUBLIC_CONSEIL_SEUL = '["conseil_syndical"]'
#: Un titre d'affaire reste lisible dans une liste.
LONGUEUR_TITRE = 200
#: Ce que dit la notification quand l'objet annonce un transfert que le corps ne
#: porte pas : c'est la forme du message qui manque, pas l'affaire.
_TRANSFERT_NON_RECONNU = (
    "l'objet annonce un transfert, mais le message transféré n'a pas été trouvé : "
    "aucun bloc « De : … » avec une adresse, suivi d'une date, dans le corps du courriel"
)
#: Ce que dit la notification d'un versement réussi : le geste qui le défait.
_SI_ERREUR = "Une erreur ? Le transfert s'annule ou se déplace depuis l'affaire."
#: Un message plus court ne se cherche pas dans le fil : « Merci » y est partout.
LONGUEUR_COMPARABLE = 40
#: Le début d'un message suffit à le reconnaître ; sa fin (la signature) est
#: justement ce que l'assistant retire.
DEBUT_COMPARE = 200


def compte_a_l_adresse(session: Session, adresse: str | None) -> Utilisateur | None:
    """Le compte ACTIF à cette adresse (« Nom <a@b.fr> » accepté), sans égard à la casse.

    Ce module ne fait qu'extraire l'adresse de l'en-tête : la question « quel
    compte ? » est celle de `auth.adresse_compte`, posée partout de la même façon.
    """
    from email.utils import parseaddr

    return compte_par_adresse(session, parseaddr(adresse or "")[1], actif_seulement=True)


def domaines_du_site(session: Session) -> set[str]:
    """Les domaines d'où le site écrit : un message qui en vient est déjà dans l'affaire."""
    from app import contexte
    from app.utils.email import _get_smtp_config
    from app.utils.smtp import adresses_a_tester

    adresses = [*adresses_a_tester(_get_smtp_config(session)), contexte.courante().expediteur]
    return {domaine_de(a) for a in adresses} - {""}


def decider_transfert(session, entetes, corps, recu_le, plancher, authentification):
    """`(décision, motif, affaire)` si ce message est un transfert que ce module
    verse — sinon None, et la relève ordinaire (`courriel_boite`) en décide."""
    from app.utils.courriel_boite import _ticket_de, correspondant_du_ticket

    lire = {k.lower(): v for k, v in entetes.items()}
    sujet = lire.get("subject", "")
    if not est_objet_de_transfert(sujet) or (
        recu_le is not None and recu_le < (plancher or PLANCHER_PAR_DEFAUT)
    ):
        return None
    qui = compte_a_l_adresse(session, lire.get("from"))
    if qui is None:
        return None  # la relève ordinaire le refuse, et le dit
    transfert = transfert_dans(sujet, corps)
    if transfert is None:
        #  🔴 29/09/2026 : un transfert de Mail pour Windows, non reconnu, est
        #  retombé dans la relève ordinaire, qui a répondu « rien ne permet de
        #  dire à quel ticket » — vrai, et sans rapport avec ce qui manquait.
        if est_moderateur(qui):
            return _refuser(session, qui, None, _TRANSFERT_NON_RECONNU)
        return None
    verdict = examiner(
        entetes, recu_le=recu_le, plancher=plancher, authentification=authentification
    )
    designe = _ticket_de(session, verdict)
    if not est_moderateur(qui):
        if (
            designe is None
            or verdict.decision != ACCEPTE
            or not correspondant_du_ticket(session, designe, qui)
        ):
            return None
        return verser(session, transfert, sujet, qui, designe, creer=False)

    ok, motif = authentification or (False, "aucune vérification d'authenticité")
    if not ok:
        return _refuser(
            session, qui, designe, f"le transfert n'a pas pu être authentifié : {motif}"
        )
    if designe is None:
        numero = repere_ecrit(sujet, transfert.note)
        if numero:
            designe = session.exec(
                select(Ticket).where(func.lower(Ticket.numero) == numero.lower())
            ).first()
            if designe is None:
                #  Un numéro à une faute de frappe d'une affaire existante : on le DIT
                #  (`courriel_numero`), on ne rattache jamais de soi-même.
                return _refuser(
                    session,
                    qui,
                    None,
                    f"l'affaire {numero} n'existe pas{aide_au_numero(session, numero)}",
                )
    return verser(session, transfert, sujet, qui, designe, creer=True)


def verser(
    session: Session,
    transfert: Transfert,
    sujet: str,
    qui: Utilisateur,
    designe: Ticket | None,
    *,
    creer: bool,
):
    """Découpe le fil et le verse. Rend `(décision, motif, affaire)`."""
    try:
        messages = messages_du_fil(transfert)
    except FilIllisible as exc:
        return _refuser(session, qui, designe, f"le fil ne se découpe pas avec certitude : {exc}")
    #  Du plus ancien au plus récent : c'est l'ordre du fil de l'affaire.
    messages = [m for m in reversed(_avant_le_site(session, messages)) if m.texte]
    if not messages:
        motif = "rien à verser : le fil ne porte que des messages du site"
        _prevenir(session, qui, designe, "Transfert sans message à verser", motif)
        return IGNORE, motif, designe

    objet = transfert.objet or sujet
    cle = cle_du_fil(objet)
    ticket = designe or (_affaire_du_fil(session, cle) if creer else None)
    if ticket is not None and valeur(ticket.statut) in STATUTS_TICKET_CLOS:
        if designe is not None:
            motif = f"l'affaire #{ticket.numero} est close : elle ne reçoit plus rien"
            _prevenir(session, qui, ticket, "Transfert non versé", motif)
            return IGNORE, motif, ticket
        ticket = None  # le fil suivait une affaire close : il en ouvre une autre

    creee = ticket is None
    avant = etat_avant(session, ticket, cle if creer else None)
    #  🔴 DEUX TEMPS (#1469, 30/09/2026) : lire et mettre en forme d'abord, écrire
    #  ensuite. Chaque appel à l'assistant écrit son journal dans SA transaction
    #  (`llm_journal.journaliser`) ; une écriture déjà en cours ici tiendrait ses
    #  verrous pendant tout l'appel à l'assistant, et le journal attendrait
    #  derrière elle.
    nouveaux, deja = _a_verser(session, ticket, messages)
    prets = [(m, mettre_en_forme(session, m.texte, m.brut)) for m in nouveaux]
    if creee:
        (premier, mis), prets = prets[0], prets[1:]
        ticket = _creer_affaire(session, qui, premier, mis, titre_du_fil(objet))
    versement = (
        ouvrir_versement(session, qui, ticket, avant, objet, creee=creee)
        if prets or creee
        else None
    )
    if creee:
        _marquer(session, ticket, premier, versement)
    ajoutees = _ecrire_les_suites(session, ticket, qui, prets, versement)
    if creer and cle:
        _retenir_le_fil(session, cle, ticket)

    if not creee and not ajoutees:
        motif = f"rien de nouveau : les {deja} message(s) du fil sont déjà dans l'affaire"
        _prevenir(session, qui, ticket, f"Transfert déjà versé — #{ticket.numero}", motif)
        return IGNORE, motif, ticket
    ticket.mis_a_jour_le = horloge.maintenant()
    session.add(ticket)
    motif = _bilan(creee, ajoutees, deja)
    titre = f"Affaire #{ticket.numero} créée" if creee else f"Transfert versé — #{ticket.numero}"
    _prevenir(session, qui, ticket, titre, f"{motif}. {_SI_ERREUR}")
    return ACCEPTE, motif, ticket


def _a_verser(session, ticket, messages: list[MessageDuFil]):
    """Les messages qui ne sont pas encore dans l'affaire, et combien le sont.

    Lecture seule : c'est le premier des deux temps de `verser`. Deux fois le
    même message dans un même transfert ne compte qu'une fois.
    """
    fil = texte_du_fil(session, ticket) if ticket is not None else ""
    vus: set[str] = set()
    nouveaux, deja = [], 0
    for m in messages:
        e = empreinte(m)
        if e in vus or (ticket is not None and _deja_verse(session, ticket, m, fil)):
            deja += 1
            continue
        vus.add(e)
        nouveaux.append(m)
    return nouveaux, deja


def _ecrire_les_suites(session, ticket, qui, prets, versement) -> int:
    """Une Suite par message déjà mis en forme. Rend le nombre ajouté."""
    ajoutees = 0
    for m, mis in prets:
        suite = suite_mise_en_forme(
            session,
            ticket,
            qui,
            mis,
            expediteur=m.expediteur,
            nom=m.nom,
            envoye_le=m.envoye_le,
            transfere_par=_transfere_par(qui, m),
            ecartable=_du_conseil(session, m),
        )
        if suite is not None:
            suite.versement_id = versement.id
            session.add(suite)
            session.flush()
            ajoutees += 1
        #  Marqué même écarté (un merci du conseil) : renvoyé, il le serait encore.
        _marquer(session, ticket, m, versement, suite)
        if suite is None:
            continue
        if suite.nouveau_statut:  # le syndic a répondu : l'affaire est chez lui
            ticket.statut = suite.nouveau_statut
    return ajoutees


def _bilan(creee: bool, ajoutees: int, deja: int) -> str:
    morceaux = ["affaire créée — Étude & travaux, conseil syndical seul"] if creee else []
    if ajoutees:
        morceaux.append(f"{ajoutees} suite(s) ajoutée(s)")
    if deja:
        morceaux.append(f"{deja} message(s) déjà présent(s), non doublé(s)")
    return " ; ".join(morceaux) or "affaire créée"


def _avant_le_site(session: Session, messages: list[MessageDuFil]) -> list[MessageDuFil]:
    """Les messages PLUS RÉCENTS que le premier courriel du site cité dans le fil."""
    domaines = domaines_du_site(session)
    retenus = []
    for m in messages:
        if m.adresse and domaine_de(m.adresse) in domaines:
            break
        retenus.append(m)
    return retenus


def _transfere_par(qui: Utilisateur, m: MessageDuFil) -> str | None:
    """Qui a transféré — tu quand c'est son propre message : « Mail reçu de
    Philippe …, transféré par Philippe » ne dirait rien de plus."""
    if m.adresse and m.adresse == normaliser_adresse(qui.email):
        return None
    return nom_affiche(qui.prenom, qui.nom)


def _du_conseil(session: Session, m: MessageDuFil) -> bool:
    compte = compte_a_l_adresse(session, m.adresse)
    return compte is not None and est_moderateur(compte)


def _affaire_du_fil(session: Session, cle: str | None) -> Ticket | None:
    if not cle:
        return None
    lien = session.exec(select(FilCourriel).where(FilCourriel.cle == cle)).first()
    return session.get(Ticket, lien.ticket_id) if lien else None


def _retenir_le_fil(session: Session, cle: str, ticket: Ticket) -> None:
    lien = session.exec(select(FilCourriel).where(FilCourriel.cle == cle)).first()
    lien = lien or FilCourriel(cle=cle, ticket_id=ticket.id)
    lien.ticket_id = ticket.id
    lien.mis_a_jour_le = horloge.maintenant()
    session.add(lien)


def _marquer(session: Session, ticket: Ticket, m: MessageDuFil, versement, suite=None) -> None:
    session.add(
        MessageVerse(
            ticket_id=ticket.id,
            empreinte=empreinte(m),
            versement_id=versement.id,
            evolution_id=suite.id if suite is not None else None,
        )
    )
    #  L'auteur du premier message écrit : « Au nom de » d'une affaire qu'on en
    #  détacherait (`versement_transfert.detacher`).
    if (suite is not None or versement.affaire_creee) and versement.premier_nom is None:
        versement.premier_nom, versement.premier_adresse = m.nom, m.adresse
        session.add(versement)


def texte_du_fil(session: Session, ticket: Ticket) -> str:
    """Tout ce que l'affaire dit déjà, normalisé — description et Suites."""
    evolutions = session.exec(
        select(TicketEvolution).where(TicketEvolution.ticket_id == ticket.id)
    ).all()
    morceaux = [ticket.description or ""]
    for e in evolutions:
        morceaux += [e.contenu or "", e.contenu_origine or ""]
    return texte_normalise(" ".join(_html_en_texte(m) for m in morceaux))


def _deja_verse(session: Session, ticket: Ticket, m: MessageDuFil, fil: str) -> bool:
    if session.exec(
        select(MessageVerse).where(
            MessageVerse.ticket_id == ticket.id, MessageVerse.empreinte == empreinte(m)
        )
    ).first():
        return True
    norme = texte_normalise(m.texte)
    return len(norme) >= LONGUEUR_COMPARABLE and norme[:DEBUT_COMPARE] in fil


def _creer_affaire(session: Session, qui: Utilisateur, m: MessageDuFil, mis, titre: str) -> Ticket:
    """L'affaire neuve : décrite par le plus ancien message, au nom de son auteur."""
    quand = moment_de_la_suite(m.envoye_le)
    return creer_affaire_du_fil(
        session,
        qui,
        nom=m.nom,
        adresse=m.adresse,
        description=contenu_de_la_suite(
            m.expediteur, m.nom, quand, mis.contenu or m.texte, _transfere_par(qui, m)
        ),
        quand=quand,
        assiste=mis.assiste,
        titre=titre or f"Courriel de {m.nom}",
    )


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


def _prevenir(session: Session, qui: Utilisateur, ticket: Ticket | None, titre: str, corps: str):
    sonner_systeme(
        session,
        "sa_demande",
        destinataire_id=qui.id,
        type="ticket_update",
        titre=titre,
        corps=corps,
        lien=lien_ticket(ticket.id) if ticket else LIEN_COURRIELS_AFFAIRES,
    )


def _refuser(session: Session, qui: Utilisateur, ticket: Ticket | None, motif: str):
    _prevenir(session, qui, ticket, "Transfert non versé", motif)
    return REFUSE, motif, ticket


__all__ = [
    "CATEGORIE_PAR_DEFAUT",
    "PUBLIC_CONSEIL_SEUL",
    "compte_a_l_adresse",
    "creer_affaire_du_fil",
    "decider_transfert",
    "domaines_du_site",
    "texte_du_fil",
    "verser",
]
