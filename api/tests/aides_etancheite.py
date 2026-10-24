"""Ce que partagent les deux essais d'étanchéité entre copropriétés (#1746, #2053).

Le témoin planté dans chaque base, le balayage des routes `GET` et son
détecteur : `test_etancheite_coproprietes.py` (deux copropriétés, résolues par un
en-tête d'essai) et `test_etancheite_installation_commune.py` (l'installation
commune réelle, résolue par l'hôte) les emploient l'un et l'autre (#2223).
"""

from __future__ import annotations

import re

from sqlmodel import Session, select

from app.auth.jwt import creer_jeton_acces
from app.main import app
from app.models.copropriete import Copropriete
from app.models.core import RoleUtilisateur
from app.models.tickets import Ticket
from tests.aides_base import compte
from tests.aides_sources import operations_montees

#: Le témoin planté dans A : un mot qu'aucun libellé de l'application ne contient.
MARQUE_A = "Fuitezq"
MARQUE_B = "Temoinb"

#: Les routes GET que le balayage n'appelle pas, avec leur raison.
ROUTES_ECARTEES = {
    "/health": "sans base ni copropriété : la sonde de Caddy",
}

#: Le cas zéro — des ordres de grandeur, pas des valeurs figées.
MINIMUM_ROUTES = 120
MINIMUM_REPONSES_200 = 40
#: Les routes qui rendent le témoin de B pour B (quatre au 10/10/2026).
MINIMUM_LECTURES_B = 3


def temoins_dans(nom: str, s: Session) -> tuple[str, int]:
    """Dans la base `s` : un administrateur, la fiche et une affaire n° 1, tous marqués
    du témoin de `nom`. Rend (jeton de l'administrateur, son identifiant)."""
    marque = MARQUE_A if nom == "a" else MARQUE_B
    admin = compte(
        s,
        prefixe=marque.lower(),
        prenom=marque,
        nom=f"{marque} Gestionnaire",
        role=RoleUtilisateur.admin,
        roles_json="admin",
    )
    ident = admin.id
    jeton = creer_jeton_acces(ident, admin.hashed_password)
    #  Le témoin aussi dans la fiche de la copropriété et dans une
    #  affaire n° 1 : plus de tables marquées, plus de routes qui lisent.
    for fiche in s.exec(select(Copropriete)).all():
        fiche.nom = f"Residence {marque}"
        s.add(fiche)
    s.add(
        Ticket(
            numero=f"TK-{nom}-1",
            titre=f"Affaire {marque}",
            description=f"Description {marque}",
            auteur_id=ident,
        )
    )
    s.commit()
    return jeton, ident


def chemins_get() -> list[str]:
    """Chaque route GET montée, ses paramètres de chemin valant 1 — l'identifiant partagé."""
    chemins = {
        re.sub(r"\{[^}]+\}", "1", chemin)
        for methode, chemin, _route in operations_montees(app)
        if methode == "GET" and chemin not in ROUTES_ECARTEES
    }
    return sorted(chemins)


def fuites(reponses: dict[str, object], marque: str) -> list[str]:
    """Les chemins dont la réponse porte `marque` — le détecteur, témoin compris."""
    return sorted(c for c, r in reponses.items() if marque in r.text)
