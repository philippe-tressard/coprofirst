"""La scène des tests d'affiche de hall — une base en mémoire, un stockage jetable.

`test_annonce_hall_assiste_ia.py` la portait seul ; `test_annonce_hall_suppression.py`
(#1828) en a besoin à l'identique. Un fichier de tests ne s'importe pas depuis un
autre (`test_aides_de_tests_source_unique.py`) : elle vit ici.

`contexte` est une fixture : un fichier de tests l'IMPORTE pour que pytest la
trouve (même forme qu'`aides_affaire.session`). Le rendu PDF est neutralisé —
WeasyPrint vit dans l'image, pas sur tous les postes —, et les affiches
s'écrivent dans le stockage de la copropriété (#1748), sous `tmp_path`.
"""

from __future__ import annotations

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session

from app.config import get_settings
from app.models.core import RoleUtilisateur
from app.routers import annonces_hall
from tests.aides_base import compte, moteur_memoire


@pytest.fixture(name="contexte")
def contexte_fixture(monkeypatch, tmp_path):
    moteur = moteur_memoire(partage=True)
    monkeypatch.setattr(annonces_hall, "generer_pdf", lambda **_: b"%PDF-test")
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    with Session(moteur) as session:
        cs = compte(session, prefixe="cs", roles_json=RoleUtilisateur.conseil_syndical.value)
        yield session, cs


def creer(session, user, **options):
    """Une affiche, par le point d'entrée UNIQUE (`creer_annonce_hall`)."""
    return annonces_hall.creer_annonce_hall(
        session=session,
        user=user,
        background_tasks=BackgroundTasks(),
        titre="Coupure d'eau",
        message="<p>Mardi, de 9 h à 12 h.</p>",
        perimetre_cible=["résidence"],
        **options,
    )
