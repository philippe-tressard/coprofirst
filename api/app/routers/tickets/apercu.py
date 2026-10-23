"""Tickets — **voir ce qui partira, avant de confirmer la diffusion**.

## Pourquoi cet endpoint existe (#498, 19/08/2026)

Demandé à l'écran :

> *« avant la diffusion il faudrait voir le mail (aperçu) avant de confirmer son
> envoi »*, puis *« cela est à intégrer partout où l'objet diffusion par mail est
> concerné »*, puis *« l'aperçu peut-il aussi englober WhatsApp ? »*

Jusqu'ici on cochait « envoyer au syndic » ou « partager sur le groupe » et on
découvrait le résultat en le recevant — quand on faisait partie des destinataires.

## 🔴 Un aperçu qui ment est pire que pas d'aperçu

C'est la règle du projet (`standards/04` §14 : observer la chose, pas son
enregistrement). Un aperçu reconstruit « à peu près » deviendrait faux à la
première évolution d'un gabarit, et **personne ne s'en apercevrait** — puisque
c'est justement l'aperçu qu'on regarderait pour le vérifier.

Cet endpoint ne recompose donc **rien** :

| Ce qu'il montre | Fonction employée | Employée aussi par |
|---|---|---|
| l'e-mail | `contexte_ticket_syndic` + `composer_email` | `envoyer_email_syndic_cs` |
| le message WhatsApp | `construire_message` | `envoyer_whatsapp` |
| les destinataires | `destinataires_syndic_cs` | l'envoi réel |

`api/tests/test_apercu_diffusion.py` échoue si l'un des deux chemins s'en écarte.

## Ce qu'il ne peut pas savoir, et qu'il DIT

L'aperçu est demandé **avant** que le ticket existe (arbitrage du 19/08 : « si
l'aperçu est correct alors envoi, sinon annulation ou retour au formulaire »).
Deux champs sont donc attribués plus tard, et l'écran les marque comme tels
plutôt que d'inventer une valeur :

  * le **numéro** du ticket (`TK-……`) ;
  * le **lien permanent**, qui en dépend.

⚠️ Un troisième cas n'est pas connaissable du tout, et l'écran doit le dire : si
une photo existe mais que son encodage pour le bridge échoue, le message WhatsApp
reçoit en plus « 📷 Photos à voir sur le site ». Cela se décide à l'envoi.
L'aperçu montre donc *le message tel qu'il sera composé*, pas *ce que le groupe
recevra à coup sûr* — la nuance est petite et réelle.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, peut_commenter
from app.database import get_session
from app.models.core import Ticket, TicketEvolution, Utilisateur
from app.utils.copie_auteur import adresse_copie, objet_de, repartir_copie
from app.utils.apercu_diffusion import (
    ApercuCanal,
    ApercuDiffusion,
    apercu_email,
    apercu_whatsapp,
)
from app.utils.photos import photos_internes, photos_json, premiere_image

from .actualite import contexte_actualite
from app.utils.destinataires import ecartes_syndic_cs

from .courriels import contexte_ticket_syndic, destinataires_syndic_cs
from .suite_groupe import message_suite
from app.utils.liens import adresse_du_site
from app.utils.categories_ticket import ticket_urgent
from app.utils.nature_affaire import est_actualite, statut_pour
from app.utils.perimetres import perimetre_cible_json
from app.utils.recuperer import ou_404
from app.utils.visibility import contenu_hors_du_groupe, reservee_au_conseil

router = APIRouter()


class BrouillonTicket(BaseModel):
    """Ce que l'écran a sous la main au moment où l'on demande l'aperçu.

    Volontairement **plat et permissif** : c'est un brouillon, pas un ticket. Le
    valider comme une création refuserait l'aperçu à qui veut justement vérifier
    avant de compléter.
    """

    #  🔴 Renseigné quand on commente un ticket EXISTANT (#498, 19/08/2026).
    #
    #  L'aperçu ne couvrait que la création, et l'utilisateur l'a découvert en
    #  commentant : il avait coché « envoyer au syndic », rien ne s'est ouvert.
    #  Une fonctionnalité livrée à moitié ne se lit pas comme « la suite arrive »,
    #  elle se lit comme cassée — et c'est la lecture juste, du côté de l'écran.
    #
    #  Le fil est le cas où l'aperçu sert le PLUS : à la création on relit ce
    #  qu'on vient d'écrire, alors qu'un commentaire part avec l'historique du
    #  ticket derrière lui, que personne ne relit avant l'envoi.
    ticket_id: Optional[int] = None
    commentaire: str = ""
    titre: str = ""
    description: str = ""
    categorie: str = ""
    perimetre_cible: Optional[list[str]] = None
    photos_urls: list[str] = []
    fichiers_urls: list[str] = []
    destinataire_syndic: bool = False
    destinataire_cs: bool = False
    partager_whatsapp: bool = False
    #  « M'envoyer une copie » — la 4e case de la Diffusion. L'aperçu doit la
    #  montrer : taire un destinataire ferait mentir l'aperçu par omission.
    envoyer_auteur: bool = False
    #  Ce qu'une actualité ajoute (#1091, lot 4) : l'urgence, et à qui l'on
    #  parle — Destinataires = « Conseil syndical » seul, et rien ne sort.
    urgente: bool = False
    public_cible: Optional[list[str]] = None
    #  🔒 « Réservé au périmètre » d'une actualité : sans lui, l'aperçu montrait
    #  la description entière d'une actualité réservée (22/10/2026).
    reserve_perimetre: bool = False


#  🔴 Les deux schémas et les deux assembleurs viennent de `app/utils/
#  apercu_diffusion.py` depuis le 31/08/2026. Ils vivaient ICI, et les tickets
#  étaient donc le seul écran capable d'aperçu : le jour où l'utilisateur a
#  demandé la même chose sur une actualité, il n'y avait rien à brancher.
#
#  ⚠️ La forme de la réponse ne change pas d'un octet — `test_apercu_diffusion`
#  le vérifie sans avoir été touché.


def _ticket_previsionnel(brouillon: BrouillonTicket, auteur: Utilisateur) -> Ticket:
    """Un `Ticket` **non persisté**, tel qu'il serait créé.

    Il n'est jamais ajouté à la session : `composer_email` et `construire_message`
    ne lisent que des attributs, et un objet en mémoire suffit. C'est ce qui
    permet l'aperçu avant création sans laisser d'objet fantôme en base.
    """
    import json

    categorie = brouillon.categorie or "question"
    return Ticket(
        numero="",  # attribué à la création
        titre=brouillon.titre,
        description=brouillon.description,
        categorie=categorie,
        statut=statut_pour(categorie),
        priorite="haute" if brouillon.urgente else "normale",
        public_cible=json.dumps(brouillon.public_cible, ensure_ascii=False)
        if brouillon.public_cible
        else None,
        auteur_id=auteur.id,
        perimetre_cible=perimetre_cible_json(brouillon.perimetre_cible),
        reserve_perimetre=brouillon.reserve_perimetre,
        photos_urls=photos_json(brouillon.photos_urls),
        fichiers_urls=photos_json(brouillon.fichiers_urls),
        destinataire_syndic=brouillon.destinataire_syndic,
        destinataire_cs=brouillon.destinataire_cs,
    )


@router.post("/apercu-diffusion", response_model=ApercuDiffusion)
def apercu_diffusion(
    brouillon: BrouillonTicket,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Ce que chaque canal coché enverra — composé par les fonctions d'envoi.

    ⚠️ `get_current_user` et non `require_cs_or_admin` : n'importe quel résident
    ouvre un ticket et peut cocher « prévenir le syndic ». Le droit de **diffuser
    sur le groupe** est vérifié à la création (`body.partager_whatsapp and est_cs`)
    — l'aperçu le reflète en marquant le canal inactif, plutôt que de montrer un
    message qui ne partira pas.
    """
    #  Deux gestes, un seul endpoint : créer un ticket, ou commenter un ticket
    #  existant. Le second lit l'objet RÉEL en base — son numéro, son titre et son
    #  fil sont déjà attribués, donc rien n'est prévisionnel de ce côté-là.
    evolutions = None
    if brouillon.ticket_id is not None:
        ticket = ou_404(session, Ticket, brouillon.ticket_id, "Ticket")
        #  ⚠️ Le droit de commenter, pas seulement de lire : l'aperçu montre le
        #  contenu du ticket et son historique. Le refuser ici évite d'en faire
        #  une voie de lecture détournée.
        if not peut_commenter(ticket, user):
            raise HTTPException(403, "Accès refusé")
        #  L'historique part AVEC le message, et c'est précisément ce que
        #  personne ne relit avant d'envoyer.
        evolutions = session.exec(
            select(TicketEvolution)
            .where(TicketEvolution.ticket_id == ticket.id)
            .order_by(TicketEvolution.cree_le)
        ).all()
    else:
        ticket = _ticket_previsionnel(brouillon, user)

    canaux: list[ApercuCanal] = []
    pieces = photos_internes(brouillon.photos_urls) + photos_internes(brouillon.fichiers_urls)
    actualite = est_actualite(ticket)

    #  🔴 Réservée au conseil, une actualité ne diffuse RIEN (#1096) : l'aperçu
    #  le dit canal par canal, plutôt que de montrer ce qui ne partira pas.
    if actualite and reservee_au_conseil(ticket):
        motif = "Réservée au conseil syndical : rien ne sort."
        coches = [
            ("email", brouillon.destinataire_syndic or brouillon.destinataire_cs),
            ("whatsapp", brouillon.partager_whatsapp),
        ]
        return ApercuDiffusion(
            canaux=[
                ApercuCanal(canal=c, actif=False, inactif_motif=motif) for c, oui in coches if oui
            ],
            attribues_a_la_creation=[],
        )

    # ── E-mail syndic / conseil syndical ────────────────────────────────────
    #  Une actualité écrit avec le gabarit de l'actualité, composé par la
    #  fonction même qui l'enverra (`contexte_actualite`).
    if brouillon.destinataire_syndic or brouillon.destinataire_cs or brouillon.envoyer_auteur:
        if actualite:
            contexte, pieces = contexte_actualite(
                ticket,
                user,
                session,
                commentaire=brouillon.commentaire or None,
                fichiers_urls=photos_internes(brouillon.fichiers_urls) or None,
            )
        else:
            contexte = contexte_ticket_syndic(
                ticket,
                user,
                session,
                pieces_jointes=pieces,
                commentaire=brouillon.commentaire or None,
                evolutions=evolutions,
            )
        destinataires = destinataires_syndic_cs(
            session, syndic=brouillon.destinataire_syndic, cs=brouillon.destinataire_cs
        )
        #  🔴 L'auteur du TICKET, pas le rédacteur : sur un commentaire du CS, ce sont
        #  deux personnes différentes (31/08/2026).
        copie = (
            adresse_copie(session, objet_de(session, Ticket, brouillon.ticket_id), user)
            if brouillon.envoyer_auteur
            else None
        )
        #  Cochée SEULE, la copie est le destinataire — avec son gabarit, comme à l'envoi.
        destinataires, bcc, seule = repartir_copie(destinataires, copie)
        copie = bcc[0] if bcc else None
        if actualite:
            code_modele = "publication_copie_auteur" if seule else "publication_syndic"
        else:
            code_modele = "ticket_copie_auteur" if seule else "ticket_syndic"
        canaux.append(
            apercu_email(
                session,
                code_modele=code_modele,
                contexte=contexte,
                destinataires=destinataires,
                lecteur=user,
                pieces_jointes=pieces,
                copie_auteur=copie,
                ecartes=ecartes_syndic_cs(
                    session, syndic=brouillon.destinataire_syndic, cs=brouillon.destinataire_cs
                ),
            )
        )

    # ── Groupe WhatsApp ─────────────────────────────────────────────────────
    if brouillon.partager_whatsapp:
        #  🔴 Une Suite montre SON message, pas la description de l'affaire : il
        #  part seul, avec le lien de la fiche pour le reste du fil — composé
        #  par la fonction même de l'envoi (28/09/2026).
        if brouillon.ticket_id is not None:
            suite = message_suite(
                session,
                ticket,
                brouillon.commentaire,
                site_url=adresse_du_site(),
                suite_enregistree=False,
                fichiers_urls=brouillon.fichiers_urls,
            )
            titre, contenu, photo, lien = suite.titre, suite.contenu, suite.photo, suite.lien
        else:
            titre = ticket.titre if actualite else f"🎫 {ticket.titre}"
            contenu, lien = ticket.description, None
            photo = premiere_image(brouillon.photos_urls)
        canaux.append(
            apercu_whatsapp(
                session,
                user,
                titre=titre,
                contenu=contenu,
                urgent=ticket_urgent(ticket),
                perimetre=ticket.perimetre_cible,
                photo=photo,
                lien=lien,
                #  La règle de l'envoi (`groupe.diffuser_l_affaire`), lue au même endroit.
                public_cible=ticket.public_cible,
                confidentiel=contenu_hors_du_groupe(ticket),
            )
        )

    #  Sur un ticket EXISTANT, rien n'est attribué plus tard : le numéro et le
    #  lien sont déjà là. Annoncer le contraire ferait douter d'un aperçu exact.
    #  Une actualité n'affiche pas de numéro : l'annoncer ferait attendre ce qui ne vient pas.
    nouveaux = ["lien permanent"] if actualite else ["numéro du ticket", "lien permanent"]
    a_attribuer = [] if brouillon.ticket_id is not None else nouveaux
    return ApercuDiffusion(
        canaux=canaux,
        attribues_a_la_creation=a_attribuer if canaux else [],
    )
