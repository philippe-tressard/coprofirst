<h1 align="center">
  <img src="docs/images/coprofirst.png" alt="CoproFirst" width="160" />
</h1>

<p align="center">
  <em>Application web de gestion de copropriétés — côté résidents et conseil syndical.</em>
</p>

<p align="center">
  <a href="https://github.com/philippe-tressard/coprofirst/actions/workflows/ci.yml"><img src="https://github.com/philippe-tressard/coprofirst/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licence-AGPL--3.0--or--later-blue.svg" alt="Licence AGPL-3.0-or-later — logiciel libre" /></a>
  <a href="https://api.reuse.software/info/github.com/philippe-tressard/coprofirst"><img src="https://api.reuse.software/badge/github.com/philippe-tressard/coprofirst" alt="REUSE compliant" /></a>
  <img src="https://img.shields.io/badge/python-3.12-3776ab.svg" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/node-22+-339933.svg" alt="Node 22+" />
</p>

---

> **Votre résidence a désormais son appli.**
> Signalez un problème, suivez les travaux, consultez vos documents, commandez un badge ou échangez entre voisins — tout se fait depuis un seul espace, sécurisé et accessible 24 h/24.

**Deux noms, deux choses.** Le logiciel s'appelle **CoproFirst** ; « 5Hostachy » est la résidence pour laquelle il est né, et le nom que ce dépôt a porté jusqu'au 09/10/2026 (les anciennes adresses redirigent ici). Rien dans le code ne nomme la résidence : son nom, son adresse et ses textes légaux se règlent dans l'administration, et l'application installée sur un téléphone porte le nom de **la résidence qui la sert**. Le pied de chaque page renvoie au code source de la version en service. **Depuis la version 3.0.0, CoproFirst est multi-copropriété** : une même installation sert plusieurs copropriétés, chacune dans sa base, ses fichiers et ses textes légaux, étanches entre elles. L'architecture : [`specs/architecture/multi-coproprietes.md`](specs/architecture/multi-coproprietes.md).

## Fonctionnalités

> 🌐 **Le détail de chaque fonctionnalité, et une démonstration à essayer en ligne : [coprofirst.fr](https://coprofirst.fr)** — la [page Démo](https://coprofirst.fr/demo.html) donne les comptes publics (données fictives). Le [manuel utilisateur](docs/manuel-utilisateur.html) décrit chaque écran.

- **Tableau de bord** — la page d'accueil : consignes du conseil syndical, éléments épinglés, kanban des dossiers en cours et fil de l'actualité.
- **Affaires / Demandes** — signalements, actualités et événements datés suivis par le conseil syndical, avec périmètre, destinataires, recherche libre et la pastille « Ce qui me concerne » (aussi sur le fil d'accueil) ; une affaire close reçoit une synthèse chiffrée, rédigée par l'assistant IA puis relue par le conseil.
- **Kanban & calendrier** — les dossiers longs avancent au kanban (AG · CS · Syndic · Prestataire · Terminé), et ce qui porte une date se lit sous le filtre Calendrier d'Affaires.
- **Documents** — GED avec catégories et accès par profil (résidents, propriétaires, conseil syndical).
- **Carnet d'entretien** — l'histoire du bâti exigée par le décret n° 2001-477, constituée par équipement à partir des contrats et des affaires résolues, avec un bilan d'exercice pour le conseil.
- **Mes lots & accès** — lots, badges Vigik, télécommandes de parking et gestion locative (baux, locataires, inventaire de remise). Le conseil voit les portes que les lots d'un badge justifient — proposées, jamais posées seules — et les badges qui s'en écartent.
- **FAQ** — questions fréquentes filtrées par profil.
- **Communauté** — idées, sondages, petites annonces et avis sur l'application, réservés aux résidents.
- **Prestataires & Contrats** — annuaire, contrats d'entretien, échéances de visite, notation, et synthèse de contrat par l'assistant IA.
- **Annonces de hall** — affiche PDF aux couleurs de la résidence, diffusable au conseil, au syndic et au groupe WhatsApp.
- **Reporting CS** — suivi des affaires en cours, relance groupée du syndic et comptes rendus de réunion CS / Syndic validés par les présents, exportables en PDF.
- **Courriels affaires** — les messages reçus à l'adresse des affaires alimentent les fils ; le journal garde le verdict de chacun, jamais son texte.
- **Questions au règlement** — l'assistant IA répond en juriste d'après le règlement de copropriété, avec extraits cités et vérifiés.
- **Administration** — comptes, pages légales, services (IA, WhatsApp, courriel), nom et logo de la résidence.
- **Périmètres** — arborescence de la copropriété (bâtiments, parking, espaces) pour localiser affaires, actualités, sondages et annonces.
- **Lots et règlement** — la désignation de chaque lot selon l'état descriptif du règlement de copropriété : nature, porte ou place, niveau, circulation qui le dessert et tantièmes par clé de charges — et ce que finance chaque clé —, importés et contrôlés par l'atelier d'import — ou lus dans le règlement par l'assistant IA, qui remplit le même atelier sans rien appliquer ; une cave ou une place est rattachée à sa circulation, pas au bâtiment de son propriétaire, et ce qui vise cette circulation (ascenseur, escalier, caves) concerne qui la paie, même sans habiter le bâtiment. Le conseil les relit dans Copropriété › Lots — constats du patrimoine, périmètres posés à la main, recalcul. La règle : [`specs/architecture/lots-et-perimetres.md`](specs/architecture/lots-et-perimetres.md).
- **WhatsApp** — notifications programmées vers le groupe de la résidence. ⚠️ Le pont passe par un client non officiel (Baileys) : le numéro peut être bloqué, le courriel reste le canal de repli.
- **Maintenance** — rôle et version de l'installation, export vérifié de la base, tâches automatiques, contrôles de santé et suivi de la consommation de l'IA.
- **Installations** — registre des installations CoproFirst inscrites, pour l'opérateur de la référence seulement.
- **Liens partageables** — chaque onglet et chaque publication a son adresse propre ; le lien n'ouvre aucun droit.
- **Installation commune** — une installation sert plusieurs copropriétés, chacune dans sa base : [`deploiement/standard/commune/LISEZMOI.md`](deploiement/standard/commune/LISEZMOI.md).
- **Démonstration publique** — `MODE_DEMO=oui` monte une résidence fictive avec trois comptes publiés, sans aucun envoi, remise à zéro chaque nuit : `specs/architecture/mode-demo.md`.

## Manuel utilisateur

Le **manuel utilisateur** décrit chaque écran : ce qu'il contient, les gestes
qu'il permet et qui peut le voir — [docs/manuel-utilisateur.html](docs/manuel-utilisateur.html).
L'application le sert aussi elle-même, à l'adresse `/manuel-utilisateur.html`.

## Stack technique

| Composant | Technologie |
|---|---|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) · SQLModel · PostgreSQL 17, répliqué en continu vers le second nœud · Alembic |
| Frontend | [SvelteKit](https://kit.svelte.dev/) · TypeScript · Vite · PWA (installable ; écrans précachés, contenus toujours en ligne) |
| Reverse proxy | [Caddy](https://caddyserver.com/) |
| Messaging | WhatsApp Bridge (Baileys) |
| Déploiement | Docker Compose · Raspberry Pi 5 |
| Tests | pytest (API) · [Playwright](https://playwright.dev/) (navigateur, bureau et mobile) · des contrôles `lint:*` sur la source (la liste : `front/package.json`) |
| CDN / Tunnel | Cloudflare Tunnel + Worker (maintenance page) |

```
coprofirst/
├── api/               # Backend FastAPI
│   ├── app/           # Code applicatif (routers, models, utils)
│   └── alembic/       # Migrations de base de données
├── front/             # Frontend SvelteKit
│   ├── src/routes/    # Pages de l'application
│   └── e2e/           # Tests de navigateur (Playwright)
├── whatsapp-bridge/   # Bridge WhatsApp (Node.js)
├── scripts/           # Tous les scripts
│   ├── exploitation/  # Lancés par cron/systemd sur les RPi (bascule, failover…)
│   ├── lib/           # Modules sourcés par les précédents
│   ├── poste/         # Développeur et CI (pré-check, rejeu CI, export hors site)
│   └── installation/  # Durcissement système et sudo, tunnel — la réinstallation
│                      # d'un nœud se suit pas à pas (docs/restauration-complete.md)
├── infra/             # Code déployé ailleurs (worker Cloudflare)
├── specs/             # Spécification d'origine — historique, le manuel fait foi
├── docs/              # Documentation déploiement & ops
├── boot-role-guard.sh # RELAIS PERMANENT vers scripts/exploitation/ : l'unité
│                      #   systemd désigne CE chemin absolu, et rien dans un
│                      #   déploiement ne la met à jour. Il reste donc.
└── docker-compose.yml
```

## Démarrage rapide

### Prérequis

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose v2+
- Git

### Installation

```bash
git clone https://github.com/philippe-tressard/coprofirst.git
cd coprofirst

# Configurer l'environnement
cp .env.example .env
# Éditer .env : SECRET_KEY (min 32 chars), WHATSAPP_API_KEY (min 16 chars) et ORIGIN.
# WHATSAPP_API_KEY est OBLIGATOIRE — sans elle, docker compose refuse de démarrer.

# Lancer
docker compose up --build -d
```

L'application est accessible sur `http://localhost`.

> 📦 **Images publiées.** Chaque version reçoit un tag `vX.Y.Z` et des images
> signées (amd64 et arm64) : `ghcr.io/philippe-tressard/coprofirst-api`, `-front`,
> `-caddy` et `-whatsapp-bridge`, étiquetées par version (et chaque commit de `main`
> par `sha-<commit>`). Vérifier une image :
> `gh attestation verify oci://ghcr.io/philippe-tressard/coprofirst-api:<version> --owner philippe-tressard`.
> Les versions choisies pour les autres installations sont **promues** sur la branche
> `replica`, avec leurs notes de version (onglet *Releases*) : après 7 jours sur la
> référence, ou sans attendre pour un correctif urgent.
> **Installer sans construire** : [`deploiement/standard/LISEZMOI.md`](deploiement/standard/LISEZMOI.md)
> — chaque version promue joint son archive de déploiement à ses notes de version.
> Le serveur d'une installation y reçoit seul ses **correctifs de sécurité** — système,
> Docker, `cloudflared` — chaque nuit à 03:00, contrôlés chaque matin
> (`deploiement/standard/correctifs-systeme.sh`).

Au premier lancement, deux comptes sont créés avec un **mot de passe aléatoire** affiché dans les logs : l'**administrateur** de la copropriété (`admin@localhost`) et l'**opérateur** de l'installation (`operateur@localhost`, administrateur aussi — supervision, santé, inscription au registre). Séparés pour confier le premier sans livrer le second.

```bash
docker compose logs api | grep -A5 "ADMIN INITIAL"
```

> **Changez immédiatement les mots de passe** après la première connexion.

### Développement local (sans Docker)

```bash
# Backend
cd api && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (autre terminal)
cd front && npm install && npm run dev

# Tests de navigateur (le serveur de dev démarre tout seul)
cd front && npx playwright install chromium && npm run e2e
```

> Les tests Playwright rendent les écrans **publics en vrai** et les écrans
> **authentifiés sur une API simulée** : ils éprouvent le comportement de
> l'interface (clavier, responsivité, rendu), pas le serveur — droits, filtres et
> forme réelle des réponses restent l'affaire de `api/tests/`.
> `front/e2e/README.md` dit ce que l'API simulée prouve, et ce qu'elle ne prouve pas.

## Configuration

Toute la configuration se fait via le fichier `.env` (voir [.env.example](.env.example)). Le tableau ci-dessous n'en retient que l'essentiel : le gabarit fait foi, et `api/tests/test_env_exemple_coherent.py` vérifie en CI qu'il démarre la stack et que chacune de ses clés est lue par quelqu'un.

| Variable | Description | Défaut |
|---|---|---|
| `SECRET_KEY` | Clé JWT — **obligatoire**, min 32 caractères | *(rejeté si non défini)* |
| `ORIGIN` | URL complète du site | `https://example.com` |
| `COOKIE_SECURE` | `true` en prod HTTPS, `false` en dev HTTP | `true` |
| `MAIL_ENABLED` | Activer les notifications email | `false` |
| `WHATSAPP_API_KEY` | Clé du bridge WhatsApp — **obligatoire**, min 16 caractères ; lue par l'API et par le bridge, seule source | *(refusée si absente, d'exemple ou trop courte)* |
| `ENABLE_API_DOCS` | Exposer `/docs` et `/redoc` | `false` |

## Documentation

| Document | Description |
|---|---|
| [specs/](specs/) | Spécification **d'origine**, fonctionnelle et technique — **historique** : le site a évolué depuis (écrans fusionnés ou retirés), le **manuel utilisateur** ci-dessous fait foi |
| [specs/architecture/lots-et-perimetres.md](specs/architecture/lots-et-perimetres.md) | Spécification **vivante** des lots selon le règlement : situé dans / desservi par, circulations, clés de charges, « mes périmètres », l'atelier de l'état descriptif et ses décisions de réalisation |
| [docs/deploy-rpi5-auto.md](docs/deploy-rpi5-auto.md) | Renvois : où se lit le déploiement automatique (`auto-deploy.sh`, `infra/points-entree/`) — plus une procédure |
| [docs/restauration-complete.md](docs/restauration-complete.md) | Réinstaller un nœud de zéro (il rejoint la paire comme standby) ; les deux perdus, la résidence renaît de la copie hors site |
| [docs/redondance-rpi5.md](docs/redondance-rpi5.md) | Architecture de redondance : réplique PostgreSQL en continu, bascule, failover |
| [docs/cloudflare-worker-maintenance.md](docs/cloudflare-worker-maintenance.md) | Page de maintenance Cloudflare |
| [docs/icones-menu.md](docs/icones-menu.md) | Renvois : où se lisent les icônes du menu (`pages.ts`, `pages-roles.ts`) — plus un inventaire |
| [docs/manuel-utilisateur.html](docs/manuel-utilisateur.html) | **Manuel utilisateur** — ce que chaque écran contient et qui peut le voir |
| [docs/contrat-sous-traitance-modele.md](docs/contrat-sous-traitance-modele.md) | **Contrat de sous-traitance** (RGPD art. 28) entre un syndicat de copropriétaires et l'opérateur de l'installation qui le sert — modèle, projet à faire relire (#2065) |
| [api/app/registre/conditions/v1.md](api/app/registre/conditions/v1.md) | **Conditions d'inscription** d'une installation au registre de la référence — un contrat d'engagements réciproques, archivé pour chaque installation ; projet à faire relire (#1876) |
| [deploiement/standard/commune/LISEZMOI.md](deploiement/standard/commune/LISEZMOI.md) | **Installation commune** à plusieurs copropriétés : adresses dérivées, aiguillage, déclaration des copropriétés, nom de domaine générique |
| [docs/licences-tierces.md](docs/licences-tierces.md) | Inventaire **généré** des licences tierces — dépendances, exceptions déclarées, fichiers repris (vérifié en CI) |
| [docs/carte-reglages.md](docs/carte-reglages.md) | Carte **générée** des réglages — qui règle quoi (administrateur, conseil syndical, opérateur, exploitant du serveur), où, et où la valeur vit ; l'accès de chaque notion est confronté à la route en CI (#2061) |

## Sécurité

- JWT avec cookies HttpOnly / Secure / SameSite=strict
- Hachage bcrypt des mots de passe
- **Autorisation centralisée** — toutes les règles dans `api/app/auth/deps.py`, chaque endpoint en dépend, les rares exceptions publiques sont énumérées et justifiées (vérifié en CI)
- **Exposition publique en liste blanche** — ce qui est lisible sans authentification est énuméré, jamais déduit par exclusion
- Rate limiting sur les endpoints d'authentification (slowapi)
- Validation Pydantic / SQLModel sur toutes les entrées
- En-têtes de sécurité — HSTS, `X-Frame-Options`, `X-Content-Type-Options` et `Referrer-Policy` servis par **Caddy**&nbsp;; la **politique de sécurité du contenu** (CSP) est émise par **SvelteKit** (`vite.config.ts`), qui seul connaît le condensat de ses scripts en ligne
- Sanitisation HTML côté client (DOMPurify)
- Protection path traversal sur les uploads
- **Vulnérabilités des dépendances vérifiées en CI, des DEUX côtés** — `npm audit` sur tout l'arbre (`devDependencies` comprises : elles servent le site) et `pip-audit` sur `api/requirements.txt`. Même mécanique de part et d'autre : exceptions **nominatives**, chacune avec son motif d'atteignabilité, sa condition de levée et sa date de revue — et une exception devenue inutile fait **échouer** le contrôle, pour forcer son retrait (`front/audit-exceptions.json`, `api/audit-exceptions.json`)
- **Le lock ne ment pas sur ses versions** — vérifié en CI : `npm audit` lit le champ `version` du lock, donc une version fausse le rend aveugle sans rien dire

Voir [SECURITY.md](SECURITY.md) pour la politique de signalement de vulnérabilités. Chaque installation sert le même canal à l'adresse standard `/.well-known/security.txt` (RFC 9116), dont l'échéance est tenue par `api/tests/test_security_txt.py`.

## Contribuer

Les contributions sont les bienvenues ! Voir [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

**[AGPL-3.0-or-later](LICENSE)** — GNU Affero General Public License, version 3
ou ultérieure. © Philippe TRESSARD, 2024-2026.

CoproFirst est un **logiciel libre** : chacun peut l'utiliser, l'étudier, le
modifier et le redistribuer, y compris à titre commercial — à condition de
publier ses modifications sous la même licence, **y compris** quand il le fait
fonctionner comme service en ligne (AGPL §13). Aucune condition additionnelle.

Les versions publiées jusqu'à la 2.115.0 restent sous leur licence d'origine ;
l'historique du changement et les mentions de copyright sont dans
[`NOTICE.md`](NOTICE.md). La licence ne cède aucun droit sur les noms, et le logo
n'est pas sous l'AGPL ([sa licence](LICENSES/LicenseRef-CoproFirst-Logo.txt)) :
leur usage suit [`MARQUE.md`](MARQUE.md) — CoproFirst est une demande de marque
déposée à l'INPI (n° 5307183, 09/10/2026).

Les composants tiers gardent leur propre licence : [`NOTICE.md`](NOTICE.md) §6
les nomme, dont `libsignal` (GPL-3.0) dans le service de messagerie — tous
compatibles avec l'AGPL-3.0-or-later, analyse validée par l'auteur.
