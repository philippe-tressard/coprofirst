"""Le TYPE d'une notification de la cloche : son pictogramme et son libellé (#2802).

Les apps montre (Apple Watch, Wear OS) dessinent sur chaque ligne de la cloche l'icône
du `type` de l'alerte (`NotificationRead.type`, périmètre arrêté le 16/11/2026,
coprofirst-ios#226). Cette table est la seule : publiée aux apps par
`app/contrat/constantes_clients.py` (`typesNotification`), jamais recopiée chez elles.

- `pictogramme` : un nom du catalogue `icones-svg.json` (Lucide), dont les tracés partent
  avec la release (#2792) ;
- `libelle` : ce que dit un lecteur d'écran.

Un type que l'app ne connaît pas (installation plus récente, type d'accès administrable)
prend `TYPE_PAR_DEFAUT`. La couleur d'une urgente reste la marque de danger de la charte
(`urgente`), pas le type.

🔒 `tests/test_types_notification.py` : chaque `type=` passé à la cloche
(`utils/cloche.sonner`, `sonner_systeme`) est une clé de `TYPES_NOTIFICATION` ou se
déclare dynamique ; chaque clé sert ; chaque pictogramme est au catalogue.
"""

from __future__ import annotations

TYPES_NOTIFICATION: dict[str, dict[str, str]] = {
    "ticket_update": {"pictogramme": "ticket", "libelle": "Affaire"},
    "document": {"pictogramme": "file-text", "libelle": "Document"},
    "sondage": {"pictogramme": "bar-chart-3", "libelle": "Sondage"},
    "communaute_reponse": {"pictogramme": "message-square-text", "libelle": "Réponse"},
    "communaute_idee": {"pictogramme": "lightbulb", "libelle": "Idée"},
    "vigik": {"pictogramme": "key-round", "libelle": "Badge"},
    "moderation": {"pictogramme": "flag", "libelle": "Modération"},
    "system": {"pictogramme": "settings", "libelle": "Système"},
    #  L'alerte d'une actualité ⚡ urgente, la seule qui sonne sur un téléphone (#2789).
    "urgence": {"pictogramme": "zap", "libelle": "Alerte"},
}

#: Le type que l'app ne connaît pas.
TYPE_PAR_DEFAUT: dict[str, str] = {"pictogramme": "bell", "libelle": "Notification"}
