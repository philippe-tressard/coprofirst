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

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session

from app.models.core import RoleUtilisateur, Utilisateur
from app.config import get_settings
from app.routers import annonces_hall
from tests.aides_base import moteur_memoire


@pytest.fixture(name="contexte")
def contexte_fixture(monkeypatch, tmp_path):
    moteur = moteur_memoire(partage=True)
    monkeypatch.setattr(annonces_hall, "generer_pdf", lambda **_: b"%PDF-test")
    #  Les affiches s'écrivent dans le stockage de la copropriété (#1748).
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    with Session(moteur) as session:
        cs = Utilisateur(
            email="cs@test.fr",
            hashed_password="x",
            nom="C",
            prenom="S",
            roles_json=RoleUtilisateur.conseil_syndical.value,
        )
        session.add(cs)
        session.commit()
        session.refresh(cs)
        yield session, cs


def _creer(session, user, **options):
    return annonces_hall.creer_annonce_hall(
        session=session,
        user=user,
        background_tasks=BackgroundTasks(),
        titre="Coupure d'eau",
        message="<p>Mardi, de 9 h à 12 h.</p>",
        perimetre_cible=["résidence"],
        **options,
    )


def test_une_annonce_redigee_avec_l_assistant_en_porte_la_marque(contexte):
    session, cs = contexte
    annonce = _creer(session, cs, assiste_ia=True)
    assert annonce.assiste_ia is True
    assert annonces_hall._to_read(annonce, session)["assiste_ia"] is True


def test_sans_l_assistant_la_marque_n_apparait_pas(contexte):
    session, cs = contexte
    annonce = _creer(session, cs)
    assert annonce.assiste_ia is False
    assert annonces_hall._to_read(annonce, session)["assiste_ia"] is False


def test_la_route_transmet_la_marque():
    """Le corps de la route l'accepte, et elle le passe au point d'entrée."""
    import inspect

    from app.routers.annonces_hall_schemas import AnnonceHallCreate

    assert "assiste_ia" in AnnonceHallCreate.model_fields
    assert "assiste_ia=body.assiste_ia" in inspect.getsource(annonces_hall.create_annonce_hall)
