# Vue d'ensemble — Architecture

> Architecture pensée pour un déploiement autonome et souverain sur **Raspberry Pi 5**, hébergé dans la copropriété ou accessible via tunnel sécurisé. Toutes les briques sont open source sous licence non copyleft forte.

## Schéma général

```
[Navigateur / PWA mobile]   [App iOS native — dépôt coprofirst-ios]
         │  HTTPS (TLS automatique)   │  HTTPS, même API (contrat publié)
         ├────────────────────────────┘
     [Caddy 2]          ← reverse proxy + Let's Encrypt + HTTP/3
         │
  ┌──────┴──────────────────────┐
  │  SvelteKit (SSR + PWA)      │  ← front-end web & mobile (même codebase)
  └─────────────────────────────┘
         │  HTTP interne
  ┌──────┴──────────────────────┐
  │  FastAPI — Python 3.12      │  ← API REST + WebSocket (JWT auth)
  └─────────────────────────────┘
         │
  ┌──────┴──────────────────────┐
  │  PostgreSQL 17              │  ← base de données, répliquée vers le second nœud
  └─────────────────────────────┘

Orchestration : Docker Compose — services caddy / front / api / postgres
Matériel      : Raspberry Pi 5 — 8 Go RAM, ARM64
```

## Composants principaux

| Composant       | Technologie                    | Rôle                                                        |
|-----------------|--------------------------------|-------------------------------------------------------------|
| Reverse proxy   | Caddy 2                        | TLS automatique, HTTP/3, compression Brotli, routage        |
| Front-end       | SvelteKit v2 + TypeScript      | SSR + SPA + PWA (service worker, manifest, hors-ligne)      |
| API back-end    | FastAPI (Python 3.12)          | API REST + WebSocket, authentification JWT, OpenAPI auto    |
| Base de données | PostgreSQL 17 + SQLModel + Alembic | Réplique en continu, migrations, sauvegarde vérifiée     |
| Hébergement     | Raspberry Pi 5 (ARM64, 8 Go)  | Auto-hébergé dans la résidence ou accessible via tunnel     |
| Accès externe   | Cloudflare Tunnel (optionnel)  | Exposition sécurisée sans ouverture de port                 |

## Flux d'authentification

```
1. L'utilisateur s'authentifie → POST /auth/login
2. Le serveur retourne : access_token (JWT, 15 min) + refresh_token (7 jours)
3. Le front stocke les tokens dans des cookies HttpOnly/Secure
4. À expiration : refresh automatique via POST /auth/refresh
5. Onboarding : invitation par lien unique (pas d'inscription publique)
```

## Clients mobiles — la PWA, et l'application iOS qui s'y ajoute

Arbitrage du 01/11/2026 (chantier #2460). Le détail, et ce qui relie les deux
clients au serveur, vit **à un seul endroit** : [stack.md § Application mobile](stack.md#application-mobile).

- **La PWA reste** le client du web et du mobile : aucun écran retiré. Workbox (via
  `@vite-pwa/sveltekit`) ; iOS 16.4+ (Safari), Android 10+ (Chrome), ajout à l'écran
  d'accueil (A2HS).
- **L'application iOS native** (SwiftUI, dépôt `philippe-tressard/coprofirst-ios`)
  s'y ajoute, **sans WebView**, reliée par le seul **contrat d'API publié** et sa
  version (#2456) ; ses notifications passent par le **relais APNs** de la plateforme
  ([notifications-push.md](notifications-push.md), #2458).
- **Android** : hors périmètre, la PWA y suffit.

## Décisions d'architecture clés

| Décision | Justification |
|----------|---------------|
| PostgreSQL | Réplication en continu vers le second nœud, une base par copropriété (`multi-coproprietes.md`, D4) |
| PWA pour tous, application iOS native en plus (01/11/2026) | La PWA reste le client commun et ne perd aucun écran ; l'app iOS ajoute un client natif et ses notifications push, sans code partagé : le contrat d'API publié est le seul lien (#2460) |
| SvelteKit | Bundle < 150 Ko gzippé, SSR natif, PWA sans surcoût, tourne en Node Alpine ARM64 |
| FastAPI | Démarre en < 1 s, < 50 Mo RAM au repos, OpenAPI auto-généré |
| Caddy | TLS automatique en 5 lignes de config, HTTP/3 natif |

> Voir [stack.md](stack.md) pour le détail complet de chaque brique.
