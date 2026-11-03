"""Enregistrer, retirer, purger les appareils d'une personne (#2493).

Spécification : `specs/architecture/notifications-push.md` §6.2 et §6.3. Un
appareil suit les SESSIONS de la personne — une session fermée ne laisse pas un
téléphone sonner :

| Quand | Qui retire |
|---|---|
| déconnexion | l'application, `DELETE /appareils/{abonnement}` |
| compte désactivé | `retirer_appareils`, appelée par la désactivation |
| compte supprimé | `utils/suppression_compte` (`CONTENUS_PERSONNELS`) |
| jeton périmé chez Apple | la porte d'envoi, sur la réponse du relais |
| abandon (`vu_le` > 60 jours) | la purge de maintenance (`utils/maintenance.purger`) |

Aucune de ces fonctions ne valide la transaction : l'appelant en décide.
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, delete, or_, select

from app.models.appareils import Appareil
from app.utils import horloge

#: Un appareil que l'application n'a pas ré-enregistré depuis ce délai se purge.
ABANDON_JOURS = 60


def enregistrer(
    session: Session, utilisateur_id: int, *, jeton: str, environnement: str, abonnement: str
) -> Appareil:
    """Enregistre ou rafraîchit l'appareil. Un jeton ou un abonnement connu sous un
    autre compte CHANGE DE MAIN : le téléphone a changé de session."""
    connus = session.exec(
        select(Appareil).where(or_(Appareil.jeton == jeton, Appareil.abonnement == abonnement))
    ).all()
    appareil = next((a for a in connus if a.jeton == jeton), None) or (
        connus[0] if connus else None
    )
    for autre in connus:
        if autre is not appareil:
            session.delete(autre)
    session.flush()
    if appareil is None:
        appareil = Appareil(utilisateur_id=utilisateur_id, jeton=jeton, abonnement=abonnement)
    appareil.utilisateur_id = utilisateur_id
    appareil.jeton = jeton
    appareil.abonnement = abonnement
    appareil.environnement = environnement
    appareil.vu_le = horloge.maintenant()
    session.add(appareil)
    session.flush()
    return appareil


def retirer_appareils(session: Session, utilisateur_id: int) -> int:
    """Retire tous les appareils du compte. Rend le nombre retiré."""
    resultat = session.exec(delete(Appareil).where(Appareil.utilisateur_id == utilisateur_id))
    return resultat.rowcount or 0


def purger_abandonnes(session: Session) -> int:
    """Retire les appareils muets depuis `ABANDON_JOURS`. Rend le nombre retiré."""
    limite = horloge.maintenant() - timedelta(days=ABANDON_JOURS)
    resultat = session.exec(delete(Appareil).where(Appareil.vu_le < limite))
    return resultat.rowcount or 0


__all__ = ["ABANDON_JOURS", "enregistrer", "purger_abandonnes", "retirer_appareils"]
