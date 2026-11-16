"""Le jeton d'une MONTRE — Apple Watch ou Wear OS : lire la cloche, rien d'autre (#2771).

## Le besoin

Les apps montre (coprofirst-ios#226, Wear OS côté coprofirst-android) affichent les
notifications de la cloche. Une montre ne peut pas reprendre la session du téléphone :
elle y est gardée derrière la biométrie, propre à l'appareil. Le téléphone CONNECTÉ
demande donc au serveur un jeton propre à la montre, et le lui transmet.

## La portée — arrêtée le 16/11/2026

- **`GET /notifications`, en lecture, et rien d'autre.** Ni `GET /auth/me` (le nom de la
  résidence passe par le téléphone à l'appairage), ni aucun marquage comme lu. La règle
  vit dans `auth/deps.lecteur_de_la_cloche`, seule dépendance qui accepte ce jeton : toute
  autre route prend la session par cookie (`get_current_user`), qui ne le lit jamais.
- **Générique** : la même portée pour les deux montres ; `plateforme` ne sert qu'à la
  liste que voit la personne.

## Révocable et expirant

- Il **expire** au bout de `DUREE_JOURS` ; seul le téléphone connecté le renouvelle.
- Il **tombe** quand le compte change d'empreinte — mot de passe posé, jeton de
  rafraîchissement rejoué (`auth/jwt.empreinte_du_compte`, comparée à chaque lecture) —,
  quand les sessions du compte se ferment (`jetons_rafraichissement.revoquer_sessions`),
  à la suppression du compte (`suppression_compte.CONTENUS_PERSONNELS`), et quand le
  téléphone le RETIRE (`DELETE /montres/{id}`, à sa déconnexion, ou depuis la liste).
- Stocké par son **empreinte** (`auth/empreinte_jeton`, #1389) : le brut n'est rendu
  qu'une fois, au téléphone qui l'a demandé, et ne vit ensuite que sur la montre.

🔒 `tests/test_jetons_montre.py`.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, delete, select

from app.auth.empreinte_jeton import empreinte
from app.auth.jwt import empreinte_du_compte
from app.models.core import Utilisateur
from app.models.jetons import JetonMontre

#: Au-delà, la montre cesse de lire jusqu'à ce que le téléphone renouvelle son jeton.
DUREE_JOURS = 30
#: Les montres admises — la même portée pour toutes.
PLATEFORMES = ("watchos", "wearos")
#: Combien de montres par compte, au plus : au-delà, les plus anciennes sont retirées.
MONTRES_PAR_COMPTE = 4


def _empreinte_compte(user: Utilisateur) -> str:
    return empreinte_du_compte(user.hashed_password, user.generation_sessions)


def emettre(
    session: Session, user: Utilisateur, plateforme: str, maintenant: datetime
) -> tuple[JetonMontre, str]:
    """Émet le jeton d'une montre pour `user`. Rend la ligne et le brut, rendu UNE fois.

    Au-delà de `MONTRES_PAR_COMPTE`, retire les plus anciennes. Ne valide pas la transaction.
    """
    brut = secrets.token_urlsafe(32)
    jeton = JetonMontre(
        utilisateur_id=user.id,
        empreinte=empreinte(brut),
        plateforme=plateforme,
        empreinte_compte=_empreinte_compte(user),
        cree_le=maintenant,
        expire_le=maintenant + timedelta(days=DUREE_JOURS),
    )
    session.add(jeton)
    session.flush()
    anciennes = session.exec(
        select(JetonMontre)
        .where(JetonMontre.utilisateur_id == user.id)
        .order_by(JetonMontre.cree_le.desc(), JetonMontre.id.desc())
        .offset(MONTRES_PAR_COMPTE)
    ).all()
    for ancienne in anciennes:
        session.delete(ancienne)
    return jeton, brut


def renouveler(
    session: Session, jeton: JetonMontre, user: Utilisateur, maintenant: datetime
) -> str:
    """Remplace le brut d'un jeton de `user` et repousse son échéance. Rend le neuf.

    L'ancien brut cesse aussitôt de servir. Ne valide pas la transaction.
    """
    brut = secrets.token_urlsafe(32)
    jeton.empreinte = empreinte(brut)
    jeton.empreinte_compte = _empreinte_compte(user)
    jeton.expire_le = maintenant + timedelta(days=DUREE_JOURS)
    session.add(jeton)
    return brut


def compte_du_jeton(session: Session, brut: str, maintenant: datetime) -> Optional[Utilisateur]:
    """Le compte d'un jeton de montre valide, ou `None` : inconnu, échu, compte inactif, ou
    empreinte du compte changée depuis l'émission. Marque la lecture (`vu_le`) et la valide."""
    if not brut:
        return None
    jeton = session.exec(
        select(JetonMontre).where(JetonMontre.empreinte == empreinte(brut))
    ).first()
    if jeton is None or jeton.expire_le <= maintenant:
        return None
    user = session.get(Utilisateur, jeton.utilisateur_id)
    if user is None or not user.actif or jeton.empreinte_compte != _empreinte_compte(user):
        return None
    jeton.vu_le = maintenant
    session.add(jeton)
    session.commit()
    return user


def retirer_montres(session: Session, user_id: int) -> int:
    """Retire TOUTES les montres du compte. Ne valide pas la transaction."""
    resultat = session.exec(delete(JetonMontre).where(JetonMontre.utilisateur_id == user_id))
    return resultat.rowcount or 0


def purger_echus(session: Session, maintenant: datetime) -> int:
    """Supprime les jetons échus. Ne valide pas la transaction."""
    resultat = session.exec(delete(JetonMontre).where(JetonMontre.expire_le <= maintenant))
    return resultat.rowcount or 0
