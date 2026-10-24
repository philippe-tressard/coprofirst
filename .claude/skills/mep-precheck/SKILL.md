---
name: mep-precheck
description: "MEP 5Hostachy : lancer `bash scripts/poste/rejouer-ci.sh` puis `bash scripts/poste/precheck-mep.sh` (tous les points s'exécutent), lire ses verdicts, dérouler le post-check P1-P12 (dont la clôture des tickets, après vérification en production, puis le retrait de la copie de travail du lot), rollback. Use when: AVANT tout `git push` sur dev ou main, avant de remettre une PR, après un merge vers main, pour diagnostiquer un déploiement qui n'a pas eu lieu ou vérifier qu'un correctif est réellement servi. L'histoire des incidents qui ont fait naître chaque contrôle est dans HISTORIQUE.md, à ouvrir seulement pour diagnostiquer."
argument-hint: "Décrire le lot à déployer ou le point à vérifier (ex. « pré-check avant MEP v2.31.3 », « post-check après merge »)"
---

# Git & MEP — pré-check, post-check et surveillance continue

Instanciation 5Hostachy de `standards/09-livraison-et-mep.md` et
`standards/04-fiabilite-des-controles.md`. **Charger cette skill avant toute MEP** :
les trois règles ci-dessous priment sur la liste des contrôles.

> 📖 **Le générique n'est pas recopié ici** — l'ouvrir en parallèle :
> `standards/09-livraison-et-mep.md` §2 (les trois exigences de même rang que la
> sécurité), §3 (grille de pré-check générique), §4 (post-check et les trois pièges
> de vérification), §6 (rollback), §7 (rétrospective) ·
> `standards/04-fiabilite-des-controles.md` — dont trois seulement sont reprises
> ci-dessous · `standards/08-git-et-versioning.md` §2–3 (étape 0) ·
> skill globale **`avant-commit`** pour les six contrôles de deux minutes.
>
> 📜 **`HISTORIQUE.md`, à côté de ce fichier** : pourquoi chaque contrôle existe,
> quel incident l'a fait naître, quels faux verts il a déjà produits. À ouvrir
> **pour diagnostiquer**, jamais pour agir — c'est ce qui permet à cette
> procédure-ci de tenir en une page.

## ⚠️ Se resynchroniser AVANT de committer (obligatoire)

La commande, le hook `pre-commit` qui le refuse, son armement par clone et la
frontière de `main` : `CLAUDE.md` → « Git & MEP — l'essentiel », déjà en contexte.
Le pourquoi : `standards/08` §2–3. Cette section en portait une troisième copie,
avec une ligne fausse — « MEP : `MaJ-Hostachy.sh` sur le RPi actif », alors que la
MEP est faite par `auto-deploy.sh` et que `MaJ-Hostachy.sh` est la **reprise en
main** (claude-config#122, 23/09/2026).

## Trois règles qui priment sur la liste des contrôles

Issues de l'incident du 26/07/2026 (cf. « Rétrospective » en fin de section). Un
contrôle mal conçu est plus dangereux qu'un contrôle absent, parce qu'il produit
de la confiance.

1. **Un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.**
   `sudo` en SSH non interactif échoue en demandant un mot de passe ; `… | grep -c`
   sur cette sortie vide affiche `0`, c'est-à-dire « aucun problème ». Le 26/07 j'ai
   annoncé un tel « 0 » : c'était un faux vert. Toute commande
   du pré-check doit soit fonctionner sans `sudo`, soit signaler explicitement son
   échec. **Ne jamais déduire un vert d'une sortie vide.**
2. **Ce qui est critique en continu ne doit pas être vérifié seulement en MEP.**
   Le pré-check est ponctuel ; les invariants de redondance sont permanents. Le
   26/07, `.active` était incohérent depuis 02:00 et personne ne l'a su avant un
   pré-check à 09:00 — entre-temps le site est resté HS ~50 min sans failover. Voir
   « À automatiser » ci-dessous.
3. **Vérifier le fait, pas le symptôme attendu.** Avant de déclarer une anomalie,
   confirmer qu'elle en est une (le 26/07 l'image API paraissait périmée : le commit
   ne touchait que `front/`). Et avant de déclarer un vert, confirmer que le
   contrôle mesure bien ce qu'on croit.

## Étape 0 — poste de développement (avant d'écrire une ligne)

| # | Vérification | Commande | Attendu |
|---|---|---|---|
| 0a | Clone à jour | `git fetch origin && git merge --ff-only origin/dev` | Fast-forward propre (cf. section ci-dessus) |
| 0b | Modes des fichiers exécutables versionnés | **Automatisé** : job CI `test-scripts` (étape « Bits d'exécution versionnés ») | `100755` sur tout ce qui doit s'exécuter, `100644` sur les modules sourcés `lib-*.sh` |

**0b** — pourquoi un clone Windows avale `chmod +x` : `standards/08` §3.
Remédiation : `git update-index --chmod=+x <fichier>`.

## Étape 0 bis — exigences sans exception (avant le pré-check)

**Trois** exigences de même rang que la sécurité, à contrôler **avant** de
dérouler le pré-check technique — autant que le tableau ci-dessous en compte, et
que `standards/09` §2 en énonce. Cette ligne disait « deux » au-dessus d'un
tableau de trois, et le renvoi de l'en-tête de cette skill disait « trois » :
trois comptes pour une liste (#122). Elles ne portent pas sur l'état des machines mais sur celui du
code et de la documentation livrée : un pré-check vert sur une base qui viole ces
règles reste un mauvais déploiement.

| # | Exigence | Vérification | Automatisé par |
|---|---|---|---|
| 0c | **Autorisation centralisée, aucun passe-droit** | Toute règle de sécurité dans `app/auth/deps.py` · tout endpoint porte une dépendance · exceptions publiques énumérées et justifiées · `has_role(RoleUtilisateur.…)` jamais `user.role` ni chaîne · exposition publique en **liste blanche** | `api/tests/test_autorisation.py` (5 tests, CI) |
| 0d | **Factorisation** | Aucun code spécifique ne réimplémente une bibliothèque partagée (dates, montants, alertes, thème PDF, destinataires) | `test_dates_fr.py` · `npm run lint:dates` · `npm run lint:notifications` — le reste par relecture |
| 0e | **Documentation à jour** | README (et ses badges) · manuel utilisateur · `specs/` reflètent l'état livré | `api/tests/test_documentation.py` pour la partie mécanique ; le fond reste à relire |

**0c — pourquoi cette exigence a besoin d'un test et non d'une consigne** (principe :
`standards/03-securite.md` §1 ; ici, son instanciation). L'audit du
26/07/2026 a trouvé l'exigence globalement respectée — 276 endpoints, aucun contrôle
sur `user.role`, tout par `has_role()` — et pourtant **trois dérives installées sans
que rien ne les signale** :
1. `GET /config` filtrait par liste **noire** : 31 clés exposées sans authentification,
   dont toute la configuration SMTP, l'URL interne du bridge WhatsApp, l'identifiant
   du groupe privé et un **lien d'invitation fonctionnel** au groupe WhatsApp des
   résidents. Le motif était correct à cinq clés de configuration ; il est devenu une
   fuite à mesure qu'elles s'accumulaient, sans que personne ne rouvre le fichier.
2. `_require_bailleur` dans `routers/bailleur.py`, doublon exact de
   `require_proprietaire`, hors du module central — 17 endpoints dessus. Un
   durcissement de la règle centrale ne les aurait pas atteints. **Aggravant :
   `specs/architecture/api.md` le documentait comme une dépendance officielle** — la
   spec légitimait la dérive au lieu de la signaler.
3. Deux contrôles par chaîne littérale (`has_role("admin")`) au lieu de l'enum.

Le point commun : **aucune n'était visible sans rouvrir le fichier concerné**. Une
exigence, même « critique et prioritaire », ne se maintient pas par la consigne — la
consigne était là. Elle se maintient par un contrôle qui échoue.

**0e — pourquoi.** La synchronisation du manuel entre `docs/` et `front/static/`
n'était qu'une case à cocher : elle a tenu, mais une case ne résiste pas à une
session pressée, et les résidents auraient lu une version périmée. Les badges du
README avaient connu la dérive inverse, réelle : Python annoncé « 3.10+ » pour une
image en 3.12. Ce qui est mécanique est désormais testé (synchronisation des manuels,
badges Python/Node/CI alignés sur `Dockerfile` et `ci.yml`) ; le fond — le manuel
décrit-il encore l'application, les specs l'état livré — reste une relecture, à faire
ici et pas après.

## Pré-check obligatoire avant MEP — il s'exécute

```bash
bash scripts/poste/precheck-mep.sh          # à la racine du dépôt
```

**Ne pas dérouler la grille à la main.** Elle l'a été trop souvent de mémoire, en
sous-ensemble : trois lots sont partis sans aucun pré-check les 07 et 08/08/2026,
et deux contrôles improvisés ont rendu des faux verts. Le script mesure, écrit sa
trace dans `.git/precheck-mep.ok`, et `.githooks/pre-push` refuse le push sans
elle.

**Fusionner la PR EST la mise en production** : `auto-deploy.sh` déploie
`origin/main` toutes les 5 minutes. Le pré-check se passe donc **avant le push sur
`dev`**, pas après la fusion.

🔴 **Depuis le 28/08/2026, c'est Claude qui crée et fusionne la PR, et qui conduit
la MEP** — l'utilisateur n'intervient plus. Le pré-check ne s'allège pas pour
autant : il est désormais **le seul** filtre entre un lot et la production, là où
il n'était qu'un préalable à une relecture. La contrepartie demandée est un
**compte rendu après** : version servie et fonctionnalités apportées.

🔴 **En session cloud, la même chaîne s'enchaîne sans validation intermédiaire**
(25/09/2026) — pré-check INCONNU dit dans la PR, post-check laissé au poste, `dev`
recréée par l'API GitHub. La règle vit dans `CLAUDE.md`, « Session cloud » : elle
n'est pas recopiée ici.

Le déroulé complet, une fois le pré-check vert :

```
gh pr create --base main --head dev …
gh pr checks <n> --watch          # TOUS les checks requis (liste : protection de main), pas un de moins
bash scripts/ci/relancer-annules.sh <n>   # un check requis ANNULÉ par GitHub bloque sans un mot (#2225)
gh pr merge <n> --squash --delete-branch
git fetch --prune && git checkout -B dev origin/main
SKIP_PRECHECK=1 git push -u origin dev   # recrée `dev` distante (piège 2)
```

⚠️ **Quatre pièges — les trois premiers rencontrés le 28/08, le quatrième le 25/09 :**

1. `--delete-branch` supprime aussi la branche **locale** et bascule sur `main`.
   Committer ensuite sans regarder `git branch --show-current` met le lot suivant
   sur `main`, où le push est refusé. Recréer `dev` **avant** de committer.
2. `origin/dev` **n'existe plus** après la fusion — et ce n'est **pas**
   `--delete-branch` : le dépôt a `delete_branch_on_merge = true`, qui supprime
   la branche source de toute PR fusionnée (mesuré le 22/09 en fusionnant sans
   l'option, #1140). Un `git fetch` sans `--prune` laisse une ref fantôme, et
   `--force-with-lease` échoue alors en « stale info » sur ce qui n'est en
   réalité qu'une **création** de branche. La recréer par un push simple, sous
   `SKIP_PRECHECK=1` : le sha de squash n'a jamais été pré-checké, et le hook
   refuserait un commit que la CI de la PR vient de valider.
3. **La fusion n'est pas le déploiement.** `auto-deploy.sh` fait le `git pull`
   **puis** le build : entre les deux, les points **12** et **18** échouent
   légitimement — le code est à jour, l'image ne l'est pas encore. Attendre la
   ligne `Déployé: <sha>` dans `/var/log/hostachy-deploy.log` sur l'**actif**.
   Le `git log` du nœud passe au vert **avant** que l'image soit bâtie : s'y fier
   fait annoncer une MEP qui n'a pas eu lieu.
4. **Un commit mécanique se perd dans le squash.** Un reformatage (`ruff format`,
   Prettier sur tout un dossier) ne se saute dans `git blame` que par son SHA
   dans `.git-blame-ignore-revs` — et ce SHA doit être celui d'un commit de
   `main` qui ne contient **que** lui. Fusionné sur `dev` avec d'autres lots, il
   est absorbé dans le squash de la MEP, puis `dev` est réaligné : son SHA
   n'existe plus nulle part. Vécu avec `ruff format` sur `api/` (#1261), fondu
   dans v2.49.0 avec #1186, #1263, #1266… — ignorer ce squash aurait caché la
   paternité de vrais changements. **Un reformatage part donc dans une MEP
   dédiée**, et c'est le SHA de son squash sur `main` qui entre dans le fichier.
   `test_documentation.py` refuse un SHA absent de l'historique.

🔴 **Après la MEP : `bash scripts/poste/precheck-mep.sh --post-mep`** (#1282,
25/09/2026). Il ne lance pas les points du LOT (0a à 0g, 15, 16), qui échouent
par construction une fois le lot fusionné — version inchangée, brief d'un commit
déjà parti, trace d'un autre commit — et il ajoute **P1** (la ligne `Déployé:` de
l'actif porte le commit de `origin/main` — ou, pour un actif démarré par la
bascule, qui n'écrit pas cette ligne : son marqueur d'images porte le commit et
son conteneur API tourne sur le manifeste de l'image étiquetée — le fait du
point 12, plus deux dates depuis #1684) et **P3** (la version servie est
celle de `origin/main`). Il conclut « MEP VÉRIFIÉE » ou « MEP NON VÉRIFIÉE », et
n'écrit **jamais** la trace qui autorise un push.
⚠️ Cette ligne disait « lire les points 1 à 18 » : lancé sans option après la
fusion, le script concluait « MEP NON AUTORISÉE » sur une MEP réussie, et il
fallait savoir lesquels de ses échecs ne comptaient pas. Une consigne pour lire
AUTOUR d'un verdict faux est un contrôle qu'on finit par ne plus lire.

### Ce que le script couvre

| # | Contrôle | Verdict possible |
|---|---|---|
| 0a | Clone à jour sur `origin/dev` | OK · FAIL |
| 0b | Modularité — ce que la CI vérifiera | OK · FAIL |
| 0c | **CI de la branche**, hors échecs que ce lot corrige | OK · FAIL · INCONNU |
| 0d | **Un seul bump de version dans le lot** | OK · ÉCART · FAIL |
| 0g | **Rang du bump conforme** à ce que le lot apporte (lu dans les préfixes de commit) | OK · ÉCART · FAIL |
| 0f | **Titre et descriptif de PR préparés** (`.git/pr-brief.md`) | OK · FAIL · INCONNU |
| 15 | Aucun endpoint orphelin | OK · FAIL |
| 16 | **CI rejouée en local sur ce commit** (`scripts/poste/rejouer-ci.sh`) | OK · FAIL · INCONNU |
| 1 | Site public répond | OK · FAIL · INCONNU |
| 2 | Rôle actif cohérent **et conforme au réel** | OK · FAIL |
| 3 | Standby sans conteneur (pas de split-brain) | OK · FAIL |
| 4 | Le `.env` de l'actif désigne PostgreSQL (`base_configuree`) — la santé de la base est le point 22 | OK · FAIL · INCONNU |
| 5 | Bridge WhatsApp connecté | OK · FAIL |
| 6 | Aucune ERROR/CRITICAL (1 h), **hors celle que ce lot corrige** | OK · FAIL · INCONNU |
| 7 | Scripts cron exécutables | OK · FAIL |
| 8 | Battement d'auto-deploy sur le standby | OK · FAIL |
| 9 | **E-mails en échec** | **INCONNU — voir ci-dessous** |
| 10 | Parité de code entre les 2 nœuds | OK · ÉCART |
| 11 | Auto-deploy de l'actif vivant | OK · FAIL |
| 12 | **Chaque conteneur sert l'image bâtie sur SON commit** (api, front, bridge, Caddy) — deux faits par service, jamais une date : les images contiennent-elles le dernier commit de son répertoire, et le conteneur tourne-t-il sur le manifeste de l'image étiquetée ? Le détail donne la commande de recréation ; pourquoi pas l'ID d'image : `lib-images-servies.sh` (#1675) | OK · FAIL · INCONNU |
| 13 | Canal d'alerte non muet | OK · FAIL |
| 14 | Hygiène disque sur les **2** nœuds | OK · FAIL |
| 17 | **Points d'entrée conformes au dépôt** (crons, unité systemd) | OK · FAIL · INCONNU |
| 18 | **Images du standby bâties sur son code** — le point 10 compare deux HEAD, pas ce qu'un failover démarre (#511) | OK · FAIL · INCONNU |
| 19 | **Liens des courriels servis par la production** | OK · ÉCART · FAIL · INCONNU |
| 20 | **Ordre du menu servi** (`pages_order`) — un fantôme rend ÉCART, une répétition FAIL (#1114) | OK · ÉCART · FAIL · INCONNU |
| 21 | **Textes légaux servis complets** — un « À RENSEIGNER » dans la page publique rend ÉCART : à compléter dans Admin › Légal (#1585) | OK · ÉCART · INCONNU |
| 22 | **Réplication PostgreSQL** — un primaire sur l'actif, une réplique qui reçoit le journal sur le standby ; deux primaires ou une réplique déconnectée rendent FAIL. Décision partagée avec C37 (`lib-replication.sh`, #1781) | OK · FAIL · INCONNU |
| 23 | **Aucune PR ouverte vers `main` hors de `dev`** — chaque MEP supprime `dev`, et GitHub réoriente vers `main` les PR qui la visaient (Dependabot compris). Une PR réorientée rend ÉCART ; la reprendre : `python scripts/poste/reprendre-dependabot.py` (relevé et montées), puis `--fermer`, et ses montées dans un lot sur `dev`. Joué aussi en `--post-mep`, premier moment où elles apparaissent (#1870) | OK · ÉCART · INCONNU |
| 24 | **Aucune alerte Dependabot haute ou critique ouverte** — deux alertes hautes (`follow-redirects`, bridge) ont dormi deux jours sans PR ni ticket (#2148). FAIL qui nomme l'alerte, son manifeste et la version corrigée ; ÉCART si le lot modifie ce manifeste (le lot correctif ne se bloque pas lui-même). Joué aussi en `--post-mep` : l'alerte se ferme à la ré-analyse de `main`, quelques minutes après la fusion. Décision : `reprendre-dependabot.py --alertes` | OK · ÉCART · FAIL · INCONNU |

### Lire le verdict

- **FAIL** → MEP non autorisée. Diagnostiquer, corriger, **relancer le script**.
- **19** → il compose les liens des modèles d'e-mail avec le `site_url` que la
  PRODUCTION sert, et refuse un 404. Ajouté le 11/09/2026 après un lien
  `https://5hostachy.fr//tickets/34` reçu par le syndic : aucun test de CI ne
  pouvait le voir, la valeur fautive étant **en base**. La CI vérifie le code,
  ce point vérifie la donnée — deux sondes indépendantes (`standards/04` §10).

  Une barre finale sur `site_url` rend **ÉCART** et non FAIL : le produit la
  neutralise à la lecture (`utils/liens.base_site`), donc bloquer une MEP dessus
  serait un faux rouge. Elle reste à nettoyer en administration — c'est la
  donnée sale dont onze lecteurs ont hérité.

- **ÉCART** (points 10, 0d et 0g) → toléré, mais à lire. Point 10 : le standby se
  aligne seul sous 5 minutes (`auto-deploy.sh`, #448 — depuis le 19/08/2026 ;
  avant, la bascule de 02:00 n'alignait que le nœud ENTRANT, donc le standby
  accumulait le retard après chaque déploiement). Point 0d : un lot
  **sans** bump se déploie quand même — c'est P3 qui devient incapable de prouver
  que le déploiement a eu lieu, la version servie étant identique avant et après.
- **0c** → il ne compte que les échecs de CI que ce lot **ne corrige pas**. Un
  échec est dépassé s'il est suivi d'un succès plus récent, **ou** si HEAD
  descend du commit fautif. Sans cette nuance, le push qui corrige une CI rouge
  était refusé par le contrôle même qui constatait le rouge — et la seule issue
  était `SKIP_PRECHECK=1`, donc désarmer tous les points pour en contourner un
  (#318, corrigé le 12/08/2026). Les **deux** conditions sont nécessaires : les
  PR étant fusionnées en squash puis `dev` réaligné, l'ascendance seule disparaît
  au premier réalignement.

  ⚠️ **Deux contrôles différents portent le nom « 0c »** : celui-ci, exécuté par
  le script, et l'exigence d'**autorisation centralisée** de l'étape 0 bis
  ci-dessus, qui est vérifiée par `test_autorisation.py`. La collision est
  historique ; à renommer un jour, en attendant lire le contexte.
- **6** → il compte les `ERROR`/`CRITICAL` de la dernière heure sur l'API de
  production. Depuis le 19/08/2026 (#502), un lot peut **déclarer la signature de
  l'erreur qu'il corrige**, dans `.git/erreur-corrigee` — même forme datée que le
  brief de PR :

  ```
  commit: 6055161
  auth/refresh
  ```

  Le point écarte alors les lignes qui correspondent, et **échoue si la signature
  ne correspond plus à rien** : la dérogation ne survit pas à son objet. Elle
  échoue aussi si le commit déclaré n'est pas HEAD (déclaration d'un lot
  précédent), ou si le motif n'ancre rien (`.*`, `ERROR` — on ne désarme pas le
  point en le déclarant). Le détail affiché dit toujours combien de lignes ont
  été écartées et par quel motif : un contrôle qui tait ce qu'il ignore ment par
  omission.

  ⚠️ **Sans déclaration, rien ne change** — le point reste intransigeant, et
  c'est le cas nominal. La déclaration est un geste explicite pour un lot qui
  répare, pas une commodité.

  Pourquoi ce mécanisme plutôt qu'une fenêtre glissante depuis le dernier
  déploiement, qui semblait plus simple : `docker compose up -d` ne recrée un
  conteneur que si son image a changé. Un lot qui touche `api/` purge donc déjà
  les logs, et un lot qui ne touche que `front/` aurait vu ses erreurs API
  réelles passer sous silence. La piste écartée échouait du côté dangereux.

- **0a en FAIL après avoir corrigé 0d** → c'est le cas prévu depuis le
  29/08/2026 (#616), et il a une déclaration, pas un contournement.

  Retirer un bump surnuméraire (ce que 0d prescrit) laisse sur `origin/dev` un
  commit que HEAD n'a plus : 0a le comptait comme un retard, et les deux points ne
  pouvaient pas être verts en même temps avant le push. La seule issue était
  `SKIP_PRECHECK=1` — désarmer vingt-quatre contrôles pour en contourner un
  (socle 04 §25, et deuxième occurrence après #318 sur le point 0c).

  Déclarer la réécriture dans `.git/reecriture-dev`, même forme datée que le
  brief de PR et que `.git/erreur-corrigee` :

  ```
  commit: 601477b
  137cab0
  ```

  🔴 **Déclarer ne suffit pas** — sinon ce serait une case à cocher pour écraser
  le travail d'une autre session. Le point vérifie que les commits déclarés sont
  **exactement** ceux qui manquent, et surtout que **chaque fichier qu'ils
  touchent a été réécrit par HEAD**. Un seul fichier non recouvert, et il refuse
  en le nommant : c'est ce recouvrement, et lui seul, qui prouve qu'aucun contenu
  n'est perdu.

  Comme les autres dérogations : elle est **datée par le commit** (une
  déclaration du lot précédent est refusée), et elle **ne survit pas à son
  objet** (déclarer un commit qui ne manque pas, ou en oublier un, refuse aussi).

- **0f** → le lot doit porter son titre et son descriptif de PR **avant** le push,
  dans `.git/pr-brief.md` : première ligne `commit: <sha court de HEAD>`, deuxième
  ligne le titre en `# …`, puis le corps (5 lignes minimum). Un brief rédigé pour
  un autre commit **échoue** — sinon il décrirait le lot précédent. Ajouté le
  11/08/2026 après deux oublis dans la même journée, le second juste après
  s'être fait reprendre sur le premier : la consigne de la skill `avant-commit`
  ne tenait pas seule.
- **0d en FAIL** → le lot porte **deux bumps ou plus**. N'en garder qu'un, posé
  en dernier : `git reset --soft <avant le 1er bump>` puis recommit et
  `push --force-with-lease` — `dev` n'est pas protégée et le force-push y est
  déjà le geste normal après chaque squash. Ne **jamais** empiler un second bump
  quand le lot repart : la version intermédiaire n'atteindra jamais la
  production et l'historique annoncera un déploiement qui n'a pas eu lieu
  (PR #297, 11/08/2026 — v2.49.1 jamais servie).
- **16** → il ne mesure rien lui-même : il **lit la trace** que `scripts/poste/rejouer-ci.sh`
  écrit dans `.git/rejeu-ci.ok`, et qui porte le commit couvert. Une trace d'un
  autre commit rend INCONNU — sinon un lot hériterait du vert du lot précédent.
  Il reprend aussi le nombre de tests **sautés** sur le poste (`SAUTS=`, #1734) :
  ceux-là — le rendu PDF, faute de WeasyPrint — seule la CI de la PR les joue.

  ```bash
  bash scripts/poste/rejouer-ci.sh
  ```

  Le script **extrait** les commandes de `.github/workflows/ci.yml` ; il n'en
  tient aucune liste, parce qu'une seconde liste divergerait au premier job
  ajouté — et c'est le job ajouté qu'on oublie de rejouer. Environ une minute.
  Il rend compte de trois genres d'étapes : les **contrôles** (exécutés), les
  **installations** (affichées, jamais exécutées — elles écraseraient
  l'environnement du poste), et les **non rejouables** (INCONNU). Une étape dont
  l'outil manque sur le poste est requalifiée en INCONNU, jamais en échec.

  Pourquoi ce point existe : le 12/08/2026, pytest, svelte-check, le build, les
  six lints du front et les self-tests avaient tous été rejoués à la main — le
  seul job non lancé, Ruff, est le seul qui a échoué (#319). La consigne de tout
  rejouer existait déjà, avec sa commande d'extraction ; rien ne forçait à
  l'exécuter, rien ne constatait qu'on l'avait fait.

  Un seul job : `bash scripts/poste/rejouer-ci.sh build-frontend` — utile en cours de
  correction, mais **aucune trace n'est écrite** et le point 16 reste INCONNU.
  **Un seul rejeu à la fois, à son tour** (#2225) : sur un poste partagé,
  `REJEU_PROPRIETAIRE="<lot> #<ticket>" bash scripts/poste/rejouer-ci.sh --attendre`
  — sans `--attendre`, il est refusé tant qu'un rejeu tourne ou qu'un autre attend.
  Qui tient le verrou, à quelle étape, qui attend : `bash scripts/poste/etat-rejeu.sh`.
  Le lancer en tâche de fond de l'outil, jamais détaché : un rejeu dont le shell
  lanceur disparaît s'arrête de lui-même et libère le verrou.
- **INCONNU** → le contrôle n'a **pas pu** mesurer. Ce n'est jamais un vert. Le
  script sort en 2 au-delà d'un seul INCONNU.
- **Point 9 est INCONNU par construction** : l'historique des e-mails s'interroge
  in-process (`GET /admin/emails/historique`) et exige une session admin. Le
  vérifier à la main dans **Admin → E-mails → Historique**, filtre `erreur`,
  7 jours. Repli sans interface : voir `HISTORIQUE.md`.

### Avant même le script — l'étape 0 bis

Les exigences 0c à 0e, hors machines, sont au tableau de l'**étape 0 bis** plus
haut, et nulle part ailleurs : ce fichier en portait une seconde copie, qui avait
recompté « deux » au-dessus de trois lignes (#122).

**Protocole si anomalie** : diagnostiquer → proposer un plan → corriger après
validation → relancer le script → livrer seulement si tout est vert.

## Post-check obligatoire après MEP

La MEP se termine par ces contrôles, pas par le merge. Un merge déclenche
`auto-deploy.sh` dans les 5 min ; **il n'y a aucune notification de fin de
déploiement**, donc rien ne garantit spontanément que le code est réellement servi.
Attendre le tick, puis :

| # | Vérification | Commande | Attendu |
|---|---|---|---|
| P1 | Le déploiement a eu lieu **et est terminé** | `precheck-mep.sh --post-mep` (lit l'actif) | Ligne `Déployé: <hash>` avec le hash attendu — ou, actif issu d'une bascule, marqueur d'images = hash et conteneur API sur le manifeste de l'image étiquetée (#1474, #1684) |
| P2 | Site debout | `curl -s -o /dev/null -w '%{http_code}' https://5hostachy.fr/api/health` | 200 |
| P3 | Version servie = version bumpée | Voir « P3 » ci-dessous — l'ancienne commande ne pouvait **pas** fonctionner | La version de `front/package.json`, ou `INCONNU` (jamais vide) |
| P4 | Image du service touché reconstruite | Point 12 (`--post-mep` le rejoue) : images bâties avec le commit du service, conteneur sur le manifeste de l'image étiquetée | Les deux faits vrais pour chaque service |
| P5 | Migrations appliquées | `docker logs hostachy_api --since 10m \| grep -iE 'alembic\|revision'` | Pas d'erreur ; head atteint |
| P6 | Aucune régression visible en logs | `docker logs hostachy_api --since 10m \| grep -cE "<MOTIF_ERREURS_API>"` — le motif se lit dans `precheck-mep.sh`, jamais recopié : il compte aussi les erreurs de bibliothèque sans niveau (#1066) | 0 |
| P7 | **Le correctif est effectivement observable** | Vérifier le comportement corrigé sur le site réel | Le bug ne se reproduit plus |
| P8 | Redondance intacte après MEP | Point 2 (rôle cohérent sur les 2 nœuds) | Inchangé et cohérent |
| P9 | Parité du standby | Point 10 | HEAD identiques, **ou** noter que le standby s'alignera seul au prochain passage d'`auto-deploy` (≤ 5 min, #448) |
| P10 | **Bilan mémoire du lot** — 🟡 priorité 3 | Relire les activités de la PR : qu'a-t-on appris qui n'est écrit nulle part ? Voir « P10 » | Chaque leçon est **écrite** (socle ou banque projet), ou explicitement écartée |
| P11 | **Clore les tickets du lot** — après P7, jamais avant | `gh issue close <n> --comment "…"` avec la preuve observée | Chaque ticket du lot est clos **ou** dit ce qu'il attend encore |
| P12 | **Retirer la copie de travail du lot** — en dernier | Depuis le clone principal : `bash scripts/poste/retirer-worktree.sh ../5hostachy-<lot>` — voir « P12 » | `RETIRÉE`, ou `GARDÉE` avec son motif, traité ou dit dans le compte rendu |

> **⏱ Attendre la BONNE condition (constaté le 26/07/2026, en utilisant ce
> post-check pour la première fois).** Ne pas attendre que `HEAD` change : dans
> `auto-deploy.sh`, `git reset --hard` a lieu **au début**, avant `docker compose
> build`. Un post-check déclenché sur le changement de HEAD s'exécute donc pendant
> le build et voit des images encore anciennes et pas de ligne `Déployé` — j'ai
> conclu à tort à un déploiement partiel. La condition de fin est la ligne
> **`Déployé: <hash>`** :
> ```bash
> until ssh <actif> "grep -q 'Déployé: <hash>' /var/log/hostachy-deploy.log"; do sleep 20; done
> ```

**P3 — l'ancienne commande renvoyait toujours du vide (corrigé le 03/08/2026).**
`curl -s https://5hostachy.fr/ | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'` ne pouvait pas
marcher : la racine **redirige vers `/auth/connexion`**, et le pied de page versionné
vit dans le layout `(app)`, donc derrière l'authentification. Le `grep` ne trouvait
rien et rendait la main sans un mot — un `$(…)` vide qu'on lit comme « rien à
signaler ». C'est la règle 1 (« une sortie vide n'est pas un vert ») dans le
post-check lui-même.

La version **est** publique : Vite intègre `front/package.json` dans le chunk du
layout `(app)`. On l'y lit sans authentification et sans rien exposer de nouveau —
c'est aussi le seul point de mesure qui reflète ce qu'un **navigateur reçoit
vraiment**, là où lire `package.json` dans le conteneur ne décrirait que l'image.

```bash
node front/scripts/check-version-servie.mjs --site https://5hostachy.fr
```

La version sur la sortie standard (code 0), ou `INCONNU: <raison>` et **code 2**.
Jamais une sortie vide — c'est la règle 1 de cette skill.

🔴 **Le script ne vit plus dans ce fichier, et c'est la leçon du 30/08/2026.**

Il y a été recopié deux fois, avec deux ancrages successifs, et les deux se sont
périmés en silence :

| Ancrage | Périmé par | Constaté |
|---|---|---|
| `[0-9]+\.[0-9]+\.[0-9]+` sur la racine | la racine redirige vers `/auth/connexion` | 03/08/2026 |
| `"hostachy-front",VAR="x.y.z"` | Rollup élague l'import JSON : le **nom du paquet** a disparu du bundle, qui ne porte plus que `const fn="3.20.0",hn={version:fn}` | 30/08/2026, MEP v3.20.0 |

Le second avait été choisi *parce que* le nom « survit à la minification,
contrairement aux noms de variables ». C'était vrai, et insuffisant : ce n'est pas
la minification qui l'a effacé, c'est l'élagage.

⚠️ **Le défaut n'est pas l'ancrage, c'est qu'aucun contrôle ne regardait s'il
marchait encore.** Le premier à l'apprendre était le post-check, en production,
une fois la MEP faite — trop tard pour que cela serve. Un script recopié dans une
documentation ne s'exécute que le jour où l'on en a besoin.

**L'extracteur est donc versionné**, et la CI l'exerce à chaque PR sur le build
local (`npm run lint:version-servie`, job `build-frontend`) : il doit y retrouver
exactement la version de `package.json`. La prochaine évolution de la chaîne
d'outils échouera **là**, avant la MEP.

C'est `standards/04` §2 retourné contre le contrôle lui-même — *ce qui est
critique ne se vérifie pas seulement en MEP* — et la règle que #498 énonce pour
l'aperçu des e-mails : **la fonction qui vérifie doit être celle qui sert.**

Le module rend `null` plutôt qu'une version quand deux formes du bundle
**divergent** : `package.json` peut être partiellement élagué et la version d'une
dépendance traîner dans le même chunk. Trancher au hasard entre deux candidates,
c'est mentir une fois sur deux. Son `--selftest` couvre les deux formes, les deux
cas ambigus et le renvoi arrière qui les distingue.

⚠️ **P3 mesure le serveur, pas le client.** Un onglet PWA resté ouvert peut servir
l'ancienne version depuis son cache — c'est ce qui s'est produit le 26/07/2026, le
pied de page bloqué en v2.22.8 après la MEP v2.23.0, alors que P3 était vert. Le
bandeau de mise à jour (v2.24.0) couvre ce cas, et `api/tests/test_pwa_maj.py` le
verrouille.

> 🔒 **Pourquoi ne pas exposer la version dans `/api/health`** (question posée le
> 03/08/2026). L'endpoint est public et porte déjà un champ `version`, mais figé à
> `"0.2.0"` — une constante (`API_VERSION`, `main.py`) sans aucun rapport avec
> l'application. Le rendre exact donnerait un P3 en une ligne, au
> prix d'une **divulgation publique de la version déployée** que rien n'impose
> aujourd'hui. Décision : on ne l'a pas fait, et elle reste vraie. Lire le bundle
> coûte trois requêtes et n'expose rien de plus qu'aujourd'hui.

**P7 — pourquoi :** c'est le seul contrôle qui teste ce que la MEP était censée
apporter. Le 26/07, le bug du mois en anglais n'a été trouvé par **aucun** contrôle
automatique ou manuel : il a été vu à l'œil sur un document. Les points P1–P6
confirment qu'on a déployé *quelque chose*, jamais qu'on a déployé *ce qu'il
fallait*. Pour un correctif de rendu, ouvrir le document concerné (fiche arrivant,
annonce de hall) et regarder.

> **🌐 Le comportement se vérifie dans un navigateur, sur une route imbriquée
> (constaté le 26/07/2026, v2.24.0 → v2.24.1).** La v2.24.0 ajoutait un bandeau
> « nouvelle version disponible » à la PWA. P1–P6 étaient **tous verts** — image
> reconstruite, version 2.24.0 dans le conteneur, hash du commit et code du bandeau
> présents dans le bundle servi — et la fonctionnalité était morte : elle avait de
> surcroît **cassé l'existant**, plus aucun service worker n'était enregistré, donc
> plus de cache hors ligne. Cause : `vite-plugin-pwa` hérite du `base` de Vite, vide
> sous SvelteKit, et génère `new Workbox('./sw.js', { scope: './' })` ; ce chemin
> **relatif** est résolu depuis la page courante, donc `/auth/sw.js` → 404 sur toute
> route autre que la racine. Trois règles en sortent :
> - **Tester ailleurs qu'à la racine.** Un chemin relatif, un cookie de portée, une
>   règle Caddy fonctionnent souvent sur `/` et nulle part ailleurs.
> - **Les artefacts ne prouvent rien sur le comportement.** Bundle, `sw.js`, image
>   Docker, version du conteneur : tout était correct pendant que la fonctionnalité
>   ne s'exécutait pas. Ouvrir la page et regarder l'état réel
>   (`navigator.serviceWorker.getRegistrations()`, console, requêtes réseau).
> - **Un composant qui reprend un mécanisme fourni par un plugin hérite de ses
>   valeurs par défaut.** Ici `injectRegister` masquait le défaut depuis toujours ;
>   le reprendre à la main l'a exposé. Quand on remplace un mécanisme automatique,
>   vérifier ce qu'il faisait *en plus* de ce qu'on voulait.
>
> Et brancher les callbacks d'erreur (`onRegisterError` ici) : l'échec n'a produit
> **aucun log**, ni côté serveur ni côté navigateur. Ce qui échoue en silence ne se
> découvre qu'à P7, ou jamais.

> **🧪 Une vérification locale ne vaut que pour le chemin d'erreur qu'elle emprunte
> (26/07/2026, v2.26.0 → v2.26.1).** La conservation du lien d'origine à travers
> l'authentification a été vérifiée dans un navigateur, sur le build de production
> servi en local : elle marchait. En production, elle ne marchait pas. En local il
> n'y a **pas de backend** : `auth.me()` échoue en **erreur réseau** et c'est la
> garde du layout qui redirige ; en production l'API répond **401**, et c'est
> `$lib/api.ts` qui redirige en premier — un troisième chemin, non corrigé. Avant de
> conclure d'un test local, se demander **quel chemin de code il a réellement
> exercé**, et si la production en emprunte un autre (API absente vs 401/403,
> cookies, HTTPS, service worker, reverse proxy). Quand un même effet a plusieurs
> points de déclenchement, les chercher tous — ici, un test qui interdit toute
> redirection en dur vers `/auth/connexion` dans `front/src` aurait trouvé le
> troisième du premier coup, là où la relecture en avait vu deux.

**P11 — clore les tickets, et surtout pas par mot-clé GitHub (11/08/2026).**
Écrire `Closes #299` dans le corps d'une PR fait fermer le ticket **au merge**.
C'est la mauvaise date : ce soir-là, #299 aurait été clos pendant qu'une
régression était en vol — quatre colonnes disparues de l'écran, trouvées par
l'utilisateur *après* la fusion. Et le matin même, un merge avait livré un
`check-reliability.sh` incapable de démarrer. **Fusionner n'est pas déployer,
déployer n'est pas vérifier.**

Un ticket se ferme quand le comportement qu'il décrit est **observé corrigé en
production** — donc après P7, et avec la preuve dans le commentaire :

```bash
gh issue close 299 --comment "Vérifié en production après la MEP v2.52.2 : <ce qui a été observé, et comment>."
```

Un ticket dont la vérification est **différée** (elle dépend d'un événement à
venir : un passage hebdomadaire, une bascule) **reste ouvert**, et reçoit un
commentaire disant ce qu'il attend et à quelle date. Le fermer « parce que le
code est livré » revient à confondre le correctif et sa preuve.

Le corps de la PR continue de **nommer** les tickets en français (« Ferme #299 »)
— c'est de la lisibilité pour le relecteur, pas un mécanisme. À ne pas confondre :
le français n'est pas reconnu par GitHub, donc cette mention ne ferme rien, et
c'est très bien ainsi. Les tickets **ouverts** par le lot se listent aussi, pour
qu'un relecteur voie ce qui a été découvert sans être traité.

**Rollback si P1–P6 échoue :** le retour arrière classique est de ramener l'actif
au commit précédent (`git reset --hard <commit-précédent>`), puis `docker compose
build && docker compose up -d`.

Ce retour au code précédent tient **sans restaurer la base** parce que les
migrations sont compatibles sur une version (#1757, `test_migrations_compatibles.py`) :
l'ancien code lit et écrit le schéma que la version fautive a migré.

🔴 **Mais ce geste ne se lance pas de sa propre initiative.** Le hook global
`garde-git-destructif.py` le **refuse** depuis l'outil Bash — y compris glissé dans
un `ssh … '… && git reset --hard …'` —, parce que rien n'en défait l'effet et qu'il
a déjà détruit du travail non committé. **L'accord de Philippe se demande**, dans
la conversation, avant le geste ; sans lui, on ne cherche pas à contourner le
hook. La voie qui ne détruit rien : une PR `revert` vers `main`, qui suit le cycle
normal (CI, fusion, `auto-deploy.sh`) — plus lente, et c'est le prix d'un geste que
personne ne peut défaire.

**P10 — bilan mémoire du lot (🟡 priorité 3, ajouté le 03/08/2026).** Une MEP réussie
n'est pas une MEP close : ce qui a été appris pendant le lot disparaît si personne ne
l'écrit. Ce point est le **dernier** du post-check, et le seul qui ne regarde pas la
production — il regarde le lot.

Ce point **ne bloque pas** la MEP (priorité 3, après la sécurité et la fiabilité des
contrôles) : il la **termine**. Une leçon écartée doit l'être explicitement, pas par
omission.

Relire les activités de la PR — pas le diff, les **surprises** — et se poser les
quatre questions dans cet ordre :

1. **Un défaut a-t-il été trouvé par l'utilisateur plutôt que par un contrôle ?**
   C'est le signal le plus fort : le contrôle manquant est la vraie leçon, pas le
   défaut. → charger la skill globale `retrospective-incident`.
2. **Cela pouvait-il arriver sur un autre projet ?** Si oui, ça monte dans le socle
   `~/.claude/standards/`, et **nulle part ailleurs** (règle de placement,
   `~/.claude/CLAUDE.md` §1). Une pratique générique recopiée dans un projet est déjà
   une divergence.
3. **Sinon, est-ce propre à 5Hostachy ?** → banque `~/.claude/projects/C--Dev-5hostachy/memory/`,
   un fichier = un fait, plus une ligne dans `MEMORY.md`.
4. **Une mémoire existante est-elle devenue fausse ?** Une mémoire périmée est pire
   qu'une mémoire absente : elle est citée avec assurance. La corriger ou la
   supprimer — ne jamais empiler une exception par-dessus.

Vérifier aussi que la documentation *visible* a suivi : manuel utilisateur mis à jour
(il ne porte plus de version ni de date à bumper depuis le 23/10/2026 —
`test_le_manuel_ne_porte_pas_de_numero_de_version` en refuse le retour), `specs/` si un
contrat d'API a changé.

**Pourquoi ce point existe :** sur le lot des pièces jointes (03/08/2026), quatre
constats n'auraient été écrits nulle part sans un rappel explicite — la version du
manuel jamais bumpée, les fins de ligne cassées par `sed -i` puis « réparées » d'une
façon qui ne restaure pas un fichier mixte, les endpoints devenus orphelins, et le
drapeau `fichiers` des e-mails calculé sur l'intention plutôt que sur la pièce jointe
réelle. Trois d'entre eux ont été soulevés **par l'utilisateur**, pas par le
processus : c'est exactement la question 1.

**P12 — retirer la copie de travail du lot (#1890, 13/10/2026).** Chaque lot
travaille dans sa copie à soi, et aucun ne la retirait : **134** s'étaient
accumulées en deux semaines. La copie se retire une fois la MEP vérifiée — la
branche reste, rien ne se perd. Le script refuse ce qui perdrait quelque chose
(modification non committée, commits sur aucune branche), retire d'abord les
**jonctions** vers le clone principal (sinon le retrait vide ses
`node_modules`, `standards/13` §10), et refuse le répertoire courant de
l'appelant : sous Windows, un répertoire tenu ouvert fait échouer le retrait **à
moitié** (`.git` parti, fichiers restés). Le lancer donc **depuis le clone
principal**, jamais depuis la copie elle-même. `GARDÉE` sort en code 1 avec son
motif. Le stock d'une session qui n'a pas fini proprement :
`bash scripts/poste/retirer-worktree.sh --inactifs` (24 h par défaut ; `--voir`
liste sans retirer).


