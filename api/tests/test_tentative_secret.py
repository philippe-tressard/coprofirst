"""La limite des secrets se compte sur la TENTATIVE, pas sur l'enregistrement (23/11/2026).

Le profil et la fiche d'un compte n'éprouvent le mot de passe de qui agit qu'à un
changement d'adresse. Poser `LIMITE_SECRET_EPROUVE` sur la route entière bloquait un
administrateur qui corrige plusieurs fiches d'affilée — une régression refusée. La
tentative se compte donc dans la porte (`utils.limiter.compter_tentative_secret`,
appelée par `demander_changement_adresse`), par visiteur.

Les deux sens se prouvent ici, chacun sous une adresse de documentation (RFC 5737) qui
lui est propre : `requete_de_test` change d'adresse à chaque appel, ces tests-ci gardent
la même — c'est ce qu'ils éprouvent.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.auth.jwt import creer_jeton_acces, hash_password
from app.models.core import RoleUtilisateur
from app.utils.limiter import LIMITE_SECRET_EPROUVE
from tests.aides_base import compte
from tests.aides_http import base_http, client_http

MDP = "Mdp-Actuel-1"

#: Au moins soixante enregistrements d'affilée passent (consigne du 23/11/2026).
ENREGISTREMENTS = 60


@pytest.fixture()
def admin_et_cible(monkeypatch):
    """Un administrateur connecté (par la vraie authentification, à travers slowapi),
    et le compte qu'il corrige ; aucun courriel ne part."""

    async def _intercepter(*args, **kwargs):
        return None

    monkeypatch.setattr("app.utils.email.send_email", _intercepter)
    with base_http() as moteur:
        empreinte = hash_password(MDP)
        http, ident = client_http(moteur, RoleUtilisateur.admin, hashed_password=empreinte)
        #  Le jeton d'accès porte l'empreinte du compte : celle du mot de passe posé ici.
        http.cookies.set("access_token", creer_jeton_acces(ident, empreinte))
        with Session(moteur) as s:
            cible = compte(s, prefixe="cible", email_verifie=True).id
        yield http, f"/admin/utilisateurs/{cible}"


def test_des_fiches_corrigees_d_affilee_ne_sont_jamais_limitees(admin_et_cible):
    """Soixante enregistrements ordinaires, d'un même visiteur, dans la même minute,
    à travers l'application — limites de route comprises."""
    http, fiche = admin_et_cible
    statuts = {
        http.patch(fiche, json={"telephone": f"06000000{i:02d}"}).status_code
        for i in range(ENREGISTREMENTS)
    }
    assert statuts == {200}, statuts


def test_les_tentatives_de_secret_sont_comptees_et_refusees_au_dela(admin_et_cible):
    """Au-delà de la limite des secrets, la tentative est refusée — le BON mot de passe
    aussi : sinon la limite ne ferait que ralentir la réponse, pas l'essai. Un
    enregistrement ordinaire, lui, passe toujours."""
    http, fiche = admin_et_cible
    plafond = int(LIMITE_SECRET_EPROUVE.split("/")[0])
    essais = [
        http.patch(fiche, json={"email": f"n{i}@exemple.test", "mot_de_passe_actuel": "x"})
        for i in range(plafond)
    ]
    assert {r.status_code for r in essais} == {400}, "un mauvais mot de passe sous la limite"
    bon = http.patch(fiche, json={"email": "ok@exemple.test", "mot_de_passe_actuel": MDP})
    assert bon.status_code == 429
    assert http.patch(fiche, json={"telephone": "0611111111"}).status_code == 200
