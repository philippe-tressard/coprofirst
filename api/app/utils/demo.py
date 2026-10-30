"""Le mode démo de l'installation (spec `specs/architecture/mode-demo.md`, lot D1 #1901).

Une installation standard à laquelle on ajoute `MODE_DEMO=oui` devient la démo
publique de CoproFirst : n'importe quel visiteur y entre sans créer de compte, par
un compte partagé dont les identifiants sont publiés (#1932). Ce module porte ce qui, dans ce mode, est FERMÉ.

## Les règles

1. **Un réglage de l'installation, pas une variante du code** (M1) : il se déclare
   dans `.env` et se lit ICI seulement (`est_demo`). Il ne s'écrit jamais depuis
   l'interface : un administrateur de démo — c'est-à-dire n'importe quel
   visiteur — ne peut pas en sortir.
2. **Absent ou mal écrit → pas de démo** : seules les valeurs de `_OUI` l'allument.
3. **Les gestes fermés vivent dans UN registre** (`GESTES_FERMES`, M3), appliqué
   par UNE garde à l'entrée des requêtes (`GardeDemo`) : jamais une vérification
   recopiée route par route, qu'une route ajoutée plus tard oublierait.
4. **Le registre suit les routes** : 🔒 `tests/test_mode_demo.py` parcourt toutes les
   routes montées et exige que chacune de `PERIMETRE` soit fermée ou déclarée
   ouverte exprès (`OUVERTS_EXPRES`), avec sa raison.
5. **Les fichiers reçus** (M10) se ferment aussi à leur porte (`utils/fichiers`) :
   une route qui accepte une pièce jointe sans être un téléversement dédié — une
   affaire avec photo — passe par elle.

6. **Rien ne part vers l'extérieur** (lot D2, #1902) : chaque PORTE d'appel sortant
   — moteur de courriel, bridge WhatsApp, fournisseur d'IA, boîte IMAP, dépôt
   GitHub — refuse en démo, quelle que soit la configuration en base, qu'un
   administrateur de démo peut réécrire. `exiger_hors_demo` est la porte des
   appels réseau ; le moteur de courriel, lui, se ferme par `envoi_actif`.
   Restent permis, exprès : les échanges avec le REGISTRE des installations
   (`app/inscription/` — la démo s'y inscrit, M11) et les alertes de PLATEFORME
   à l'opérateur (`utils/sante_plateforme`) : aucun visiteur ne les déclenche.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from fastapi.responses import JSONResponse

from app.config import get_settings

#: La clé publique de `GET /config` qui dit au front que l'installation est une
#: démo. Écrite ici, pour que le mot `mode_demo` ne se lise nulle part ailleurs.
CLE_PUBLIQUE = "mode_demo"

#: Le début de toute réponse refusée en démo.
MESSAGE = "Indisponible en démonstration."

_OUI = {"oui", "1", "true", "yes", "on"}


def est_demo(valeur: Optional[str] = None) -> bool:
    """PURE sur sa valeur : cette installation est-elle la démo publique ? (règle 2)."""
    brut = get_settings().mode_demo if valeur is None else valeur
    return (brut or "").strip().lower() in _OUI


@dataclass(frozen=True)
class Famille:
    """Une famille de gestes fermés en démo, et pourquoi."""

    nom: str
    raison: str
    gestes: tuple[tuple[str, str], ...]


#: Les gestes FERMÉS en démo — `(méthode, chemin de la route)`, sans le préfixe
#: `/api` que pose Caddy. Relevé du 13/10/2026 (spec §4.3).
GESTES_FERMES: tuple[Famille, ...] = (
    Famille(
        "Inscription et comptes anonymes",
        "On entre dans la démo par un compte publié, sans créer de compte.",
        (
            ("POST", "/auth/register"),
            ("POST", "/auth/renvoyer-verification"),
            ("POST", "/auth/mot-de-passe-oublie"),
            ("POST", "/auth/reinitialiser-mot-de-passe"),
        ),
    ),
    Famille(
        "Identité des comptes partagés",
        "Les comptes publiés sont partagés entre tous les visiteurs.",
        (
            ("PATCH", "/auth/me"),
            ("POST", "/auth/change-password"),
            ("PATCH", "/admin/utilisateurs/{user_id}"),
            ("DELETE", "/admin/utilisateurs/{user_id}"),
            ("POST", "/admin/utilisateurs/{user_id}/ajouter-role"),
            ("POST", "/admin/utilisateurs/{user_id}/retirer-role"),
            ("PATCH", "/admin/utilisateurs/{user_id}/ban-communaute"),
        ),
    ),
    Famille(
        "Réglages et secrets",
        "La configuration de la démo ne se modifie pas.",
        (
            ("PUT", "/config"),
            ("POST", "/config/logo"),
            ("DELETE", "/config/logo"),
            ("PUT", "/config/palette"),
            ("POST", "/config/textes-legaux/relecture"),
            ("PATCH", "/copropriete"),
            ("POST", "/perimetres"),
            ("PATCH", "/perimetres/{perimetre_id}"),
            ("DELETE", "/perimetres/{perimetre_id}"),
            ("POST", "/perimetres/{perimetre_id}/dupliquer"),
            ("PATCH", "/admin/modeles-email/{modele_id}"),
            ("POST", "/admin/modeles-email/reinitialiser"),
            ("POST", "/admin/modeles-email/{modele_id}/reinitialiser"),
        ),
    ),
    Famille(
        "Canaux d'envoi",
        "Aucun courriel, message ni appel à l'IA ne part de la démo.",
        (
            ("POST", "/config/smtp-test"),
            ("POST", "/config/imap-test"),
            ("POST", "/config/whatsapp-test"),
            ("POST", "/config/llm-test"),
            ("POST", "/config/llm-tarif"),
            ("PUT", "/config/whatsapp-scheduled/{item_id}"),
            ("GET", "/config/whatsapp-qr"),
            ("GET", "/config/whatsapp-status"),
            ("GET", "/config/llm-modeles"),
        ),
    ),
    Famille(
        "Exploitation",
        "La machine de démonstration ne s'administre pas depuis l'interface.",
        (
            ("POST", "/admin/sauvegardes/maintenant"),
            ("PUT", "/admin/sauvegardes/config"),
            ("POST", "/admin/maintenance/lancer"),
            ("POST", "/admin/maintenance/purges"),
            #  L'accusé de copie des archives d'affaires (#2014) : la démo n'en produit pas.
            ("POST", "/admin/maintenance/archives-affaires/copiees"),
            ("POST", "/admin/installations/{identifiant}/decisions"),
            ("PUT", "/admin/installations/{identifiant}/services"),
            ("PUT", "/admin/installations/{identifiant}/distribution"),
            ("POST", "/admin/installations/{identifiant}/suppression"),
            ("POST", "/admin/export-copropriete"),
            ("POST", "/admin/export-copropriete/verifier"),
            ("GET", "/admin/export-copropriete/dernier"),
            ("POST", "/admin/controle-sante"),
            ("POST", "/admin/telemetry/agreger"),
        ),
    ),
    Famille(
        "Téléversements",
        "Les visiteurs ne déposent pas de fichiers ; la démo apporte les siens.",
        (
            ("POST", "/uploads/avatar"),
            ("POST", "/uploads/fichier"),
            ("POST", "/uploads/residence"),
            ("POST", "/lots/admin/imports/upload"),
            ("POST", "/acces/admin/imports/upload"),
            ("POST", "/acces/admin/imports-vigik/upload"),
        ),
    ),
    Famille(
        "Partage par courriel",
        "Aucun courriel ne part de la démo.",
        (("POST", "/partage"),),
    ),
)

#: Les routes que le registre doit couvrir : `(méthodes, motif du chemin)`. Toute
#: route montée qui y répond est fermée, ou déclarée dans `OUVERTS_EXPRES` (règle 4).
#: `None` = toutes les méthodes.
PERIMETRE: tuple[tuple[Optional[frozenset[str]], str], ...] = (
    (frozenset({"POST", "PUT", "PATCH", "DELETE"}), r"^/auth/"),
    (frozenset({"POST", "PUT", "PATCH", "DELETE"}), r"^/admin/utilisateurs/"),
    (frozenset({"POST", "PUT", "PATCH", "DELETE"}), r"^/config(/|$)"),
    (None, r"^/config/(smtp|imap|whatsapp|llm)"),
    (frozenset({"POST", "PUT", "PATCH", "DELETE"}), r"^/copropriete$"),
    (frozenset({"POST", "PUT", "PATCH", "DELETE"}), r"^/perimetres"),
    (frozenset({"POST", "PUT", "PATCH", "DELETE"}), r"^/admin/modeles-email"),
    (None, r"^/admin/(sauvegardes|maintenance|db|export-copropriete|installation)"),
    (frozenset({"POST", "PUT", "PATCH", "DELETE"}), r"^/admin/(telemetry|controle-sante)"),
    (frozenset({"POST"}), r"(^/uploads/|/upload$)"),
    (frozenset({"POST", "PUT", "PATCH", "DELETE"}), r"^/partage"),
)

#: Les routes du périmètre laissées OUVERTES, et pourquoi.
OUVERTS_EXPRES: dict[tuple[str, str], str] = {
    ("POST", "/auth/login"): "la page de connexion reste servie",
    ("POST", "/auth/logout"): "un visiteur se déconnecte",
    ("POST", "/auth/refresh"): "la session d'un compte publié se renouvelle",
    ("POST", "/auth/me/demande-modification"): "une demande au conseil, montrée par la démo",
    ("PATCH", "/auth/me/opt-out-telemetrie"): "le droit d'opposition reste ouvert",
    ("DELETE", "/auth/me/telemetrie"): "le droit d'effacement reste ouvert",
    ("POST", "/admin/utilisateurs/{user_id}/accueil-arrivant"): "geste de l'accueil, montré",
    ("POST", "/admin/utilisateurs/{user_id}/auto-match"): "rattachement aux lots, montré",
    ("GET", "/config/whatsapp-logs"): "lecture du journal local",
    ("GET", "/config/whatsapp-scheduled"): "lecture des messages planifiés",
    ("GET", "/config/llm-consommation"): "lecture locale de la consommation",
    ("GET", "/config/llm-usages"): "lecture locale des usages",
    ("GET", "/admin/sauvegardes/config"): "lecture",
    ("GET", "/admin/sauvegardes/historique"): "lecture",
    ("GET", "/admin/db/integrite"): "lecture",
    ("GET", "/admin/maintenance/dernier-rapport"): "lecture",
    ("GET", "/admin/maintenance/historique"): "lecture",
    ("GET", "/admin/maintenance/sante"): "lecture",
    ("GET", "/admin/installation/conditions"): "lecture des conditions d'inscription",
    ("GET", "/admin/installation/inscription"): "lecture de l'état d'inscription",
    ("POST", "/admin/maintenance/rapport"): "la remise à zéro nocturne rend compte (clé de "
    "maintenance, jamais un visiteur)",
    ("POST", "/admin/maintenance/battement"): "battement des scripts (clé de maintenance)",
    ("POST", "/admin/maintenance/bail"): "le bail que lit la mise à jour nocturne (clé de "
    "maintenance, jamais un visiteur)",
    ("GET", "/admin/installation"): "lecture, réservée à l'opérateur",
    ("GET", "/admin/installations"): "lecture du registre, réservée à l'opérateur — servi par "
    "la référence seule, il dit « éteint » en démo",
    ("GET", "/admin/installations/{identifiant}"): "lecture d'une fiche du registre (404 "
    "hors de la référence)",
    ("POST", "/admin/installation/inscription"): "la démo s'inscrit au registre (M11), "
    "réservé à l'opérateur",
    ("POST", "/admin/installation/bail"): "le bail du registre (M11), réservé à l'opérateur",
}


def _motif(chemin: str) -> re.Pattern[str]:
    """`/a/{id}/b` → l'expression qui reconnaît un chemin concret de cette route."""
    morceaux = re.split(r"(\{[^}]+\})", chemin)
    corps = "".join(
        (".+" if m.endswith(":path}") else "[^/]+") if m.startswith("{") else re.escape(m)
        for m in morceaux
    )
    return re.compile(f"^{corps}$")


_INDEX: tuple[tuple[str, re.Pattern[str], Famille], ...] = tuple(
    (methode, _motif(chemin), famille)
    for famille in GESTES_FERMES
    for methode, chemin in famille.gestes
)


def famille_fermee(methode: str, chemin: str) -> Optional[Famille]:
    """PURE : la famille qui ferme ce geste, ou `None`. `HEAD` vaut `GET`."""
    methode = "GET" if methode == "HEAD" else methode
    chemin = chemin.rstrip("/") or "/"
    for m, motif, famille in _INDEX:
        if m == methode and motif.match(chemin):
            return famille
    return None


class FermeEnDemo(RuntimeError):
    """Un appel vers l'extérieur refusé : l'installation est la démo publique (règle 6)."""


def exiger_hors_demo(canal: str) -> None:
    """La porte des appels réseau : lève `FermeEnDemo` en démo, avant toute connexion."""
    if est_demo():
        raise FermeEnDemo(f"{MESSAGE} {canal} : aucun appel ne part de la démo.")


def reponse_refus(famille: Famille) -> JSONResponse:
    """La réponse d'un geste fermé : 403, et ce qu'il faut en comprendre."""
    return JSONResponse({"detail": f"{MESSAGE} {famille.raison}"}, status_code=403)


class GardeDemo:
    """Intergiciel ASGI : en démo, un geste fermé reçoit 403 avant toute route."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http" and est_demo():
            famille = famille_fermee(scope["method"], scope["path"])
            if famille is not None:
                await reponse_refus(famille)(scope, receive, send)
                return
        await self.app(scope, receive, send)


#: La famille qui ferme les fichiers reçus à leur porte (règle 5).
TELEVERSEMENTS = next(f for f in GESTES_FERMES if f.nom == "Téléversements")


def refuser_fichier_recu() -> None:
    """Lève 403 en démo : appelée par les deux portes d'écriture de `utils/fichiers`."""
    if est_demo():
        from fastapi import HTTPException

        raise HTTPException(403, f"{MESSAGE} {TELEVERSEMENTS.raison}")
