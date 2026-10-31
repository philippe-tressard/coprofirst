"""Le rôle de l'installation et l'écart de sa version (#1761).

Ce que ces tests tiennent, dans l'ordre des règles de `utils/installation.py` :
le rôle se déclare et se lit à UN endroit, son absence rend « Inconnu » et jamais
« Référence », un verdict de comparaison vient du dépôt et jamais d'une supposition,
et la vérification ne part pas tant que le service est coupé (règle 9 de §4.10).
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.models.core import ConfigSite, RoleUtilisateur
from app.models.roles import ROLE_OPERATEUR
from app.routers.admin import installation as routeur_installation
from app.utils import installation
from tests.aides_http import base_http, client_http
from tests.aides_installation_commune import COPROPRIETES, installation_commune
from tests.aides_sources import modules_app


@pytest.mark.parametrize(
    ("valeur", "attendu"),
    [
        ("reference", "reference"),
        ("Référence", "reference"),
        #  L'ancien nom de la référence, retiré quand les deux `.env` ont dit
        #  `reference` (#1892, 13/10/2026) : il n'est plus lu.
        ("maitre", "inconnu"),
        ("Référence", "reference"),
        (" replique ", "replique"),
        ("réplique", "replique"),
        ("", "inconnu"),
        ("master", "inconnu"),
        ("main", "inconnu"),
    ],
)
def test_un_role_absent_ou_mal_ecrit_est_inconnu_jamais_reference(valeur, attendu):
    assert installation.role_installation(valeur) == attendu


def test_chaque_role_suit_sa_branche():
    assert installation.ROLES["reference"][1] == "main"
    assert installation.ROLES["replique"][1] == "replica"


@pytest.mark.parametrize(
    ("statut", "en_avance", "etat", "retard"),
    [
        ("identical", 0, "a_jour", 0),
        ("ahead", 3, "en_retard", 3),
        ("behind", 0, "ecart", 0),
        ("diverged", 0, "ecart", 0),
        (None, 0, "non_verifie", 0),
        ("bizarre", 0, "non_verifie", 0),
    ],
)
def test_le_verdict_vient_de_la_comparaison(statut, en_avance, etat, retard):
    v = installation.verdict_comparaison(statut, en_avance)
    assert (v.etat, v.retard) == (etat, retard)


class _Reponse:
    def __init__(self, code, corps=None):
        self.status_code, self._corps = code, corps or {}

    def json(self):
        return self._corps


class _Client:
    def __init__(self, reponse=None, erreur=None):
        self.reponse, self.erreur, self.urls = reponse, erreur, []

    def get(self, url, headers=None):
        self.urls.append(url)
        if self.erreur:
            raise self.erreur
        return self.reponse


def test_la_verification_compare_le_commit_a_la_branche():
    client = _Client(_Reponse(200, {"status": "ahead", "ahead_by": 2}))
    v = installation.verifier("7bec36e", "main", client=client)
    assert (v.etat, v.retard) == ("en_retard", 2)
    assert client.urls == [
        f"https://api.github.com/repos/{installation.DEPOT}/compare/7bec36e...main"
    ]


@pytest.mark.parametrize(
    "client",
    [_Client(_Reponse(404)), _Client(erreur=OSError("réseau")), _Client(_Reponse(200, {}))],
)
def test_une_impossibilite_rend_non_verifie_jamais_a_jour(client):
    assert installation.verifier("7bec36e", "main", client=client).etat == "non_verifie"


def test_une_image_sans_commit_n_est_pas_verifiee():
    assert installation.empreinte("dev") == ""
    client = _Client(_Reponse(200, {"status": "identical"}))
    assert installation.verifier("", "main", client=client).etat == "non_verifie"
    assert client.urls == [], "rien ne part sans commit à comparer"


def test_le_role_ne_se_lit_qu_ici():
    """La clé `role_installation` n'est lue que par `utils/installation.py`."""
    lecteurs = [
        m.rel
        for m in modules_app()
        if "role_installation" in m.source
        and m.rel not in ("utils/installation.py", "config.py", "routers/admin/installation.py")
    ]
    assert lecteurs == [], lecteurs


@pytest.fixture
def moteur():
    with base_http() as moteur:
        yield moteur


#  L'administrateur de copropriété n'y a plus accès : le bloc Installation est de la
#  supervision technique, réservée à l'opérateur de la plateforme (#1750).
@pytest.mark.parametrize(
    "role",
    [None, RoleUtilisateur.résident, RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin],
)
def test_la_route_est_reservee_a_l_operateur(moteur, role):
    http, _ = client_http(moteur, role)
    assert http.get("/admin/installation").status_code in (401, 403)


def test_service_coupe_rien_ne_part(moteur, monkeypatch):
    """Par défaut le service est coupé : la route répond sans interroger le dépôt."""
    monkeypatch.setattr(installation, "role_installation", lambda valeur=None: "reference")
    appels = []
    monkeypatch.setattr(
        routeur_installation.installation,
        "verifier",
        lambda *a, **k: appels.append(a) or installation.Verification("a_jour"),
    )
    http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=f"admin,{ROLE_OPERATEUR}")
    corps = http.get("/admin/installation").json()
    assert (corps["role"], corps["branche"], corps["etat"]) == ("reference", "main", "non_verifie")
    assert corps["verification_active"] is False and appels == []


def test_service_active_la_route_verifie(moteur, monkeypatch):
    with Session(moteur) as s:
        s.add(ConfigSite(cle="verification_version_active", valeur="1"))
        s.commit()
    monkeypatch.setattr(installation, "role_installation", lambda valeur=None: "replique")
    monkeypatch.setattr(
        routeur_installation.installation,
        "verifier",
        lambda empreinte, branche: installation.Verification("en_retard", retard=1),
    )
    http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=f"admin,{ROLE_OPERATEUR}")
    corps = http.get("/admin/installation").json()
    assert (corps["libelle"], corps["branche"], corps["etat"], corps["retard"]) == (
        "Réplique",
        "replica",
        "en_retard",
        1,
    )


#  Une ou plusieurs copropriétés : un constat lu par `contexte.est_commune()`,
#  jamais un réglage ni un nombre supposé (#2400, règle 5).
def test_une_installation_propre_sert_une_seule_copropriete(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "coproprietes_fichier", "")
    assert installation.coproprietes_servies() == installation.CoproprietesServies(
        commune=False, nombre=1
    )


def test_une_installation_commune_compte_ses_coproprietes(tmp_path, monkeypatch):
    with installation_commune(tmp_path, monkeypatch):
        servies = installation.coproprietes_servies()
    assert (servies.commune, servies.nombre) == (True, len(COPROPRIETES))


def test_une_declaration_invalide_le_dit_au_lieu_d_un_nombre(tmp_path, monkeypatch):
    with installation_commune(tmp_path, monkeypatch, coproprietes=[{"alias": "?"}]):
        servies = installation.coproprietes_servies()
    assert (servies.commune, servies.nombre) == (True, None)
    assert servies.detail


def test_la_route_dit_le_mode(moteur, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "coproprietes_fichier", "")
    http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=f"admin,{ROLE_OPERATEUR}")
    corps = http.get("/admin/installation").json()
    assert (corps["commune"], corps["nombre_coproprietes"]) == (False, 1)
