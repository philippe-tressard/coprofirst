"""Les comptes PUBLICS de la démo (spec `mode-demo.md` §5, lots D3 #1903 et D8 #1932).

Arbitré par l'auteur le 13/10/2026 : on entre dans la démo par le **formulaire de
connexion**, avec des identifiants publiés sur la page « Démo » du site vitrine.
Trois comptes, PARTAGÉS entre tous les visiteurs (M5) :

| Code | Qui |
|---|---|
| `user-cs` | copropriétaire résident, membre du conseil syndical |
| `user-copro` | copropriétaire résident |
| `user-loc` | locataire |

🔴 **Leurs mots de passe sont publics et versionnés**, exprès : ils ne servent qu'en
démo, où le générateur les pose (`app/demo/charger`, qui refuse hors démo).
Ils passent par la règle de robustesse du produit (`verifier_robustesse`) comme
n'importe quel mot de passe — 🔒 `test_demo_comptes_publics.py`. Changer de mot de
passe ou d'adresse est fermé en démo (`utils/demo`, §4.3) : un visiteur ne peut
pas fermer un compte aux autres.

L'**administrateur n'est pas public** : c'est l'administrateur initial d'une
installation standard, que le seed crée (mot de passe dans les journaux du serveur).

Les comptes eux-mêmes sont créés par le jeu de données (`comptes.py`) ; ce module
dit QUI ils sont et comment on s'y connecte. Les noms sont inventés et figurent
dans la liste blanche de `tests/test_identites_fictives.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.roles import RoleUtilisateur, StatutUtilisateur

#: Le domaine des identifiants publiés. Un sous-domaine sans serveur de courrier :
#: rien ne peut y être livré, et aucune porte d'envoi n'est ouverte en démo.
DOMAINE = "demo.coprofirst.fr"


@dataclass(frozen=True)
class Personnage:
    code: str  #: la partie locale de l'identifiant : `user-cs@demo.coprofirst.fr`
    mot_de_passe: str  #: PUBLIC — voir l'en-tête
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


_COPROPRIETAIRE = (RoleUtilisateur.propriétaire, RoleUtilisateur.résident)

PERSONNAGES: dict[str, Personnage] = {
    p.code: p
    for p in (
        Personnage(
            "user-cs",
            "PSWD-user-cs1",
            prenom="Sophie",
            nom="Delmas",
            statut=StatutUtilisateur.copropriétaire_résident,
            roles=(*_COPROPRIETAIRE, RoleUtilisateur.conseil_syndical),
        ),
        Personnage(
            "user-copro",
            "PSWD-user-copro1",
            prenom="Claire",
            nom="Durand",
            statut=StatutUtilisateur.copropriétaire_résident,
            roles=_COPROPRIETAIRE,
        ),
        Personnage(
            "user-loc",
            "PSWD-user-loc1",
            prenom="Bruno",
            nom="Martin",
            statut=StatutUtilisateur.locataire,
            roles=(RoleUtilisateur.résident,),
        ),
    )
}
