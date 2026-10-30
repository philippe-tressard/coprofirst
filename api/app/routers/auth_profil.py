"""Router auth/profil — sa fiche personnelle : la lire, la corriger, en demander la modification.

Extrait de `routers/auth.py` le 09/09/2026, au fil de l'eau : ce fichier était à
561 lignes et le contrôle de modularité refuse qu'un fichier déjà au-dessus de
500 grossisse (rang 1 §4). Il fallait y ajouter l'alerte de divergence d'étage.

## Pourquoi cette césure-là

`auth.py` répond à *prouver qu'on est soi* — s'inscrire, se connecter, renouveler
sa session. Ce module-ci répond à *décrire qui l'on est*, et les deux n'ont pas
les mêmes raisons de changer : un champ de plus sur la fiche ne touche jamais au
cycle des jetons. C'est la même césure qu'au 14/08/2026 pour le mot de passe
(`auth_mot_de_passe.py`) et pour la télémétrie (`auth_telemetrie.py`).

Le router porte le même préfixe `/auth` et est monté à part dans `main.py` :
FastAPI additionne les routers, les URL publiques sont donc **rigoureusement
inchangées**. `api/tests/test_endpoints_orphelins.py` le vérifie.

⚠️ `construire_user_read` a suivi, mais dans `utils/`, pas ici : les DEUX routeurs
en ont besoin, et un routeur qui en importe un autre n'est plus un routeur.
"""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import (
    DemandeModificationProfil,
    StatutDemandeProfil,
    StatutUtilisateur,
    Utilisateur,
)
from app.schemas import UserRead
from app.schemas_communs import nom_en_majuscules
from app.utils.alerte_etage import alerter_divergence_etage
from app.utils.limiter import (
    LIMITE_LECTURE_AUTHENTIFIEE,
    LIMITE_PREFERENCE,
    limiter,
)
from app.utils.etages import ETAGE_HORS_BORNES, etage_hors_bornes
from app.utils.demandes_profil import DemandeModifRead, lire_demande
from app.utils.lecture_utilisateur import construire_user_read
from app.utils.verification_adresse import demander_changement_adresse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserRead)
@limiter.limit(LIMITE_LECTURE_AUTHENTIFIEE)
def me(
    request: Request,
    user: Utilisateur = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return construire_user_read(user, session)


class MeUpdate(BaseModel):
    prenom: str | None = None
    nom: str | None = None
    #  Une adresse DIFFÉRENTE n'est qu'une demande : elle exige le mot de passe
    #  actuel, et ne remplace l'ancienne qu'une fois confirmée (#1549).
    email: str | None = None
    mot_de_passe_actuel: str | None = None
    telephone: str | None = None
    societe: str | None = None
    fonction: str | None = None
    #  L'étage où la personne HABITE — modifiable depuis le profil depuis le
    #  08/09/2026. Distinct de `Lot.etage`, qui décrit un BIEN : un bailleur a un
    #  lot au 4ᵉ et habite ailleurs.
    etage: int | None = None
    last_seen_actualites: str | None = None
    preferences_notifications: str | None = None
    restreindre_a_mes_batiments: bool | None = None
    decor_fetes: bool | None = None
    demarche_arrivant: str | None = None

    @field_validator("nom", mode="before")
    @classmethod
    def uppercase_nom(cls, v: str | None) -> str | None:
        return nom_en_majuscules(v)

    @field_validator("prenom", mode="before")
    @classmethod
    def titlecase_prenom(cls, v: str | None) -> str | None:
        return v.strip().title() if v else v


@router.patch("/me", response_model=UserRead)
@limiter.limit(LIMITE_PREFERENCE)
def update_me(
    request: Request,
    body: MeUpdate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    if body.email is not None:
        #  🔴 L'adresse ne s'écrit PAS ici (#1549) : elle s'écrivait sur-le-champ,
        #  sans mot de passe ni re-vérification, et une session volée suffisait à
        #  détourner le compte. La demande éprouve le mot de passe, envoie le lien
        #  à la nouvelle adresse et l'avis à l'ancienne — qui reste celle du
        #  compte jusqu'au clic. EN PREMIER : un refus n'enregistre rien du reste.
        demander_changement_adresse(
            session,
            cible=user,
            acteur=user,
            nouvelle_adresse=body.email,
            mot_de_passe=body.mot_de_passe_actuel,
            background_tasks=background_tasks,
        )
    if body.prenom is not None:
        user.prenom = body.prenom
    if body.nom is not None:
        user.nom = body.nom
    if body.telephone is not None:
        user.telephone = body.telephone
    if body.societe is not None:
        user.societe = body.societe
    if body.fonction is not None:
        user.fonction = body.fonction
    if body.etage is not None:
        #  🔴 SANS validation du conseil syndical, et c'est délibéré (#835).
        #
        #  Le changement de BÂTIMENT passe par `demanderModification` parce
        #  qu'il touche à ce qu'on est dans la copropriété. L'étage ne revendique
        #  rien : c'est un repère de voisinage, comme le téléphone juste
        #  au-dessus. Le mettre derrière une approbation ajouterait une friction
        #  sans rien protéger.
        #
        #  ⚠️ Bornes vérifiées ICI et pas seulement dans l'écran : un champ borné
        #  côté client se poste directement. Elles vivent dans `utils/etages.py`
        #  depuis qu'un SECOND écran saisit un étage (un lot, 09/09/2026).
        if etage_hors_bornes(body.etage):
            raise HTTPException(400, ETAGE_HORS_BORNES)
        #  🔴 La comparaison se fait AVANT l'écriture, et sur un CHANGEMENT réel.
        #  C'est ce qui tient lieu de déduplication : réenregistrer son profil
        #  sans toucher à l'étage ne réalerte pas. Un désaccord que
        #  l'administrateur n'a pas encore tranché produirait sinon un courriel à
        #  chaque sauvegarde — et un canal qu'on ignore est un canal absent
        #  (`standards/07`). Une valeur NOUVELLE, elle, est une information neuve :
        #  elle mérite sa propre alerte.
        if body.etage != user.etage:
            alerter_divergence_etage(session, background_tasks, user, body.etage)
        user.etage = body.etage
    if body.last_seen_actualites is not None:
        user.last_seen_actualites = datetime.fromisoformat(
            body.last_seen_actualites.replace("Z", "+00:00")
        )
    if body.preferences_notifications is not None:
        user.preferences_notifications = body.preferences_notifications
    if body.restreindre_a_mes_batiments is not None:
        #  L'utilisateur se restreint LUI-MÊME : aucun contrôle de droit à faire,
        #  cette préférence ne peut que lui montrer moins.
        user.restreindre_a_mes_batiments = body.restreindre_a_mes_batiments
    if body.decor_fetes is not None:
        #  Une préférence pour soi : elle n'allume rien que l'administration a éteint.
        user.decor_fetes = body.decor_fetes
    if body.demarche_arrivant is not None:
        if body.demarche_arrivant not in ("nouvel_arrivant", "deja_resident"):
            raise HTTPException(400, "Valeur invalide pour demarche_arrivant")
        user.demarche_arrivant = body.demarche_arrivant
    session.add(user)
    session.commit()
    session.refresh(user)
    return construire_user_read(user, session)


# ── Demandes de modification de profil (statut / bâtiment) ───────────────────


class DemandeModifCreate(BaseModel):
    statut_souhaite: str | None = None
    batiment_id_souhaite: int | None = None
    motif: str | None = None


@router.post("/me/demande-modification", status_code=201, response_model=DemandeModifRead)
@limiter.limit(LIMITE_PREFERENCE)
def creer_demande_modif(
    request: Request,
    body: DemandeModifCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Soumet une demande de changement de type de résident et/ou de bâtiment, soumise à validation CS."""
    if not body.statut_souhaite and not body.batiment_id_souhaite:
        raise HTTPException(400, "Au moins un champ à modifier (statut ou bâtiment) est requis.")

    # Valider le statut si fourni
    if body.statut_souhaite:
        try:
            StatutUtilisateur(body.statut_souhaite)
        except ValueError:
            raise HTTPException(400, f"Statut invalide : {body.statut_souhaite}")

    # Vérifier qu'il n'y a pas déjà une demande en attente
    existante = session.exec(
        select(DemandeModificationProfil).where(
            DemandeModificationProfil.utilisateur_id == user.id,
            DemandeModificationProfil.statut_demande == StatutDemandeProfil.en_attente,
        )
    ).first()
    if existante:
        raise HTTPException(409, "Une demande est déjà en cours. Attendez qu'elle soit traitée.")

    demande = DemandeModificationProfil(
        utilisateur_id=user.id,
        statut_souhaite=body.statut_souhaite,
        batiment_id_souhaite=body.batiment_id_souhaite,
        motif=body.motif,
    )
    session.add(demande)
    session.commit()
    session.refresh(demande)
    return lire_demande(session, demande)


@router.get("/me/demandes-modification", response_model=list[DemandeModifRead])
@limiter.limit(LIMITE_LECTURE_AUTHENTIFIEE)
def mes_demandes_modif(
    request: Request,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Retourne les demandes de modification de profil de l'utilisateur connecté."""
    demandes = session.exec(
        select(DemandeModificationProfil)
        .where(DemandeModificationProfil.utilisateur_id == user.id)
        .order_by(DemandeModificationProfil.cree_le.desc())
        .limit(10)
    ).all()
    return [lire_demande(session, d) for d in demandes]


# ──────────────────────────────────────────────
#  Vérification email
# ──────────────────────────────────────────────
