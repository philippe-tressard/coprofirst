"""La SUSPENSION appliquée : lecture seule, export ouvert (D20, §4.11 — R6 #1882).

Sur décision signée de l'opérateur de la référence — portée par le bail, jamais
par un appel entrant (règle 5) —, l'installation passe en lecture seule.

## Les règles

1. **Jamais d'arrêt sec ni d'effacement** par la référence : tout se lit ; les
   tâches planifiées, les sauvegardes, les courriels de sécurité et les durées de
   conservation légales de l'exploitant continuent.
2. **Une seule garde, à l'entrée des requêtes** (`GardeSuspension`) : toute
   ÉCRITURE — `POST`, `PUT`, `PATCH`, `DELETE` — reçoit 403 avant toute route,
   sauf les gestes de `OUVERTS_EN_SUSPENSION`, chacun avec sa raison. Une route
   ajoutée demain est fermée sans qu'on y pense : c'est une liste BLANCHE.
3. **L'export reste ouvert à l'administrateur de chaque copropriété** : `POST
   /admin/export-copropriete` (et sa vérification) ; la lecture de l'archive est
   un `GET`.
4. **Le seul chemin du retour** est une décision de la référence (« rétablir »),
   reçue avec le bail : l'opérateur de l'installation peut le redemander sans
   attendre la nuit (`POST /admin/installation/bail`, ouvert).
5. **Un bail échu n'est jamais une suspension** (D19) : il ramène au mode limité
   (`constat.constater`), et rien ici ne s'applique. Le retour au constat
   (`REGISTRE_CONSTAT`) lève aussi la garde (`regime.regime_applique`).

🔒 `tests/test_registre_suspension.py` balaie toutes les routes d'écriture montées.

⚠️ Ce que la garde ne voit pas : un `GET` qui écrirait. Il n'en existe pas qui
modifie une donnée de la copropriété ; une lecture qui laisse une trace (dernière
connexion, journal) n'en est pas une.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse

from app.inscription.regime import est_suspendue
from app.utils import gestes_http

#: La clé publique de `GET /config` qui dit à l'écran que l'installation est en lecture
#: seule — le bandeau, la connexion (`utils/config_publique`). Calculée, jamais saisie.
CLE_PUBLIQUE = "installation_suspendue"

#: Les méthodes qui ÉCRIVENT : la garde ne regarde qu'elles.
ECRITURES = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Le refus, pour l'administrateur comme pour un résident : ce qui se passe, ce qui
#: reste possible, quoi faire.
MESSAGE = (
    "Installation suspendue par la référence CoproFirst : elle est en lecture seule. "
    "Tout reste consultable, et l'administrateur de la copropriété peut en exporter les "
    "données (Administration › Maintenance › Export vérifié). Pour la rétablir, "
    "l'opérateur de l'installation s'adresse à la référence."
)

#: Les gestes d'ÉCRITURE qui restent ouverts pendant une suspension, et pourquoi.
OUVERTS_EN_SUSPENSION: dict[tuple[str, str], str] = {
    #  Entrer et lire : la lecture seule suppose une session.
    ("POST", "/auth/login"): "on se connecte pour lire",
    ("POST", "/auth/refresh"): "la session se renouvelle",
    ("POST", "/auth/logout"): "on se déconnecte",
    #  La sécurité du compte n'est pas un service (§4.8) : elle ne se suspend pas.
    ("POST", "/auth/change-password"): "sécurité du compte",
    ("POST", "/auth/mot-de-passe-oublie"): "sécurité du compte",
    ("POST", "/auth/reinitialiser-mot-de-passe"): "sécurité du compte",
    ("POST", "/auth/renvoyer-verification"): "sécurité du compte",
    #  Les droits de la personne (RGPD) ne dépendent pas d'un bail.
    ("PATCH", "/auth/me/opt-out-telemetrie"): "droit d'opposition",
    ("DELETE", "/auth/me/telemetrie"): "droit d'effacement de la mesure d'usage",
    ("POST", "/auth/demande-suppression"): "droit à l'effacement : la demande se dépose",
    ("DELETE", "/auth/demande-suppression"): "retirer sa demande d'effacement",
    ("DELETE", "/appareils/{abonnement}"): "couper les notifications d'un appareil",
    ("DELETE", "/montres/{montre_id}"): "révoquer une montre",
    #  Lire ses notifications : l'état de lecture de la personne, rien de la copropriété.
    ("PATCH", "/notifications/{notif_id}/lue"): "lire une notification",
    ("POST", "/notifications/tout-marquer-lu"): "lire ses notifications",
    #  Des calculs servis en POST, qui n'écrivent rien.
    ("POST", "/lectures/apercu"): "dit qui lirait une saisie, sans rien écrire",
    ("POST", "/perimetres/libelle"): "nomme une sélection, sans rien écrire",
    ("POST", "/plateforme/aiguillage"): "redirige vers une copropriété, sans rien écrire",
    #  L'export, ouvert à l'administrateur de chaque copropriété (D20).
    ("POST", "/admin/export-copropriete"): "l'export reste ouvert (D20)",
    ("POST", "/admin/export-copropriete/verifier"): "vérifier l'export avant de le prendre",
    #  Le chemin du retour : un bail redemandé à la référence (règle 4).
    ("POST", "/admin/installation/bail"): "redemander le bail, seul chemin du retour",
    ("POST", "/admin/installation/inscription"): "rectifier le contact déclaré à la référence",
    #  L'exploitation de la machine : sauvegardes, santé, maintenance (règle 1).
    ("POST", "/admin/sauvegardes/maintenant"): "une sauvegarde ne s'arrête jamais",
    ("POST", "/admin/controle-sante"): "le contrôle de santé de l'installation",
    ("POST", "/admin/maintenance/lancer"): "la maintenance de la machine",
    ("POST", "/admin/maintenance/rapport"): "les scripts d'exploitation rendent compte",
    ("POST", "/admin/maintenance/battement"): "les scripts d'exploitation rendent compte",
    ("POST", "/admin/maintenance/bail"): "la mise à jour nocturne lit le bail",
    ("POST", "/admin/maintenance/archives-affaires/copiees"): "la copie hors site se déclare",
    ("POST", "/admin/maintenance/purges"): "les durées de conservation légales courent",
}

_OUVERTS = gestes_http.indexer(OUVERTS_EN_SUSPENSION)


def geste_ferme(methode: str, chemin: str) -> bool:
    """PURE : ce geste est-il refusé à une installation suspendue ? (règle 2)"""
    return methode in ECRITURES and not gestes_http.reconnu(_OUVERTS, methode, chemin)


class GardeSuspension:
    """Intergiciel ASGI : une installation suspendue refuse toute écriture hors liste."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        #  L'ordre compte : la méthode d'abord (un `GET` ne lit pas le bail), puis
        #  la liste, puis seulement le bail — lu sur le disque, sans appel.
        if (
            scope["type"] == "http"
            and geste_ferme(scope["method"], scope["path"])
            and est_suspendue()
        ):
            await JSONResponse({"detail": MESSAGE}, status_code=403)(scope, receive, send)
            return
        await self.app(scope, receive, send)
