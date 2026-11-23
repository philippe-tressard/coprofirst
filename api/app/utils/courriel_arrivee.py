"""Le message d'arrivée d'un résident — **un modèle, trois publics** (#848).

## Ce que ce module porte

L'envoi de `nouvel_arrivant_bal` au **syndic**, au **nouvel arrivant** et au
**conseil syndical de son bâtiment**. Un seul modèle, adapté par
`role_destinataire` : le socle du message — la carte d'arrivée, qui, quel
bâtiment, quel occupant précédent — est écrit une fois dans le gabarit et sert
aux trois ; seules la formule d'appel et la demande changent.

## Ce qui manquait, et ce qui ne manquait pas

Demandé le 08/09/2026 : *« un mail envoyé au nouveau résident et au CS du
bâtiment comprenant le lien ou le PDF Consignes de la copropriété »*.

Les consignes ne **sortaient pas** de l'application : elles ne vivaient que dans
une notification, que l'arrivant devait ouvrir pour apprendre qu'il devait
l'ouvrir. Et le conseil du bâtiment n'en recevait aucune trace — sa seule
notification parle de l'interphone.

🔴 Mais le **modèle**, lui, existait, depuis la migration 0066. Un second modèle
d'accueil a failli naître : il aurait porté les mêmes trois variables d'arrivée,
la même carte, le même parcours, et les deux auraient divergé au premier
changement de l'un. Réponse de l'utilisateur, le jour même : *« je rappelle la
consigne de standardiser et non de dupliquer »*.

## Pourquoi ce module, à côté de ses deux pairs

`routers/admin/arrivants.py` déléguait déjà le ticket (`ticket_arrivant`) et
l'annonce aux voisins (`annonce_arrivee`). L'ajout de cet envoi l'a porté à
**512 lignes** et le garde-fou de modularité l'a refusé — à juste titre : un
routeur route, il ne rédige pas. Les trois gestes de l'accueil vivent désormais
côte à côte.
"""

from __future__ import annotations

from typing import Optional

from fastapi import BackgroundTasks
from sqlmodel import Session

from app.models.core import Utilisateur

#: Les « Consignes de la copropriété » — règlement intérieur, tri, accès,
#: stationnement, contacts. **Une seule écriture du chemin**, ici.
#:
#: La fiche n'était référencée NULLE PART dans le parcours : la notification de
#: bienvenue affirmait que « l'ensemble des consignes est disponible dans
#: l'application » sans le moindre lien, et son champ `lien` pointait sur `/`.
#: L'arrivant devait tomber par hasard sur la carte du tableau de bord.
#:
#: ⚠️ Elle est lue à DEUX endroits — la notification in-app (`routers/admin/
#: arrivants.py`) et le modèle d'e-mail, qui la reçoit en **variable** et la
#: préfixe de `{{ app.url }}`. Un modèle vit en base et se réécrit depuis
#: Admin › Présentation › Modèles e-mail : l'y coder en dur en ferait une copie que personne ne
#: reverrait le jour où la route change.
FICHE_CONSIGNES = "/api/admin/fiche-arrivant"

#: Le modèle unique, et les rôles qu'il sait servir.
CODE_MODELE = "nouvel_arrivant_bal"
ROLE_SYNDIC = "syndic"
ROLE_RESIDENT = "resident"
ROLE_CS = "cs"

#: Les deux rôles qui reçoivent les consignes. C'est leur envoi conjoint, et lui
#: seul, qui autorise le ticket de suivi à ne pas diffuser.
ROLES_CONSIGNES = frozenset({ROLE_RESIDENT, ROLE_CS})


def destinataires_arrivee(
    session: Session,
    user: Utilisateur,
    *,
    syndic_principal,
    membres_cs_notifies: set[int],
) -> list[tuple[Optional[int], str, str]]:
    """`(user_id, adresse, rôle)` pour les trois publics, dans l'ordre d'envoi.

    🔴 Le courriel vise **exactement** les membres du conseil que la notification
    d'interphone atteint, et pas un de plus — d'où `membres_cs_notifies`, calculé
    par l'appelant.

    `membres_cs_notifiables(session, None)` rend **tout** le conseil, alors que le
    parcours d'accueil, sans bâtiment connu, se limite au gestionnaire du site.
    Prendre l'une pour l'autre écrirait l'arrivée d'un résident à des membres qui
    n'ont jamais reçu sa notification : deux listes pour une même question,
    divergentes dans le cas — le cas sans bâtiment — que personne n'essaie.

    L'intersection garde le meilleur des deux : la **règle de périmètre** vient de
    l'appelant, le **filtrage** (compte actif, adresse renseignée, dédoublonnage
    par adresse) de `membres_cs_notifiables`, qui en est la source unique.
    """
    from app.utils.destinataires import membres_cs_notifiables

    destinataires: list[tuple[Optional[int], str, str]] = []

    if syndic_principal and syndic_principal.email:
        destinataires.append((syndic_principal.user_id, syndic_principal.email, ROLE_SYNDIC))
    if user.email:
        destinataires.append((user.id, user.email, ROLE_RESIDENT))

    batiments_cible = {user.batiment_id} if user.batiment_id else None
    for cs_user_id, cs_email in membres_cs_notifiables(session, batiments_cible):
        if cs_user_id not in membres_cs_notifies:
            continue
        #  L'arrivant peut lui-même siéger au conseil : il recevrait alors deux
        #  fois le même message, dont une version rédigée pour quelqu'un d'autre.
        if cs_user_id == user.id:
            continue
        destinataires.append((cs_user_id, cs_email, ROLE_CS))

    return destinataires


def envoyer(
    session: Session,
    background_tasks: BackgroundTasks,
    destinataires: list[tuple[Optional[int], str, str]],
    *,
    nom_complet: str,
    batiment: str,
    ancien_resident: str,
) -> bool:
    """Programme les envois et dit si les CONSIGNES sont bien sorties.

    Rend `True` seulement quand l'arrivant **et** au moins un membre du conseil
    sont servis : c'est cette valeur qui autorise le ticket de suivi à ne pas
    diffuser. Si l'un des deux n'a rien reçu — pas d'adresse, préférences
    coupées — la diffusion doit reprendre son rôle d'alerte, sinon le suivi
    n'aurait aucun destinataire.

    ⚠️ La préférence « e-mails de mon bâtiment » est respectée sans que ce code
    la lise : `send_email` la consulte dès qu'un `destinataire_id` est fourni.
    Ce que cette fonction affirme est donc que l'envoi a été **demandé**, pas
    qu'il a abouti — et c'est le bon niveau : un destinataire qui a coupé ses
    e-mails a déjà décidé, la diffusion du ticket ne le rattraperait pas.
    """
    from app.utils.email import send_email

    for dest_id, dest_email, role in destinataires:
        background_tasks.add_task(
            send_email,
            code=CODE_MODELE,
            to=dest_email,
            context={
                "nom_complet": nom_complet,
                "batiment": batiment,
                "ancien_resident": ancien_resident,
                "role_destinataire": role,
                "lien_consignes": FICHE_CONSIGNES,
                #  Le syndic n'a pas toujours de compte : le modèle ne lit
                #  `destinataire.prenom` que dans les deux autres branches.
                "destinataire": session.get(Utilisateur, dest_id) if dest_id else None,
            },
            session=session,
            destinataire_id=dest_id,
        )

    return ROLES_CONSIGNES <= {role for _, _, role in destinataires}


__all__ = [
    "CODE_MODELE",
    "FICHE_CONSIGNES",
    "ROLES_CONSIGNES",
    "ROLE_CS",
    "ROLE_RESIDENT",
    "ROLE_SYNDIC",
    "destinataires_arrivee",
    "envoyer",
]
