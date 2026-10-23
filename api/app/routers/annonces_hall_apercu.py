"""Annonce de hall — **voir ce qui partira, avant de confirmer la diffusion**.

Dernier des neuf points de diffusion du site à recevoir l'aperçu de #498, et le
seul qui en était privé **délibérément** : tant que le serveur n'y consommait
qu'un canal sur trois, un aperçu y aurait montré un envoi qui n'a pas lieu —
c'est-à-dire exactement le mensonge que #498 existe pour empêcher. Les trois
canaux sont consommés depuis le 01/09/2026 (#480), et la condition est levée.

## Ce qu'il ne recompose PAS

| Ce qu'il montre | Fonction employée | Employée aussi par |
|---|---|---|
| l'e-mail | `contexte_annonce_hall` + `apercu_email` | `_envoyer_email_annonce` |
| les destinataires | `destinataires_annonce` | l'envoi réel |
| le message WhatsApp | `apercu_whatsapp` → `construire_message` | `envoyer_whatsapp_avec_log` |
| le lien joint au message | `lien_affiche` | les **deux** canaux |

🔴 C'est la condition, et elle a un pourquoi : un aperçu qui **recompose** devient
faux à la première évolution du gabarit, sans que personne le voie — puisque c'est
justement l'aperçu qu'on regarde pour vérifier.

## Ce qu'il ne peut pas savoir, et qu'il DIT

L'affiche n'existe pas encore : son identifiant et son PDF sont produits à la
création. Le **format** et le **nom du fichier**, eux, sont calculés par les mêmes
fonctions que la création (`choisir_format`, `nom_fichier`) — les taire aurait fait
mentir l'aperçu sur deux valeurs que le gabarit cite en toutes lettres.
"""

from __future__ import annotations

import json
from app.utils import horloge
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import AnnonceHall, Utilisateur
from app.utils.annonce_hall import choisir_format, nom_fichier, texte_brut
from app.utils.apercu_diffusion import (
    ApercuCanal,
    ApercuDiffusion,
    apercu_email,
    apercu_whatsapp,
)
from app.utils.copie_auteur import adresse_copie
from app.utils.perimetres import perimetre_cible_json
from app.utils.photos import photos_internes
from app.utils.recuperer import ou_404

from .annonces_hall_courriels import (
    contexte_annonce_hall,
    destinataires_annonce,
    ecartes_annonce,
    lien_affiche,
    reserve_de_l_affiche,
)

router = APIRouter()


class BrouillonAnnonceHall(BaseModel):
    """Ce que l'écran a sous la main au moment où l'on demande l'aperçu.

    Volontairement **plat et permissif** : c'est un brouillon, pas une affiche.
    Le valider comme une création refuserait l'aperçu à qui veut justement
    vérifier avant de compléter.
    """

    #  Renseigné quand l'affiche est pré-remplie depuis une actualité — une
    #  affaire depuis le 23/09/2026 (#1091) : c'est ce qui donne son lien au
    #  message WhatsApp, et lui seul.
    ticket_id: Optional[int] = None
    titre: str = ""
    message: str = ""
    perimetre_cible: Optional[list[str]] = None
    format_demande: str = "auto"
    images: list[str] = []
    envoyer_cs: bool = False
    envoyer_syndic: bool = False
    partager_whatsapp: bool = False
    envoyer_auteur: bool = False


def _annonce_previsionnelle(b: BrouillonAnnonceHall, auteur: Utilisateur) -> AnnonceHall:
    """Une `AnnonceHall` **non persistée**, telle qu'elle serait créée.

    Elle n'est jamais ajoutée à la session : les fonctions de composition ne lisent
    que des attributs. C'est ce qui permet l'aperçu avant création sans laisser
    d'objet fantôme en base.

    ⚠️ `format_effectif` et `pdf_nom` sont calculés par les MÊMES fonctions que la
    création. Le gabarit les cite (« prêt à imprimer au format A5 », « Pièce jointe :
    <fichier> ») : les laisser vides aurait fait mentir l'aperçu sur ce que le
    destinataire lira.
    """
    cree_le = horloge.maintenant()
    images = photos_internes(b.images)
    fmt = choisir_format(b.message, b.format_demande, titre=b.titre, avec_photos=bool(images))
    return AnnonceHall(
        titre=b.titre,
        message=b.message,
        perimetre_cible=perimetre_cible_json(b.perimetre_cible),
        format_effectif=fmt,
        pdf_nom=nom_fichier(b.titre, cree_le),
        #  Le PDF n'existe pas (ni clé ni chemin) : l'e-mail réel le joindra,
        #  l'aperçu ne peut pas le montrer. `apercu_email` reçoit donc une pièce
        #  jointe NOMMÉE — annoncer un fichier absent vaut mieux que la taire.
        auteur_id=auteur.id,
        ticket_id=b.ticket_id,
        cree_le=cree_le,
        images=json.dumps(images, ensure_ascii=False),
    )


@router.post("/apercu-diffusion", response_model=ApercuDiffusion)
def apercu_diffusion_annonce(
    brouillon: BrouillonAnnonceHall,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Ce que chaque canal coché enverra — composé par les fonctions d'envoi.

    ⚠️ `get_current_user` et non `require_cs_or_admin`, comme pour les actualités :
    le droit de diffuser sur le groupe est vérifié par `apercu_whatsapp`, qui rend
    le canal inactif **avec son motif** plutôt que de montrer un message qui ne
    partira pas. Refuser l'endpoint entier priverait d'aperçu ceux qui n'ont coché
    que l'e-mail.
    """
    if brouillon.ticket_id is not None:
        from app.models.core import Ticket

        ou_404(session, Ticket, brouillon.ticket_id, "Actualité")

    annonce = _annonce_previsionnelle(brouillon, user)
    canaux: list[ApercuCanal] = []

    # ── E-mail syndic / conseil syndical du périmètre ────────────────────────
    if brouillon.envoyer_cs or brouillon.envoyer_syndic:
        canaux.append(
            apercu_email(
                session,
                code_modele="annonce_hall",
                contexte=contexte_annonce_hall(annonce, user),
                destinataires=destinataires_annonce(
                    annonce, session, syndic=brouillon.envoyer_syndic, cs=brouillon.envoyer_cs
                ),
                lecteur=user,
                pieces_jointes=[annonce.pdf_nom],
                #  L'affiche n'existe pas encore : son auteur SERA le rédacteur.
                #  `adresse_copie` le sait et rend son adresse — la taire ferait
                #  annoncer un destinataire de moins que ce qui part.
                copie_auteur=(
                    adresse_copie(session, None, user) if brouillon.envoyer_auteur else None
                ),
                ecartes=ecartes_annonce(
                    annonce, session, syndic=brouillon.envoyer_syndic, cs=brouillon.envoyer_cs
                ),
            )
        )

    # ── Groupe WhatsApp ──────────────────────────────────────────────────────
    if brouillon.partager_whatsapp:
        public_cible, confidentiel = reserve_de_l_affiche(session, annonce)
        canaux.append(
            apercu_whatsapp(
                session,
                user,
                titre=annonce.titre,
                contenu=texte_brut(annonce.message),
                urgent=False,
                perimetre=annonce.perimetre_cible,
                #  Le groupe reçoit un LIEN, jamais le PDF ni les photos de
                #  l'affiche — arbitré le 01/09/2026, cf. `_partager_sur_le_groupe`.
                photo=None,
                lien=lien_affiche(annonce),
                #  La règle de l'envoi (`_partager_sur_le_groupe`), lue au même endroit.
                public_cible=public_cible,
                confidentiel=confidentiel,
            )
        )

    #  L'affiche n'existe pas encore : son PDF est produit à la création. On le
    #  dit plutôt que de laisser croire que la pièce jointe est déjà là.
    return ApercuDiffusion(
        canaux=canaux,
        attribues_a_la_creation=["le PDF de l'affiche"] if canaux else [],
    )
