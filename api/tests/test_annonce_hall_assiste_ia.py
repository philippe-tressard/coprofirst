"""L'annonce de hall porte la marque « rédigé avec l'assistant IA » (#1089).

Arbitré le 20/09/2026 : l'annonce de hall emploie la section Description
standard, assistant IA compris — c'était le seul formulaire à Description qui en
était privé. La règle de `utils/assiste_ia` suit : la marque est une colonne sur
**chaque** entité qui porte une section Description.

Ce test crée une annonce par le point d'entrée UNIQUE (`creer_annonce_hall`,
commun à l'écran et au pré-remplissage depuis une actualité), le rendu PDF
neutralisé — WeasyPrint vit dans l'image, pas sur tous les postes.
"""

from __future__ import annotations

from app.routers import annonces_hall
from tests.aides_annonce_hall import contexte_fixture, creer  # noqa: F401 — la fixture `contexte`


def test_une_annonce_redigee_avec_l_assistant_en_porte_la_marque(contexte):
    session, cs = contexte
    annonce = creer(session, cs, assiste_ia=True)
    assert annonce.assiste_ia is True
    assert annonces_hall._to_read(annonce, session)["assiste_ia"] is True


def test_sans_l_assistant_la_marque_n_apparait_pas(contexte):
    session, cs = contexte
    annonce = creer(session, cs)
    assert annonce.assiste_ia is False
    assert annonces_hall._to_read(annonce, session)["assiste_ia"] is False


def test_la_route_transmet_la_marque():
    """Le corps de la route l'accepte, et elle le passe au point d'entrée."""
    import inspect

    from app.routers.annonces_hall_schemas import AnnonceHallCreate

    assert "assiste_ia" in AnnonceHallCreate.model_fields
    assert "assiste_ia=body.assiste_ia" in inspect.getsource(annonces_hall.create_annonce_hall)
