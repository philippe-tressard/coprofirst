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
  <img src="https://img.shields.io/badge/node-26+-339933.svg" alt="Node 26+" />
</p>

---

> **Votre résidence a désormais son appli.**
> Signalez un problème, suivez les travaux, consultez vos documents, commandez un badge ou échangez entre voisins — tout se fait depuis un seul espace, sécurisé et accessible 24 h/24.

**Deux noms, deux choses.** Le logiciel s'appelle **CoproFirst** ; « 5Hostachy » est la résidence pour laquelle il est né, et le nom que ce dépôt a porté jusqu'au 09/10/2026 (les anciennes adresses redirigent ici). Rien dans le code ne nomme la résidence : son nom, son adresse et ses textes légaux se règlent dans l'administration, et l'application installée sur un téléphone porte le nom de **la résidence qui la sert**. Le pied de chaque page renvoie au code source de la version en service. **Depuis la version 3.0.0, CoproFirst est multi-copropriété** : une même installation sert plusieurs copropriétés, chacune dans sa base, ses fichiers et ses textes légaux, étanches entre elles. L'architecture : [`specs/architecture/multi-coproprietes.md`](specs/architecture/multi-coproprietes.md).

## Fonctionnalités

> 🌐 **Une présentation du produit, et une démonstration à essayer en ligne : [coprofirst.fr](https://coprofirst.fr)** — la [page Démo](https://coprofirst.fr/demo.html) donne les comptes publics (données fictives). Le détail de chaque écran est dans le [manuel utilisateur](docs/manuel-utilisateur.html).

- **Tableau de bord** — la page d'accueil : consignes du conseil syndical, éléments épinglés, kanban des dossiers en cours et fil de l'actualité. L'API sert aussi le fil d'une **période** (`GET /flux?du=&au=`, 31 jours au plus) pour le carnet des applications : chaque carte y est rangée à son jour — l'échéance de son affaire, sinon sa publication —, et une carte de plusieurs jours revient chaque jour couvert.
- **Affaires / Demandes** — signalements, actualités et événements datés suivis par le conseil syndical, avec périmètre, destinataires, recherche libre et la pastille « Ce qui me concerne » (aussi sur le fil d'accueil) ; une affaire close reçoit une synthèse chiffrée, rédigée par l'assistant IA puis relue par le conseil. Une actualité marquée ⚡ urgente par le conseil fait sonner la cloche de ses lecteurs : c'est la seule notification qui sonne aussi sur un téléphone (relais de la plateforme, sans aucune donnée personnelle dans le message).
- **Kanban & calendrier** — les dossiers longs avancent au kanban (AG · CS · Syndic · Prestataire · Terminé), et ce qui porte une date se lit sous le filtre Calendrier d'Affaires.
- **Documents** — GED avec catégories et accès par profil (résidents, propriétaires, conseil syndical).
- **Carnet d'entretien** — l'histoire du bâti exigée par le décret n° 2001-477, constituée par équipement à partir des contrats et des affaires résolues, avec un bilan d'exercice pour le conseil.
- **Mes lots & accès** — lots, badges Vigik, télécommandes de parking et gestion locative (baux, locataires, inventaire de remise). Le conseil voit les portes que les lots d'un badge justifient — proposées, jamais posées seules — et les badges qui s'en écartent.
- **FAQ** — questions fréquentes filtrées par profil.
- **Communauté** — idées, sondages, petites annonces et avis sur l'application, réservés aux résidents ; seul l'onglet Avis s'ouvre aussi au syndic et au mandataire. Tout contenu se **signale** au conseil syndical, une affaire, ses suites et la réponse de l'assistant IA comprises ; chacun peut **masquer**, pour lui seul, ce que signe un autre résident (annonces, réponses, messages), et revenir sur ce choix dans son profil.
- **Prestataires & Contrats** — annuaire, contrats d'entretien, échéances de visite, résiliation d'un contrat et prestataire qui le remplace, notation, synthèse de contrat par l'assistant IA ; une affaire peut désigner plusieurs prestataires, dans l'ordre. L'onglet **Consommations** tient les compteurs de la résidence et leurs relevés (date, index, note, photo).
- **Annuaire** — qui contacter, et pour quoi : les membres du conseil syndical et le syndic.
- **Délégations** — un proche aidant lit le site à la place d'une personne aidée, en lecture seule ; le conseil syndical (ou l'administrateur) crée la délégation, l'aidant l'accepte. Ce n'est pas une procuration d'assemblée générale.
- **Annonces Hall** — une annonce du hall, imprimée en affiche PDF aux couleurs de la résidence, diffusable au conseil, au syndic et au groupe WhatsApp.
- **Écrans du hall** — une Apple TV appairée par le conseil (code court saisi dans l'Espace CS) fait défiler les annonces du hall en cours de son périmètre, sans auteur ni destinataires ; son jeton n'ouvre que cette lecture, comme celui d'une montre n'ouvre que la cloche (un seul mécanisme de jeton d'appareil, à portée unique).
- **Reporting CS** — suivi des affaires en cours, relance groupée du syndic et comptes rendus de réunion CS / Syndic validés par les présents, exportables en PDF.
- **Courriels affaires** — les messages reçus à l'adresse des affaires alimentent les fils, avec leurs pièces jointes (documents et photos, dix au plus, hors signature) ; seuls l'auteur, le conseil et le syndic y écrivent ; le journal garde le verdict de chacun, jamais son texte.
- **Questions au règlement** — l'assistant IA répond en juriste d'après le règlement de copropriété **et les décisions d'assemblée générale**, en synthèse courte dont chaque affirmation renvoie à un extrait (acte, rubrique, page), détaillée en sections pliées (règlement, AG, réserves), extraits cités et vérifiés ; les PV d'AG se transcrivent par l'assistant — résolutions seules, sans nom — et n'entrent qu'après relecture de l'administration.
- **Admin** (la page *Paramétrage*) — comptes, pages légales, services (IA, WhatsApp, courriel, décor des jours de fête), télémétrie (chaque accès — web, app Apple, app Android — éclaté par type d'appareil, jamais son modèle), nom, logo et palette de couleurs de la résidence (site, courriels, annonces du hall, documents PDF).
- **Périmètres** — arborescence de la copropriété (bâtiments, parking, espaces), sur trois niveaux au plus, pour localiser affaires, actualités, sondages et annonces.
- **Équipements** — ce sur quoi l'on intervient (ascenseur, chauffage, plomberie…, et l'assurance ou le syndic pour les contrats), administrés dans Admin › Copropriété › Équipements : libellé, icône, abréviation, périmètres concernés. Ils rangent les contrats, le carnet d'entretien et les prestataires ; dans une affaire, l'équipement et le périmètre se proposent l'un l'autre.
- **Lots et règlement** — la désignation de chaque lot selon l'état descriptif du règlement de copropriété : nature, porte ou place, niveau, circulation qui le dessert et tantièmes par clé de charges — et ce que finance chaque clé —, importés et contrôlés par l'atelier d'import — ou lus dans le règlement par l'assistant IA, qui remplit le même atelier sans rien appliquer ; une cave ou une place est rattachée à sa circulation, pas au bâtiment de son propriétaire, et ce qui vise cette circulation (ascenseur, escalier, caves) concerne qui la paie, même sans habiter le bâtiment. Le conseil les relit dans Admin › Copropriété › Lots — constats du patrimoine, périmètres posés à la main, recalcul. La règle : [`specs/architecture/lots-et-perimetres.md`](specs/architecture/lots-et-perimetres.md).
- **WhatsApp** — notifications programmées vers le groupe de la résidence. ⚠️ Le pont passe par un client non officiel (Baileys) : le numéro peut être bloqué, le courriel reste le canal de repli.
- **Installation** — rôle, version, inscription au registre et bail de l'installation, pour l'opérateur.
- **Maintenance** — export vérifié de la base, tâches automatiques, contrôles de santé, audit de sécurité nocturne de chaque nœud et suivi de la consommation de l'IA.
- **Installations** — registre des installations CoproFirst inscrites, pour l'opérateur de la référence seulement.
- **Liens partageables** — chaque onglet et chaque publication a son adresse propre ; le lien n'ouvre aucun droit.
- **Thème clair ou sombre** — Automatique (suit le réglage de l'appareil), Clair ou Sombre, choisi dans le profil et retenu par appareil ; la page arrive déjà dans son thème, sans éclair, et l'impression reste claire. Le décor des jours de fête, allumé par l'administration, s'éteint pour soi au même endroit (retenu par le compte).
- **Saisie d'une affaire, Essentielle ou Complète** — réglée dans le profil, pour tout le compte : la saisie essentielle ne montre que les champs qu'il faut selon la catégorie et range les autres dans « Plus de détails » ; la complète montre tout. Par défaut, Essentielle pour tout le monde.
- **Demander la suppression de son compte** — depuis le profil (et l'app iPhone), mot de passe exigé : l'administration la traite dans « À traiter » sous 30 jours au plus, par la purge habituelle (données personnelles effacées, contributions collectives gardées sans nom) ; la demande se retire jusque-là (#2699).
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
│   ├── alembic/       # Migrations de la base d'une copropriété
│   └── alembic_plateforme/ # Migrations de la base du registre des installations
├── front/             # Frontend SvelteKit
│   ├── src/routes/    # Pages de l'application
│   └── e2e/           # Tests de navigateur (Playwright)
├── whatsapp-bridge/   # Bridge WhatsApp (Node.js)
├── scripts/           # Tous les scripts
│   ├── exploitation/  # Lancés par cron/systemd sur les RPi (bascule, failover…)
│   ├── lib/           # Modules sourcés par les précédents
│   ├── poste/         # Développeur et CI (pré-check, rejeu CI, export hors site)
│   ├── ci/            # Lancés par la CI (publication, tags, purge des images, essais)
│   └── installation/  # Durcissement système et sudo, tunnel — la réinstallation
│                      # d'un nœud se suit pas à pas (docs/restauration-complete.md)
├── infra/             # Worker Cloudflare, points d'entrée de la référence (crons,
│                      #   systemd — infra/points-entree/), PostgreSQL (initdb, pg_hba)
├── deploiement/       # Installation standard depuis les images publiées, démo publique
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
# Éditer .env — sans ces valeurs, rien ne démarre :
#   SECRET_KEY               32 caractères au moins ; l'API refuse la valeur d'exemple
#   WHATSAPP_API_KEY         16 caractères au moins, même sans WhatsApp :
#                            docker compose refuse de démarrer sans elle
#   POSTGRES_PASSWORD        openssl rand -hex 32 : sans lui, la base refuse de s'initialiser
#   DATABASE_URL             y recopier POSTGRES_PASSWORD à la place de <POSTGRES_PASSWORD>
#   PG_REPLICATION_PASSWORD  openssl rand -hex 32 : sans lui, l'initialisation de la base
#                            s'arrête (infra/postgresql/initdb/10-replication.sh)
# et ORIGIN, l'adresse du site (http://localhost en local, avec COOKIE_SECURE=false).

# Lancer
docker compose up --build -d
```

L'application est accessible sur `http://localhost`.

> 📦 **Images publiées.** Chaque version reçoit un tag `vX.Y.Z` et des images
> signées (amd64 et arm64) : `ghcr.io/philippe-tressard/coprofirst-api`, `-front`,
> `-caddy` et `-whatsapp-bridge`, étiquetées par version (et chaque commit de `main`
> par `sha-<commit>`). Vérifier une image :
> `gh attestation verify oci://ghcr.io/philippe-tressard/coprofirst-api:<version> --owner philippe-tressard`.
> **Ce que reçoit une installation** se décide à la référence, dans son **bail**
> d'inscription au registre : son **canal** — *Urgence*, la dernière version publiée,
> ou une version choisie — et sa **vague** — *Urgence* (aussitôt), *Standard* (le
> défaut : le dernier correctif de plus de 7 jours de la mineure qui précède la
> dernière) ou *Fixe* (la version choisie, 7 jours après sa publication). La mise à
> jour nocturne installe la version que le bail porte, et rien sans bail valide
> (`api/app/registre/canaux.py`). La branche `replica` n'en décide plus depuis #2210.
> **Installer sans construire** : [`deploiement/standard/LISEZMOI.md`](deploiement/standard/LISEZMOI.md)
> — chaque version taguée joint son archive de déploiement à ses notes de version
> (onglet *Releases*).
> Le serveur d'une installation y reçoit seul ses **correctifs de sécurité** — système,
> Docker, `cloudflared` — chaque nuit à 03:00, contrôlés chaque matin
> (`deploiement/standard/correctifs-systeme.sh`).
> **Contrat d'API.** Chaque version taguée joint aussi `openapi.json` à sa release —
> le schéma de l'API, exporté de son image publiée —, avec les tables que le site
> partage (`tables-clients.json` : onglets, statuts, jetons de la charte, palettes),
> les constantes de l'API (`constantes-clients.json`) et le catalogue d'icônes
> (`icones-svg.json`) : un client hors du navigateur (les apps iOS et Android) en
> génère son code. La liste brute des onglets (`pages.ts`) y reste jointe tant que
> l'app iOS la lit (#2686). Une installation dit le contrat
> qu'elle sert par `GET /config` (`version_contrat`) ; le schéma n'est jamais servi
> par le site (`api/app/contrat`).

Au premier lancement, deux comptes sont créés avec un **mot de passe aléatoire** affiché dans les logs : l'**administrateur** de la copropriété (`admin@localhost`) et l'**opérateur** de l'installation (`operateur@localhost`, administrateur aussi — supervision, santé, inscription au registre). Séparés pour confier le premier sans livrer le second. Sur une installation **commune**, qui sert plusieurs copropriétés, l'opérateur n'est pas accordé par un administrateur : l'exploitant du serveur le désigne dans le fichier des copropriétés (champ `operateurs`).

Tant qu'elle n'a pas de bail actif du registre de la référence (inscription validée), une réplique est en **mode limité** : **5 comptes actifs** au plus — ces deux comptes techniques ne comptent pas, aucun compte existant n'est touché —, ni service du registre, ni mise à jour automatique. Suspendue par la référence, elle passe en **lecture seule**, export ouvert à l'administrateur. Un bail échu ramène au mode limité, jamais à la lecture seule. `REGISTRE_CONSTAT=true` (`.env`) remet le plafond et la lecture seule en simple constat (spec `multi-coproprietes.md` §4.11).

```bash
docker compose logs api | grep -A5 "ADMIN INITIAL"
```

> **Changez immédiatement les mots de passe** après la première connexion.

### Développement local (sans Docker)

```bash
# Backend — DATABASE_URL désigne alors un PostgreSQL 17 joignable depuis le poste
cd api && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (autre terminal)
cd front && npm install && npm run dev

# Tests de navigateur (le serveur de dev démarre tout seul)
#   (npm run e2e joue Chromium ET WebKit, bureau et mobile)
cd front && npx playwright install chromium webkit && npm run e2e
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
| [docs/licences-tierces.md](docs/licences-tierces.md) | Inventaire **généré** des licences tierces — dépendances, bibliothèques système des images, exceptions déclarées, fichiers repris (vérifié en CI) |
| [docs/carte-reglages.md](docs/carte-reglages.md) | Carte **générée** des réglages — qui règle quoi (administrateur, conseil syndical, opérateur, exploitant du serveur), où, et où la valeur vit ; l'accès de chaque notion est confronté à la route en CI (#2061) |

## Sécurité

- JWT avec cookies HttpOnly / Secure / SameSite=strict
- Hachage bcrypt des mots de passe
- **Autorisation centralisée** — dans `api/app/auth/` : les dépendances d'accès (`deps.py`), les règles d'appartenance — « cet objet est-il le mien ? » (`appartenance.py`), l'opérateur de la plateforme (`operateur.py`) et les jetons d'appareil (`jetons_appareil.py`) ; chaque endpoint en dépend, les rares exceptions publiques sont énumérées et justifiées (vérifié en CI)
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
