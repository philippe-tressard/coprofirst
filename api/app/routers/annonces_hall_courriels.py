"""La DIFFUSION d'une annonce de hall — courriel et groupe WhatsApp.

Toutes les entités du site portent leur diffusion dans un module dédié :
`calendrier_courriels.py`, `publications/courriels.py`, `tickets/courriels.py`.
L'annonce de hall écrivait la sienne dans son routeur — c'était tenable tant
qu'elle n'avait **qu'un** canal sur trois.

Extrait le 01/09/2026 en lui donnant les deux autres (#480), sur refus du
contrôle de modularité — qui désignait, comme les huit fois précédentes cette
semaine, un **placement** et non une longueur.

## 🔴 Ce que l'annonce de hall fait AUTREMENT, et qu'il ne faut pas uniformiser

Le conseil syndical y est choisi **par le PÉRIMÈTRE**, pas par le rôle : une
affiche du bâtiment 3 ne concerne pas le conseiller du bâtiment 1, qui ne
l'imprimera pas. C'est l'autre règle de `destinataires.py`, et les confondre
enverrait le bon message aux mauvaises personnes.

Ce qui est **commun**, en revanche, c'est la déduplication — le syndic passe en
premier et gagne le doublon — et elle vit dans `syndic_puis`.
"""

from __future__ import annotations


from typing import Optional

from fastapi import BackgroundTasks
from sqlmodel import Session

from app.models.core import AnnonceHall, Ticket, Utilisateur
from app.utils import horloge
from app.utils.annonce_hall import APERCU_MAX, date_longue, format_libelle, texte_brut

from app.utils.copie_auteur import copie_demandee
from app.utils.destinataires import (
    batiments_du_perimetre,
    cs_du_perimetre_ecartes,
    ecartes_du_syndic,
    membres_cs_notifiables,
    syndic_puis,
)
from app.utils.email import send_email_group
from app.utils.stockage import stockage
from app.utils.liens import lien_ticket
from app.utils.perimetres import parse_json_perimetres, perimetre_label_liste
from app.utils.preferences_mail import Ecarte
from app.utils.noms import contexte_personne
from app.utils.diffusion import config_diffusion, diffuser
from app.utils.visibility import contenu_hors_du_groupe


def lien_affiche(annonce: AnnonceHall) -> str | None:
    """Le lien qui accompagne une affiche — ou `None` quand il n'y en a pas.

    🔴 **Un seul lien pour les deux canaux.** L'e-mail et le groupe WhatsApp
    parlent de la même affiche : s'ils pointaient deux endroits différents, l'un
    des deux aurait tort, et rien ne le dirait.

    ⚠️ Il pointe l'**ACTUALITÉ** dont l'affiche est tirée, et seulement si elle
    existe. L'historique des affiches vit dans `/espace-cs`, que le front réserve
    au conseil syndical (`if (!$isCS) goto('/tableau-de-bord')`) : le syndic — qui
    reçoit ce courriel depuis le 01/09/2026 (#480) — y était renvoyé au tableau de
    bord. Le bouton était **mort pour la moitié de ses destinataires**, et le
    modèle d'e-mail était le seul du site à viser une route à accès restreint.

    Une affiche autonome part donc **sans lien** : le PDF est en pièce jointe,
    c'est tout son contenu, et un bouton qui ne mène nulle part vaut moins que
    pas de bouton.
    """
    #  L'affaire « Actualité » d'origine (#1091) ; la migration 0210 a reporté
    #  sur elle les affiches nées d'une publication.
    return lien_ticket(annonce.ticket_id) if annonce.ticket_id else None


def contexte_annonce_hall(annonce: AnnonceHall, user: Utilisateur) -> dict:
    """Le contexte du gabarit `annonce_hall` — composé ICI, et une seule fois.

    🔴 C'est la condition de l'aperçu avant envoi (#498/#480). Tant qu'une
    fonction d'envoi construit son contexte dans son propre corps, un aperçu doit
    le **recopier** — et un aperçu recomposé devient faux à la première évolution
    du gabarit, sans que personne le voie, puisque c'est justement l'aperçu qu'on
    regarde pour vérifier. La leçon est celle de `contexte_publication_syndic`,
    extraite le 31/08/2026 pour la même raison.
    """
    perimetres = parse_json_perimetres(annonce.perimetre_cible)
    return {
        "annonce": {
            "id": annonce.id,
            "titre": annonce.titre,
            "perimetre": perimetre_label_liste(perimetres),
            "format": format_libelle(annonce.format_effectif),
            "date": date_longue(horloge.jour_civil(annonce.cree_le)),
            "apercu": texte_brut(annonce.message)[:APERCU_MAX],
            "fichier": annonce.pdf_nom,
            #  Le bouton du gabarit est conditionné à cette clé — voir `lien_affiche`.
            "lien": lien_affiche(annonce),
        },
        "auteur": contexte_personne(user),
    }


def destinataires_annonce(
    annonce: AnnonceHall, session: Session, *, syndic: bool, cs: bool
) -> list[tuple[int | None, str]]:
    """Qui reçoit cette affiche — l'envoi et l'aperçu appellent la MÊME fonction.

    🔴 Le CS est choisi **par le PÉRIMÈTRE**, pas par le rôle : une affiche du
    bâtiment 3 ne concerne pas le conseiller du bâtiment 1, qui ne l'imprimera
    pas. C'est l'autre règle de `destinataires.py`, et les confondre enverrait le
    bon message aux mauvaises personnes.

    La déduplication, elle, est commune — `syndic_puis` : le syndic passe en
    premier et gagne le doublon (#480).
    """
    return syndic_puis(
        session,
        syndic=syndic,
        membres=membres_cs_notifiables(session, _batiments_de(annonce)) if cs else [],
    )


def _batiments_de(annonce: AnnonceHall) -> Optional[set[int]]:
    """Les bâtiments visés par l'affiche — None : tout le conseil."""
    return batiments_du_perimetre(parse_json_perimetres(annonce.perimetre_cible))


def ecartes_annonce(
    annonce: AnnonceHall, session: Session, *, syndic: bool, cs: bool
) -> list[Ecarte]:
    """Ceux que `destinataires_annonce` n'atteindra pas, et pourquoi — pour l'aperçu (#2006)."""
    return [
        *(ecartes_du_syndic(session) if syndic else []),
        *(cs_du_perimetre_ecartes(session, _batiments_de(annonce)) if cs else []),
    ]


def _envoyer_email_annonce(
    annonce: AnnonceHall,
    user: Utilisateur,
    background_tasks: BackgroundTasks,
    session: Session,
    *,
    syndic: bool = False,
    cs: bool = True,
    auteur: bool = False,
) -> list[str]:
    """Programme l'envoi de l'annonce, et rend les e-mails visés.

    Le choix des destinataires et la composition du contexte vivent au-dessus :
    l'aperçu (#498) appelle les mêmes fonctions, sinon il montrerait autre chose
    que ce qui part.
    """
    destinataires = destinataires_annonce(annonce, session, syndic=syndic, cs=cs)
    if not destinataires:
        return []

    ctx = contexte_annonce_hall(annonce, user)
    emails = [email for _, email in destinataires]
    #  🔴 La copie va à l'auteur de l'AFFICHE, et SUR DEMANDE. Elle partait ici
    #  d'office — le formulaire annonçait ses destinataires et en servait un de
    #  plus. Règle commune : `app/utils/copie_auteur.py` (01/09/2026).
    auteur_bcc = copie_demandee(
        session,
        annonce,
        emails,
        demandee=auteur,
    )
    background_tasks.add_task(
        send_email_group,
        code="annonce_hall",
        to_recipients=destinataires,
        context=ctx,
        session=session,
        bcc=auteur_bcc,
        attachments=[str(pdf)] if (pdf := stockage().fichier_de(annonce, "pdf")) else None,
    )
    return emails


def reserve_de_l_affiche(session: Session, annonce: AnnonceHall) -> tuple[Optional[str], bool]:
    """Le public visé et la réserve d'une affiche, pour le groupe — lus sur l'objet.

    Une affiche est faite pour le hall, lu de tous : elle n'a pas de réserve
    propre. Tirée d'une affaire, elle porte celle de l'affaire — que
    `sources_disponibles` refuse de reprendre si elle est réservée, mais qu'un
    appel direct à l'API pourrait encore nommer ; le groupe n'en reçoit alors que
    le titre (22/10/2026). L'envoi et son aperçu la lisent ici.
    """
    source = session.get(Ticket, annonce.ticket_id) if annonce.ticket_id else None
    if source is None:
        return None, False
    return source.public_cible, contenu_hors_du_groupe(source)


def _partager_sur_le_groupe(
    annonce: AnnonceHall, background_tasks: BackgroundTasks, session: Session
) -> bool:
    """Annonce l'affiche sur le groupe WhatsApp, avec un LIEN.

    🔴 **Un lien, pas le PDF** — arbitré le 01/09/2026. Le bridge n'envoie que
    du texte et une image ; joindre un document demanderait de l'exposer à une URL
    publique, c'est-à-dire d'ouvrir un accès non authentifié à un document dont le
    périmètre est parfois restreint.

    ⚠️ **Le lien pointe l'ACTUALITÉ dont l'affiche est tirée**, et seulement si
    elle existe. L'historique des affiches est un écran d'administration : y
    envoyer les résidents leur donnerait un 403. Une affiche autonome part donc
    **sans lien** — son titre et son message sont déjà tout son contenu, et un lien
    cassé vaut moins que pas de lien.

    Rend `True` si l'envoi a été programmé — le WhatsApp peut être éteint, et le
    dire évite d'inscrire dans l'historique une diffusion qui n'a pas eu lieu.
    """
    cfg = config_diffusion(session)
    if cfg is None:
        return False
    perimetres = parse_json_perimetres(annonce.perimetre_cible)
    public_cible, confidentiel = reserve_de_l_affiche(session, annonce)
    diffuser(
        background_tasks,
        cfg,
        annonce.titre,
        texte_brut(annonce.message),
        perimetre_cible=",".join(perimetres) if perimetres else None,
        public_cible=public_cible,
        confidentiel=confidentiel,
        lien=lien_affiche(annonce),
    )
    return True
