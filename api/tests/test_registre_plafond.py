"""Le plafond du MODE LIMITÉ appliqué : 5 comptes actifs au plus (D18 — R6 #1882).

Ce que ce fichier tient (spec `multi-coproprietes.md` §4.11, règles 2, 4 et 7) :

1. le sixième compte est refusé — à la validation, à la réactivation, et à la base
   elle-même, quelle que soit la route ; les cinq premiers restent intacts ;
2. aucun compte existant n'est désactivé, masqué ni effacé, même au-delà du plafond ;
3. la référence ne passe jamais en mode limité ; la démo et l'essai en sont exemptés ;
4. référence éteinte : une installation active le reste pendant toute la durée de
   son bail, sans un appel ; échu, le bail ramène au mode limité ;
5. le retour au constat (`REGISTRE_CONSTAT`) lève le plafond sans nouvelle image.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session

from app.config import get_settings
from app.inscription import plafond, regime
from app.inscription.client import constat_courant
from app.models.core import RoleUtilisateur, StatutUtilisateur, Utilisateur
from app.utils import horloge, installation
from tests.aides_base import compte
from tests.aides_baux import replique_au_bail
from tests.aides_http import base_http, client_http

PLAFOND = regime.PLAFOND_COMPTES_ACTIFS


@pytest.fixture
def moteur():
    with base_http() as moteur:
        yield moteur


def _non_inscrite(monkeypatch, tmp_path) -> None:
    """Une RÉPLIQUE jamais inscrite : le cas le plus courant du mode limité."""
    reglages = get_settings()
    monkeypatch.setattr(reglages, "installation_dir", str(tmp_path / "installation"))
    monkeypatch.setattr(reglages, "installation_essai", False)
    monkeypatch.setattr(reglages, "registre_constat", False)
    monkeypatch.setattr(installation, "role_installation", lambda valeur=None: "replique")
    assert constat_courant().etat == "limitee"


@pytest.fixture
def non_inscrite(monkeypatch, tmp_path):
    _non_inscrite(monkeypatch, tmp_path)


def _ouvrir(moteur, n: int) -> list[int]:
    with Session(moteur) as s:
        return [compte(s).id for _ in range(n)]


def _en_attente(moteur) -> int:
    with Session(moteur) as s:
        return compte(s, actif=False).id


def _actifs(moteur, ids) -> list[bool]:
    with Session(moteur) as s:
        return [s.get(Utilisateur, i).actif for i in ids]


# ── 1. Le sixième compte ─────────────────────────────────────────────────────


def test_le_sixieme_compte_est_refuse_a_la_validation(moteur, non_inscrite):
    http, admin = client_http(moteur, RoleUtilisateur.admin)
    cinq = [admin, *_ouvrir(moteur, PLAFOND - 1)]
    attente = _en_attente(moteur)

    reponse = http.post(f"/admin/comptes/{attente}/traiter", json={"action": "valider"})

    assert reponse.status_code == 409
    assert reponse.json()["detail"] == plafond.MESSAGE
    assert _actifs(moteur, cinq) == [True] * PLAFOND, "les cinq premiers restent intacts"
    with Session(moteur) as s:
        refuse = s.get(Utilisateur, attente)
        assert not refuse.actif and refuse.decision_compte_le is None, "il attend toujours"


def test_le_message_dit_quoi_faire():
    assert "Administration › Utilisateurs" in plafond.MESSAGE
    assert "Aucun compte existant n'est touché" in plafond.MESSAGE


def test_la_reactivation_est_un_sixieme_compte(moteur, non_inscrite):
    http, admin = client_http(moteur, RoleUtilisateur.admin)
    autres = _ouvrir(moteur, PLAFOND - 1)
    sorti = autres[0]
    assert http.patch(f"/admin/utilisateurs/{sorti}", json={"actif": False}).status_code == 200
    nouveau = _ouvrir(moteur, 1)[0]  # la place libérée est reprise

    reponse = http.patch(f"/admin/utilisateurs/{sorti}", json={"actif": True})

    assert reponse.status_code == 409 and reponse.json()["detail"] == plafond.MESSAGE
    assert _actifs(moteur, [admin, *autres[1:], nouveau]) == [True] * PLAFOND
    assert http.patch(f"/admin/utilisateurs/{nouveau}", json={"actif": False}).status_code == 200
    assert http.patch(f"/admin/utilisateurs/{sorti}", json={"actif": True}).status_code == 200


def test_la_porte_est_a_la_base_pas_a_la_route(moteur, non_inscrite):
    """Aucune route n'est en jeu : la prochaine qui ouvrirait un compte est couverte."""
    _ouvrir(moteur, PLAFOND)
    with Session(moteur) as s, pytest.raises(plafond.PlafondAtteint):
        compte(s)
    attente = _en_attente(moteur)
    with Session(moteur) as s:
        #  Objet expiré par le commit, écrit sans être relu : l'« avant » vient de la base.
        user = s.get(Utilisateur, attente)
        s.commit()
        user.actif = True
        with pytest.raises(plafond.PlafondAtteint):
            s.commit()


def test_un_compte_technique_ne_compte_pas(moteur, non_inscrite):
    _ouvrir(moteur, PLAFOND)
    with Session(moteur) as s:
        compte(s, statut=StatutUtilisateur.admin_technique)
        with pytest.raises(plafond.PlafondAtteint):
            compte(s)


# ── 2. Rien de ce qui existe n'est touché ────────────────────────────────────


def test_les_comptes_au_dela_du_plafond_restent_intacts(moteur, monkeypatch, tmp_path):
    """Une installation qui comptait déjà plus de 5 comptes les garde TOUS, et ils restent
    modifiables ; seul un compte de PLUS est refusé."""
    http, admin = client_http(moteur, RoleUtilisateur.admin)
    sept = [admin, *_ouvrir(moteur, PLAFOND + 1)]  # avant le mode limité
    _non_inscrite(monkeypatch, tmp_path)
    assert regime.plafond_applique() is not None

    assert http.patch(f"/admin/utilisateurs/{sept[1]}", json={"nom": "AUTRE"}).status_code == 200
    lus = {u["id"]: u["actif"] for u in http.get("/admin/utilisateurs").json()}
    assert all(lus[i] for i in sept), "aucun compte désactivé, masqué ni effacé"
    assert http.patch(f"/admin/utilisateurs/{sept[1]}", json={"actif": False}).status_code == 200
    assert http.patch(f"/admin/utilisateurs/{sept[1]}", json={"actif": True}).status_code == 409


# ── 3. Qui n'est jamais limité ───────────────────────────────────────────────


def test_la_reference_ne_passe_jamais_en_mode_limite(moteur, monkeypatch, tmp_path):
    reglages = get_settings()
    monkeypatch.setattr(reglages, "installation_dir", str(tmp_path / "installation"))
    monkeypatch.setattr(installation, "role_installation", lambda valeur=None: "reference")
    assert constat_courant().etat == "reference"
    assert regime.plafond_applique() is None and not regime.est_suspendue()
    _ouvrir(moteur, PLAFOND + 3)


@pytest.mark.parametrize("role", ["", "inconnu"])
def test_un_role_inconnu_n_est_pas_une_replique(moteur, monkeypatch, role):
    monkeypatch.setattr(get_settings(), "role_installation", role)
    assert regime.plafond_applique() is None
    _ouvrir(moteur, PLAFOND + 1)


def test_la_demo_est_exemptee(moteur, non_inscrite, monkeypatch):
    monkeypatch.setattr(get_settings(), "mode_demo", "oui")
    assert regime.plafond_applique() is None
    _ouvrir(moteur, PLAFOND + 3)


def test_le_retour_au_constat_leve_le_plafond(moteur, non_inscrite, monkeypatch):
    monkeypatch.setattr(get_settings(), "registre_constat", True)
    assert regime.plafond_applique() is None
    assert constat_courant().etat == "limitee", "l'état se constate toujours"
    _ouvrir(moteur, PLAFOND + 1)


# ── 4. Référence éteinte ─────────────────────────────────────────────────────


def test_reference_eteinte_l_installation_active_le_reste_tout_le_bail(
    moteur, monkeypatch, tmp_path
):
    """Le registre ne répond plus (tout appel échoue) : jusqu'à la dernière seconde du bail,
    l'installation est active et n'a pas de plafond ; échu, il ramène au mode limité."""
    echeance = replique_au_bail(monkeypatch, tmp_path)
    for instant in (horloge.maintenant(), echeance - timedelta(seconds=1)):
        monkeypatch.setattr(horloge, "maintenant", lambda i=instant: i)
        assert constat_courant().etat == "active"
        assert regime.plafond_applique() is None
    _ouvrir(moteur, PLAFOND + 1)

    monkeypatch.setattr(horloge, "maintenant", lambda: echeance + timedelta(seconds=1))
    assert constat_courant().etat == "limitee"
    assert not regime.est_suspendue(), "un bail échu ne met jamais en lecture seule"
    with Session(moteur) as s, pytest.raises(plafond.PlafondAtteint):
        compte(s)
