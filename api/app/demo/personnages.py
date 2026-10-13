"""Les personnages de la démo publique (spec `mode-demo.md` §5, lot D3 #1903).

Un personnage est un compte PARTAGÉ (M5) : tous les visiteurs qui cliquent sur
« Résident » sont le même compte. Quatre personnages (§11, question 5) ; la page
d'accueil de CoproFirst en propose trois, la page de connexion de la démo les
quatre.

Les comptes eux-mêmes sont créés par le jeu de données (lot D4) ; ce module dit
QUI ils sont, et l'adresse qui les retrouve. Les noms sont inventés et figurent
dans la liste blanche de `tests/test_identites_fictives.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.roles import RoleUtilisateur, StatutUtilisateur
from app.utils.roles_libelles import libelle_role

#: Le domaine des adresses des personnages : `.invalid` est réservé (RFC 2606) —
#: aucun courriel ne peut y être livré, même si une porte d'envoi s'ouvrait.
DOMAINE = "demo.coprofirst.invalid"


@dataclass(frozen=True)
class Personnage:
    code: str  #: le segment de l'adresse d'entrée : `/api/demo/entrer/{code}`
    libelle: str
    description: str  #: ce que le visiteur verra, pour la page de connexion
    prenom: str
    nom: str
    statut: StatutUtilisateur
    roles: tuple[RoleUtilisateur, ...]

    @property
    def adresse(self) -> str:
        return f"{self.code}@{DOMAINE}"

    @property
    def roles_json(self) -> str:
        return ",".join(r.value for r in self.roles)


PERSONNAGES: dict[str, Personnage] = {
    p.code: p
    for p in (
        Personnage(
            "resident",
            "Résident",
            "Copropriétaire qui habite son lot : ses affaires, l'actualité, les votes.",
            prenom="Claire",
            nom="Durand",
            statut=StatutUtilisateur.copropriétaire_résident,
            roles=(RoleUtilisateur.propriétaire, RoleUtilisateur.résident),
        ),
        Personnage(
            "locataire",
            "Locataire",
            "Locataire d'un lot : ce que la résidence lui ouvre, sans les votes.",
            prenom="Bruno",
            nom="Martin",
            statut=StatutUtilisateur.locataire,
            roles=(RoleUtilisateur.résident,),
        ),
        Personnage(
            "conseil-syndical",
            libelle_role(RoleUtilisateur.conseil_syndical),
            "Membre du conseil : il suit les affaires, publie et modère.",
            prenom="Sophie",
            nom="Delmas",
            statut=StatutUtilisateur.copropriétaire_résident,
            roles=(
                RoleUtilisateur.propriétaire,
                RoleUtilisateur.résident,
                RoleUtilisateur.conseil_syndical,
            ),
        ),
        Personnage(
            "administrateur",
            "Administrateur",
            "Gestionnaire du site : comptes, contenus et administration.",
            prenom="Marc",
            nom="Verdière",
            statut=StatutUtilisateur.admin_technique,
            roles=(RoleUtilisateur.admin,),
        ),
    )
}
