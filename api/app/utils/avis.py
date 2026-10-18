"""Les RÈGLES d'un avis sur l'application — écrites une fois (#2075).

## Les seuils, arbitrés le 18/10/2026

| Note | Ce que l'avis demande | Ce qu'il permet |
|---|---|---|
| 1–2 | une **remarque** : ce qui a manqué, pour améliorer le site | — |
| 3 | rien de plus | — |
| 4–5 | l'**accord** de l'auteur, Oui ou Non, sans réponse par défaut | paraître sur coprofirst.fr, si le gestionnaire le retient |

🔴 **L'accord ne se présume jamais.** Une case pré-cochée n'est pas un
consentement (RGPD art. 4-11, considérant 32 ; CJUE *Planet49*, C-673/17) :
la question exige une réponse, et `None` vaut « pas d'accord ».

## Qui voit quoi

L'avis se lit de tous les comptes de la copropriété. Ce qui ne regarde que
l'auteur et le gestionnaire du site — la remarque, l'accord, la validation —
ne sort qu'à eux (`routers/avis.lire`). Un avis retiré (archivé) ne se lit plus que
d'eux deux, aux Archives.

## Ce qui part sur coprofirst.fr

`exporter` : les seuls avis **publiables** (note ≥ 4, accord donné, non
retirés) **et** retenus par le gestionnaire. Le prénom et l'initiale du nom,
le rôle, la note, le titre, le texte et le jour — ni adresse, ni identifiant,
ni nom de résidence.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session

from app.models.avis import Avis
from app.models.core import Utilisateur
from app.utils import horloge
from app.utils.annonce_hall import texte_brut
from app.utils.noms import nom_abrege
from app.utils.recuperer import precharger
from app.utils.roles_libelles import role_signature

NOTE_MIN = 1
NOTE_MAX = 5
#: Sous ce seuil, l'avis dit ce qui a manqué.
NOTE_REMARQUE = 3
#: À partir de ce seuil, l'auteur dit s'il accepte que l'avis paraisse.
NOTE_PUBLIABLE = 4


def exiger_saisie_valide(
    note: int, remarque: Optional[str], consentement: Optional[bool]
) -> tuple[Optional[str], Optional[bool]]:
    """Refuse une saisie hors des règles ; rend la remarque et l'accord à ENREGISTRER.

    Ce qui ne s'applique pas à la note ne s'enregistre pas : une remarque
    laissée d'une note basse relevée ensuite, un accord donné à 5 étoiles puis
    retombé à 3. Garder l'un ou l'autre ferait dire à l'avis ce qu'il ne dit plus.
    """
    if not NOTE_MIN <= note <= NOTE_MAX:
        raise HTTPException(422, f"La note va de {NOTE_MIN} à {NOTE_MAX} étoiles")
    remarque = (remarque or "").strip() or None
    if note < NOTE_REMARQUE and not remarque:
        raise HTTPException(
            422,
            "Sous 3 étoiles, dites-nous ce qui vous a manqué : c'est ce qui fait progresser le site",
        )
    if note < NOTE_PUBLIABLE:
        return (remarque if note < NOTE_REMARQUE else None), None
    if consentement is None:
        raise HTTPException(422, "Répondez par Oui ou par Non à la question de publication")
    return None, consentement


def est_publiable(avis: Avis) -> bool:
    """L'avis PEUT paraître sur coprofirst.fr — avant le choix du gestionnaire."""
    return (
        avis.note >= NOTE_PUBLIABLE
        and avis.consentement_publication is True
        and avis.archive_le is None
    )


def est_exporte(avis: Avis) -> bool:
    """L'avis part dans l'export : publiable, ET retenu par le gestionnaire."""
    return est_publiable(avis) and avis.publication_validee_le is not None


def signature(auteur: Optional[Utilisateur]) -> tuple[str, Optional[str]]:
    """« Prénom N. » et le rôle — la seule façon dont un avis nomme son auteur."""
    if auteur is None:
        return "", None
    return nom_abrege(auteur.prenom, auteur.nom), role_signature(auteur)


def auteurs_de(session: Session, avis: list[Avis]) -> dict[int, Utilisateur]:
    """Les auteurs d'une liste d'avis, lus en UNE requête (`precharger`, #1838)."""
    return {u.id: u for u in precharger(session, Utilisateur, [a.auteur_id for a in avis])}


def exporter(session: Session, avis: list[Avis]) -> list[dict]:
    """Ce qui part sur coprofirst.fr — les seuls avis exportés, sans rien qui identifie."""
    retenus = [a for a in avis if est_exporte(a)]
    auteurs = auteurs_de(session, retenus)
    sortie = []
    for a in retenus:
        nom, role = signature(auteurs.get(a.auteur_id))
        sortie.append(
            {
                "titre": a.titre,
                "texte": texte_brut(a.description),
                "note": a.note,
                "auteur": nom,
                "role": role,
                "date": horloge.jour_civil(a.mis_a_jour_le or a.cree_le).isoformat(),
            }
        )
    return sortie
