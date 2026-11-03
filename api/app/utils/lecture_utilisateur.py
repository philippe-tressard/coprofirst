"""Sérialiser un `Utilisateur` en `UserRead` — bâtiment, rôles, délégations.

Extraite de `routers/auth.py` le 09/09/2026, avec le bloc « profil » : les deux
routeurs qui en sortent (`auth` pour l'inscription et la connexion, `auth_profil`
pour la fiche personnelle) en ont besoin tous les deux.

🔴 **C'est pour cela qu'elle ne pouvait pas rester dans l'un des deux.** Un
`from app.routers.auth import _build_user_read` aurait fait dépendre le second du
premier — un routeur n'est pas une bibliothèque, et le nom souligné disait déjà
qu'il n'était pas fait pour voyager. La duplication aurait suivi au premier champ
ajouté à `UserRead`, comme pour `EvolutionRead` dans les publications (#294).
"""

from __future__ import annotations


from sqlmodel import Session

from app.models.core import Batiment, Utilisateur
from app.schemas import UserRead
from app.utils.batiments import libelle_batiment
from app.utils.logement import libelle_logement
from app.utils.lots_rattaches import lots_de
from app.utils.noms import nom_affiche


def construire_user_read(user: Utilisateur, session: Session) -> UserRead:
    from app.utils.delegations_actives import delegations_de_l_aidant

    batiment_nom = None
    if user.batiment_id:
        bat = session.get(Batiment, user.batiment_id)
        if bat:
            batiment_nom = libelle_batiment(bat)
    # Charger les délégations actives où l'utilisateur est aidant
    deleg_rows = delegations_de_l_aidant(session, user.id)
    delegations_aidant = []
    for d in deleg_rows:
        mandant = session.get(Utilisateur, d.mandant_id)
        if mandant:
            delegations_aidant.append(
                {
                    "delegation_id": d.id,
                    "mandant_id": mandant.id,
                    "mandant_nom": nom_affiche(mandant.prenom, mandant.nom),
                }
            )
    lecture = UserRead.from_orm_with_roles(
        user, batiment_nom=batiment_nom, delegations_aidant=delegations_aidant
    )
    #  Le logement, nommé par le serveur pour le site ET l'app iOS (#2500).
    lecture.libelle_logement = (
        libelle_logement(lots_de(session, user), batiment_nom or "", user.etage) or None
    )
    return lecture
