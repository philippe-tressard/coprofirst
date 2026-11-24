"""Le nommage technique est français — l'existant figé, le suivant refusé (#1056).

« Français exclusif (interface + nommage des champs) », dit CLAUDE.md. L'interface
l'est ; le nommage technique ne l'était pas partout, et rien ne le gardait.

🔒 **Les noms anglais existants sont FIGÉS DÉFINITIVEMENT** (décision de l'auteur,
30/10/2026, #2314). Les renommer coûterait, pour chaque table, une migration en
deux versions (`CONTRACTIONS`, #1757) et, pour chaque route, le client front et
les onglets PWA restés ouverts sur l'ancienne adresse — pour un gain que
l'utilisateur ne voit pas. Ce ne sont plus des dettes à résorber : ce sont des
noms établis, et les listes ci-dessous ne sont plus un plafond. Ce test tient
les deux bouts, comme `lint:confirmation` :

- un nom anglais NOUVEAU (table, segment de route) échoue — la règle reste
  entière pour tout ce qui naît ;
- un nom figé qui viendrait à être renommé (par exemple `whatsapp_*` au second
  canal de diffusion, #1060) doit SORTIR de la liste — une entrée qui ne sert
  plus fait échouer.

Le vocabulaire surveillé est volontairement court : des mots sans équivalent
français homographe. « auto » (auto-résoudre) et « vérification » le sont, donc
ils n'y figurent pas — un faux positif désarme un contrôle en une semaine.

Les COLONNES aussi (#2954, 24/11/2026) : « champs et tables en français » ne
lisait que les tables, les routes et les tags. Quarante-huit colonnes portaient un mot
anglais (`user_id`, `hashed_password`, `negotiable`…) : figées comme les tables
(`COLONNES_FIGEES`) — renommer une colonne, c'est une migration en deux temps
pour un gain invisible —, et la suivante est refusée. Elles se lisent dans
`SQLModel.metadata` : colonnes réelles, héritées d'un mixin comprises.

Mots ajoutés au vocabulaire pour les colonnes : `hashed`, `enabled`, `revoked`,
`used`, `negotiable`, `require`, `onboarding`, `rule`, `raw`, `events` — aucun
n'est un mot français écrit sans accent. Écartés, parce qu'ils le sont ou que
le français les emploie : `type`, `email`, `url`, `purges`, `label`, `message`,
`ban`, et `complete` (« complète » s'écrit `complete` dans un nom sans accent,
comme `validee` ou `terminee`).

Les TAGS d'OpenAPI suivent une convention : minuscules, mots séparés par un
tiret, sans espace ni apostrophe (accents permis). Trois y dérogeaient ; renommés
le 24/09/2026 — un tag ne change aucune adresse.
"""

from __future__ import annotations

import re

import pytest
import sqlalchemy as sa
from sqlmodel import SQLModel

import app.models.core  # enregistre toutes les tables
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
    #  Ajoutés pour les colonnes (#2954) — voir l'en-tête.
    "hashed",
    "enabled",
    "revoked",
    "used",
    "negotiable",
    "require",
    "onboarding",
    "rule",
    "raw",
    "events",
}

#: Tables anglaises existantes au 24/09/2026 — figées définitivement (#2314,
#: 30/10/2026) : une table renommée, c'est une migration en deux versions.
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

#: Routes existantes portant un mot anglais au 24/09/2026 — figées définitivement
#: (#2314, 30/10/2026) : une route renommée casse le client et les onglets PWA.
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

#: Colonnes existantes portant un mot anglais au 24/11/2026, `table.colonne` —
#: figées définitivement comme les tables (#2314, #2954) : une colonne renommée,
#: c'est une migration en deux temps (`CONTRACTIONS`). Une figée renommée en sort.
COLONNES_FIGEES = {
    "commande_acces.user_id",
    "derniere_visite.user_id",
    "email_verification_token.expires_at",
    "email_verification_token.token",
    "email_verification_token.used",
    "email_verification_token.user_id",
    "evenement.saisi_pour_user_id",
    "historique_maintenance.tokens_supprimes",
    "historique_sauvegarde.declenchee_par_user_id",
    "historique_telemetrie.daily_purges",
    "historique_telemetrie.events_purges",
    "historique_telemetrie.monthly_purges",
    "lot_import.etage_raw",
    "lot_import.type_raw",
    "membre_cs.user_id",
    "membre_syndic.user_id",
    "password_reset_token.expires_at",
    "password_reset_token.token",
    "password_reset_token.used",
    "password_reset_token.user_id",
    "petite_annonce.negotiable",
    "presence_mensuelle.user_id",
    "profil_acces_document.require_cs",
    "refresh_token.expires_at",
    "refresh_token.revoked",
    "refresh_token.token",
    "refresh_token.user_id",
    "telecommande.user_id",
    "telecommande_import.user_locataire_id",
    "telecommande_import.user_proprietaire_id",
    "telemetry_event.user_id",
    "ticket.saisi_pour_user_id",
    "user_lot.user_id",
    "utilisateur.communaute_ban_count",
    "utilisateur.hashed_password",
    "utilisateur.last_seen_actualites",
    "utilisateur.onboarding_complete",
    "utilisateur.onboarding_etape",
    "vigik.user_id",
    "vigik_import.appartement_raw",
    "vigik_import.batiment_raw",
    "vigik_import.user_locataire_id",
    "vigik_import.user_proprietaire_id",
    "vote_idee.user_id",
    "vote_sondage.user_id",
    "whatsapp_log.scheduled_id",
    "whatsapp_scheduled.cron_rule",
    "whatsapp_scheduled.enabled",
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


def colonnes_anglaises(tables) -> set[str]:
    """Les `table.colonne` dont un mot est du vocabulaire anglais. PURE."""
    return {f"{t.name}.{c.name}" for t in tables for c in t.columns if _mots(c.name) & ANGLAIS}


def test_le_controle_des_colonnes_sait_refuser():
    table = sa.Table(
        "tableau",
        sa.MetaData(),
        sa.Column("user_id", sa.Integer),
        sa.Column("enabled", sa.Boolean),
        sa.Column("type_lot", sa.String),
        sa.Column("auteur_id", sa.Integer),
    )
    assert colonnes_anglaises([table]) == {"tableau.user_id", "tableau.enabled"}


def test_aucune_colonne_anglaise_nouvelle():
    anglaises = colonnes_anglaises(SQLModel.metadata.tables.values())
    assert len(anglaises) >= 20, "le relevé des colonnes ne voit rien : contrôle vide"
    assert not anglaises - COLONNES_FIGEES, (
        f"colonne(s) au nom anglais : {sorted(anglaises - COLONNES_FIGEES)} — nommer en français"
    )
    assert not COLONNES_FIGEES - anglaises, (
        f"renommée(s), à retirer de COLONNES_FIGEES : {sorted(COLONNES_FIGEES - anglaises)}"
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
