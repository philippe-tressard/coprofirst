"""Ce que lit l'opérateur de la plateforme ne porte aucune donnée personnelle (#1750).

Chantier multi-copropriétés, spec §4.7 et §5.5 (D5) : l'opérateur supervise
l'installation — santé, contrôles, base — et ne lit AUCUNE donnée d'une
copropriété, ni nom, ni courriel, ni contenu d'affaire. Les routes qu'il est seul
à atteindre (`require_operateur`) sont relevées sur l'application montée ; chacune
qui se lit sans effet est appelée sur une base où chaque donnée personnelle porte
un témoin, et aucune réponse ne doit le rendre.

## Ce qu'il ne voit pas — dit, pour ne pas le croire plus large

- les routes À EFFET (lancer une maintenance, un point de contrôle, une purge) :
  elles ne sont pas appelées, leur réponse est un compte (`ROUTES_A_EFFET`) ;
- le TEXTE que les scripts d'exploitation écrivent dans `historique_maintenance`
  (constats, erreurs) : il vient des nœuds, pas de cette base. Le journal de
  sécurité, qui n'écrit jamais de donnée personnelle, en est le modèle
  (`test_journal_securite.py`).
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.main import app
from app.models.core import RoleUtilisateur
from app.models.roles import ROLE_OPERATEUR
from app.models.tickets import Ticket
from tests.aides_base import compte
from tests.aides_http import base_http, client_http
from tests.aides_sources import operations_montees

#: Le témoin planté dans chaque donnée personnelle : un mot qu'aucun libellé ne contient.
TEMOIN = "Personnelzq"

#: Les routes de l'opérateur qui ont un EFFET, et pourquoi elles ne sont pas appelées.
ROUTES_A_EFFET = {
    ("POST", "/admin/maintenance/lancer"): "lance la maintenance ; rend un identifiant de trace",
    ("POST", "/admin/installation/inscription"): "envoie à la référence le contact de "
    "l'administrateur d'INSTALLATION (pas d'un résident) ; rend l'état constaté (#1878)",
    ("POST", "/admin/installation/bail"): "demande le bail à la référence ; rend l'état "
    "constaté (#1878)",
    ("PUT", "/admin/sauvegardes/config"): "règle l'heure et le nombre de versions de la "
    "sauvegarde ; rend la ligne de réglage — des nombres et l'identifiant de qui l'a "
    "modifiée (#2061 : réservée à l'opérateur, comme l'écran)",
}

#: Les routes de l'opérateur qui lisent un OBJET du registre (base `plateforme`), et
#: pourquoi elles ne sont pas appelées ici : leur chemin porte l'identifiant d'une
#: installation, et le registre est éteint dans ce test. Ce qu'elles rendent ne vient
#: d'aucune copropriété — le contact est celui de l'administrateur d'INSTALLATION, que
#: le contrat d'inscription destine à l'opérateur ; `test_registre_installations_admin.py`
#: les éprouve, registre allumé.
ROUTES_DU_REGISTRE = {
    ("GET", "/admin/installations/{identifiant}"): "la fiche d'une installation (R4 #1880)",
    ("POST", "/admin/installations/{identifiant}/decisions"): "valider, suspendre, rétablir, "
    "résilier une installation ; rend sa fiche (R4 #1880)",
    ("PUT", "/admin/installations/{identifiant}/services"): "les services accordés à une "
    "installation ; rend sa fiche (R4 #1880)",
    ("POST", "/admin/installations/{identifiant}/suppression"): "supprimer une installation "
    "résiliée ; ne rend rien (204, #1980)",
    ("PUT", "/admin/installations/{identifiant}/distribution"): "le canal, la vague et la "
    "version épinglée d'une installation ; rend sa fiche (R5 #1881)",
    ("PUT", "/admin/canaux-distribution/{nom}"): "créer ou avancer un canal spécial ; rend les "
    "canaux — des noms et des versions (R5 #1881)",
}

#: Le cas zéro : neuf routes au 10/10/2026 (supervision technique et base).
MINIMUM_ROUTES = 9


def routes_de_l_operateur() -> set[tuple[str, str]]:
    return {
        (methode, chemin)
        for methode, chemin, route in operations_montees(app)
        if any(
            getattr(d.call, "__name__", "") == "require_operateur"
            for d in route.dependant.dependencies
        )
    }


def fuites(reponses: dict, temoin: str = TEMOIN) -> list:
    """Les routes dont la réponse porte le témoin — le détecteur, témoin compris."""
    return sorted(cle for cle, texte in reponses.items() if temoin in texte)


def test_le_releve_voit_les_routes_de_l_operateur():
    routes = routes_de_l_operateur()
    assert len(routes) >= MINIMUM_ROUTES, f"cas zéro : {len(routes)} route(s) de l'opérateur"
    assert set(ROUTES_A_EFFET) <= routes, "une route à effet déclarée n'est plus à l'opérateur"
    assert set(ROUTES_DU_REGISTRE) <= routes, "une route du registre déclarée n'est plus à lui"


def test_aucune_route_de_l_operateur_ne_rend_une_donnee_personnelle():
    with base_http() as moteur:
        with Session(moteur) as s:
            voisin = compte(
                s, prefixe=TEMOIN.lower(), prenom=TEMOIN, nom=f"{TEMOIN} Voisin", telephone=TEMOIN
            )
            s.add(
                Ticket(
                    numero="TK-1",
                    titre=f"Affaire {TEMOIN}",
                    description=f"Chez {TEMOIN}",
                    auteur_id=voisin.id,
                )
            )
            s.commit()
        http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=f"admin,{ROLE_OPERATEUR}")
        lues = sorted(routes_de_l_operateur() - set(ROUTES_A_EFFET) - set(ROUTES_DU_REGISTRE))
        brutes = {(m, c): http.request(m, c) for m, c in lues}
    reponses = {cle: r.text for cle, r in brutes.items()}
    #  Cas zéro : chaque route lue a répondu — un refus ne prouverait rien.
    assert len(lues) >= MINIMUM_ROUTES - len(ROUTES_A_EFFET) - len(ROUTES_DU_REGISTRE)
    assert all(r.status_code == 200 for r in brutes.values()), {
        cle: r.status_code for cle, r in brutes.items() if r.status_code != 200
    }
    assert not fuites(reponses), (
        "Donnée personnelle rendue à l'opérateur de la plateforme (#1750, D5) :\n  "
        + "\n  ".join(f"{m} {c}" for m, c in fuites(reponses))
    )


def test_le_detecteur_voit_le_temoin():
    reponses = {("GET", "/a"): '{"nom": "x"}', ("GET", "/b"): f'{{"nom": "{TEMOIN} Voisin"}}'}
    assert fuites(reponses) == [("GET", "/b")]


@pytest.mark.parametrize(
    "roles, attendu",
    [
        ("admin", 403),
        (f"admin,{ROLE_OPERATEUR}", 200),
        (ROLE_OPERATEUR, 200),
        ("conseil_syndical", 403),
    ],
)
def test_seul_l_operateur_lit_la_supervision(roles, attendu):
    """L'administrateur de copropriété n'y a plus accès ; l'opérateur, même sans être admin."""
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=roles)
        assert http.get("/admin/maintenance/sante").status_code == attendu
