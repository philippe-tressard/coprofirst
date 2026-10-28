---
name: security-audit
description: "Run a complete OWASP Top 10 security audit on the 5Hostachy project (FastAPI + SvelteKit + PostgreSQL). Use when: checking for vulnerabilities, reviewing security posture, before a release, after adding auth/upload/API features."
argument-hint: "Optional: scope the audit (e.g. 'auth only', 'uploads', 'full')"
---

# Security Audit — 5Hostachy (OWASP Top 10)

Audit de sécurité complet du projet. Exécuter chaque vérification dans l'ordre, reporter les findings, et proposer des fixes.

## Stack technique

- **Backend** : FastAPI + SQLModel + PostgreSQL
- **Frontend** : SvelteKit (SSR + CSR)
- **Auth** : JWT en cookie HTTP-only (bcrypt)
- **Déploiement** : Docker sur Raspberry Pi 5, Caddy reverse proxy

## Procédure d'audit

### 1. SQL Injection (A03:2021)

**Rechercher** les requêtes SQL brutes avec interpolation :
```powershell
Get-ChildItem -Recurse -Filter "*.py" | Where-Object { $_.FullName -notmatch "__pycache__|alembic" } | Select-String -Pattern "text\(f[`"']|\.format\(|%\s" | Where-Object { $_.Line -match "SELECT|INSERT|UPDATE|DELETE" }
```

**Règle** : SQLAlchemy ORM = safe. `text()` avec f-string/format = CRITIQUE.
**Fix** : `text("... :val").bindparams(val=...)` — toujours des paramètres liés.

### 2. XSS — Cross-Site Scripting (A07:2021)

**Rechercher** les usages de `{@html}` dans Svelte :
```powershell
Get-ChildItem -Recurse -Filter "*.svelte" | Select-String -Pattern "@html"
```

**Règle** : Tout `{@html}` DOIT passer par une fonction de `#lib/sanitize.ts` — elles sont **trois** (`safeHtml`, `safeRichContent`, `safeDescription`), toutes adossées à DOMPurify. Vérifié en CI par `npm run lint:html` (`CLAUDE.md`, règle front n° 1), qui exige que le nom vienne de l'**import** : une fonction locale homonyme ne prouve rien (#429).
**Exceptions** : déclarées dans `front/scripts/check-html.mjs` (`EXCEPTIONS`), avec leur raison — et le contrôle **échoue** si l'une cesse de servir. Ne pas les recopier ici : cette ligne n'en nommait qu'une sur deux, et un audit qui la suivait signalait la seconde comme un écart qui n'en était pas un (#1051).
**Fix** : `import { safeDescription } from '#lib/sanitize.ts'` → `{@html safeDescription(contenu)}` — et jamais un helper local, fût-il correct : c'est ainsi que trois copies de `safeDescription` ont coexisté.

Configuration DOMPurify — **lire `front/src/lib/sanitize.ts`**, jamais cette page :
la liste recopiée ici avait déjà perdu `details` et `summary`, ajoutés le 17/09/2026
avec les blocs dépliables (#992 ; `open` est volontairement hors `ALLOWED_ATTR`).

### 3. Téléversement : une seule porte (A01:2021)

🔴 **Le geste ne se réécrit pas, il s'appelle.** Un fichier reçu s'écrit sur
disque par `utils/fichiers.enregistrer_fichier_recu`, et nulle part ailleurs.
Les règles vivent dans `FAMILLES` du même module — liste blanche de types,
plafond de taille, extensions autorisées —, une entrée par famille :
`image`, `document`, `document_prive`, `tableur`.

**Un routeur nomme une famille**, il ne redéfinit pas ce qu'il accepte.

#### Ce que l'audit du 19/09/2026 a trouvé (#1026)

Le téléversement avait **trois écritures**, appliquant des règles différentes :

| Chemin | Types | Plafond | Signature |
|---|---|---|---|
| documents privés (`utils/fichiers`) | **aucun** | **aucun** | oui |
| images (`routers/uploads`) | oui | oui | réencodage PIL |
| documents joints (`routers/uploads`) | oui | oui | oui, **recopiée** |

Et **trois imports de tableur n'avaient aucun contrôle** : ni type, ni taille.
Ils n'étaient pas dans la portée du test de signature, dont le critère était
« les endpoints qui **écrivent** sur le disque » — or un import analyse en
mémoire. La portée était juste, et elle laissait dehors trois chemins par
lesquels un fichier arbitraire entrait.

⚠️ **Une duplication de règle de sécurité ne produit aucun signal** : un fichier
accepté à tort est stocké, servi, et personne ne s'en plaint. C'est pourquoi
cette question se mesure par des contrôles, et non en relisant les routeurs.

#### Les contrôles, et ce que chacun tient

| Contrôle | Ce qu'il refuse |
|---|---|
| `test_televersement_source_unique.py` | une écriture de fichier reçu hors du module ; une liste MIME ou un plafond redéclaré dans un routeur ; une famille qui oublie l'une des trois règles |
| `test_signature_fichiers.py` | un point de réception qui n'appelle pas la règle — **les sept**, imports de tableur compris |
| `test_pieces_jointes.py` | une divergence entre ce que le front propose et ce que le serveur accepte |

Le PDF d'affiche de hall est la **seule** écriture déclarée hors du module :
l'application le **produit**, il n'est pas reçu, donc il n'a ni type à vérifier
ni signature à confronter. La distinction est écrite dans le contrôle.

#### Le nom stocké

`nom_stocke` : préfixe UUID, radical assaini, et **extension dérivée du type**,
jamais du nom fourni. `/uploads/*` est servi en statique et Caddy pose le
`Content-Type` d'après l'extension sur disque : un `.html` téléversé sous un
type MIME autorisé s'exécuterait sur notre origine.

#### La racine du volume

`Settings.uploads_dir`, lue par le seul contexte de copropriété ; un fichier ne
se situe que par `utils/stockage`, qui borne toute clé sous la racine (#1748).
Elle était écrite six fois, puis traduite en `"/app" + url` à trois endroits. Un fichier posé hors du volume n'est ni répliqué vers le
standby par `bascule.sh`, ni sauvegardé par `backup.py` — il est perdu à la
première bascule, sans aucun signal.

### 3 bis. Contrôle d'accès : chercher la règle à son CONTENU (A01:2021)

Une règle d'accès vit dans `auth/deps.py` (dépendances et prédicats),
`auth/appartenance.py` (« est-ce le vôtre ? ») ou `utils/visibility/` (« qui
voit quoi ») — la règle d'emplacement est dans `CLAUDE.md`, Backend.

🔴 **Ce que l'audit doit chercher, c'est la règle recopiée qui ne LÈVE pas.**
Une visibilité rend `False`, une liste fait `continue` : ni l'une ni l'autre ne
porte de `HTTPException` ni un nom en `*_visible`. L'audit du 02/10/2026 en a
trouvé trois (#1551), identiques à leur source ce jour-là, donc invisibles à
l'usage — la divergence n'arrive que le jour où la source apprend quelque chose.

| Contenu qui trahit une copie | Source | Contrôle |
|---|---|---|
| `….roles_autorises` lu | `visibility.profil_admet` | `test_autorisation.py` |
| un élément de `….user_lots` jugé sur `actif` | `deps.est_rattache_au_lot` | `test_appartenance_lot_source_unique.py` |
| un champ comparé à `user.id` par `auth/appartenance.py`, recomparé ailleurs | le prédicat du module (`peut_defaire_le_versement`…) | `test_appartenance_source_unique.py` |

**Le geste d'audit** : pour une règle neuve, se demander *quelle donnée elle
lit* (un champ de profil, `actif`, un champ de propriété), puis chercher cette
lecture sur l'AST hors de la source. Un écran qui **liste** ce qu'un geste
**autorise** doit appeler le même prédicat : sinon il propose un bouton qui
rend 403, ou tait un geste permis.

### 4. Authentication & Session (A07:2021)

#### Cookies JWT
```powershell
Get-ChildItem -Recurse -Filter "*.py" | Select-String -Pattern "secure=|samesite=|httponly="
```

**Vérifier dans `api/app/routers/auth.py`** (`COOKIE_OPTS`) — et non dans le paquet `api/app/auth/`, qui porte les dépendances et le JWT, aucun cookie :
- `secure=settings.cookie_secure` (True en prod, False en dev via `.env`)
- `samesite="strict"`
- `httponly=True`

#### SECRET_KEY
```powershell
Get-ChildItem -Recurse -Filter "*.py" | Select-String -Pattern "secret_key.*=.*\""
```

**Vérifier dans `config.py`** :
- `field_validator` rejetant les valeurs connues insécurisées
- Longueur minimale 32 caractères

#### Password hashing
```powershell
Get-ChildItem -Recurse -Filter "*.py" | Select-String -Pattern "bcrypt|passlib|sha256|md5|hashlib|plaintext"
```
**Attendu** : bcrypt uniquement (via `passlib` ou `bcrypt` direct).

#### Poser un mot de passe = fermer les sessions qu'il ouvrait

🔴 Deux routes posent un mot de passe — « changer le mien » et « j'ai oublié le
mien » — et elles ont **divergé** jusqu'au 19/09/2026 : la seconde révoquait les
sessions actives, la première ne révoquait rien. Un attaquant qui détenait une
session la conservait sept jours après que la victime avait changé son mot de
passe (#1027).

**Le geste s'écrit une fois** : `app/utils/mots_de_passe.poser_mot_de_passe()` —
hachage, révocation des autres sessions, et la session appelante conservée quand
elle se présente. `api/tests/test_reinitialisation_mot_de_passe.py` refuse qu'une
route hache un mot de passe elle-même.

⚠️ **Ce que la révocation ne couvre pas** : le jeton d'accès est un JWT
autoporteur de 120 minutes, que rien ne révoque côté serveur. La fenêtre passe de
sept jours à deux heures, pas à zéro — #1063 porte la décision.

### 5. CORS (A05:2021)

```powershell
Get-ChildItem -Recurse -Filter "*.py" | Select-String -Pattern "CORSMiddleware|allow_origins|allow_methods|allow_credentials"
```

**Vérifier dans `main.py`** :
- `allow_origins` : liste explicite (JAMAIS `["*"]` avec `credentials=True`)
- `allow_methods` : liste explicite (`["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"]`)
- `allow_credentials=True` seulement si origins explicites

### 6. Rate Limiting (A04:2021)

```powershell
Get-ChildItem -Recurse -Filter "*.py" | Select-String -Pattern "slowapi|RateLimiter|throttle|limiter"
```

**Les limites vivent dans `api/app/utils/limiter.py`**, une constante par
**intention** (secret éprouvé, courriel déclenché, session, contrôle de fichier,
lecture authentifiée, collecte d'audience, données personnelles, lecture publique). Chaque constante dit pourquoi
elle vaut ce qu'elle vaut — et c'est là qu'on lit la valeur, pas ici.

🔴 Ce tableau les recopiait, et il a été **faux** : `/auth/change-password` et
`/auth/verifier-email` n'avaient aucune limite alors que les deux éprouvent un
secret, et les quatre routes de `auth_profil.py` non plus. Une liste recopiée ne
dit rien des routes qu'elle omet — c'est précisément ce qui manquait (#1027).

🔒 **Le contrôle qui remplace ce tableau** : `api/tests/test_limites_debit_auth.py`
exige que **toute** route d'un module `auth*.py` porte un `@limiter.limit`, que sa
valeur vienne d'une constante de `utils.limiter`, que le décorateur soit **sous**
celui de la route (au-dessus, il n'a aucun effet, en silence) et que la fonction
reçoive une `request` (sans elle, slowapi lève au premier visiteur, pas au
démarrage).

🔒 **Les limites valent PAR VISITEUR** depuis le 25/09/2026 (#1300) : Caddy lit
`Cf-Connecting-Ip` d'un proxy de confiance (le réseau Docker, pas le LAN) et
uvicorn prend ce qu'il transmet. `api/tests/test_adresse_client.py` tient la
chaîne. Avant, un seul seau pour tout le site.

🔒 **Un appel qui se FACTURE** (fournisseur d'IA, `utils.llm.demander`) porte
`LIMITE_APPEL_FACTURE` : `api/tests/test_limite_appel_facture.py` relève dans le
code les routes qui l'atteignent. Aucune ne l'avait avant le 25/09/2026 (#1299).

**Ce qu'il reste à faire à la main** : juger si le plafond d'une route est *bien
réglé*. Le contrôle vérifie qu'il existe et qu'il est nommé, jamais qu'il est
prudent.

### 7. Refresh Token Rotation (A07:2021)

**Vérifier** que `/auth/refresh` :
1. Invalide l'ancien refresh token (`revoked=True`)
2. Crée un nouveau refresh token
3. Retourne le nouveau token en cookie
4. **Ferme toutes les sessions du compte** quand un jeton déjà **échangé** revient
   après le délai de grâce : c'est le seul signal d'un vol de session (27/09/2026).
   Un jeton fermé par une déconnexion ou un mot de passe posé ne déclenche rien.
   La règle, la purge qui garde les jetons échangés et le délai vivent dans
   `app/auth/jetons_rafraichissement.py` — 🔒 `test_jeton_rejoue.py` éprouve les
   trois révocations et refuse une purge ou un échange écrits ailleurs.

5. **Le jeton en base est une EMPREINTE** (`auth/empreinte_jeton`, #1389) : le
   cookie porte le brut, `refresh_token.token` son HMAC. Vaut aussi pour les
   jetons de mot de passe oublié et de vérification d'adresse. 🔒
   `test_jetons_empreinte.py` refuse une écriture ou une recherche en clair.

Une **clé partagée** (`MAINTENANCE_KEY`) se compare par `hmac.compare_digest`, en
octets — jamais `==` : 🔒 `test_cle_maintenance.py` refuse un réglage secret
comparé par égalité.

### 8. Secrets & Configuration (A02:2021)

```powershell
# Secrets hardcodés
Get-ChildItem -Recurse -Filter "*.py" | Select-String -Pattern "secret_key.*=.*\"|password.*=.*\"|api_key.*=.*\""

# .env dans .gitignore
Get-Content .gitignore | Select-String -Pattern "\.env"

# .env.example sans vraies valeurs
if (Test-Path .env.example) { Get-Content .env.example }
```

#### Un secret s'écrit une fois, et jamais dans une URL (#1596, #1598)

- **La clé du bridge WhatsApp** : `.env` seulement (`WHATSAPP_API_KEY`), lue par
  le bridge et par `utils/whatsapp.entetes_bridge` — `ConfigSite` la refuse
  (`utils/reglages.REFUSEES`, #2055). Le bridge refuse au démarrage une clé vide, d'exemple ou
  trop courte, et ignore `?apikey=`. 🔒 `api/tests/test_cle_bridge_whatsapp.py`,
  `whatsapp-bridge/tests/contrat-http.test.js`.
- **Le SSH entre les nœuds** authentifie aussi le SERVEUR : clé d'hôte épinglée
  dans `/root/.ssh/known_hosts_bascule`, commande écrite dans
  `scripts/lib/lib-ssh-noeuds.sh` seulement. 🔒 `scripts/poste/scripts-ci-ssh-noeuds.sh`
  (job `test-scripts`) refuse la confiance d'office (`StrictHostKeyChecking` à `no`) et toute copie.

#### Aucune personne réelle dans le dépôt — il est PUBLIC (#1493)

Un test, un e2e, un commentaire qui cite le cas signalé : le nom vient de l'écran,
du fichier d'import ou du courriel — c'est une donnée personnelle publiée, et
l'historique git la garde (`standards/14`). Trente-trois fichiers en portaient le
01/10/2026 : syndic, résidents, l'auteur.

- Un nom inventé **de même forme** (casse, trait d'union, accent, particule —
  c'est souvent ce que le test éprouve), jamais le vrai, même pour « reproduire
  exactement ».
- 🔒 `api/tests/test_identites_fictives.py` tient une **liste blanche** de noms
  inventés : un nom de personne hors de la liste fait échouer la CI. Une liste
  noire republierait les vrais noms, compilés. Ses limites — formes repérées et
  ce qu'il ne voit pas — sont écrites dans son en-tête.
- Sa portée : code, tests, **migrations** (`api/alembic`) et **documents**
  (`docs/`, `specs/`, `infra/`, `.claude/skills/`, `.github/`, `.md` de la
  racine). Les deux derniers n'y sont que depuis #1544 : la docstring d'une
  migration recopiait une formule d'appel avec deux noms du syndic. Un dossier
  public qui n'y figure pas n'est **pas** contrôlé — l'ajouter à `PORTEE`.
- Un nom se cherche et se remplace **sans tenir compte de la casse** : le premier
  passage (v2.89.2) a laissé deux clés en minuscules et un nom à casse mixte,
  trouvés à la vérification sur `main`, pas avant.
- Ce qu'aucun contrôle ne lit est public aussi : **message de commit, titre et
  corps d'un ticket ou d'une PR**. Y décrire le cas sans le nom (« un
  copropriétaire homonyme d'une banque »).
- L'attribution légale (licences, SPDX, mentions légales) nomme l'auteur : c'est
  la seule exception, et elle est hors de la portée du contrôle.
- Historique : arbitré le 01/10/2026 — accepté tel quel, non réécrit (GitHub
  garde les références des PR ; une réécriture serait incomplète).

#### Exception assumée : l'identifiant SSH d'exploitation et les IP du LAN (#1581)

Arbitré par Philippe le **06/10/2026** (option « garder »), après l'audit du
02/10/2026 : l'identifiant SSH des nœuds et leurs adresses `192.168.1.x`
figurent dans les scripts, crontabs, sudoers et documents d'exploitation d'un dépôt
PUBLIC. Ce n'est **pas** un oubli, c'est une décision :

- une adresse du LAN (RFC 1918) n'est pas routable depuis Internet, et l'accès SSH
  se fait par clé ed25519 — pas de mot de passe à deviner ;
- les sortir du dépôt toucherait crontabs, sudoers et une quarantaine de scripts
  (un lot d'infrastructure entier, avec le risque d'un nœud qui ne se reconnaît
  plus), pour un gain de sécurité que la clé et le non-routage rendent faible.

⚠️ **Ce que la décision suppose, et que le poste ne peut pas vérifier** : le port
22 des nœuds n'est ouvert nulle part sur la box. Si un jour il l'est (redirection,
accès distant), l'exception **se rouvre** et ces identifiants se sortent du dépôt.

🔒 `api/tests/test_hygiene_depot.py` l'enferme : l'identifiant et les IP restent
dans `scripts/`, `infra/`, `docs/`, `.claude/` et deux fichiers de la racine —
**jamais** dans `api/app`, `front/src`, le bridge ni un test — et le nombre de
fichiers qui les portent est **fixé** : il échoue dans les deux sens (un fichier de
plus, ou un retiré sans baisser la valeur). Un nouvel identifiant d'infrastructure
s'écrit dans les scripts d'exploitation, pas dans l'application.

### 9. Dépendances vulnérables (A06:2021)

```powershell
# Python
pip audit --requirement api/requirements.txt

# Node.js
cd front; npm audit
```

### 10. Headers de sécurité (A05:2021)

**Vérifier dans `Caddyfile`** :
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security` (HSTS)
- `Content-Security-Policy`

## Rapport d'audit

Pour chaque finding, reporter :

| Champ | Description |
|-------|-------------|
| **Sévérité** | CRITICAL / HIGH / MEDIUM / LOW / INFO |
| **Catégorie OWASP** | A01-A10 |
| **Fichier** | Chemin du fichier affecté |
| **Ligne** | Numéro de ligne |
| **Description** | Ce qui a été trouvé |
| **Fix** | Code correctif proposé |

## Sévérités

| Niveau | Critères |
|--------|----------|
| CRITICAL | Exploitation directe, accès données, RCE |
| HIGH | Contournement auth, injection, path traversal |
| MEDIUM | CORS mal configuré, headers manquants, rate limit absent |
| LOW | Bonnes pratiques non respectées, info disclosure |
| INFO | Recommandation d'amélioration |
