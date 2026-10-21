"""Le point CS / Syndic du Suivi des entretiens périodiques passe par le MÊME code
que celui du Suivi des affaires (#2085, lot 4/4) : ce test le prouve en jouant le
cycle complet dans le mode « entretien » — ouverture, compte rendu, fin, validation,
PDF rangé et envoyé (à, copie), historique du mode — sans une règle propre au mode.

Seule exception arbitrée le 20/10/2026 : l'affaire « Points annexes » n'est créée
qu'au Suivi affaires (`test_points_conseil_etats.py`)."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.models.core import RoleUtilisateur
from app.models.points_conseil import PointConseil
from app.utils.stockage import DOSSIER_PRIVE
from tests.aides_http import base_http, client_http
from tests.aides_points_conseil import intercepter_envois, point_termine


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


@pytest.fixture(name="envois")
def envois_fixture(monkeypatch, disque_jetable):
    return intercepter_envois(monkeypatch)


def test_le_point_des_entretiens_se_valide_range_et_envoie_comme_celui_des_affaires(moteur, envois):
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    point, _, adresse_cs = point_termine(moteur, cs, mode="entretien")
    envois.clear()
    assert cs.post(f"/points-conseil/{point}/valider").status_code == 204
    with Session(moteur) as s:
        p = s.get(PointConseil, point)
        assert p.mode == "entretien" and p.etat == "valide"
        assert p.pdf_cle and p.pdf_cle.startswith(f"{DOSSIER_PRIVE}/")
    (envoi,) = envois
    assert envoi["code"] == "point_conseil_valide"
    assert sorted(envoi["to"]) == sorted([adresse_cs, "gestion@exemple.test"])
    assert envoi["cc"], "tout le conseil en copie, comme au Suivi affaires"
    (h,) = cs.get("/points-conseil/historique?mode=entretien").json()
    assert (h["id"], h["pdf_range"]) == (point, True)
    assert cs.get("/points-conseil/historique?mode=affaires").json() == []
    assert cs.post(f"/points-conseil/{point}/pdf").status_code == 200
