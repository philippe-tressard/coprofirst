"""Un jeton d'appareil n'ouvre QUE les routes de sa portée — toutes les routes, chaque portée.

Le mécanisme est un (#2770, #2771) : `auth/jetons_appareil.PORTEES` dit, portée par
portée, les routes qu'un appareil appairé — montre, écran de hall — peut lire. Ce
fichier tient la table de trois façons :

1. **Le balayage** : pour CHAQUE portée, un vrai jeton est émis par son vrai parcours
   (le téléphone connecté pour la montre, l'appairage RFC 8628 pour l'écran), puis
   CHAQUE opération montée de l'application est appelée avec lui seul. Hors de la table,
   le jeton ne doit rien changer à ce qu'un anonyme obtient : refusé là où l'anonyme est
   refusé, rien de plus là où la route est publique. Dans la table, il doit passer.
2. **Le défaut fermé** : portée inconnue, méthode ou chemin absents, segment de trop.
3. **Les deux sens du câblage** : toute route qui lit un jeton d'appareil est dans la
   table, et toute route de la table en lit un.

Une portée neuve sans son émission ici fait échouer `test_chaque_portee_est_balayee`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import deps
from app.auth.jetons_appareil import PORTEES, route_ouverte
from app.main import app
from tests.aides_appareils import jeton_d_ecran, jeton_de_montre
from tests.aides_http import base_http
from tests.aides_sources import chemin_concret, operations_montees, resout

#: Le cas zéro du balayage — un ordre de grandeur, pas une valeur figée.
MINIMUM_OPERATIONS = 300
#: Ce qui dit « refusé » au porteur d'un jeton.
REFUS = (401, 403)


@pytest.fixture()
def moteur(batiments):
    with base_http() as m:
        yield m


#: L'émission réelle de chaque portée.
EMISSIONS = {"montre": jeton_de_montre, "ecran": jeton_d_ecran}


def _operations() -> list[tuple[str, str]]:
    return sorted({(m, c) for m, c, _r in operations_montees(app) if m != "HEAD"})


def test_chaque_portee_est_balayee():
    assert set(EMISSIONS) == set(PORTEES), (
        "une portée sans émission ici n'est pas balayée : ajouter son parcours à EMISSIONS"
    )


@pytest.mark.parametrize("portee", sorted(PORTEES))
def test_un_jeton_d_appareil_n_ouvre_que_les_routes_de_sa_portee(moteur, portee):
    brut = EMISSIONS[portee](moteur)
    appareil = TestClient(app, headers={"Authorization": f"Bearer {brut}"})
    anonyme = TestClient(app)
    operations = _operations()
    assert len(operations) > MINIMUM_OPERATIONS, f"{len(operations)} opérations — cas zéro"
    ouvertes, ecarts = set(), []
    for methode, gabarit in operations:
        chemin = chemin_concret(gabarit)
        avec = appareil.request(methode, chemin)
        if route_ouverte(portee, methode, chemin):
            ouvertes.add((methode, gabarit))
            if avec.status_code in REFUS:
                ecarts.append(f"{methode} {gabarit} : {avec.status_code} DANS la portée")
            continue
        if avec.status_code in REFUS:
            continue
        sans = anonyme.request(methode, chemin)
        if avec.status_code != sans.status_code:
            ecarts.append(
                f"{methode} {gabarit} : {avec.status_code} avec le jeton, {sans.status_code} sans"
            )
    assert not ecarts, f"portée « {portee} » :\n" + "\n".join(ecarts)
    #  Chaque route de la table a bien été rencontrée, et ouverte : la table ne cite rien de mort.
    assert ouvertes == set(PORTEES[portee].routes), ouvertes


def test_une_route_d_ecriture_refuse_le_jeton_d_appareil(moteur):
    ecran = TestClient(app, headers={"Authorization": f"Bearer {jeton_d_ecran(moteur)}"})
    montre = TestClient(app, headers={"Authorization": f"Bearer {jeton_de_montre(moteur)}"})
    for appareil in (ecran, montre):
        assert appareil.delete("/ecrans/1").status_code in REFUS
        assert appareil.post("/annonces-hall", json={}).status_code in REFUS
        assert appareil.post("/notifications/tout-marquer-lu").status_code in REFUS
        assert appareil.post("/montres", json={"plateforme": "watchos"}).status_code in REFUS
    #  Une portée ne lit pas les routes de l'autre.
    assert ecran.get("/notifications").status_code == 403
    assert montre.get("/ecrans/moi/affiches").status_code == 403


def test_la_table_est_fermee_par_defaut():
    assert route_ouverte("ecran", "GET", "/ecrans/moi/affiches")
    assert route_ouverte("ecran", "GET", "/ecrans/moi/affiches/3/images/0")
    assert route_ouverte("montre", "GET", "/notifications")
    refusees = [
        ("inconnue", "GET", "/notifications"),
        ("", "GET", "/notifications"),
        ("ecran", "POST", "/ecrans/moi/affiches"),
        ("ecran", "HEAD", "/ecrans/moi/affiches"),
        ("ecran", "GET", "/ecrans/moi/affiches/"),
        ("ecran", "GET", "/ecrans/moi/affiches/3/images/0/autre"),
        ("ecran", "GET", "/ecrans/moi/affiches/3/images/a/b"),
        ("ecran", "GET", "/ecrans"),
        ("montre", "GET", "/notifications/1"),
        ("montre", "PATCH", "/notifications"),
        ("montre", "GET", "/auth/me"),
    ]
    for portee, methode, chemin in refusees:
        assert not route_ouverte(portee, methode, chemin), (portee, methode, chemin)


def _lit_un_jeton_d_appareil(dependant) -> bool:
    return resout(dependant, (deps.lecteur_de_la_cloche, deps.ecran_appaire, deps._JETON_APPAREIL))


def test_les_deux_sens_du_cablage():
    """Une route qui lit un jeton d'appareil est dans la table ; une route de la table en lit un."""
    lectrices = {
        (m, c)
        for m, c, r in operations_montees(app)
        if m != "HEAD" and _lit_un_jeton_d_appareil(r.dependant)
    }
    assert lectrices, "aucune route ne lit de jeton d'appareil — cas zéro, la lecture a échoué"
    table = {route for p in PORTEES.values() for route in p.routes}
    assert lectrices == table, (
        f"hors table : {lectrices - table} ; sans lecteur : {table - lectrices}"
    )


def test_la_porte_relit_la_table_meme_sur_une_route_qui_prend_la_dependance(moteur):
    """Défense en profondeur : une route qui prendrait `ecran_appaire` HORS de la table — un
    câblage que le test précédent refuse — est refusée quand même, à la requête : la porte
    relit la table sur le chemin DEMANDÉ, pas sur celui que déclare un sous-routeur."""
    from fastapi import APIRouter, Depends, FastAPI

    from app.database import get_session

    essai = FastAPI()
    routeur = APIRouter(prefix="/ecrans")
    sous = APIRouter(prefix="/moi")

    @sous.get("/hors-table")
    def hors_table(_=Depends(deps.ecran_appaire)):
        return {"ouvert": True}

    @sous.post("/affiches")
    def ecriture(_=Depends(deps.ecran_appaire)):
        return {"ouvert": True}

    @sous.get("/affiches")
    def dans_la_table(_=Depends(deps.ecran_appaire)):
        return {"ouvert": True}

    routeur.include_router(sous)
    essai.include_router(routeur)
    essai.dependency_overrides[get_session] = app.dependency_overrides[get_session]
    http = TestClient(essai, headers={"Authorization": f"Bearer {jeton_d_ecran(moteur)}"})
    assert http.get("/ecrans/moi/hors-table").status_code == 403
    assert http.post("/ecrans/moi/affiches").status_code == 403
    assert http.get("/ecrans/moi/affiches").json() == {"ouvert": True}
