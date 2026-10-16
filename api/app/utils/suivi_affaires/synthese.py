"""La synthèse des affaires en cours par l'assistant — l'usage
`synthese_affaires_en_cours` (16/10/2026).

Geste MANUEL : l'icône ✨ du rapport « Suivi des affaires », réservée au conseil
syndical et à l'administration (l'appel est facturé, comme l'usage `description`).
Elle n'enregistre RIEN : la synthèse s'affiche, se relit, et part dans le PDF si
le conseil l'exporte ensuite.

Ce qui part : catégorie, titre, date d'ouverture, ancienneté, état et descriptif
de chaque affaire. Ni l'auteur, ni le lot, ni les messages, ni les pièces jointes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlmodel import Session

from app.utils.dates_fr import date_courte
from app.utils.description_format import ReponseIllisible
from app.utils.llm import ErreurLLM, config_llm, demander
from app.utils.suivi_affaires.format import (
    FORMAT_REPONSE,
    USAGE_SYNTHESE_AFFAIRES_EN_COURS,
    construire_message,
    lire_reponse,
)
from app.utils.suivi_affaires.releve import Releve

logger = logging.getLogger("hostachy.assistant")


@dataclass(frozen=True)
class Synthese:
    resume: str
    points: list[str]


def message_du_releve(r: Releve) -> str:
    """PURE. Le message de l'assistant, tiré du relevé."""
    return construire_message(
        date_courte(r.jour),
        [
            {
                "libelle_categorie": a.libelle_categorie,
                "titre": a.titre,
                "ouverte_le": date_courte(a.ouverte_le),
                "age_jours": a.age_jours,
                "libelle_statut": a.libelle_statut,
                "descriptif": a.descriptif,
            }
            for a in r.affaires
        ],
    )


async def rediger(session: Session, r: Releve, *, demandeur: int) -> Synthese:
    """Pose le relevé au modèle de l'usage et rend sa synthèse. N'enregistre RIEN."""
    if not r.affaires:
        raise ErreurLLM("Aucune affaire ouverte : rien à synthétiser.")
    cfg = config_llm(session, USAGE_SYNTHESE_AFFAIRES_EN_COURS)
    #  Le prompt de l'administrateur D'ABORD, le format du code ENSUITE.
    consigne = cfg.prompt.rstrip() + "\n\n" + FORMAT_REPONSE
    reponse = await demander(
        session,
        usage=USAGE_SYNTHESE_AFFAIRES_EN_COURS,
        consigne=consigne,
        message=message_du_releve(r),
        demandeur=demandeur,
    )
    try:
        lu = lire_reponse(reponse.texte)
    except ReponseIllisible as exc:
        logger.warning("Synthèse des affaires en cours : %s", exc)
        raise ErreurLLM("Le modèle n'a pas répondu dans le format attendu — réessayez.") from exc
    return Synthese(resume=lu["resume"], points=lu["points"])


def disponible(session: Session) -> bool:
    """Le ✨ a-t-il un sens ? — c'est le SERVEUR qui le dit (`ConfigLLM.pret`)."""
    return config_llm(session, USAGE_SYNTHESE_AFFAIRES_EN_COURS).pret
