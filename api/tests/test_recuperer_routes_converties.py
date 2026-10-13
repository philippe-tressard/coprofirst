"""Les 404 convertis aux aides de `utils/recuperer` répondent comme avant (#1571).

13/10/2026 : la photo d'un relevé de compteur (condition composée « relevé
absent OU sans photo », séparée en `ou_404` puis `present_ou_404`) et la
catégorie de FAQ à renommer. Aucun test n'exerçait ces chemins : une conversion
qui aurait rendu 200 ou 500 serait passée sans un mot.
"""

import pytest
from sqlmodel import Session

from app.models.compteurs import ReleveCompteur
from app.models.core import RoleUtilisateur
from tests.aides_http import base_http, client_http


@pytest.fixture
def moteur():
    with base_http() as moteur:
        yield moteur


def _releve(moteur, photo_url):
    with Session(moteur) as s:
        r = ReleveCompteur(type_compteur="eau_general", photo_url=photo_url)
        s.add(r)
        s.commit()
        return r.id


@pytest.mark.parametrize(
    ("photo_url", "detail"),
    [(None, "Photo introuvable"), ("", "Photo introuvable")],
)
def test_un_releve_sans_photo_rend_404(moteur, photo_url, detail):
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    r_id = _releve(moteur, photo_url)
    reponse = http.get(f"/prestataires/releves/{r_id}/photo/x.jpg")
    assert reponse.status_code == 404
    assert reponse.json()["detail"] == detail


def test_un_releve_absent_rend_404(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    reponse = http.get("/prestataires/releves/999/photo/x.jpg")
    assert reponse.status_code == 404
    assert reponse.json()["detail"] == "Relevé introuvable"


def test_renommer_une_categorie_absente_rend_404(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    reponse = http.patch(
        "/faq/categories/rename", json={"old_name": "Inexistante", "new_name": "Autre"}
    )
    assert reponse.status_code == 404
    assert reponse.json()["detail"] == "Catégorie introuvable"
