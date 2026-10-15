"""Les anciennes adresses d'actualité et d'événement mènent à l'affaire (#1091, #1092, #1094).

Chaque courriel et chaque message WhatsApp d'une actualité portait
`/actualites#pub-N`, que l'écran résout par `GET /publications/{N}` ; ceux d'un
événement, `/calendrier#ev-N`, résolu par `GET /calendrier/{N}`. Depuis le
23/09/2026, actualités et événements sont des affaires : l'ancien numéro ne vit
plus que sur l'affaire, dans `ticket.promu_depuis_publication_id` ou
`ticket.promu_depuis_evenement_id` — les tables d'origine ont été supprimées.

Les deux routeurs tiennent le même contrat ; chaque test l'éprouve sur les deux
(`REDIRECTIONS`) et liste TOUS les écarts, pas seulement le premier :

1. **410 avec l'affaire** — « ça a existé, voici où c'est parti » ;
2. **404 pour un numéro jamais attribué** — sinon on annoncerait une affaire
   qui n'existe pas ;
3. **plus rien d'autre** sous `/publications` ni sous `/calendrier` : aucun des
   deux paquets ne doit regrossir en silence d'une seconde écriture.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import get_session
from app.main import app
from app.models.core import RoleUtilisateur, Ticket
from tests.aides_base import compte, moteur_de_test

#: (préfixe d'URL, champ de l'affaire qui garde l'ancien numéro, module du routeur,
#:  seule route qui doit y rester)
REDIRECTIONS = (
    ("/publications", "promu_depuis_publication_id", "app.routers.publications", "{pub_id}"),
    ("/calendrier", "promu_depuis_evenement_id", "app.routers.calendrier", "{ev_id}"),
)


@pytest.fixture(name="session")
def session_fixture():
    with Session(moteur_de_test()) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    from app.auth.deps import get_current_user

    lecteur = compte(
        session, prefixe="r", nom="R", prenom="R", roles_json=RoleUtilisateur.résident.value
    )
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: lecteur
    yield TestClient(app), lecteur
    app.dependency_overrides.clear()


def test_un_objet_migre_rend_410_avec_son_affaire(session: Session, client):
    http, lecteur = client
    ecarts = []
    for rang, (prefixe, champ, _module, _route) in enumerate(REDIRECTIONS, start=1):
        ancien_numero = 4240 + rang
        affaire = Ticket(
            numero=f"TK-R{rang:05d}",
            titre="Ancien objet",
            description="x",
            categorie="actualite",
            statut="publie",
            auteur_id=lecteur.id,
            **{champ: ancien_numero},
        )
        session.add(affaire)
        session.commit()

        r = http.get(f"{prefixe}/{ancien_numero}")
        if r.status_code != 410:
            ecarts.append(f"{prefixe}/{ancien_numero} : {r.status_code} au lieu de 410 — {r.text}")
        elif r.json()["detail"].get("promu_en_affaire") != affaire.id:
            ecarts.append(f"{prefixe}/{ancien_numero} : n'annonce pas l'affaire {affaire.id}")
    assert not ecarts, "\n".join(ecarts)


def test_un_numero_jamais_attribue_rend_404(client):
    http, _ = client
    ecarts = [
        f"{prefixe}/999999 : {code}"
        for prefixe, *_ in REDIRECTIONS
        if (code := http.get(f"{prefixe}/999999").status_code) != 404
    ]
    assert not ecarts, "un numéro jamais attribué doit rendre 404 :\n" + "\n".join(ecarts)


def test_il_ne_reste_que_la_redirection():
    """Aucun des deux routeurs ne doit regrossir en silence d'une seconde écriture."""
    #  Le routeur du paquet, et non `app.routes` : cette version de FastAPI
    #  n'aplatit plus les routes incluses (`test_routeurs_montes.py`).
    ecarts = []
    for prefixe, _champ, module, route in REDIRECTIONS:
        routeur = importlib.import_module(module).router
        routes = sorted((sorted(r.methods), r.path) for r in routeur.routes)
        attendues = [(["GET"], f"{prefixe}/{route}")]
        if routes != attendues:
            ecarts.append(f"{module} : {routes} au lieu de {attendues}")
    assert not ecarts, "\n".join(ecarts)
