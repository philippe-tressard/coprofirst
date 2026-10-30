"""Poser une question au règlement : appel à l'assistant, extraits vérifiés, trace.

## Ce qui part chez le fournisseur

La consigne de l'usage, le texte du règlement (ses fichiers Markdown joints, bout
à bout), les décisions d'AG transcrites s'il y en a, et la question — rien d'autre : ni le nom de qui la pose, ni celui du résident pour qui elle l'est.
La politique de confidentialité le dit (`seed/contenus_legaux.QUESTION_REGLEMENT`).

## L'ordre des écritures

L'appel à l'assistant se fait AVANT toute écriture dans la session : le journal
des appels écrit dans sa propre transaction, et une écriture en cours dans
celle de l'appelant le verrouillerait (« database is locked », #1469).

## Un échec ne laisse pas de trace ici

IA coupée, plafond atteint, réponse illisible : la question n'est pas
enregistrée, l'écran dit pourquoi, et l'appel parti est compté dans `appel_ia`
comme tout autre. L'historique ne garde que des réponses.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session

from app.models.reglement import QuestionReglement
from app.utils.description_format import ReponseIllisible
from app.utils.question_reglement.extraits import en_json, verifier
from app.utils.question_reglement.format import (
    MAX_CARACTERES_QUESTION,
    SECTIONS,
    USAGE_QUESTION_REGLEMENT,
    consigne_complete,
    construire_message,
    lire_reponse,
)
from app.utils.question_reglement.provenance import lire_provenance
from app.utils.question_reglement.texte import assembler, enregistrer_version


def disponible(session: Session) -> bool:
    """L'usage peut-il être proposé ? — activé aux deux étages, clé et modèle."""
    from app.utils.llm import config_llm

    return config_llm(session, USAGE_QUESTION_REGLEMENT).pret


def ouvert_aux_coproprietaires(session: Session) -> bool:
    """L'administration a-t-elle ouvert les questions aux copropriétaires ?

    Une case de l'usage (Admin › Assistant IA), décochée par défaut : elle ne
    dit rien de l'assistant lui-même — `disponible` le dit —, seulement de QUI
    entre. Le conseil et l'administration entrent toujours
    (`auth/deps.require_questions_reglement`)."""
    from app.utils.llm import config_llm

    return config_llm(session, USAGE_QUESTION_REGLEMENT).ouvert_coproprietaires


async def repondre(session: Session, question: str, auteur_id: Optional[int]) -> QuestionReglement:
    """Pose la question, vérifie les extraits, enregistre la réponse.

    Lève `HTTPException(400)` — l'écran affiche le message tel quel.
    """
    from app.utils.llm import ErreurLLM, config_llm, demander
    from app.utils.llm_journal import cout_appel

    question = (question or "").strip()
    if not question:
        raise HTTPException(400, "La question est vide.")
    if len(question) > MAX_CARACTERES_QUESTION:
        raise HTTPException(
            400, f"La question dépasse {MAX_CARACTERES_QUESTION} caractères : resserrez-la."
        )
    texte = assembler(session)
    if texte is None:
        raise HTTPException(400, "Aucun fichier Markdown du règlement n'est joint.")
    cfg = config_llm(session, USAGE_QUESTION_REGLEMENT)
    try:
        rep = await demander(
            session,
            usage=USAGE_QUESTION_REGLEMENT,
            message=construire_message(texte.reglement, question, texte.decisions_ag),
            consigne=consigne_complete(cfg.prompt, avec_ag=bool(texte.decisions_ag)),
            demandeur=auteur_id,
        )
        lu = lire_reponse(rep.texte)
    except ErreurLLM as exc:
        raise HTTPException(400, str(exc))
    except ReponseIllisible as exc:
        raise HTTPException(400, f"Réponse de l'assistant illisible : {exc}")

    extraits = verifier(texte.contenu, lu["extraits"], texte.debut_ag)
    version = enregistrer_version(session, texte)
    ligne = QuestionReglement(
        question=question,
        verdict=lu["verdict"],
        reponse=lu["reponse"],
        reserves=lu["reserves"] or None,
        **{cle: lu[cle] or None for cle in SECTIONS},
        extraits_json=json.dumps(en_json(extraits), ensure_ascii=False),
        texte_id=version.id,
        auteur_id=auteur_id,
        modele=cfg.modele,
        provenance=lire_provenance(session),
        jetons_entree=rep.jetons_entree,
        jetons_sortie=rep.jetons_sortie,
        cout_usd=cout_appel(
            session,
            USAGE_QUESTION_REGLEMENT,
            rep.jetons_entree,
            rep.jetons_sortie,
            rep.jetons_cache,
        ),
    )
    session.add(ligne)
    session.commit()
    session.refresh(ligne)
    return ligne


__all__ = ["disponible", "ouvert_aux_coproprietaires", "repondre"]
