"""L'intégrité se MESURE, jamais ne se déclare (#1781, DI-7b).

`dialecte.verifier_integrite` lit les sommes de contrôle de pages (posées à
l'initialisation, docker-compose.yml) ; la base de la suite est initialisée
comme en production.
"""

from __future__ import annotations

from app import dialecte
from tests.aides_base import moteur_de_test


def test_une_base_saine_rend_ok_sur_le_moteur_de_la_suite():
    moteur = moteur_de_test()
    with moteur.connect() as conn:
        assert dialecte.verifier_integrite(conn) == "ok"


class _Simulee:
    """Une connexion PostgreSQL simulée : `SHOW data_checksums` et le compteur."""

    def __init__(self, sommes: str, echecs: int):
        self.dialect = type("D", (), {"name": "postgresql"})()
        self._sommes, self._echecs = sommes, echecs

    def execute(self, requete):
        valeur = self._sommes if "data_checksums" in str(requete) else self._echecs
        return type("R", (), {"scalar": lambda _s: valeur})()


def test_sans_sommes_de_controle_le_verdict_n_est_pas_vert():
    assert dialecte.verifier_integrite(_Simulee("off", 0)) != "ok"


def test_une_page_en_echec_est_dite():
    assert "2 page(s)" in dialecte.verifier_integrite(_Simulee("on", 2))


def test_sommes_actives_et_aucun_echec():
    assert dialecte.verifier_integrite(_Simulee("on", 0)) == "ok"
