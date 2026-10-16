# Vue d'ensemble — Architecture

> Architecture pensée pour un déploiement autonome et souverain sur **Raspberry Pi 5**, hébergé dans la copropriété ou accessible via tunnel sécurisé. Toutes les briques sont open source sous licence non copyleft forte.

## Schéma général

```
[Navigateur / PWA mobile]
         │  HTTPS (TLS automatique)
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

## Stratégie PWA (mobile)

- Une seule codebase front-end pour web et mobile (pas d'app native).
- Workbox (via `@vite-pwa/sveltekit`) : cache des pages statiques et données essentielles.
- Fonctionne hors-ligne pour la consultation ; synchronisation à la reconnexion.
- Plateformes : iOS 16.4+ (Safari), Android 10+ (Chrome), ajout à l'écran d'accueil (A2HS).

## Décisions d'architecture clés

| Décision | Justification |
|----------|---------------|
| PostgreSQL | Réplication en continu vers le second nœud, une base par copropriété (`multi-coproprietes.md`, D4) |
| PWA plutôt qu'app native | Une seule codebase, aucun App Store, adapté à une audience fermée et identifiée |
| SvelteKit | Bundle < 150 Ko gzippé, SSR natif, PWA sans surcoût, tourne en Node Alpine ARM64 |
| FastAPI | Démarre en < 1 s, < 50 Mo RAM au repos, OpenAPI auto-généré |
| Caddy | TLS automatique en 5 lignes de config, HTTP/3 natif |

> Voir [stack.md](stack.md) pour le détail complet de chaque brique.
