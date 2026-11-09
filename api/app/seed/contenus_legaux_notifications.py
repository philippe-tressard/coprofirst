"""Ce que la politique de confidentialité dit des NOTIFICATIONS (#2495, #2535).

Deux paragraphes, écrits UNE fois : le gabarit (`contenus_legaux.CONTENUS`), ses
ajouts (`AJOUTS_1034`) et la migration 0329, qui les insère dans le texte servi, les
lisent ici.

- `NOTIFICATIONS_PUSH` — ce qui part chez Apple quand le service de notifications sur
  téléphone est actif (spécification `specs/architecture/notifications-push.md` §5 :
  un texte fixe, un identifiant tiré au hasard, et le niveau « urgent » d'un avis
  urgent — qui apprend à Apple qu'un avis est urgent, sans dire lequel).
- `CONSERVATION_NOTIFICATIONS` — combien de temps une notification et
  l'enregistrement d'un téléphone sont gardés. Les durées viennent des purges
  elles-mêmes : les recopier ferait mentir le texte au premier changement.

Rangés hors de `contenus_legaux.py`, qui approche des 500 lignes (`standards/02` §6),
comme la licence et l'identité avant eux.
"""

from __future__ import annotations

from app.utils.purge_notifications import CONSERVATION_JOURS
from app.utils.push.appareils import ABANDON_JOURS

#: Le service tiers qui reçoit une donnée : Apple, par le relais de CoproFirst.
NOTIFICATIONS_PUSH = (
    "<li><strong>Notifications sur téléphone (application iOS)</strong> — service coupé "
    "par défaut, que l'administration peut activer. Si vous utilisez l'application et "
    "autorisez ses notifications, votre téléphone est enregistré auprès de ce site par le "
    "<strong>jeton</strong> qu'Apple lui attribue et par un identifiant tiré au hasard par "
    "l'application. Pour vous prévenir, ce site transmet ce jeton, cet identifiant et le "
    "niveau de l'avis au <strong>relais de notifications de CoproFirst</strong>, qui les "
    "transmet au service de notifications d'Apple (APNs) avec un texte fixe —\xa0«\xa0Vous "
    "avez une nouvelle notification\xa0»\xa0— et <strong>rien d'autre</strong>\xa0: ni votre "
    "nom, ni la résidence, ni le contenu de l'avis, que l'application lit ensuite sur ce "
    "site. Pour un avis urgent (fuite, ascenseur bloqué), l'envoi porte en plus le niveau "
    "«\xa0urgent\xa0» d'Apple, qui apprend à Apple qu'un avis est urgent, sans dire lequel. "
    "Vous pouvez couper ces notifications dans les réglages du téléphone.</li>"
)

#: La conservation, telle que les purges la pratiquent (#2535, décidée le 08/11/2026).
CONSERVATION_NOTIFICATIONS = (
    "<li>Notifications de l'application\xa0: une notification <strong>lue</strong> est "
    f"conservée <strong>{CONSERVATION_JOURS}\xa0jours</strong> après sa création, puis "
    "<strong>supprimée automatiquement</strong>\xa0; une notification non lue reste "
    "jusqu'à ce que vous la lisiez ou la supprimiez. L'enregistrement d'un téléphone "
    "pour les notifications est retiré à la déconnexion, et après "
    f"<strong>{ABANDON_JOURS}\xa0jours</strong> sans connexion.</li>"
)


__all__ = ["CONSERVATION_NOTIFICATIONS", "NOTIFICATIONS_PUSH"]
