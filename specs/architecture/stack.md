# Stack technique

> Architecture pensée pour un déploiement autonome sur **Raspberry Pi 5** (ARM64, 4 ou 8 Go RAM).
> Priorité : simplicité d'installation, faible consommation de ressources, maintenance minimale.

Contrainte : Le choix des logiciels est Opensource avec des licences non copyleft forte.

---

## Vue d'ensemble

```
[Navigateur / PWA]   [App iOS — dépôt coprofirst-ios]
       │  HTTPS        │  HTTPS (même API, contrat publié)
       ├───────────────┘
  [Caddy] ← reverse proxy + TLS automatique (Let's Encrypt)
       │
  ┌────┴────────────────────┐
  │  SvelteKit (SSR/SPA)    │  ← front-end
  └─────────────────────────┘
       │  HTTP interne
  ┌────┴────────────────────┐
  │  FastAPI (Python 3.12)  │  ← API REST + WebSocket
  └─────────────────────────┘
       │
  ┌────┴────────────────────┐
  │  PostgreSQL 17          │  ← base de données
  └─────────────────────────┘

Orchestration : Docker Compose (services : caddy / front / api / postgres)
```

---

## Front-end web

- **Framework :** [SvelteKit](https://kit.svelte.dev/) v2
- **Langage :** TypeScript
- **Build :** Vite 5
- **CSS :** CSS natif + variables CSS (tokens charte graphique) — pas de framework CSS lourd
- **Icônes :** Lucide Svelte
- **PWA :** `@vite-pwa/sveltekit` — service worker + manifest généré automatiquement
- **HTTP client :** `fetch` natif (pas de dépendance Axios)
- **Justification :** Bundle minimal (<150 Ko gzippé), SSR natif, génère la PWA sans surcoût, tourne facilement dans un container Node Alpine sur ARM64.

---

## Application mobile

> 🧭 **Révisé le 01/11/2026** (arbitrage de l'auteur, chantier #2460) : cette section
> n'est plus historique, elle se tient à jour à chaque arbitrage. Elle disait jusque-là
> que la PWA serait le seul client mobile, sans application native ni App Store :
> c'est faux depuis cette date.

Deux clients, **un seul serveur** :

| Client | Ce qu'il est | Où il vit |
|---|---|---|
| **PWA** | le site, installable sur l'écran d'accueil (A2HS) — iOS 16.4+ (Safari), Android 10+ (Chrome) | ce dépôt, `front/` |
| **Application iOS native** | SwiftUI, publiée sur l'App Store ; vitrine, entrée dans une installation, puis les écrans du site **par étapes** jusqu'à la parité | dépôt distinct `philippe-tressard/coprofirst-ios` |

- **La PWA reste** : aucun écran n'en est retiré, et elle reste le seul client sur
  Android et sur ordinateur. L'application iOS **s'ajoute**, elle ne remplace rien.
- **Pas de WebView** : l'application ne charge pas le site dans un cadre ; chaque
  écran est natif. Un écran pas encore porté n'existe pas dans l'application — il
  reste servi par la PWA.
- **Android est hors périmètre** : la PWA y suffit. Une application Android serait
  un nouvel arbitrage, pas une suite de celui-ci.

**Ce qui relie l'application au serveur — et rien d'autre** :

1. **Le contrat d'API publié** (#2456) : `openapi.json` produit par `app.openapi()`,
   joint à la release de chaque version ; l'application en **génère** son client
   (`swift-openapi-generator`). Jamais une route recopiée à la main, jamais du code
   partagé entre les deux dépôts. La documentation d'API reste **fermée** en
   production (`ENABLE_API_DOCS=false`) : le contrat se publie comme fichier.
2. **La version du contrat** (#2456), rendue par `GET /config` : une installation
   peut être plus ancienne que l'application (vague *Fixe*, `registre/versions`) ;
   l'application y adapte ses gestes au lieu d'échouer.
3. **La même porte d'authentification que le navigateur** (#2457) : cookies
   `httponly`, rafraîchissement et sa rotation — pas de second mode (Bearer).
4. **Le relais de notifications** (#2458) : les notifications push APNs passent par
   un relais de la plateforme, la clé d'Apple ne quittant jamais la référence —
   spécification : [`notifications-push.md`](notifications-push.md).
5. **Les liens universels** (#2459) : `/.well-known/apple-app-site-association`,
   servi par chaque installation, ouvre l'application sur la bonne installation.

**Où la vérité se lit** : l'état de chaque lot dans ses tickets (#2455 à #2459,
chapeautés par #2460) ; ce que le serveur expose, dans le contrat publié ; ce que
l'application fait, dans son propre dépôt. Ce paragraphe ne dit que leur lien.

- **Fonctionnement hors-ligne de la PWA :** Workbox (intégré via vite-pwa) — cache
  des pages statiques et des données essentielles.
- **Notifications push de la PWA (Web Push) :** non prévues ; l'application iOS a
  les siennes (APNs, ci-dessus).

---

## Back-end / API

- **Langage :** Python 3.12
- **Framework :** [FastAPI](https://fastapi.tiangolo.com/) — async, OpenAPI auto-généré, léger
- **Serveur ASGI :** Uvicorn (avec Gunicorn en mode worker sur le Pi)
- **Authentification :**
  - JWT (access token 15 min + refresh token 7 jours)
  - Mots de passe hashés bcrypt via `passlib`
  - Invitation par lien unique pour l'onboarding des résidents (pas d'inscription publique)
- **Validation :** Pydantic v2 (intégré FastAPI)
- **Emails :** `fastapi-mail` + SMTP local (ou relay Brevo/Mailgun) — templates rendué via **Jinja2** (déjà dépendance de FastAPI), contenu stocké en base et éditable sans redéploiement
- **Justification :** Python est disponible nativement sur RPi, FastAPI démarre en < 1 s, consomme < 50 Mo RAM au repos.

---

## Base de données

- **SGBD :** PostgreSQL 17 (volume Docker `pg_data`), répliqué en continu vers le second nœud
- **ORM :** [SQLModel](https://sqlmodel.tiangolo.com/) (combine SQLAlchemy + Pydantic — aligné avec FastAPI)
- **Migrations :** Alembic
- **Backup :** sauvegarde périodique paramétrable depuis l'interface admin (EF-WEB-015) — fréquence quotidienne / **hebdomadaire (défaut)** / mensuelle, **3 versions historisées par défaut** (1–30 configurable), rotation automatique. Périmètre : export vérifié de la base + répertoire fichiers uploadés. Archive `.tar.gz` dans le volume `/backups`. Cron géré par **APScheduler** (dépendance FastAPI). Restauration via l'UI avec confirmation par mot de passe admin. Notification email en cas d’échec.

---

## Infrastructure / Hébergement

### Matériel cible

| Composant     | Spécification recommandée                        |
|---------------|--------------------------------------------------|
| Carte         | Raspberry Pi 5 — 8 Go RAM                       |
| Stockage OS   | Carte microSD A2 ≥ 64 Go (ou SSD NVMe via HAT)  |
| Stockage data | SSD USB 3 externe ≥ 128 Go (volumes Docker)     |
| OS            | Raspberry Pi OS Lite 64-bit (Debian Bookworm)    |
| Alimentation  | Alimentation officielle 5V/5A USB-C              |

### Orchestration

- **Docker Engine** 26+ (ARM64) + **Docker Compose** v2
- Fichier unique `docker-compose.yml` à la racine du projet :

```yaml
# aperçu — les services principaux
services:
  caddy:      # reverse proxy TLS
  front:      # SvelteKit (node:26-alpine)
  api:        # FastAPI (python:3.12-slim)
  postgres:   # PostgreSQL 17
volumes:
  caddy_data:
  caddy_logs: # journal d'accès anonyme de Caddy, 7 jours (#1588)
  app_data:   # identité au registre, cache du manuel PDF
  backups:
  pg_data:    # la base
```

### Reverse proxy

- **Caddy 2** : TLS automatique Let's Encrypt, configuration en 5 lignes (Caddyfile), support HTTP/3, compression Brotli native.
- Domaine : sous-domaine dédié (ex. `parc.local` en LAN ou `example.com` avec DynDNS si accès externe).

### Accès réseau

- **LAN uniquement (option 1) :** accès via IP fixe locale (ex. `<RPi-IP>`) — le Pi n'est pas exposé sur Internet. Simple et sécurisé.
- **Accès externe (option 2) :** tunnel [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) (gratuit, sans ouvrir de port sur la box) — recommandé si les résidents accèdent depuis l'extérieur.

### Pare-feu (UFW)

| Règle | Ports | Source |
|-------|-------|--------|
| SSH | 22/tcp | LAN `192.168.x.0/24` uniquement |
| HTTP | 80/tcp | toutes sources |
| HTTPS | 443/tcp + 443/udp | toutes sources |
| Tout le reste | — | **bloqué** |

### CI/CD

- **Déploiement :** `git pull` + `docker compose up -d --build` sur le Pi (déclenché manuellement ou via webhook GitHub/Gitea).
- **Gitea** (optionnel) : instance Git auto-hébergée sur le Pi si l'équipe ne veut pas dépendre de GitHub.
- **Watchtower** (optionnel) : mise à jour automatique des images Docker en production.

---

## Prérequis d'installation (résumé)

```bash
# 1. Sur le Pi (Raspberry Pi OS 64-bit)
sudo apt update && sudo apt install -y docker.io docker-compose-plugin

# 2. Cloner le dépôt
git clone https://github.com/philippe-tressard/coprofirst.git
cd coprofirst

# 3. Configurer l'environnement
cp .env.example .env
# éditer .env : SECRET_KEY, domaine, SMTP...

# 4. Lancer
docker compose up -d
```

---

## Contraintes et limites connues

| Contrainte | Impact | Mitigation |
|---|---|---|
| Coupure de courant | Perte de données non persistées | Volume SSD + UPS (alimentation sans coupure) recommandé |
| Pas de CDN | Latence légèrement plus haute si accès distant | Cloudflare Tunnel inclut un cache CDN gratuit |
| Mises à jour manuelles | Intervention humaine requise | Watchtower ou cron `git pull` automatisable |
