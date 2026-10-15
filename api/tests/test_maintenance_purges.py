"""Les purges hebdomadaires s'exécutent DANS l'API, derrière la clé (#1232).

`maintenance.sh` purge chaque dimanche par `POST /admin/maintenance/purges`, qui
passe par `utils.maintenance.purger` — la même fonction que la maintenance
lancée depuis l'administration.

Ce que ces tests verrouillent :
1. sans clé, ou avec une mauvaise, la route refuse — et ne purge rien ;
2. avec la clé, elle purge VRAIMENT (un jeton expiré part, un valide reste)
   et rend les comptes que le script écrit dans son rapport.

`test_acces_base_scripts.py` tient l'autre moitié : plus aucun script
n'importe `app.database`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import get_settings
from app.main import app
from app.models.core import RoleUtilisateur
from app.models.jetons import EmailVerificationToken, RefreshToken
from tests.aides_base import compte, moteur_de_test

CLE = "cle-de-test-des-purges"
ROUTE = "/admin/maintenance/purges"


@pytest.fixture(name="moteur")
def moteur_fixture(monkeypatch):
    moteur = moteur_de_test()
    #  `purger` demande le moteur au contexte de copropriété (#1744), qui le lit
    #  dans `app.database` : c'est lui qu'on remplace, pas une dépendance
    #  FastAPI — la fonction sert aussi hors requête.
    monkeypatch.setattr("app.database.engine", moteur)
    monkeypatch.setattr(get_settings(), "maintenance_key", CLE)
    return moteur


def _jetons(moteur) -> list[str]:
    with Session(moteur) as s:
        user = compte(
            s, prefixe="m", nom="M", prenom="M", roles_json=RoleUtilisateur.résident.value
        )
        maintenant = datetime.now(timezone.utc)
        s.add(
            RefreshToken(user_id=user.id, token="expire", expires_at=maintenant - timedelta(days=1))
        )
        s.add(
            RefreshToken(user_id=user.id, token="valide", expires_at=maintenant + timedelta(days=1))
        )
        s.commit()
    return ["expire", "valide"]


def _restants(moteur) -> set[str]:
    with Session(moteur) as s:
        return {t.token for t in s.exec(select(RefreshToken)).all()}


@pytest.mark.parametrize("entetes", [{}, {"x-maintenance-key": "mauvaise"}])
def test_sans_la_cle_rien_n_est_purge(moteur, entetes):
    _jetons(moteur)
    reponse = TestClient(app).post(ROUTE, headers=entetes)
    assert reponse.status_code == 403
    assert _restants(moteur) == {"expire", "valide"}


def test_avec_la_cle_les_purges_ont_lieu_et_rendent_leurs_comptes(moteur):
    _jetons(moteur)
    reponse = TestClient(app).post(ROUTE, headers={"x-maintenance-key": CLE})
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["erreurs"] == []
    assert corps["comptes"]["tokens"] == 1
    #  Les clés que `maintenance.sh` lit pour son rapport : les renommer côté
    #  API sans le script ferait des zéros silencieux dans l'historique.
    assert set(corps["comptes"]) == {
        "tokens",
        "prt",
        "verifications",
        "notifications",
        "historique",
        "emails",
        "ia",
        "whatsapp",
        "releves",
    }
    assert _restants(moteur) == {"valide"}


def test_les_jetons_de_verification_perimes_ou_utilises_sont_purges(moteur):
    """La seule famille de jetons qu'aucune purge ne touchait (#1382)."""
    _jetons(moteur)
    maintenant = datetime.now(timezone.utc)
    with Session(moteur) as s:
        for jeton, expire, utilise in (
            ("perime", maintenant - timedelta(days=1), False),
            ("utilise", maintenant + timedelta(days=1), True),
            ("en-attente", maintenant + timedelta(days=1), False),
        ):
            s.add(EmailVerificationToken(user_id=1, token=jeton, expires_at=expire, used=utilise))
        s.commit()
    corps = TestClient(app).post(ROUTE, headers={"x-maintenance-key": CLE}).json()
    assert corps["comptes"]["verifications"] == 2
    with Session(moteur) as s:
        restants = {t.token for t in s.exec(select(EmailVerificationToken)).all()}
    #  Un lien de vérification encore valide, dans une boîte de réception,
    #  doit continuer de marcher.
    assert restants == {"en-attente"}
