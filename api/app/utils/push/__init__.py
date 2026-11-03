"""Les notifications push de l'installation (#2493, lot P2 de `notifications-push.md`).

| Module | La question |
|---|---|
| `envoi` | ce qui part de l'installation vers le relais — un schéma FERMÉ, rien de personnel |
| `transport` | comment cela part — une interface ; le relais (P1, #2494) s'y branchera |
| `porte` | QUAND cela part — la seule porte, appelée par `utils/cloche`, après le commit |
| `appareils` | enregistrer, retirer, purger les appareils d'une personne |
"""
