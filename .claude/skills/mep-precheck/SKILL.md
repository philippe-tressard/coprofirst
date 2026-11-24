---
name: mep-precheck
description: "MEP 5Hostachy — l'ordre d'un lot (rejeu `bash scripts/poste/rejouer-ci.sh`, push de la branche, PR vers `dev`, CI verte, pré-check `bash scripts/poste/precheck-mep.sh`, puis `bash scripts/poste/conduire-mep.sh`), lecture des verdicts du pré-check (tous les points s'exécutent), version et images publiées, post-check P1-P12 (dont la clôture des tickets après vérification en production, puis le retrait de la copie de travail du lot), retour arrière. À charger : avant d'ouvrir la PR d'un lot, avant le pré-check et `conduire-mep.sh`, après une fusion vers `main`, pour diagnostiquer un déploiement qui n'a pas eu lieu ou vérifier qu'un correctif est réellement servi. L'histoire des incidents qui ont fait naître chaque contrôle est dans HISTORIQUE.md, à ouvrir seulement pour diagnostiquer."
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
| modes | Modes des fichiers exécutables versionnés | **Automatisé** : job CI `test-scripts` (étape « Bits d'exécution versionnés ») | `100755` sur tout ce qui doit s'exécuter, `100644` sur les modules sourcés `lib-*.sh` |

**Modes** (sans numéro : `0b` est la modularité, au script) — pourquoi un clone Windows avale `chmod +x` : `standards/08` §3.
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
| E1 | **Autorisation centralisée, aucun passe-droit** | Les dépendances d'auth dans `app/auth/deps.py`, les règles d'appartenance dans `app/auth/appartenance.py` (`CLAUDE.md`, « Dépendances d'auth ») · tout endpoint porte une dépendance · exceptions publiques énumérées et justifiées · `has_role(RoleUtilisateur.…)` jamais `user.role` ni chaîne · exposition publique en **liste blanche** | `api/tests/test_autorisation.py` (CI) |
| E2 | **Factorisation** | Aucun code spécifique ne réimplémente une bibliothèque partagée (dates, montants, alertes, thème PDF, destinataires) | `test_dates_fr.py` · `npm run lint:dates` · `npm run lint:notifications` — le reste par relecture |
| E3 | **Documentation à jour** | README (et ses badges) · manuel utilisateur · `specs/` reflètent l'état livré | `api/tests/test_documentation.py` pour la partie mécanique ; le fond reste à relire |

**E1 — pourquoi cette exigence a besoin d'un test et non d'une consigne** (principe :
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

**E3 — pourquoi.** La synchronisation du manuel entre `docs/` et `front/static/`
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
trace dans `.git/precheck-mep.ok`, et `.githooks/pre-push` refuse sans elle un push
À LA MAIN sur `dev` ou `main` — le chemin nominal n'en fait plus : `conduire-mep.sh`
pousse la version sous `SKIP_PRECHECK=1`.

**Fusionner vers `main` EST la mise en production** : `auto-deploy.sh` déploie
`origin/main` toutes les 5 minutes. Le pré-check se passe donc **avant
`conduire-mep.sh`**, jamais après la fusion — et après la CI verte de la PR du lot,
que le point 16 lit. L'ordre d'un lot s'écrit une fois, dans `CLAUDE.md` (« Ordre d'un
lot ») ; cette skill dit ce que chaque point y lit (#2908).

🔴 **Depuis le 28/08/2026, c'est Claude qui crée et fusionne la PR, et qui conduit
la MEP** — l'utilisateur n'intervient plus. Le pré-check ne s'allège pas pour
autant : il est désormais **le seul** filtre entre un lot et la production, là où
il n'était qu'un préalable à une relecture. La contrepartie demandée est un
**compte rendu après** : version servie et fonctionnalités apportées.

🔴 **En session cloud, la même chaîne s'enchaîne sans validation intermédiaire**
(25/09/2026) — pré-check INCONNU dit dans la PR, post-check laissé au poste, `dev`
recréée par l'API GitHub. La règle vit dans `CLAUDE.md`, « Session cloud » : elle
n'est pas recopiée ici.

Le déroulé complet, une fois le pré-check du lot vert, est **conduit par un script
versionné** (#2631) — jamais par des gestes enchaînés de mémoire, ni par un script
du dossier temporaire d'une session, qui disparaît avec elle :

```
bash scripts/poste/conduire-mep.sh --lot <n° de la PR vers dev | -> \
     --titre "<préfixe>: {version} — <ce que le train apporte>" --corps <fichier>
bash scripts/poste/conduire-mep.sh … --a-blanc    # tout est mesuré et décidé, rien n'est écrit
bash scripts/ci/relancer-annules.sh <n>           # un check requis ANNULÉ bloque sans un mot (#2225)
```

Il fusionne le lot (checks verts **et** état `CLEAN` — jamais pendant `UNKNOWN`,
le défaut du 10/11), **pose la version** du train sur `dev`, ouvre ou retitre
l'unique PR `dev → main`, la fusionne **hors de la fenêtre de bascule**
(`FENETRE_BASCULE_*`, confrontée par son autotest à la crontab), recrée `dev`, y
ramène les PR qui la visaient — reciblées, ou **rouvertes** si GitHub les a fermées
(un brouillon l'est, #2619 ; une PR fermée **à la main** reste fermée, nommée au
journal : `geste_pr_suivie`, #2688) —, attend `Déployé:` sur l'actif, joue `--post-mep` et
relance la veille. ⚠️ GitHub supprime `dev` **après** la fusion, de façon
asynchrone : lue une seconde après, elle est encore là — le conducteur attend le
fait (`attendre_dev_supprimee`, délai borné), relit chaque PR reciblée et s'arrête
en la nommant si elle n'est pas sur `dev` (#2676, vécu à la v3.86.0).
**Tué, il se relance avec les mêmes arguments** : son état
(`conduite-mep.etat`) et son verrou vivent dans le répertoire git commun, et chaque
étape vérifie son fait avant d'agir. Ses décisions sont des fonctions pures de
`scripts/lib/lib-mep-conduite.sh` (`--selftest`, job `test-scripts`).

🔴 **La version se pose À LA MEP, plus dans le lot** (#2631) : `conduire-mep.sh` la
calcule de `main` et des préfixes des commits du train (`feat` → mineure, `!` →
majeure, sinon correctif — `rang_attendu`, la lecture de 0g ; sujets et pied
`BREAKING CHANGE` seulement, jamais un corps cité : `declarations`, #2896) et la commit sur `dev`
par `npm version`, dans une copie jetable. Un lot n'emporte plus de
`chore(version)` : 0d le refuse sur la branche d'un lot ; sur `dev`, 0d et 0g
jugent le train. Le titre porte la marque `{version}`, et son préfixe doit annoncer
le rang du train — c'est lui qui devient le commit de `main`. Trois collisions de
numéro le 10/11 (3.79.0, deux fois 3.81.0) venaient de la version posée lot par lot.

⚠️ **Quatre pièges — les trois premiers rencontrés le 28/08, le quatrième le 25/09 ;
les trois premiers sont tenus par `conduire-mep.sh`, qui ne touche à aucune copie
de travail :**

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
   Et il se **prouve** sans effet : `node scripts/comparer-rendu.mjs <réf. d'avant>`
   (depuis `front/`) compile chaque composant avant et après et liste ceux dont le
   rendu change — la PR explique chacun. Une coupure `{a}`/`{b}` sur deux lignes
   garde l'écran, pas le texte du DOM (#2900).

🔴 **Après la MEP : `bash scripts/poste/precheck-mep.sh --post-mep`** (#1282,
25/09/2026). Il ne lance pas les points du LOT (0a à 0h, 15, 16), qui échouent
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
| 0d | **Version** : aucun bump sur la branche d'un lot ; un seul sur `dev` (le train) | OK · ÉCART · FAIL |
| 0g | **Rang du bump conforme** à ce que le train apporte (lu dans les préfixes de commit) ; sur un lot, le rang annoncé | OK · ÉCART · FAIL |
| 0f | **Titre et descriptif de PR préparés** (`.git/pr-brief.md`) | OK · FAIL · INCONNU |
| 0h | **Migrations de texte légal : prise sur le texte servi** — chaque migration du lot qui nomme un texte légal, jouée en mémoire sur `/api/config/legal` ; un passage ni pris ni déjà servi = FAIL (#2571, le cas de la 0329) | OK · FAIL · INCONNU |
| 15 | Aucun endpoint orphelin | OK · FAIL |
| 16 | **Suite de la CI verte sur cet arbre** : phase rapide au poste (`scripts/poste/rejouer-ci.sh`), pytest et e2e sur la CI de la PR | OK · FAIL · INCONNU |
| 1 | Site public répond | OK · FAIL · INCONNU |
| 2 | Rôle actif cohérent **et conforme au réel** | OK · FAIL |
| 3 | Standby sans conteneur (pas de split-brain) | OK · FAIL |
| 4 | Le `.env` de l'actif désigne PostgreSQL (`base_configuree`) — la santé de la base est le point 22 | OK · FAIL · INCONNU |
| 5 | Bridge WhatsApp connecté | OK · FAIL |
| 6 | Aucune ERROR/CRITICAL (1 h), **hors celle que ce lot corrige** | OK · FAIL · INCONNU |
| 7 | Scripts cron exécutables | OK · FAIL |
| 8 | Battement d'auto-deploy sur le standby | OK · FAIL |
| 9 | **E-mails en échec** (7 j), **exception datée** d'un incident clos comprise | OK · ÉCART · FAIL · INCONNU |
| 10 | Parité de code entre les 2 nœuds | OK · ÉCART |
| 11 | Auto-deploy de l'actif vivant | OK · FAIL |
| 12 | **Chaque conteneur sert l'image bâtie sur SON commit** (api, front, bridge, Caddy) — deux faits par service, jamais une date : les images contiennent-elles le dernier commit de son répertoire, et le conteneur tourne-t-il sur le manifeste de l'image étiquetée ? Le détail donne la commande de recréation ; pourquoi pas l'ID d'image : `lib-images-servies.sh` (#1675) | OK · FAIL · INCONNU |
| 13 | Canal d'alerte non muet | OK · FAIL |
| 14 | Hygiène disque sur les **2** nœuds | OK · FAIL |
| 17 | **Points d'entrée conformes au dépôt** (crons, unité systemd ; sur le poste, le lien du Bureau vers le lanceur de la copie hors site, #2708) | OK · FAIL · INCONNU |
| 18 | **Images du standby bâties sur son code** — le point 10 compare deux HEAD, pas ce qu'un failover démarre (#511) | OK · FAIL · INCONNU |
| 19 | **Liens des courriels servis par la production** | OK · ÉCART · FAIL · INCONNU |
| 20 | **Ordre du menu servi** (`pages_order`) — un fantôme rend ÉCART, une répétition FAIL (#1114) | OK · ÉCART · FAIL · INCONNU |
| 21 | **Textes légaux servis complets** — un « À RENSEIGNER » dans la page publique rend ÉCART : à compléter dans Admin › Légal (#1585) | OK · ÉCART · INCONNU |
| 22 | **Réplication PostgreSQL** — un primaire sur l'actif, une réplique qui reçoit le journal sur le standby ; deux primaires ou une réplique déconnectée rendent FAIL. Décision partagée avec C37 (`lib-replication.sh`, #1781) | OK · FAIL · INCONNU |
| 23 | **Aucune PR ouverte vers `main` hors de `dev`** — chaque MEP supprime `dev`, et GitHub réoriente vers `main` les PR qui la visaient (Dependabot compris). Une PR réorientée rend ÉCART ; la reprendre : `python scripts/poste/reprendre-dependabot.py` (relevé et montées), puis `--fermer`, et ses montées dans un lot sur `dev`. Joué aussi en `--post-mep`, premier moment où elles apparaissent (#1870) | OK · ÉCART · INCONNU |
| 24 | **Aucune alerte Dependabot haute ou critique ouverte** — deux alertes hautes (`follow-redirects`, bridge) ont dormi deux jours sans PR ni ticket (#2148). FAIL qui nomme l'alerte, son manifeste et la version corrigée ; ÉCART si le lot modifie ce manifeste (le lot correctif ne se bloque pas lui-même). Joué aussi en `--post-mep` : l'alerte se ferme à la ré-analyse de `main`, quelques minutes après la fusion. Décision : `reprendre-dependabot.py --alertes` | OK · ÉCART · FAIL · INCONNU |
| 25 | **Dérogations des règles partagées portées par un ticket ouvert** — neuf règles que le front calcule encore étaient portées par deux tickets fermés (#2633) : la dette n'avait plus de porteur. FAIL qui nomme le porteur fermé et ses règles — repointer sur un ticket ouvert ou migrer. Joué aussi en `--post-mep`. Décision : `check-regles-partagees.mjs --tickets` (`verdictPorteurs`, autotesté) | OK · FAIL · INCONNU |

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
  accumulait le retard après chaque déploiement). Point 0d, sur `dev` : un train
  **sans** bump se déploie quand même — c'est P3 qui devient incapable de prouver
  que le déploiement a eu lieu, la version servie étant identique avant et après.
- **0c** → il ne compte que les échecs de CI que ce lot **ne corrige pas**. Un
  échec est dépassé s'il est suivi d'un succès plus récent, **ou** si HEAD
  descend du commit fautif. Sans cette nuance, le push qui corrige une CI rouge
  était refusé par le contrôle même qui constatait le rouge — et la seule issue
  était `SKIP_PRECHECK=1`, donc désarmer tous les points pour en contourner un
  (#318, corrigé le 12/08/2026). Les **deux** conditions sont nécessaires : les
  PR étant fusionnées en squash puis `dev` réaligné, l'ascendance seule disparaît
  au premier réalignement. Une **troisième** depuis #2337 (30/10/2026) : le
  commit en échec a été **retiré** et déclaré dans `.git/reecriture-dev`, et 0a
  a validé la déclaration — le bump rejoué derrière un commit neuf n'est plus un
  ancêtre de HEAD, et son échec bloquait le lot qui le remplace. Une déclaration
  refusée par 0a ne dépasse rien (`ascendance_0c`, `lib-reecriture.sh`).

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

- **0f** → le lot doit porter son titre et son descriptif de PR dans
  `.git/pr-brief.md`, rédigés avant d'ouvrir la PR : première ligne `commit: <sha court de HEAD>`, deuxième
  ligne le titre en `# …`, puis le corps (5 lignes minimum). Un brief rédigé pour
  un autre commit **échoue** — sinon il décrirait le lot précédent. Ajouté le
  11/08/2026 après deux oublis dans la même journée, le second juste après
  s'être fait reprendre sur le premier : la consigne de la skill `avant-commit`
  ne tenait pas seule.
- **0d en FAIL sur la branche d'un lot** → le lot porte un bump : le retirer, la
  version se pose par `conduire-mep.sh` à la MEP (#2631).
- **0d en FAIL sur `dev`** → le train porte **deux bumps ou plus**. N'en garder qu'un, posé
  en dernier : `git reset --soft <avant le 1er bump>` puis recommit et
  `push --force-with-lease` — `dev` n'est pas protégée et le force-push y est
  déjà le geste normal après chaque squash. Ne **jamais** empiler un second bump
  quand le lot repart : la version intermédiaire n'atteindra jamais la
  production et l'historique annoncera un déploiement qui n'a pas eu lieu
  (PR #297, 11/08/2026 — v2.49.1 jamais servie).
- **16** → il ne mesure rien lui-même : il **lit la trace** que `scripts/poste/rejouer-ci.sh`
  écrit dans `.git/rejeu-ci.ok`, et qui porte le commit couvert. Une trace d'un
  autre commit rend INCONNU — sinon un lot hériterait du vert du lot précédent. Elle porte aussi
  l'**arbre** git : un autre sha à arbre identique (reword, squash) reste valide, le détail le dit
  (« même arbre », #2245) ; une trace sans arbre, ou un contenu modifié, rend INCONNU.
  Il reprend aussi le nombre de tests **sautés** sur le poste (`SAUTS=`, #1734) :
  ceux-là — le rendu PDF, faute de WeasyPrint — seule la CI de la PR les joue.
  🔴 **Depuis #2571, le rejeu ordinaire s'arrête à la phase rapide** : les étapes lentes
  (pytest, tests de navigateur) sont **confiées à la CI de la PR**, et la trace le dit
  (`MODE=rapide`). Sur une telle trace, le point lit par `gh` les checks de la PR ouverte
  pour la branche : même arbre et tous verts → OK ; un check rouge → FAIL ; en cours, PR
  absente, autre arbre ou `gh` muet → INCONNU. C'est pourquoi le pré-check vient **après**
  la CI de la PR (l'ordre : `CLAUDE.md`, « Ordre d'un lot »). `--complet` joue tout au poste.

  ```bash
  bash scripts/poste/rejouer-ci.sh
  ```

  Le script **extrait** les commandes de `.github/workflows/ci.yml` ; il n'en
  tient aucune liste, parce qu'une seconde liste divergerait au premier job
  ajouté — et c'est le job ajouté qu'on oublie de rejouer. Il commence par un
  **pré-vol** (dépendances, base des tests, Playwright, versions, venv) qui refuse
  en quelques secondes au lieu de finir INCONNU, puis joue les étapes **rapides**
  de tous les jobs, en couloirs parallèles — et, avec `--complet` seulement, les
  **lentes** (qui démarrent sur les créneaux libres) ; un rouge l'arrête à la fin
  de sa phase, sans trace (#2224). Après une correction :
  `bash scripts/poste/rejouer-ci.sh --reprendre` rejoue d'abord ce qui était rouge.
  Dépendances du poste en écart : `--venv` (venv aligné sur le lot, réutilisé).
  Où passe le temps des rejeux : `python scripts/poste/mesurer-rejeux.py`.
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
- **Point 9 — un incident clos se DÉCLARE, daté** (#2631). Le point lit les échecs
  par le canal machine (`GET /admin/emails/echecs-recents`, total, codes et date du
  `dernier`) ; un échec connu et clos ne se redéclare plus à la main dans chaque PR :
  une ligne dans `exceptions-precheck`, au répertoire git **commun** (tous les
  worktrees du poste la lisent) —

      # point|ticket|borne : aucun fait après|échéance|motif
      9|#2528|2026-11-04 21:30 +0100|2026-11-11 21:00 +0100|26 courriels de l'incident clos

  Le point la vérifie lui-même : OK « déclaré » tant que le `dernier` échec n'est
  pas postérieur à la borne et que l'échéance n'est pas passée ; **FAIL** au premier
  échec plus récent ou passé l'échéance ; INCONNU si la date est illisible ; ÉCART
  « à retirer » quand le point est redevenu vert. Règle et cas : `juger_exception`
  (`scripts/lib/lib-precheck-exception.sh`, `--selftest`) — tout point qui mesure un
  fait daté peut l'appeler ; seul le 9 le fait aujourd'hui.

### Avant même le script — l'étape 0 bis

Les exigences E1 à E3, hors machines, sont au tableau de l'**étape 0 bis** plus
haut, et nulle part ailleurs : ce fichier en portait une seconde copie, qui avait
recompté « deux » au-dessus de trois lignes (#122).

**Protocole si anomalie** : diagnostiquer → proposer un plan → corriger après
validation → relancer le script → livrer seulement si tout est vert.

## Sommaire — les annexes

Cette skill passait 800 lignes (#2910). L'ordre, l'étape 0 et le pré-check restent ici ; le post-check, le rejeu et la version sont en annexe, chargée à la demande. L'histoire des contrôles : HISTORIQUE.md.

| Annexe | Ce qu'elle porte |
|---|---|
| `POSTCHECK.md` | Post-check P1 à P12 après la MEP : déploiement constaté, version servie, clôture des tickets, retour arrière |
| `REJEU-ET-VERSION.md` | Le rejeu de la CI en détail, version, images publiées, réplique et promotion |
