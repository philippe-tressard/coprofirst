"""Retravailler un titre et une description avec l'assistant — l'usage
`description` (#985, 17/09/2026).

## Ce que ce module fait

Il reçoit ce qu'un formulaire porte — le titre, la description, le contexte de
l'objet (catégorie, périmètre, état, date…) et une précision éventuelle de
l'auteur —, le pose au modèle configuré pour cet usage, relit la réponse et rend
une PROPOSITION : un titre, une description, et pour chacun s'il a changé.

Il n'enregistre RIEN. C'est l'auteur qui applique la proposition dans son
formulaire, puis enregistre — ou l'ignore. Rien ne distingue alors ce texte de
ce qu'il aurait tapé, sinon la marque `assiste_ia` qu'il pose en enregistrant
(`utils/assiste_ia`).

## 🔴 Le format est tenu par le CODE, le ton par l'ADMINISTRATEUR

Le prompt de l'usage est modifiable dans l'administration. Le format de la
réponse — un objet JSON à deux clés — ne l'est pas : il est **ajouté** à la
consigne ici (`description_format.FORMAT_REPONSE`), après le prompt, et c'est
lui que `lire_reponse` sait relire. Un administrateur peut réécrire tout le
reste sans pouvoir casser la lecture.

## Ce qui part, et ce qui ne part pas

Le titre, la description, le contexte déclaré par l'écran (des libellés courts,
plafonnés) et la précision. **Aucune pièce jointe, aucun autre objet.** Le
contexte est déclaré au modèle comme « à ne pas réécrire ».
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session

from app.utils.description_format import (
    FORMAT_INATTENDU,
    FORMAT_REPONSE,
    MAX_CARACTERES_CONTEXTE,
    MAX_CARACTERES_DESCRIPTION,
    MAX_CARACTERES_PRECISION,
    ReponseIllisible,
    a_change,
    construire_message,
    lire_reponse,
)
from app.utils.llm import ErreurLLM, config_llm, demander
from app.utils.llm_usages import USAGE_DESCRIPTION

logger = logging.getLogger("hostachy.assistant")


@dataclass(frozen=True)
class Demande:
    """Ce que le formulaire envoie."""

    entite: str
    titre: Optional[str]
    description: Optional[str]
    contexte: dict[str, str]
    precision: Optional[str]
    #: Faux sur une entrée de fil : un commentaire n'a pas de titre à proposer.
    avec_titre: bool


@dataclass(frozen=True)
class Proposition:
    """Ce que le modèle propose — et ce qui a changé, pour que l'écran le dise.

    🔴 `titre_modifie` / `description_modifiee` sont calculés ICI, sur le texte
    normalisé : l'écran signale à l'auteur ce qu'il doit relire (« Titre
    modifié »), et une comparaison faite côté client sur du HTML brut dirait
    « modifié » à chaque espace que l'éditeur ajoute.
    """

    titre: Optional[str]
    description: str
    titre_modifie: bool
    description_modifiee: bool


def _borner(texte: Optional[str], maximum: int) -> Optional[str]:
    if texte is None:
        return None
    return texte[:maximum]


def preparer(demande: Demande) -> Demande:
    """La demande, bornée — un texte au-delà des plafonds coûte des jetons pour
    rien, et un contexte de mille caractères n'est plus un contexte."""
    if not (demande.titre or "").strip() and not (demande.description or "").strip():
        raise ErreurLLM("Rien à retravailler : le titre et la description sont vides.")
    return Demande(
        entite=demande.entite[:80],
        titre=_borner(demande.titre, 300),
        description=_borner(demande.description, MAX_CARACTERES_DESCRIPTION),
        contexte={
            str(k)[:60]: str(v)[:MAX_CARACTERES_CONTEXTE]
            for k, v in (demande.contexte or {}).items()
            if v
        },
        precision=_borner(demande.precision, MAX_CARACTERES_PRECISION),
        avec_titre=demande.avec_titre,
    )


async def retravailler(session: Session, demande: Demande, *, demandeur: int) -> Proposition:
    """Pose la demande au modèle de l'usage et rend sa proposition. N'enregistre RIEN."""
    d = preparer(demande)
    cfg = config_llm(session, USAGE_DESCRIPTION)
    #  Le prompt de l'administrateur D'ABORD, le format du code ENSUITE : le
    #  dernier mot sur la forme reste à ce que `lire_reponse` sait lire.
    consigne = cfg.prompt.rstrip() + "\n\n" + FORMAT_REPONSE
    message = construire_message(
        entite=d.entite,
        titre=d.titre,
        description=d.description,
        contexte=d.contexte,
        precision=d.precision,
        avec_titre=d.avec_titre,
    )
    reponse = await demander(
        session,
        usage=USAGE_DESCRIPTION,
        consigne=consigne,
        message=message,
        demandeur=demandeur,
    )
    try:
        lu = lire_reponse(reponse.texte)
    except ReponseIllisible as exc:
        #  ⚠️ Le texte du modèle est journalisé, pas recopié à l'écran : il peut
        #  contenir la description qu'on vient d'envoyer.
        logger.warning("Assistant description : %s — %s", exc, reponse.texte[:300])
        raise ErreurLLM(FORMAT_INATTENDU) from exc
    titre = lu["titre"] if d.avec_titre else None
    return Proposition(
        titre=titre,
        description=lu["description"],
        titre_modifie=d.avec_titre and a_change(d.titre, titre),
        description_modifiee=a_change(d.description, lu["description"]),
    )


def disponible(session: Session) -> bool:
    """Le geste a-t-il un sens ? — activation aux deux étages, clé, modèle.

    🔴 C'est le SERVEUR qui le dit (`ConfigLLM.pret`), pas l'écran : la
    configuration de l'assistant n'a rien à faire dans la session d'un membre
    du conseil syndical (`standards/03` §1).
    """
    return config_llm(session, USAGE_DESCRIPTION).pret


__all__ = ["Demande", "Proposition", "disponible", "preparer", "retravailler"]
