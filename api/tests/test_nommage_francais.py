"""Le nommage technique est français — l'existant figé, le suivant refusé (#1056).

« Français exclusif (interface + nommage des champs) », dit CLAUDE.md. L'interface
l'est ; le nommage technique ne l'était pas partout, et rien ne le gardait. Le
renommer en bloc serait une série de migrations et de clients front : il se fait
AU FIL DE L'EAU, quand un lot touche la table ou la route. Ce test tient les deux
bouts, comme `lint:confirmation` :

- un nom anglais NOUVEAU (table, segment de route) échoue ;
- un nom figé qui a été renommé doit SORTIR de la liste — elle ne fait que
  décroître, et une entrée qui ne sert plus fait échouer.

Le vocabulaire surveillé est volontairement court : des mots sans équivalent
français homographe. « auto » (auto-résoudre) et « vérification » le sont, donc
ils n'y figurent pas — un faux positif désarme un contrôle en une semaine.

Les TAGS d'OpenAPI suivent une convention : minuscules, mots séparés par un
tiret, sans espace ni apostrophe (accents permis). Trois y dérogeaient ; renommés
le 24/09/2026 — un tag ne change aucune adresse.
"""

from __future__ import annotations

import re

import pytest
from sqlmodel import SQLModel

import app.models.core  # noqa: F401 — enregistre toutes les tables
from app.main import app

ANGLAIS = {
    "user",
    "users",
    "token",
    "tokens",
    "expires",
    "last",
    "seen",
    "login",
    "logout",
    "register",
    "refresh",
    "upload",
    "stats",
    "match",
    "search",
    "count",
    "active",
    "event",
    "daily",
    "monthly",
    "scheduled",
    "log",
    "logs",
    "test",
    "status",
    "reset",
    "password",
    "me",
    "telemetry",
}

#: Tables anglaises existantes au 24/09/2026 — à renommer au fil de l'eau.
#: Carte des plafonds décroissants : #1571.
TABLES_FIGEES = {
    "email_verification_token",
    "password_reset_token",
    "refresh_token",
    "telemetry_daily",
    "telemetry_event",
    "telemetry_monthly",
    "user_lot",
    "whatsapp_log",
    "whatsapp_scheduled",
}

#: Routes existantes portant un mot anglais au 24/09/2026 — même régime.
#: Carte des plafonds décroissants : #1571.
ROUTES_FIGEES = {
    "/acces/admin/imports-vigik/auto-match",
    "/acces/admin/imports-vigik/stats",
    "/acces/admin/imports-vigik/upload",
    "/acces/admin/imports/auto-match",
    "/acces/admin/imports/stats",
    "/acces/admin/imports/upload",
    "/admin/audit/user-lots",
    "/admin/comptes/{user_id}/traiter",
    "/admin/me/accueil-arrivant",
    "/admin/telemetry/agreger",
    "/admin/telemetry/historique",
    "/admin/user-lots/{user_lot_id}",
    "/admin/utilisateurs/{user_id}",
    "/admin/utilisateurs/{user_id}/accueil-arrivant",
    "/admin/utilisateurs/{user_id}/ajouter-role",
    "/admin/utilisateurs/{user_id}/auto-match",
    "/admin/utilisateurs/{user_id}/ban-communaute",
    "/admin/utilisateurs/{user_id}/retirer-role",
    "/auth/change-password",
    "/auth/login",
    "/auth/logout",
    "/auth/me",
    "/auth/me/demande-modification",
    "/auth/me/demandes-modification",
    "/auth/me/opt-out-telemetrie",
    "/auth/me/telemetrie",
    "/auth/refresh",
    "/auth/register",
    "/bailleur/search-locataire",
    "/config/imap-test",
    "/config/llm-test",
    "/config/smtp-test",
    "/config/whatsapp-logs",
    "/config/whatsapp-scheduled",
    "/config/whatsapp-scheduled/{item_id}",
    "/config/whatsapp-status",
    "/config/whatsapp-test",
    "/lots/admin/imports/auto-match",
    "/lots/admin/imports/stats",
    "/lots/admin/imports/upload",
    "/signalements/count",
    "/telemetry/collect",
    "/telemetry/dashboard",
    "/telemetry/users-active",
}

TAG_CONFORME = re.compile(r"[a-zà-ÿ0-9]+(?:-[a-zà-ÿ0-9]+)*")


def _mots(nom: str) -> set[str]:
    return {m for m in re.split(r"[/_\-{}.]+", nom.lower()) if m}


@pytest.fixture(scope="module")
def schema():
    return app.openapi()


def test_le_vocabulaire_voit_quelque_chose(schema):
    """Cas zéro : un motif qui ne verrait rien rendrait les deux tests verts à vide."""
    assert len(SQLModel.metadata.tables) > 40
    assert len(schema["paths"]) > 180


def test_aucune_table_anglaise_nouvelle():
    anglaises = {t for t in SQLModel.metadata.tables if _mots(t) & ANGLAIS}
    assert not anglaises - TABLES_FIGEES, (
        f"table(s) au nom anglais : {sorted(anglaises - TABLES_FIGEES)} — nommer en français"
    )
    assert not TABLES_FIGEES - anglaises, (
        f"renommée(s), à retirer de TABLES_FIGEES : {sorted(TABLES_FIGEES - anglaises)}"
    )


def test_aucune_route_anglaise_nouvelle(schema):
    anglaises = {p for p in schema["paths"] if _mots(p) & ANGLAIS}
    assert not anglaises - ROUTES_FIGEES, (
        f"route(s) au segment anglais : {sorted(anglaises - ROUTES_FIGEES)} — nommer en français"
    )
    assert not ROUTES_FIGEES - anglaises, (
        f"renommée(s), à retirer de ROUTES_FIGEES : {sorted(ROUTES_FIGEES - anglaises)}"
    )


def test_les_tags_suivent_la_convention(schema):
    tags = {
        t
        for chemin in schema["paths"].values()
        for op in chemin.values()
        if isinstance(op, dict)
        for t in op.get("tags", [])
    }
    assert tags, "aucun tag lu"
    fautifs = sorted(t for t in tags if not TAG_CONFORME.fullmatch(t))
    assert not fautifs, f"tag(s) hors convention (minuscules, tirets) : {fautifs}"
