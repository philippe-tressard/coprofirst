"""Ce que la politique de confidentialité dit des NOTIFICATIONS (#2495, #2535).

Deux paragraphes, écrits UNE fois : le gabarit (`contenus_legaux.DEFAULT_LEGAL`) et
les migrations qui les ont portés dans le texte servi (0329, 0330, 0342) les lisent
ici.

- `NOTIFICATIONS_PUSH` — ce qui part chez Apple ou Google (#2789) quand le service de notifications sur
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

#: Le service tiers qui reçoit une donnée : Apple ou Google, par le relais de CoproFirst.
#:
#: 🔴 #2981 (audit du 23/11/2026) : la rédaction du 16/11 laissait croire que tout avis
#: part vers le téléphone, l'urgent avec une marque de plus. Depuis la décision du
#: 18/11/2026 (#2789), seule l'alerte d'une actualité ⚡ urgente part
#: (`utils/push/porte.TYPE_POUSSE`), toujours au niveau urgent. L'ancienne est gardée
#: littérale : la migration la remplace dans le texte servi.
NOTIFICATIONS_PUSH_ANCIEN = (
    "<li><strong>Notifications sur téléphone (applications iOS et Android)</strong> — "
    "service coupé par défaut, que l'administration peut activer. Si vous utilisez "
    "l'application et autorisez ses notifications, votre téléphone est enregistré auprès de "
    "ce site par le <strong>jeton</strong> que lui attribue le service de notifications de "
    "son système —\xa0le service de notifications d'Apple (APNs) pour un iPhone, Firebase "
    "Cloud Messaging de Google (FCM) pour un téléphone Android\xa0— et par un identifiant "
    "tiré au hasard par "
    "l'application. Pour vous prévenir, ce site transmet ce jeton, cet identifiant et le "
    "niveau de l'avis au <strong>relais de notifications de CoproFirst</strong>, qui les "
    "transmet à ce service avec un texte fixe —\xa0«\xa0Vous avez une nouvelle "
    "notification\xa0»\xa0— et <strong>rien d'autre</strong>\xa0: ni votre nom, ni la "
    "résidence, ni le contenu de l'avis, que l'application lit ensuite sur ce site. Pour un "
    "avis urgent (fuite, ascenseur bloqué), l'envoi porte en plus un niveau «\xa0urgent\xa0», "
    "qui apprend à ce service qu'un avis est urgent, sans dire lequel. Une montre reliée au "
    "téléphone en reprend l'avis, sans rien recevoir de plus. Vous pouvez couper ces "
    "notifications dans les réglages du téléphone.</li>"
)
NOTIFICATIONS_PUSH = (
    "<li><strong>Notifications sur téléphone (applications iOS et Android)</strong> — "
    "service coupé par défaut, que l'administration peut activer. Si vous utilisez "
    "l'application et autorisez ses notifications, votre téléphone est enregistré auprès de "
    "ce site par le <strong>jeton</strong> que lui attribue le service de notifications de "
    "son système —\xa0le service de notifications d'Apple (APNs) pour un iPhone, Firebase "
    "Cloud Messaging de Google (FCM) pour un téléphone Android\xa0— et par un identifiant "
    "tiré au hasard par l'application. <strong>Seule l'alerte d'une actualité marquée "
    "urgente</strong> (fuite, ascenseur bloqué) part vers votre téléphone\xa0; tout autre "
    "avis reste dans l'application. Pour vous prévenir, ce site transmet ce jeton et cet "
    "identifiant au <strong>relais de notifications de CoproFirst</strong>, qui les "
    "transmet à ce service avec un texte fixe —\xa0«\xa0Vous avez une nouvelle "
    "notification\xa0»\xa0—, le niveau «\xa0urgent\xa0» et <strong>rien d'autre</strong>\xa0: "
    "ni votre nom, ni la résidence, ni le contenu de l'avis, que l'application lit ensuite "
    "sur ce site. Une montre reliée au téléphone en reprend l'avis, sans rien recevoir de "
    "plus. Vous pouvez couper ces notifications dans les réglages du téléphone.</li>"
)

#: La conservation, telle que les purges la pratiquent (#2535, décidée le 08/11/2026).
#: #2981 : l'enregistrement part aussi avec le compte (`push/appareils`), et le délai
#: court depuis le dernier RENOUVELLEMENT par l'application, pas depuis la dernière
#: connexion. L'ancienne rédaction reste pour la migration.
CONSERVATION_NOTIFICATIONS_ANCIEN = (
    "<li>Notifications de l'application\xa0: une notification <strong>lue</strong> est "
    f"conservée <strong>{CONSERVATION_JOURS}\xa0jours</strong> après sa création, puis "
    "<strong>supprimée automatiquement</strong>\xa0; une notification non lue reste "
    "jusqu'à ce que vous la lisiez ou la supprimiez. L'enregistrement d'un téléphone "
    "pour les notifications est retiré à la déconnexion, et après "
    f"<strong>{ABANDON_JOURS}\xa0jours</strong> sans connexion.</li>"
)
CONSERVATION_NOTIFICATIONS = CONSERVATION_NOTIFICATIONS_ANCIEN.replace(
    "est retiré à la déconnexion, et après ",
    "est retiré à la déconnexion, à la suppression du compte, et après ",
).replace(
    "\xa0jours</strong> sans connexion.</li>",
    "\xa0jours</strong> sans que l'application l'ait renouvelé.</li>",
)


__all__ = [
    "CONSERVATION_NOTIFICATIONS",
    "CONSERVATION_NOTIFICATIONS_ANCIEN",
    "NOTIFICATIONS_PUSH",
    "NOTIFICATIONS_PUSH_ANCIEN",
]
