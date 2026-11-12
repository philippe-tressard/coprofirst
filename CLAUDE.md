# CLAUDE.md — 5Hostachy

Ce fichier ne porte que ce qui doit être vrai **à chaque session**. Le détail vit dans
les skills du projet (`.claude/skills/`), chargées quand la tâche le demande — les ouvrir
*avant* d'agir. Les pratiques génériques sont dans le socle `~/.claude/standards/`
(routage : `~/.claude/CLAUDE.md` §1) ; ici, seulement leur instanciation.

**Avant toute implémentation, chercher le motif existant.** S'il existe deux fois ou
plus, l'appliquer à l'identique ; si une demande contredit un motif établi, le dire et
demander confirmation.

## Stack

- **Backend** : FastAPI + SQLModel + Alembic (`api/`) — **PostgreSQL 17**, seul moteur :
  production (répliquée vers le standby) et tests (CI et poste, `TESTS_BASE_URL`)
- **Documents imprimables** : HTML/CSS → PDF via WeasyPrint (libs système dans `api/Dockerfile`)
- **Frontend** : SvelteKit v3 + TypeScript strict + Vite 8 + PWA (`front/`)
- **Infra** : Docker Compose + Caddy + 2 Raspberry Pi 5
- **Langue** : français exclusif (interface et nommage des champs)

## Skills du projet

| Tâche | Skill |
|---|---|
| MEP, rejeu de la CI, pré-check, post-check, rollback, version et images | `mep-precheck` |
| Infra, bascule, RPi, base, crons, WhatsApp, incident, scripts d'infra en CI | `infra-rpi` |
| Écran, composant, libellé, checklist front avant commit | `ux-patterns` |
| Page ou composant SvelteKit, store, appel API côté front, tests Playwright | `svelte-patterns` |
| Code de l'API : modèle, schéma, routeur, migration, utilitaire, tests pytest | `api-scaffold` |
| Auth, droits, secrets, téléversement, fichiers servis, exposition publique | `security-audit` |
| Documentation utilisateur — manuel **et** `README.md` | `user-manual` |

---

## Règle d'or des données (PostgreSQL)

La base est un PostgreSQL par nœud : un **primaire** sur l'actif, une **réplique** en
flux sur le standby (DI-7b, #1781). La lire depuis un autre processus est permis
(`docker exec hostachy_postgres psql`, C37, la sauvegarde). Les gestes qui détruisent
sont interdits :

- **Jamais deux primaires.** Un ancien primaire ne se relance jamais tel quel après une
  promotion : il s'isole, puis se reconstruit en réplique
  (`sudo bash scripts/exploitation/reconstruire-replique.sh --oui`, sur le standby, en root).
- **Jamais une base absente démarrée sur un nœud qui prend la main** : l'image
  l'initialiserait en primaire VIDE. Un `docker compose up -d` complet sur un standby sans
  réplique fait exactement cela — passer par `lib-promotion.sh` (`decider_prise_de_main`),
  comme la bascule, le failover et la garde au démarrage.
- **Jamais `docker compose up|stop|down` sans liste de services** : sur le standby il
  arrêterait la réplique, sur un nœud rétrogradé il relancerait un primaire (#1997). Les
  listes : `$SERVICES_APPLICATIFS`, `$SERVICE_BASE`, `$SERVICES_DU_NOEUD`
  (`lib-applicatifs.sh`). 🔒 `test_applicatifs_source_unique.py` (scripts **et** consignes,
  #2706).
- **Un nœud ne sert que sur un rôle relu à l'instant** : `servir_images` (`lib-servir.sh`,
  auto-deploy et `MaJ-Hostachy.sh`) relit `.active` avant chaque démarrage, et le failover
  isole l'ancien actif sous son verrou de déploiement, `.active` réécrit dans le même appel
  (`lib-failover.sh`, #1997 #2000).
- **Jamais `docker volume rm 5hostachy_pg_data`**, ni une écriture sur la réplique.

C37 (`lib-replication.sh`) et le point 22 du pré-check disent deux primaires, une réplique
absente, déconnectée ou en retard. Conduite à tenir : `infra-rpi`.

**Exporter la base** (#1749) : par l'administration — `POST /admin/export-copropriete`
(archive complète) et `…/verifier` (réimport dans une base jetable), dans le processus de
l'API, en une transaction. `python -m app.utils.export_copropriete` dans le conteneur ne
sert qu'à **importer** une archive dans une base CIBLE neuve. Un état multi-fichiers
qu'un processus tient ouvert ne se copie pas à chaud (`standards/06` §1 ; l'état
d'authentification WhatsApp, `infra-rpi`).

---

## Front — les quatre règles

Le détail des motifs : `ux-patterns` (et sa checklist avant commit) et `svelte-patterns`.
Les arbitrages d'interface sont numérotés dans `.claude/skills/ux-patterns/ARBITRAGES.md`
(exemple : arbitrage n° 21, ✨ ne se dit que de l'IA).

1. **XSS** : jamais `{@html contenu}`, toujours `{@html <assainisseur>(contenu)}`. Les
   trois assainisseurs, exportés par `#lib/sanitize.ts` et adossés à DOMPurify : `safeHtml`
   (HTML riche), `safeRichContent` (riche ou texte, sans enveloppe — dans un `<p>`),
   `safeDescription` (idem, avec enveloppe `<p>`). 🔒 `npm run lint:html` lit leur liste
   dans `sanitize.ts` et exige que le nom vienne de l'import.

   Deux exceptions, déclarées dans `EXCEPTIONS` du contrôle, qui échoue si l'une cesse de
   servir : `Icon.svelte` (SVG codé en dur) et `QRCode.svelte` (SVG produit localement par
   `qrcode-generator`, jamais interpolé). Toute nouvelle exception s'ajoute ici avec sa
   raison.
2. **Dates, montants, nombres** : jamais un format réimplémenté dans une page. `#lib/date.ts`
   (`fmtDate`, `fmtDatetime`, `fmtMonthYear`…), `#lib/utils.ts` (`fmtMontant`, `fmtOctets`,
   `fmtNombre`, `perimetreLabel`), côté API `app/utils/dates_fr.py`. Un nombre ou un mois que
   l'API envoie ne se rend pas brut (une clé `AAAA-MM` se type `MoisIso`, `api/valeurs.ts`,
   #2358). 🔒 `api/tests/test_dates_fr.py`, `npm run lint:dates` (`check-nombres-bruts.mjs`,
   écarts déclarés : `NON_QUANTITES`, `HOMONYMES`).
3. **Accessibilité** : tout élément cliquable non-`<button>` porte `role="button"`,
   `tabindex="0"` et `on:keydown` (Enter/Space) ; `aria-label` sur les boutons icône-seule ;
   `role="dialog"` + `aria-modal="true"` sur les modales (`standards/11` §2).
4. **Icônes de contexte** : 📍 = lieu physique, 🔹 = périmètre logique, jamais mélangés. Le
   périmètre par défaut ne s'affiche pas : la question se pose à `estPerimetreParDefaut`
   (`#lib/perimetres`), jamais par un `=== 'résidence'` (le nom de la racine est
   administrable). Le badge 🔹 ne se rend que par `BadgePerimetre` (🔒 `npm run
   lint:pictogrammes`). Côté API : `app/utils/perimetres/arbre.py` —
   `est_perimetre_par_defaut(codes)`, `perimetre_cible_json(codes)`,
   `perimetre_defaut_liste()`, qui lisent la racine dans l'arbre (`code_par_defaut`) ; le code
   « résidence » n'est écrit que par le seed (🔒 `test_perimetre_racine_source_unique.py`,
   exception déclarée : `Document.perimetre`, autre axe — *qui lit* un fichier).

---

## Backend — les portes uniques

Chaque notion a **une** porte ; le détail, les pièges et les exceptions sont dans
`api-scaffold` §8–9. Un test refuse la copie.

- **Modèle** dans le module de son domaine (`app/models/<domaine>.py`), importé par
  `models/__init__.py` — jamais dans `core.py` (🔒 `test_core_sans_modele_neuf.py`,
  `test_modeles_enregistres.py`). Champs et tables en français ; noms anglais existants
  figés (`test_nommage_francais.py`).
- **Horloge** : `horloge.maintenant()` (UTC naïf, champ `NaiveDatetime`), le jour du résident
  `horloge.aujourd_hui()` — jamais `datetime.utcnow()`, `date.today()` ni `datetime.now()`
  sans fuseau (🔒 `test_horloge.py`).
- **Une copropriété** : `app/contexte.py` (`nouvelle_session`, `moteur`, `courante`,
  `etat`) — jamais `engine`, `SessionLocal` ni `settings.database_url|secret_key|…`
  (🔒 `test_contexte_source_unique.py`, `test_etancheite_coproprietes.py`).
- **Lire ou 404** : `utils/recuperer.ou_404` ; **lire puis 403** :
  `auth/appartenance.exiger_objet_autorise` ; **rendre** : `Schema.model_validate` ou
  `utils/lecture.lire_objet`.
- **Énumération** : `utils/valeurs.valeur(x)` ; écrite pour une personne, son `libelle_*`.
- **Archiver**, pas de colonne `actif` par réflexe : `utils/archivage.REGLES`.
- **Lot** : `utils/designation_lot` (nature), `utils/perimetres/lots` (périmètres).
- **Destinataires** : `app/utils/destinataires.py` ; **diffusion** vers le groupe :
  `utils/diffusion` ; **service activé ?** : `utils/services.service_actif`.
- **PDF** : `app/utils/pdf_theme.py`, rendu hors du process par `app/utils/pdf_rendu.py`
  (enfant `spawn`, jamais `fork`).
- **Tâches planifiées** : `app/utils/taches.TACHES_PERMANENTES`, enregistrées par copropriété.
- **Contrat de l'API** (`api/app/contrat/reference.json`) et tables publiées pour l'app iOS
  (`front/tables-clients.json`) : générés, jamais édités ; un retrait s'annonce dans
  `RETRAITS`. Une règle d'affichage que le site et l'app montrent se calcule dans l'API.

### Migrations Alembic
- **Deux chaînes, deux bases** : `alembic/` migre la base d'une copropriété ;
  `alembic_plateforme/` migre la base `plateforme` du registre des installations, par
  `python -m app.registre.migrer` — jamais `alembic upgrade head`. Ses tables ont leurs
  métadonnées (`registre/modeles.registre_plateforme`), jamais sous `app/models/`
  (🔒 `test_registre_inscription.py`).
- ID séquentiel à 4 chiffres (`0087`, `0088`…). **Jamais** modifier une migration
  existante : en créer une nouvelle.
- **Jamais de f-string dans `op.execute()` pour une valeur** → `text(...).bindparams(...)`.
  Un identifiant s'interpole depuis une constante du fichier, dit en commentaire.
  🔒 `test_migrations.py` ; Ruff `S608` sur `api/app/`.
- `start.sh` a `set -e` : une migration qui plante bloque le conteneur.
- **Une migration reste compatible avec la version précédente du code** (#1757) : revenir
  en arrière n'est qu'un changement d'image, sans restaurer la base. **Ajouter, puis
  retirer — jamais dans la même version** : une colonne neuve est nullable ou porte un
  `server_default` ; retirer, renommer, passer à `nullable=False` est un second temps,
  annoncé dans `CONTRACTIONS` par le lot où le code cesse d'en dépendre. Pas de SQL brut
  qui retire ou renomme. 🔒 `test_migrations_compatibles.py`.

### Dépendances d'auth
| Dependency | Usage |
|-----------|-------|
| `get_current_user` | Tout utilisateur connecté |
| `require_cs_or_admin` | Création/modification de contenu |
| `require_admin` | Suppression définitive, config système |
| `require_operateur` | Supervision technique et base (`/admin/maintenance/sante`, `/admin/db/*`…) — l'opérateur de la plateforme, pas l'administrateur de la copropriété (#1750). Sur une instance commune, désigné par l'exploitant (`operateurs` de la déclaration) : `auth/operateur.roles_effectifs` |
| `require_proprietaire` | Fonctions propriétaires |
| `require_questions_reglement` | Questions au règlement : `require_proprietaire`, puis la case de l'admin qui ouvre l'usage aux copropriétaires (le CS passe toujours) |

Ces six-là refusent (401 ou 403). La délégation n'en a pas : elle est en **lecture seule**
(#1534) — l'aidant lit ce que lit la personne aidée, par `utils/delegations_actives`.
🔒 `test_autorisation.py` refuse une dépendance qu'aucune route ne prend. Les
**prédicats** disent sans refuser ; ils s'appellent, jamais ne se redérivent :

| Prédicat | La question |
|---|---|
| `est_moderateur(user)` | conseil syndical **ou** admin — « qui modère » (🔒 `test_moderateur_source_unique.py` refuse `has_role(conseil_syndical, admin)` en ligne) |
| `est_rattache_au_lot(user, lot_id, comme=…)` | « ce lot est le mien » (lien actif exigé) ; `comme` en restreint la nature — donner à bail exige un lien copropriétaire (#1535) |
| `peut_commenter` / `peut_editer` | l'auteur, le « saisi pour », l'admin (+ le CS pour commenter) ; une actualité : le CS et son auteur (#1091) |

Les règles d'**appartenance** — « cet objet est-il le mien ? » — vivent dans
`auth/appartenance.py`, jamais chez un routeur ; elles ne sont pas fondues en une
fonction, et c'est voulu (`security-audit` §11). 🔒 `test_appartenance_source_unique.py`.

- **Une route qui reçoit un `lot_id`** (chemin, requête, formulaire ou corps) pose la
  question — `est_rattache_au_lot` ou `exiger_lot_du_bailleur` —, ou se réserve au
  CS/admin, ou se déclare dans `ROUTES_SANS_QUESTION` avec sa raison (#1535).
  🔒 `test_appartenance_lot_source_unique.py`.
- **Une liste qui FILTRE appelle le prédicat du geste qui REFUSE**, jamais sa copie : une
  règle qui rend `False` ou fait `continue` ne lève rien (#1551). Les trois contrôles
  ci-dessus lisent le contenu sur l'AST (`security-audit` §3 bis).

---

## Sécurité — les portes uniques

Le détail de chacune : `security-audit` §11.

- JWT HS256 en cookies `httponly=True`, `secure=settings.cookie_secure`,
  `samesite="strict"` ; CORS en liste explicite, jamais `["*"]` avec `credentials=True` ;
  limitation de débit (slowapi) sur `/auth/*`.
- **Réglages** : `PUT /config` n'écrit qu'une clé déclarée dans `utils/reglages`, une clé
  n'appartient qu'à un onglet, un réglage écrivable est lu ; qui règle quoi :
  `docs/carte-reglages.md`, générée (🔒 `test_reglages_liste_blanche.py`,
  `test_carte_reglages.py`, `test_reglages_lus.py`).
- **Jetons** stockés par leur empreinte (`auth/empreinte_jeton.empreinte`), jamais en clair
  (🔒 `test_jetons_empreinte.py`).
- **Le compte d'une adresse** : `auth/adresse_compte` (🔒
  `test_adresse_compte_source_unique.py`, qui refuse une comparaison sur `Utilisateur.email`). **Changer d'adresse est une demande** :
  `utils/verification_adresse.demander_changement_adresse` (🔒 `test_changement_adresse.py`).
- **Journal de sécurité** : `utils/journal_securite.journaliser_securite` pour tout geste de
  `GESTES_SENSIBLES`, jamais un `logger` local ; **jamais de donnée personnelle dans une
  ligne de journal** (un identifiant, jamais une adresse, un mot de passe ou un jeton) ;
  niveau `WARNING`, jamais `ERROR` (🔒 `test_journal_securite.py`).
- **HTML d'un utilisateur côté serveur** : `utils/html_sur` (🔒 `test_html_sur.py`).
  **Courriel reçu lu par le modèle** : `utils/ia_courriel.lire_un_courriel`, qui ne rend
  que du texte (🔒 `test_ia_courriel.py`, `test_canari_ia.py`).
- **Leurres** : registre `utils/leurres`, valeurs dans le `.env` du nœud seulement
  (🔒 `test_leurres.py`). **Clé du bridge** : vers `whatsapp.adresse_du_bridge` seulement
  (🔒 `test_adresse_bridge.py`).
- **Conteneurs durcis** : `<<: *conteneur_durci` dans `docker-compose.yml` ; une commande
  dans l'API prend `-u app` (🔒 `test_conteneurs_non_root.py`, autotest de S4).
- **Téléversement** : `utils/fichiers.enregistrer_fichier_recu` et nulle part ailleurs ; un
  routeur nomme une famille de `FAMILLES` (🔒 `test_televersement_source_unique.py`,
  `test_signature_fichiers.py`). **Aucune image décodée dans le process de l'API**
  (`utils/images`, 🔒 `test_images_hors_process.py`). **Un fichier servi se lit par son
  porteur** (`utils/visibility/fichiers.exiger_fichier_lisible`, 🔒
  `test_acces_fichiers_porteur.py`). **Un fichier se situe par `utils/stockage`**
  (🔒 `test_stockage_source_unique.py`).
- **Le dépôt est PUBLIC : aucun nom de personne réelle** — ni test, ni commentaire, ni
  commit, ni ticket ; un nom inventé de même forme (🔒 `test_identites_fictives.py`).
  Exception assumée (#1581) : l'identifiant SSH d'exploitation et les IP du LAN restent dans
  les scripts, crontabs et documents, jamais dans l'application (🔒
  `test_hygiene_depot.py`, `security-audit` §8).

---

## Tests et CI — l'essentiel

- La CI (`.github/workflows/ci.yml`) joue à chaque PR : pytest sur PostgreSQL, lints du
  front et du backend, Playwright (bureau et mobile, Chromium et WebKit), self-tests des
  scripts d'infra. Les checks requis se lisent dans la protection de `main`.
- **Rejouer la CI en local** : `REJEU_PROPRIETAIRE="<lot> #<ticket>" bash
  scripts/poste/rejouer-ci.sh --attendre` (sur le Mac, `--venv` et `TESTS_BASE_URL`). Le
  rejeu s'arrête à la phase rapide ; pytest et Playwright sont confiés à la CI de la PR
  (#2571). Un seul rejeu à la fois ; son verrou ne s'efface jamais à la main. Détail :
  `mep-precheck`.
- Pendant le développement : `cd api && pytest tests/<fichier> -q`, `cd front && npx
  playwright test e2e/<spec>`.
- Un correctif s'accompagne du garde-fou qui refuse la récidive, branché dans la CI
  (`standards/05`). Où vivent les garde-fous : pytest → `api-scaffold` §9 ; Playwright →
  `svelte-patterns` ; scripts d'infra → `infra-rpi` ; CI elle-même → `mep-precheck`.

---

## Infrastructure — l'essentiel

Production **HA sur 2 Raspberry Pi** : rpi1 `192.168.1.222` (PhT-RB5), rpi2
`192.168.1.223` (PhT-RB5i2). Les conteneurs de l'application ne tournent que sur le **RPi
actif** (`cat /opt/5hostachy/.active`) ; le standby ne porte que la réplique de la base.
Des conteneurs applicatifs sur les deux = **split-brain**, à traiter avant toute autre
chose.

**Site HS** : SSH sur l'actif, relire `.active` (il doit nommer ce nœud) et vérifier que sa
base est là. Rôle douteux ou base absente → ne rien démarrer : `decider_prise_de_main`
(`lib-promotion.sh`), ou la reprise en main `sudo bash scripts/exploitation/MaJ-Hostachy.sh`.
Sinon :
`cd /opt/5hostachy && . scripts/lib/lib-env-role.sh && . scripts/lib/lib-applicatifs.sh && env_role_appliquer .env actif && docker compose up -d --no-recreate $SERVICE_BASE && docker compose up -d $SERVICES_APPLICATIFS`.

`env_role_appliquer` n'est pas décoratif : `ORIGIN` (nom public pour l'actif, IP locale pour
le standby) dit quel nom l'API sert (sinon **421** au public, #1751), et `COOKIE_SECURE` est
absent chez l'actif (`false` chez le standby). La règle vit dans `scripts/lib/lib-env-role.sh`
seulement (#1077). Bascule manuelle (test), depuis l'actif :
`sudo bash /opt/5hostachy/scripts/exploitation/bascule.sh`.

**Avant de suspecter un nœud** : depuis l'autre RPi, `curl http://<actif>/api/health`. S'il
répond 200, la panne est sur le chemin public (box, DNS, Cloudflare) — ne pas basculer, ne
pas redémarrer la stack (`standards/04` §10 : deux sondes indépendantes avant toute décision
destructive).

Les crons root (`bascule.sh`, `maintenance.sh`, `health-watch.sh`, `check-reliability.sh`) et
le cron utilisateur `auto-deploy.sh` sont versionnés dans `infra/points-entree/` ; le point
17 du pré-check compare l'installé au dépôt. Toute intervention infra commence par charger
`infra-rpi`.

---

## Git & MEP — l'essentiel

**Premier réflexe de toute session, avant le moindre commit** :

```bash
git fetch origin && git merge --ff-only origin/dev
```

`.githooks/pre-commit` refuse un commit en retard sur son upstream ; il s'arme une fois par
clone : `git config core.hooksPath .githooks && git config pull.ff only && git config
blame.ignoreRevsFile .git-blame-ignore-revs`. Contournement d'urgence : `ALLOW_STALE=1 git
commit …`. Avant de réécrire un fichier partagé : `git worktree list` (`standards/13` §10).

- `main` = production, protégée (checks requis, `enforce_admins`, ni push direct ni
  `--force`) : tout passe par une PR depuis `dev`.
- Préfixes de commit : `feat:` `fix:` `docs:` `refactor:` `test:` `chore:` `perf:`.
- **Claude crée et fusionne la PR du lot, puis conduit la MEP**, sans validation préalable ;
  la contrepartie est un **compte rendu après** : la version et les fonctionnalités
  apportées. Le pré-check remplace la relecture. Aucune MEP sans avoir chargé
  `mep-precheck`.
- **Ordre d'un lot** : rejeu → pousser la branche → PR vers `dev` → CI verte → pré-check
  (`bash scripts/poste/precheck-mep.sh`) → MEP par `bash scripts/poste/conduire-mep.sh`
  (fusion sur checks verts et état `CLEAN`, version du train, PR `dev → main`, fenêtre de
  bascule, `dev` recréée, `Déployé:` sur l'actif, `--post-mep`). Après lui, une copie restée
  sur `dev` se réaligne (`checkout -B dev origin/main`).
- **La fusion n'est pas la MEP** : `auto-deploy.sh` tire les images de la CI puis
  redémarre ; attendre `Déployé: <sha>` dans `/var/log/hostachy-deploy.log` **sur l'actif**,
  puis post-check. Reprise en main : `sudo bash scripts/exploitation/MaJ-Hostachy.sh`, sur
  l'actif seulement.
- **Trois règles qui priment sur les contrôles** : un contrôle qui ne peut pas s'exécuter
  renvoie INCONNU, jamais OK ; ce qui est critique en continu ne se vérifie pas seulement en
  MEP ; vérifier le fait et le comportement, jamais le symptôme attendu ni l'artefact
  (`standards/04`, `standards/09`).
- **Session cloud** (claude.ai/code) : aucun SSH vers les RPi. La MEP s'y enchaîne **sans
  validation intermédiaire** (arbitré le 25/09/2026) : PR du lot vers `dev` → fusion dès les
  checks requis verts → PR `dev → main` → fusion → `dev` recréée depuis `main`, comme
  `conduire-mep.sh` (qui s'arrête faute de SSH à la lecture de l'actif). Le pré-check est
  INCONNU et la PR le dit ; le post-check P1–P9 reste au poste, et le compte rendu le
  demande. Les tickets se ferment à la fusion dans `main`, avec l'observation en production
  restant à faire. Environnement : `.claude/cloud/LISEZMOI.md`.
- `.env` non versionné · `SECRET_KEY` ≥ 32 caractères · `ENABLE_API_DOCS=false` en prod.

## Versioning

- La version vit dans `front/package.json` et `front/package-lock.json` (`npm run
  lint:lock`) ; elle s'affiche au pied de page (P3).
- **Elle se pose à la MEP, jamais dans un lot** (#2631) : `conduire-mep.sh` la calcule des
  préfixes des commits du train et la commit sur `dev` ; un lot qui porte un bump est refusé
  par le point 0d.
- Chaque commit de `main` publie ses images (`ghcr.io`, `sha-<commit>`) ; une version reçoit
  le tag `vX.Y.Z` par `scripts/ci/tag-version.sh`, jamais à la main.
- **Je ne promeus jamais une version vers `replica` de moi-même** : c'est la décision de
  l'auteur, qui choisit la version (workflow « Promotion »). Images, réplique, promotion et
  mise à jour des installations : `mep-precheck`.
