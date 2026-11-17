"""Le jeton d'une MONTRE — Apple Watch ou Wear OS : lire la cloche, rien d'autre (#2771).

## Le besoin

Les apps montre (coprofirst-ios#226, Wear OS côté coprofirst-android) affichent les
notifications de la cloche. Une montre ne peut pas reprendre la session du téléphone :
elle y est gardée derrière la biométrie, propre à l'appareil. Le téléphone CONNECTÉ
demande donc au serveur un jeton propre à la montre, et le lui transmet.

## Une portée du mécanisme commun

Le jeton d'une montre est un jeton d'APPAREIL (`auth/jetons_appareil`, #2770) : sa
portée, `PORTEES["montre"]`, n'ouvre que `GET /notifications`, en lecture — ni
`GET /auth/me` (le nom de la résidence passe par le téléphone à l'appairage), ni aucun
marquage comme lu. Échéance, rotation, lecture et purge y sont communes avec l'écran
de hall. Ce module ne garde que ce qui est propre à la montre : son émission par le
téléphone (plateforme, plafond par compte, empreinte du compte) et son retrait avec
les sessions du compte.

## Révocable et expirant

- Il **expire** au bout de `PORTEES["montre"].duree` ; seul le téléphone connecté le
  renouvelle (`jetons_appareil.renouveler`).
- Il **tombe** quand le compte change d'empreinte — mot de passe posé, jeton de
  rafraîchissement rejoué (`auth/jwt.empreinte_du_compte`, comparée à chaque lecture) —,
  quand les sessions du compte se ferment (`jetons_rafraichissement.revoquer_sessions`),
  à la suppression du compte (`suppression_compte.CONTENUS_PERSONNELS`), et quand le
  téléphone le RETIRE (`DELETE /montres/{id}`, à sa déconnexion, ou depuis la liste).

🔒 `tests/test_jetons_montre.py`, `tests/test_jetons_appareil.py`.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, delete, select

from app.auth.empreinte_jeton import empreinte
from app.auth.jetons_appareil import echeance, nouveau_brut
from app.auth.jwt import empreinte_du_compte
from app.models.core import Utilisateur
from app.models.jetons import JetonMontre

#: Les montres admises — la même portée pour toutes.
PLATEFORMES = ("watchos", "wearos")
#: Combien de montres par compte, au plus : au-delà, les plus anciennes sont retirées.
MONTRES_PAR_COMPTE = 4


def emettre(
    session: Session, user: Utilisateur, plateforme: str, maintenant: datetime
) -> tuple[JetonMontre, str]:
    """Émet le jeton d'une montre pour `user`. Rend la ligne et le brut, rendu UNE fois.

    Au-delà de `MONTRES_PAR_COMPTE`, retire les plus anciennes. Ne valide pas la transaction.
    """
    brut = nouveau_brut()
    jeton = JetonMontre(
        utilisateur_id=user.id,
        empreinte=empreinte(brut),
        plateforme=plateforme,
        empreinte_compte=empreinte_du_compte(user.hashed_password, user.generation_sessions),
        cree_le=maintenant,
        expire_le=echeance("montre", maintenant),
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


def suivre_le_compte(jeton: JetonMontre, user: Utilisateur) -> None:
    """Au renouvellement par le téléphone CONNECTÉ, le jeton reprend l'empreinte du compte."""
    jeton.empreinte_compte = empreinte_du_compte(user.hashed_password, user.generation_sessions)


def retirer_montres(session: Session, user_id: int) -> int:
    """Retire TOUTES les montres du compte. Ne valide pas la transaction."""
    resultat = session.exec(delete(JetonMontre).where(JetonMontre.utilisateur_id == user_id))
    return resultat.rowcount or 0
