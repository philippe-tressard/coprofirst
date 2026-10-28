"""Flux — rubrique Règlement : les questions posées au règlement de copropriété.

Ajouté le 11/10/2026 : *« la réponse à une question posée doit aussi figurer dans
le fil d'actualité avec les mêmes droits de visibilité (si elle est supprimée, elle
disparaît) »*.

- **Les mêmes droits** : le fil appelle `question_reglement_visible`, le prédicat
  qui filtre l'historique de l'onglet — l'auteur, le conseil, l'administration,
  et rien quand l'usage est refermé aux copropriétaires. Jamais sa copie.
- **Supprimée, elle disparaît** : le fil lit la table, et une question effacée
  n'y est plus. Aucun marqueur à tenir.
- La carte paraît à la RÉPONSE (`cree_le` : la ligne naît avec elle) et mène à la
  question, dépliée, dans Ma résidence › Règlement.
"""

from sqlmodel import col, select

from app.auth.deps import question_reglement_visible
from app.models.reglement import QuestionReglement
from app.utils.liens import lien_element
from app.utils.question_reglement.format import VERDICTS

from .commun import ContexteFlux, auteur_nom, strip_html
from .schemas import FluxItem


def collecter(ctx: ContexteFlux) -> list[FluxItem]:
    questions = ctx.session.exec(
        select(QuestionReglement)
        .where(QuestionReglement.cree_le >= ctx.since)
        .order_by(col(QuestionReglement.cree_le).desc())
    ).all()
    return [
        FluxItem(
            id=f"qr_{q.id}",
            type="question_reglement",
            date=q.cree_le,
            cree_le=q.cree_le,
            titre=q.question,
            detail=f"Question au règlement — {strip_html(q.reponse, 200)}",
            icon="⚖️",
            badges=[VERDICTS.get(q.verdict, q.verdict)],
            lien=lien_element("question-reglement", q.id),
            meta={
                "question_reglement_id": q.id,
                #  Le CODE du verdict : la capsule prend sa teinte, comme dans
                #  l'onglet (`#lib/reglement`, `CLASSE_VERDICT`).
                "verdict": q.verdict,
                "auteur": auteur_nom(ctx.session, q.auteur_id),
            },
        )
        for q in questions
        if question_reglement_visible(q, ctx.user, ctx.session)
    ]
