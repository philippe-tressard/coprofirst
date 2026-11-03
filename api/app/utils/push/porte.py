"""La porte d'envoi des notifications push — une seule, dans la cloche (#2493).

Spécification : `specs/architecture/notifications-push.md` §6.4 (N6).

## Où elle s'ouvre

`noter` n'est appelée que par `utils/cloche._poser`, le seul endroit où une
`Notification` se construit (🔒 `test_cloche_porte_unique.py`). Elle hérite donc
de ce que la cloche décide : le profil (`sonner`) et les motifs système
(`sonner_systeme`). Une cloche qui ne sonne pas ne pousse rien.
🔒 `test_push_porte.py` refuse un appel de `noter` ou du transport ailleurs.

## Quand l'envoi part

1. `noter` retient le destinataire dans la session SQLAlchemy (`session.info`) —
   rien du tout si le service `notifications_push` est coupé (défaut, démo).
2. **Après le commit seulement** (`after_commit`), l'envoi part, dans un fil à
   part : une notification annulée par un `rollback` n'a averti aucun téléphone,
   et la requête qui l'a posée n'attend pas le relais.
3. Un envoi par appareil du destinataire, au niveau `urgent` si l'un des avis du
   commit l'est. Un échec se journalise par l'identifiant de l'appareil — jamais
   son jeton, même tronqué (N8) — et ne remonte jamais à la requête.
4. Le fil travaille dans la copropriété de la requête (`contexte.dans`).
"""

from __future__ import annotations

import logging
import threading

from sqlalchemy import event
from sqlmodel import Session, select

from app import contexte
from app.models.appareils import Appareil
from app.utils.config_site import config_site
from app.utils.push import transport
from app.utils.push.envoi import envoi_pour
from app.utils.push.transport import Resultat
from app.utils.services import SERVICE_PUSH, cle_actif, service_actif

logger = logging.getLogger(__name__)

#: Les destinataires à avertir après le commit : {utilisateur_id: urgent}.
_EN_ATTENTE = "push_en_attente"


def _service_actif(session: Session) -> bool:
    cfg = config_site(session, cle_actif(SERVICE_PUSH))
    return service_actif(cfg, SERVICE_PUSH)


def noter(session: Session, destinataire_id: int, *, urgente: bool) -> None:
    """Retient `destinataire_id`, à avertir quand la transaction sera validée."""
    if not _service_actif(session):
        return
    en_attente = session.info.setdefault(_EN_ATTENTE, {})
    en_attente[destinataire_id] = en_attente.get(destinataire_id, False) or urgente
    if not event.contains(session, "after_commit", _apres_commit):
        event.listen(session, "after_commit", _apres_commit)
        event.listen(session, "after_rollback", _apres_rollback)


def _apres_rollback(session: Session) -> None:
    session.info.pop(_EN_ATTENTE, None)


def _apres_commit(session: Session) -> None:
    en_attente = session.info.pop(_EN_ATTENTE, None)
    if en_attente:
        lancer(contexte.courante(), en_attente)


def lancer(copro: contexte.Copropriete, en_attente: dict[int, bool]) -> None:
    """Hors de la requête : un fil par commit qui a sonné, et rien de plus."""
    threading.Thread(target=avertir, args=(copro, en_attente), daemon=True).start()


def avertir(copro: contexte.Copropriete, en_attente: dict[int, bool]) -> None:
    """Avertit chaque appareil des destinataires, dans leur copropriété — jamais ne lève."""
    try:
        with contexte.dans(copro), contexte.nouvelle_session() as s:
            avertir_dans(s, en_attente)
    except Exception as exc:
        logger.warning("Notifications push : envoi abandonné (%s)", type(exc).__name__)


def avertir_dans(session: Session, en_attente: dict[int, bool]) -> None:
    """Un envoi par appareil ; un jeton périmé chez Apple retire l'appareil."""
    appareils = session.exec(
        select(Appareil).where(Appareil.utilisateur_id.in_(list(en_attente)))  # type: ignore[attr-defined]
    ).all()
    for appareil in appareils:
        if _transmettre(appareil, urgent=en_attente[appareil.utilisateur_id]):
            session.delete(appareil)
    session.commit()


def _transmettre(appareil: Appareil, *, urgent: bool) -> bool:
    """Un envoi ; rend vrai si l'appareil est à retirer (jeton périmé chez Apple)."""
    try:
        resultat = transport.TRANSPORT.transmettre(envoi_pour(appareil, urgent=urgent))
    except Exception as exc:
        #  Le nom de l'exception seul : son message pourrait répéter la requête.
        resultat = Resultat("refuse", f"transport en échec ({type(exc).__name__})")
    logger.info(
        "Notifications push : appareil %s, %s%s%s",
        appareil.id,
        resultat.statut,
        f", apns-id {resultat.apns_id}" if resultat.apns_id else "",
        f" — {resultat.motif}" if resultat.motif else "",
    )
    return resultat.statut == "jeton_perime"


__all__ = ["avertir", "avertir_dans", "lancer", "noter"]
