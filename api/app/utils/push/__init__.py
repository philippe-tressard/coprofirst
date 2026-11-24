"""Les notifications push de l'installation (#2493, lot P2 de `notifications-push.md`).

| Module | La question |
|---|---|
| `envoi` | ce qui part de l'installation vers le relais — un schéma FERMÉ, rien de personnel |
| `transport` | comment cela part — vers le relais de la plateforme, ou en processus chez la référence |
| `relais` | ce que le relais transmet, chez la référence seule — FCM et APNs ; sans la clé `.p8`, il refuse un appareil `apns` (#2494) |
| `fcm` | le transport vers Firebase Cloud Messaging HTTP v1 (#2789) |
| `apns` | le transport vers APNs, en HTTP/2 (#2494) |
| `porte` | QUAND cela part — la seule porte, appelée par `utils/cloche`, après le commit |
| `appareils` | enregistrer, retirer, purger les appareils d'une personne |
"""
