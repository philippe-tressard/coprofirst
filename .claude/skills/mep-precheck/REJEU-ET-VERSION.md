# mep-precheck — Le rejeu de la CI en détail, version, images publiées, réplique et bail

Annexe de `SKILL.md`, chargée à la demande (#2910) : le sommaire est dans `SKILL.md`.
Les titres et numéros de section sont ceux de toujours : un renvoi se lit au sommaire.

## Le rejeu et la CI — le détail (venu de `CLAUDE.md`, #2709)

Ce que le point 16 ci-dessus ne dit pas, et qui sert quand un rejeu ou un job déraille.

### Le poste
- **macOS : les outils GNU par une seule porte** (#2419). Chaque script de `scripts/poste/`
  appelle `poste_gnu_poser` (`lib-poste-gnu.sh`), qui met en tête du PATH les `gnubin` de
  Homebrew et son `bash` (celui d'Apple est un 3.2). Sans eux, le pré-vol refuse et le
  pré-check rend INCONNU : `brew install coreutils findutils gnu-sed grep bash`. Ce qui n'a pas
  d'homonyme GNU a sa branche `Darwin` (`ci_ps_bsd_lire`, `sysctl vm.loadavg`). 🔒 L'autotest
  de la porte exige que chaque script du poste l'appelle.
- **Le catalogue de la base des tests se mesure** au pré-vol (#2399) : relations, tuples morts,
  place par ligne, temps d'un DDL témoin ; au-delà d'un seuil, `VACUUM FULL` du catalogue
  d'office, puis refus s'il reste gonflé ; illisible → INCONNU (`ci_catalogue_verdict`,
  `lib-ci-base.sh`).
- **Dépendances du poste ≠ celles du lot → INCONNU** (#1417) : la ligne `ENV … dépendances`
  donne l'écart et la commande (`scripts/poste/verifier-dependances-poste.py`). Un lot qui
  monte des dépendances Python se mesure dans un venv en tête de PATH (`--venv`, ou à la main :
  `requirements-dev.txt` + chaque outil que `ci.yml` installe hors requirements, à ses
  versions) — jamais dans le Python du poste, que partagent les sessions. Le rejeu n'expose
  pas l'interpréteur du venv (`ci_script_a_exposer`, #2112).
- Sur un poste chargé, les e2e passent à un seul worker (`E2E_WORKERS`, règle
  `ci_workers_e2e`, #1665) ; pytest se borne par `PYTEST_WORKERS`, sinon `workers_suite`
  (cœurs, `max_connections`, table des verrous — `max_locks_per_transaction` × connexions ÷
  `VERROUS_PAR_WORKER`).
- Un `front/node_modules` en **jonction** vers le clone principal partage le cache de Vite :
  e2e INCONNU, avec la commande qui répare (`rmdir` de la jonction puis `npm ci`, #1722,
  `ci_node_modules_etat`).

### Le rejeu qui déraille
- **Gel** (#2270) : une étape au-delà de 4 × sa durée mesurée (20 min au moins) et muette
  depuis 15 min est arrêtée, INCONNU, avec `pg_stat_activity` et la pile des tests bloqués
  (`lib-ci-gel.sh`, `faulthandler_timeout`).
- **Mort du rejeu** : l'arbre de processus se retrouve par la fermeture des ppid
  (`lib-ci-arbre.sh`) ; sortir, arrêter une étape ou la mort du lanceur tuent tout l'arbre ;
  le pré-vol tue les restes d'un rejeu mort (`REJEU_ORPHELINS=signaler` pour seulement les
  nommer) et retire les schémas de test abandonnés (créateur mort, ou inconnu et de plus d'une
  heure ; jamais celui d'une connexion ouverte).
- **E2E relancé une fois sur une cause propre au poste** (« Failed to fetch dynamically
  imported module », #1809 ; `net::ERR_NO_BUFFER_SPACE`, #1989 — liste dans `ci_cause_relance`,
  plafond dans `ci_relance_e2e`, `lib-ci-e2e.sh`) : vert, l'étape reste OK, le point 16 reprend
  `RELANCES=`, chaque relance s'inscrit dans `rejeu-e2e-relances.log`. Un rechargement de Vite
  (#1421) n'y ouvre jamais droit.
- **Le verrou** ne se retire que par son propriétaire ; un verrou au pid mort se reprend seul
  (#1808) — ne jamais l'effacer à la main. `bash scripts/poste/file-rejeu.sh` réordonne la file
  (`devant`, `retirer`, `purger`) et reprend un verrou orphelin (`reprendre "<motif>"`,
  journalisé). Règles : `scripts/lib/lib-ci-verrou.sh`.
- **Le verrou du poste** (#2765) : son verrou pris, le rejeu prend son rang au verrou commun
  des tâches lourdes (`~/.claude/bin/verrou_poste.py`, claude-config#552) et attend qu'un
  `xcodebuild` ou un Gradle finisse ; `etat-rejeu.sh` dit qui le tient (ligne `Poste`). Absent
  (CI, autre machine), le rejeu tourne et le dit INCONNU. Ordre des deux verrous et pourquoi :
  `scripts/lib/lib-ci-verrou-poste.sh`.
- Lentes et rapides se départagent par la durée **mesurée** au rejeu précédent
  (`rejeu-ci-durees.tsv`), jamais par une liste ; couloirs côte à côte : `REJEU_PARALLELE`
  (défaut : cœurs libres / 4, au plus 8 ; `1` = en série) ; `--tout` joue tout. La trace
  (`.git/rejeu-ci.ok`) dit son mode (`MODE=rapide`, `CONFIEES=`) ; son format s'écrit et se lit
  dans `lib-depot.sh` (`verdict_suite_complete`). Les sauts du poste se comptent par le crochet
  de `api/tests/conftest.py` (`tests/aides_rejeu.py`, `ci_resumer_sauts`).
- Chaque rejeu écrit une ligne par étape dans `rejeu-durees.log` (répertoire git commun) ;
  règles d'orchestration et exceptions de couloir : `scripts/lib/lib-ci-orchestration.sh`,
  pré-vol : `lib-ci-prevol.sh`.

### La CI GitHub
- Un check requis **annulé** par GitHub bloque une PR sans un mot : `bash scripts/ci/relancer-annules.sh <n° de PR>`.
- **Un rouge de `main` ou d'un passage planifié ouvre un ticket** (#2988, `scripts/ci/signaler_echec_ci.py`) ; fermé à la main, sur le vert revenu.
- **Un arbre déjà jugé vert ne se rejoue pas** (#2632) : le job `arbre` saute un job requis
  quand une exécution précédente le prouve (même workflow, même dépôt, job `success` joué,
  arbre recalculé égal à `HEAD^{tree}`, base d'alors ancêtre de la tête). L'artefact
  `arbre-vert-<job>-<arbre>` n'est qu'un index ; dans le doute, le job joue. Un job requis neuf
  passe par lui. 🔒 `test_ci_arbre_deja_vert.py`, règles : `scripts/ci/arbre_deja_vert.py`.
- **CodeQL juge dès la PR vers `dev`** (#2571) : `codeql-avant-dev.yml` ne bloque que les
  alertes NEUVES face à `main` (`scripts/ci/codeql_nouvelles_alertes.py`) ; pas un check
  requis. 🔒 `test_codeql_avant_dev.py`.
- **apt de la CI : `scripts/ci/apt-ci.sh`** (#2694) — `installer <paquets>` ou `executer --
  <commande>` ; un miroir que le résolveur ne connaît plus prend un repli déclaré (adresse en
  DNS-sur-HTTPS posée dans `/etc/hosts` le temps de la commande), sinon « panne de miroir ».
  Aucun `apt-get` ni `--with-deps` ailleurs ; `bash scripts/ci/apt-ci.sh --selftest`.
- **La CI se rejoue à l'identique** (#1584) : tout `pip install` s'épingle
  (`test_ci_installations_epinglees.py`), chaque `uses:` par SHA avec sa version en commentaire
  (`test_ci_actions_epinglees.py`). Un workflow se mesure comme du code (500 lignes) ; `ci.yml`
  seul est admis au-dessus (`EXCEPTIONS_PLAFOND` de `scripts-ci-modularite.sh`, #1547). Le
  `timeout-minutes` d'un job tient sa durée mesurée : `plafonds-jobs.yml` le confronte chaque
  semaine au p95 (`scripts/ci/plafonds_jobs.py`, #2576). L'image de Caddy porte une mineure
  explicite (`FROM caddy:2.11`, `test_image_caddy_epinglee.py`) ; Python et Node flottent.
- **Ce que Trivy voit dans une image** (#2377) : une image Node d'exécution n'emporte pas npm
  (`test_images_sans_npm.py`), une étape Alpine fait `apk upgrade`, Caddy est recompilé depuis
  sa source tant que le binaire officiel retarde (`Dockerfile.caddy` dit quand y revenir). Le
  juge : la veille nocturne (`scripts/ci/veille-securite.sh`).

## Version, images, réplique — le détail (venu de `CLAUDE.md`, #2709)

- La version vit dans `front/package.json` (pied de page, contrôlé par **P3**) **et** dans
  `front/package-lock.json`, en tête et à `packages[""]` (`npm run lint:lock`).
- **Chaque commit de `main` publie ses images** (#1753) : `images.yml` publie les images
  signées des quatre services sur `ghcr.io/philippe-tressard/coprofirst-*` (amd64 et arm64),
  étiquetées `sha-<commit>` ; une version bumpée reçoit le tag git `vX.Y.Z`
  (`scripts/ci/tag-version.sh`, jamais à la main) et l'étiquette `X.Y.Z` ; construite dès la PR (`images-pr.yml`, #2963).
  🔒 `test_images_publiees.py`, `test_contexte_images.py`.
- **La référence TIRE ces images** (#1758) : `auto-deploy.sh` et la bascule passent par
  `obtenir_images` (`scripts/lib/lib-images-ci.sh`) ; tant qu'elles ne sont pas publiées, le
  journal dit « en attente des images de la CI », et au-delà de 30 min le nœud construit en
  secours et alerte. `Déployé:` arrive donc après la CI « Images », une quinzaine de minutes.
- **Une réplique suit son BAIL** (#2210) : canal Urgence ou une version choisie ; vagues
  (Urgence, Standard, Fixe — la vague Pilote est retirée, `canaux.py`) et règle dans `registre/versions` et `registre/canaux`,
  réglées par l'opérateur dans Admin › Installations. Chaque version taguée est publiée
  (release + archive, job `publier-version`) et la purge nocturne retire ce que plus aucune
  vague ne sert (`purge-paquets.yml`, règle de `python3 -I api/app/registre/versions.py
  garder`).
- **La branche `replica` et la promotion sont retirées** (#3009, 24/11/2026) : aucune
  installation ne les lisait plus depuis #2210. Un tag `v*` reste ni déplacé ni supprimé
  (règle du dépôt) ; les notes de version partent avec chaque tag (`publier-version`).
  🔒 `test_replica_retiree.py`.
- **Une réplique s'installe par `deploiement/standard/`** (#1755) : la surcouche
  `compose.images.yml` (`build: !reset`, image publiée à `COPROFIRST_VERSION`) se pose sur le
  `docker-compose.yml` de la racine, seule description des
  services ; mode d'emploi dans son `LISEZMOI.md`. Le contenu de `front/static/` ne nomme jamais
  la résidence (`npm run lint:nom-residence`).
- **Une réplique se met à jour seule chaque nuit** (#1756) : `deploiement/standard/mise-a-jour.sh`
  — sauvegarde vérifiée avant tout geste, retour à l'image précédente puis à la sauvegarde si
  la santé reste KO, rapport `mise_a_jour` (`utils/sante_mise_a_jour`). Le retour tient parce
  que `start.sh` saute les migrations d'une base en avance sur le code (`utils/revision_base`).
- **Le rôle de l'installation** (#1761) : `ROLE_INSTALLATION` (`reference` sur les deux RPi —
  l'ancien `maitre` n'est plus lu depuis #1892 —,
  `replique` posé par `compose.images.yml`) se lit dans `utils/installation` seul ; absent →
  « Inconnu ». Le bloc Installation d'Admin › Maintenance le montre, avec l'écart au dépôt si le
  service « Vérification de la version » est activé (coupé par défaut).
- Un onglet PWA resté ouvert peut servir une version en cache : le bandeau de mise à jour
  existe pour ça (`test_pwa_maj.py`).
