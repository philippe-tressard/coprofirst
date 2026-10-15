# MEP — l'histoire derrière chaque contrôle

> Chargé **pour diagnostiquer**, pas pour agir. La procédure vit dans
> `SKILL.md` ; ce fichier explique **pourquoi** chaque point existe, quel
> incident l'a fait naître, et quels faux verts il a déjà produits.
>
> Séparé le 09/08/2026 : `SKILL.md` faisait 716 lignes (≈ 13 500 jetons), plus
> que tout le socle chargé en permanence. On ne pouvait pas ouvrir la procédure
> sans charger toute l'histoire — donc on ne l'ouvrait pas.

## Les « pourquoi » du pré-check

| 15 | **Aucun endpoint orphelin introduit par le lot** | `cd api && pytest tests/test_endpoints_orphelins.py -q` (poste de dev, avant le push) | 3 tests verts — voir « Point 15 » |

**Point 2 — pourquoi (26/07/2026) :** « fichier présent, cohérent » était trop vague
et ne disait pas *cohérent avec quoi*.

Déroulé réel, après **coupure d'électricité** (confirmé : rpi2 a redémarré à 07:37,
`uptime` 2 h ; rpi1 n'a **pas** redémarré, `uptime` 4 jours — probablement onduleur
côté rpi1, mais perte de la connectivité externe, d'où `github` injoignable et
`Email KO`) :
1. 02:00 — bascule rpi2 → rpi1 réussie ; les 2 flags disent `rpi1`.
2. Coupure ; rpi1 cesse de servir (dernière écriture en base à 04:53).
3. 06:53 — rpi2, encore debout, voit le site HS, tente un failover, **échoue**
   (réseau) mais a déjà écrit `.active=rpi2`. Les 2 nœuds se croient actifs.
4. 06:57→07:42 — `health-watch.sh` ne bascule que s'il se croit **standby** (« je
   suis l'actif → pas d'intervention, le standby me surveille »). Les deux
   s'abstiennent : site HS ~50 min **sans aucun failover**.
5. 07:37 — rpi2 redémarre ; 07:38:49 `boot-role-guard.sh` reprend la main et le site
   revient vers 07:45. Mais le flag de rpi1 reste faux jusqu'à correction manuelle
   (09:28).

> **🐛 Cause racine — `boot-role-guard.sh` ne corrige pas le flag du peer.**
> Son log du 26/07 est explicite : `Peer rpi1 joignable — conteneurs=0
> cloudflared=inactive .active=rpi1` → `Décision : active` → `.active → rpi2`.
> Il **constate** que le peer, *joignable*, se croit encore actif, décide
> correctement d'assumer le rôle… et laisse le flag du peer inchangé. C'est ce
> qui fabrique l'incohérence, et donc la neutralisation du failover.
> **À corriger** : quand `boot-role-guard` prend le rôle actif et que le peer est
> joignable, il doit aussi écrire `.active` chez le peer (ou alerter s'il n'y
> parvient pas). Idem pour le failover de `health-watch.sh`, qui a laissé la même
> incohérence à 06:53. Tant que ce n'est pas fait, **toute coupure ou reboot d'un
> nœud peut laisser les deux flags en désaccord** — donc vérifier le point 2 après
> chaque événement électrique ou redémarrage.
En parallèle, `auto-deploy.sh` sur rpi1 franchissait son garde-fou anti-split-brain
à chaque tick de 5 min (`ACTIVE == SELF`) et n'échouait qu'ensuite, au `git fetch`,
faute de réseau — un merge sur `main` avec le WAN rétabli aurait donc démarré les
conteneurs sur les deux nœuds, soit **deux bases divergentes**. Le contrôle doit
comparer les deux fichiers entre eux **et** au réel (qui porte les conteneurs).

**Point 13 — pourquoi (26/07/2026) :** pendant cette même panne,
`health-watch.sh` a loggué `Email KO: [Errno 101] Network is unreachable`. L'alerting
est **mono-canal (SMTP)** et tombe précisément quand le réseau tombe, c'est-à-dire
quand on en a besoin. Tant qu'il n'y a pas de second canal, vérifier au moins que le
premier n'est pas muet.

**Coupure de courant — réflexe.** Les deux RPi partagent le même local, donc la même
alimentation : la redondance ne protège **pas** contre une coupure électrique, elle
protège contre la panne d'un nœud. Après tout événement électrique, contrôler dans
l'ordre : point 2 (les 2 flags), point 3 (split-brain), `uptime` sur les 2 pour
savoir qui a redémarré, puis point 22 (un seul primaire, une réplique qui reçoit)
et l'intégrité de la base (`GET /admin/db/integrite`).

**Point 5 — méthode sans token (26/07/2026) :** `GET /status` du bridge répond
`{"error":"Unauthorized"}` sans clé d'API — le pré-check ne doit pas exiger un
secret. Lire l'état dans les logs, qui sont horodatés en epoch ms :
```bash
docker logs hostachy_whatsapp --since 14h 2>&1 \
  | grep -oE '"time":[0-9]+[^}]*"msg":"[^"]+"' | tail -20
```
Vert si le dernier `WhatsApp connected ✓` est **postérieur** au dernier
`Connection closed`. Des fermetures suivies de « Reconnexion programmée » puis d'une
reconnexion sont le **fonctionnement normal** du backoff v2.20.x, pas une panne — ne
pas confondre avec la boucle morte du 24/07 (fermetures sans jamais de reconnexion).

**Point 9 — comment vérifier** : interface **Admin → Emails → Historique**,
filtrer `statut = erreur` sur 7 jours (`GET /admin/emails/historique`).

**Point 7 — pourquoi :** un script peut perdre son bit d'exécution sans prévenir (ex. `auto-deploy.sh` le 21/04 → `Permission denied` silencieux dans le cron pendant des semaines, empêchant le déploiement automatique de v2.18.11). Vérifier en particulier `auto-deploy.sh`, `bascule.sh`, `health-watch.sh`, `maintenance.sh`, `MaJ-Hostachy.sh`, `check-reliability.sh`, `boot-role-guard.sh`. Si un bit `x` manque : `chmod +x <script>` sur le(s) RPi concerné(s). (`check-stack.sh` n'y figure plus depuis le 06/08/2026 : il n'est plus dans aucun cron — voir le point 8.)

**Point 8 — pourquoi :** le point 7 ne couvre que **la cause** déjà rencontrée (perte du bit `x`). Le point 8 détecte **le symptôme** quelle qu'en soit la cause (droits, chemin déplacé, faute de syntaxe, dépendance manquante…) en inspectant directement les logs produits par les crons — c'est ce qui aurait permis de détecter le problème `auto-deploy.sh` dès sa première occurrence le 21/04, au lieu d'attendre 7 semaines. Si une erreur récurrente apparaît → diagnostiquer la cause (pas seulement les droits) avant de poursuivre la MEP. ⚠ **Angle mort** : ce point ne détecte **rien** si le log est figé/absent/non-inscriptible (aucune ligne à lire = faux « OK ») — précisément le cas du bug auto-deploy du 15/07 (cf. **point 11**). Un `tail` vide ou un log root-owned n'est PAS un feu vert.
⚠ **Second angle mort, découvert le 26/07/2026 — le battement manquant.** La liste de
motifs (`Permission denied`…) ne couvre que des erreurs *attendues*. Ce jour-là,
`auto-deploy.sh` sur rpi1 écrivait une ligne « n'est pas l'actif — ignoré » toutes les
5 min jusqu'à 01:58, puis **plus rien de daté pendant 7 h 30** : il franchissait
désormais le garde-fou et mourait au `git fetch`, ne laissant que des blocs d'erreur
git **non horodatés** (`ssh: connect to host github.com port 22: Network is
unreachable`) — invisibles à un `grep` de motifs et à un tri par date. Donc vérifier
aussi la **présence** des lignes périodiques attendues, pas seulement l'absence
d'erreurs :
```bash
# rpi standby : ~12 lignes/heure attendues ; un trou = le script ne va plus au bout
grep -c "$(date '+%Y-%m-%d %H')" /var/log/hostachy-deploy.log
grep -E '^\[[0-9]{4}-' /var/log/hostachy-deploy.log | tail -5   # dernières décisions datées
```
Et élargir les motifs d'erreur au réseau et à git : `Network is unreachable`,
`Could not read from remote repository`, `fatal:`, `Connection timed out`.

⚠ **Troisième angle mort — tous les logs ne battent pas (05/08/2026).**
`hostachy-health-watch.log` était figé depuis **44 h** sur les deux nœuds, ce qui
ressemble exactement au battement manquant du point précédent — sauf que
`health-watch.sh` sort en `exit 0` **sans écrire** quand le site répond 200
(ligne « Site OK »). Son silence est le fonctionnement nominal : il n'écrit que
sur panne. Crier au loup ici ferait perdre du temps avant chaque MEP, et pire,
apprendrait à ignorer ce log.

Avant de conclure au battement manquant, **savoir si le script écrit à chaque
passage** :

| Log | Bat à chaque passage ? | Silence = |
|---|---|---|
| `hostachy-deploy.log` (standby) | oui, ~12 lignes/h | anomalie |
| `hostachy-reliability.log` | oui, toutes les 15 min | anomalie |
| `hostachy-health-watch.log` | **non — seulement si le site est HS** | normal |
| `hostachy-bascule.log` | non — une fois par nuit à 02:00 | normal |
| `hostachy-maintenance.log` | non — le dimanche à 03:00 | normal |
| `hostachy-role-guard.log` | non — au démarrage du nœud | normal |
| `hostachy-check.log` | **plus alimenté** — `check-stack.sh` retiré du cron le 06/08/2026 | normal (log figé) |

⚠️ **Ce tableau a lui-même menti, et c'est instructif (06/08/2026).** Il annonçait
`hostachy-check.log (actif) — oui, toutes les 10 min, silence = anomalie`. Trois
erreurs dans une seule ligne : ce n'était pas l'actif mais **rpi2 quel que soit son
rôle** ; il ne battait pas, puisque `check-stack.sh` y **échouait avant d'écrire quoi
que ce soit d'utile** (port 8080 tenu par l'application co-hébergée, 144 échecs par
jour) ; et sa sortie n'est de toute façon **pas horodatée**, donc son battement
n'était pas mesurable — ce qui est précisément ce qui a permis à la ligne de rester
fausse. Sur rpi1, où le port est libre, le script n'était pas planifié du tout : la
couverture réelle était nulle sur les deux nœuds, à l'inverse l'un de l'autre.

`check-stack.sh` a d'abord été **rendu à ce que son en-tête décrivait** — un outil
ponctuel, à lancer après une modification de Caddy, pas un cron. Vérifié avant
retrait qu'aucun script ne l'appelle et qu'aucun ne lit son log.

🔴 **Il est supprimé depuis le 20/09/2026 (#1029), et l'outil ponctuel ne manque
à personne** : il montait une stack *stub*, écrivait lui-même le Caddyfile qu'il
allait interroger, puis vérifiait que ce Caddyfile rendait bien les en-têtes qu'il
venait d'y écrire. Un contrôle qui fabrique son propre sujet ne mesure que
lui-même — il ne disait donc **rien** de la configuration servie, et c'est ce qui
lui a permis d'attendre `SAMEORIGIN` pendant des mois sans que l'écart se voie.
Ce que le dépôt sert est vérifié par **C23** (`check-reliability.sh`), sur les
en-têtes **réellement reçus** du nœud actif, toutes les quinze minutes.
La leçon générique est au socle : un contrôle sans destinataire est un contrôle
absent (`standards/04-fiabilite-des-controles.md` §7), et une sortie non horodatée
rend son propre battement invérifiable.

⚠ **Et ne pas écrire `$(grep -c … || echo 0)`** — le piège documenté en
« Surveillance continue » §4 se retend à chaque pré-check improvisé : `grep -c`
affiche déjà `0` **et** sort en code 1, donc le `||` ajoute une seconde valeur et
le test qui suit devient inexploitable. Reproduit le 05/08/2026 dans un contrôle
écrit à la volée, avec la documentation du piège sous les yeux : sept fichiers
sont apparus « illisibles » alors qu'ils étaient simplement sans erreur.

**Point 9 — pourquoi :** les emails partent en `BackgroundTask` et échouent **silencieusement** — l'erreur n'apparaît que dans la table `historique_email`, jamais dans les logs API ni à l'écran. La même cause racine (un template Jinja2 référence une variable absente du contexte du point d'appel → `UndefinedError`) s'est produite deux fois en 12 jours : `reinitialisation_mdp` le 03/06 (`destinataire.prenom` manquant) puis `ticket_statut_change` le 15/06 (même variable). Dans les deux cas, découvert seulement après un signalement utilisateur « je ne reçois pas mes mails ». Comme le point 8, ce point lit **le symptôme** quelle qu'en soit la cause (contexte template, SMTP HS, adresse invalide, domaine `.local` filtré…). Si une ligne `erreur` apparaît → ouvrir le template et le contexte du point d'appel (`send_email(code=...)`), vérifier que toute variable `{{ x.y }}` du template est fournie ; aligner sur un template voisin qui fonctionne (ex. `verification_email`).
**Repli quand l'UI n'est pas accessible** — lire la table sur le **primaire** (le
nœud actif) : un autre processus peut lire la base PostgreSQL.
```bash
ssh <actif> "docker exec hostachy_postgres psql -U coprofirst -d coprofirst -Atc \
  \"SELECT code, COUNT(*), MAX(cree_le) FROM historique_email WHERE statut='erreur' \
     AND cree_le >= now() - interval '7 days' GROUP BY code\""
```
Toute ligne est un signal fort.

**Point 10 — pourquoi :** `auto-deploy.sh` ne tourne que sur le RPi **actif** (il fait `docker compose up -d` → l'exécuter sur le standby créerait un split-brain). Le code du standby ne suit donc jamais `main` : il dérive derrière la DB. Le 16/06/2026, l'actif (rpi2) avait appliqué la migration `0111` ; la bascule nocturne a poussé cette DB vers rpi1 dont le code était resté à `0110` → `alembic upgrade head` au démarrage = `Can't locate revision identified by '0111'` → `start.sh` (`set -e`) → API en crash-loop → timeout phase 5 → bascule annulée. Correctif pérenne : `bascule.sh` phase 0 resynchronise le code du peer sur le commit de l'actif (`git reset --hard` + rebuild) **avant** toute opération destructive, et avorte proprement (prod intacte) si la resync échoue. Ce point 10 est le garde-fou amont : si les 2 HEAD diffèrent avant une MEP → resynchroniser le standby (`ssh <standby> 'cd /opt/5hostachy && git fetch origin main && git reset --hard origin/main && docker compose build'`, **sans** `up -d`).

**Point 11 — pourquoi :** `auto-deploy.sh` est le **seul cron utilisateur** (`ptressard`) ; tous les autres crons tournent en root. Or `/var/log` est `root:root` : si `hostachy-deploy.log` devient root-owned, la redirection `>> /var/log/hostachy-deploy.log` du cron user échoue en `Permission denied` et **cron n'exécute même pas le script** → l'actif cesse de se déployer **silencieusement**. Découvert le 15/07/2026 : rpi1 bloqué à v2.20.7 malgré 3 merges, chaque MEP exigeant un `bash auto-deploy.sh` manuel — invisible au point 8 (aucun log produit = angle mort). Cause structurelle : `maintenance.sh` (root, dimanche) faisait `mv .tmp log` → repassait le log root-owned **chaque semaine**, cassant le cron user de façon permanente après la 1ʳᵉ rotation. Corrigé (v2.20.10) : `chown 1000:1000` du log après rotation dans `maintenance.sh` (self-healing sur les 2 RPi) + contrôle automatisé **C13** dans `check-reliability.sh` (cron */15). Au pré-check : si le log est root-owned → `sudo chown ptressard:ptressard /var/log/hostachy-deploy.log` ; si HEAD actif ≠ `origin/main` alors que `dev` est mergé → auto-deploy ne tourne pas, diagnostiquer (ownership du log en premier) **avant** MEP.

**Point 12 — pourquoi :** le point 10 vérifie que le **git** du RPi est à jour, mais **la parité de HEAD ne garantit PAS que l'image Docker en cours a été construite depuis ce commit**. Le 18/07/2026, après la bascule nocturne rpi1 → rpi2, rpi2 était à jour côté git (`1211767`) mais son **image API datait du 16/07** (rebuild sauté par `bascule.sh` phase 0, qui ne rebuildait que si les HEAD différaient) → le conteneur servait l'ancien `flux.py` sans le filtre `_is_archived` (fix v2.20.16) → le bug de la publication épinglée résolue **réapparaissait** au tableau de bord. Diagnostic (lecture seule) : `docker inspect hostachy_api --format '{{.Created}}'` antérieur au dernier commit servi = image périmée ; confirmer avec `docker exec hostachy_api grep -c <marqueur> /app/...` vs le même `grep` sur `/opt/5hostachy/...` (disque). Remédiation (réversible, cycle standard) : `cd /opt/5hostachy && docker compose build <svc> && docker compose up -d <svc>`. Correctif pérenne (v2.20.19) : `bascule.sh` phase 0 rebuild **toujours** l'image du peer, même à git égal (cache Docker → quasi instantané si rien n'a changé). Cf. [[project_bascule_image_stale]].
⚠ **Faux positif à écarter d'abord (26/07/2026) :** une image antérieure au commit HEAD
n'est une anomalie que si ce commit **touche ce service**. Ce jour-là l'image API
précédait le HEAD de 10 min, mais le commit ne modifiait que `front/` — rien
d'anormal. Établir le périmètre avant de conclure :
```bash
git diff --name-only <dernier-commit-couvert-par-l-image>..HEAD | cut -d/ -f1 | sort -u
# api/ touché -> vérifier hostachy_api ; front/ touché -> vérifier hostachy_front
```

**Protocole si anomalie :**
1. Diagnostiquer la cause
2. Proposer un plan de correction à l'utilisateur
3. Corriger après validation
4. Relancer le pré-check complet
5. MEP uniquement si tous les points sont verts

Un point **INCONNU** (contrôle impossible à exécuter) se traite comme une anomalie :
soit on trouve un moyen de le mesurer, soit on décide explicitement de passer outre
en le disant. Jamais de vert par défaut.

**Point 14 — pourquoi (31/07/2026 ; principe : `standards/07-observabilite-et-alertes.md` §6–7) :** trois oublis d'hygiène, tous silencieux, tous
sur le **standby** que le pré-check n'inspectait pas :
- `maintenance.sh` ne tournait **que sur l'actif**, alors que rotation, `chown` et
  prune ne touchent ni l'appli ni la base. Un nœud n'étant actif qu'**un dimanche
  sur deux** (bascule alternée), le standby dérivait : 80 218 lignes dans
  `hostachy-check.log` sur rpi2. Corrigé — `hygiene_locale()` tourne sur les 2 nœuds.
- La rotation listait les logs **nominativement** : `hostachy-reliability.log`
  (1,7 Mo, ~2 100 lignes/jour) et `hostachy-role-guard.log` n'y figuraient pas et
  n'ont **jamais** été rotés. Corrigé — la boucle itère sur le glob
  `/var/log/hostachy-*.log`, donc sur tout log ajouté ensuite. **Un log hors de ce
  motif ne sera jamais roté** : le job CI `test-scripts` refuse désormais tout
  chemin `/var/log/…` qui n'y correspond pas (c'est ainsi qu'a été trouvé
  `5hostachy-backup.log` dans `scripts/installation/setup-rpi5.sh`).
- Le **cache de build BuildKit** n'était purgé par rien (`docker image prune` ne le
  touche pas) : 64 Go sur rpi1 (disque à 66 %) et 59 Go sur rpi2, à raison d'un
  rebuild du peer par nuit depuis la v2.20.19. Purgé à 10 Go
  (`docker builder prune -f --max-used-space 10G`) → rpi1 71 → 22 Go, rpi2 66 → 21 Go,
  sans toucher images, volumes ni sauvegardes. Plafonné chaque dimanche, surveillé
  par **C16** (WARN ≥ 40 Go). Ne pas descendre sous 10 Go : la bascule compte sur ce
  cache pour ne pas rejouer `npm run build` (OOM). Cf. [[project_retention_logs_maintenance]].

⚠ **Le seuil de C16 était à 20 Go, et il criait au loup 4 jours sur 7 (06/08/2026).**
Il avait été « déduit » du plafond du dimanche — 10 Go plafonnés, donc 20 = le double,
donc la purge est en panne. Le raisonnement oublie que le plafond n'est pas un régime :
il s'applique **une fois par semaine**, et le cache regrossit ensuite d'environ 3,1 Go
par nuit puisque la bascule reconstruit l'image du peer. Le régime stationnaire est
donc `plafond + 6 nuits` ≈ 29 Go, **au-dessus** du seuil censé le surveiller : WARN sur
les deux nœuds dès le mercredi, sur une infra parfaitement saine.

Deux corrections, et la seconde est la vraie :
- le seuil se **déduit désormais de la politique de rétention** (`BUILD_CACHE_FLOOR_GB`
  + 6 × `BUILD_CACHE_GROWTH_GB`), et le self-test **échoue** si on le redescend sous ce
  régime — l'erreur d'origine ne peut plus être refaite par le même raisonnement ;
- le message **n'affirme plus de cause**. Il disait « la purge hebdomadaire ne fait plus
  son travail » alors qu'elle avait réclamé 1,76 Go quatre jours plus tôt : il envoyait
  déboguer `maintenance.sh` pour rien. Un contrôle rapporte ce qu'il mesure ; désigner
  une cause qu'il n'a pas mesurée est une erreur de conception, pas de formulation.

Et surtout : **la taille du cache était un proxy, jamais le fait**. « La maintenance
a-t-elle tourné ? » ne se mesurait qu'ici, au point 14, donc seulement les jours de MEP
— alors que l'invariant est permanent (règle 2). C'est désormais **C17**, toutes les
15 minutes, sur les deux nœuds : âge de la dernière ligne `Garde-fou` de
`hostachy-maintenance.log`, WARN au-delà de 8 jours, INCONNU si le log est absent ou
illisible. Le point 14 reste utile pour les logs et le disque ; l'hygiène, elle, n'a
plus besoin d'un pré-check pour être vue.

> 📖 Généralisé au socle — c'est là que vit la règle, pas ici :
> `standards/04-fiabilite-des-controles.md` §18 (un seuil se règle sur le **régime** de
> ce qu'il surveille, pas sur l'action corrective ; et il se valide **à la veille** du
> passage suivant, pas au lendemain du précédent) et §19 (un contrôle nomme ce qu'il a
> mesuré, jamais la cause qu'il suppose). Ce qui précède n'en est que l'instanciation
> 5Hostachy : les seuils, les logs et les numéros de contrôle.

**Point 15 — pourquoi (03/08/2026) :** en basculant les pièces jointes vers
`POST /uploads/fichier`, deux endpoints (`/uploads/ticket/{id}`,
`/uploads/evenement/{id}`) se sont retrouvés **sans le moindre appelant**, et
personne ne l'a vu — ni la CI, ni le pré-check, ni `svelte-check`, qui ne signale
que le code mort *à l'intérieur* d'un fichier, jamais une route serveur devenue
inutile. Un endpoint orphelin n'est pas un simple déchet : c'est une **surface
d'attaque authentifiée que plus aucun test ne parcourt**, et il fige un contrat
(ici : alimenter `photos_urls` après création) que le reste du code ne respecte
plus — donc il diverge en silence jusqu'au jour où quelqu'un s'y fie.

Le contrôle est **automatisé**, `api/tests/test_endpoints_orphelins.py` : il lit les
décorateurs `@router.<méthode>` par analyse statique (aucun import de l'app, donc
aucune base) et cherche un consommateur dans `front/src` **et** dans les `*.sh` —
`maintenance.sh` et `check-reliability.sh` sont des clients aussi légitimes qu'une
page Svelte, c'est ce qui distingue `/admin/db/integrite` d'une route morte.

Deux détails qui font la différence entre un garde-fou et un décor :
- la liste d'exceptions `SANS_CONSOMMATEUR_FRONT` est vérifiée **dans les deux sens** —
  une entrée qui a retrouvé un appelant fait échouer le test, sinon la liste
  grossit à chaque exception et finit par tout couvrir ;
- le détecteur s'auto-contrôle (`> 200 routes`, sources consommatrices non vides) :
  un parseur cassé rendrait tout « consommé », donc vert à vide.

Ce point se déroule **sur le poste de développement, avant le push** : il ne
nécessite aucun accès aux RPi. Une route orpheline n'est pas bloquante en soi —
c'est la **décision** qui l'est : supprimer l'endpoint *et* son client TypeScript,
ou l'inscrire dans la liste d'exceptions avec sa raison en une ligne.

⚠ **Daemon Docker partagé sur rpi2** (co-hébergement de List-dons) : le prune d'images
est **filtré sur `label=com.docker.compose.project=5hostachy`** — un prune nu
supprimerait aussi les couches orphelines de l'autre application, et arbitrer sur ses
ressources n'est pas notre rôle. `docker system prune` est **interdit** (il détruirait
ses volumes et réseaux). Les deux règles sont vérifiées en CI. Seul le **cache
BuildKit** reste commun — aucun filtre par projet n'existe : il est purgé **par âge**
(> 7 j) d'abord, le plafond de 10 Go ne servant que de garde-fou.


## Rétrospective du 26/07/2026 — ce que le processus n'a pas vu

Inventaire honnête, à garder comme étalon de ce que les contrôles doivent attraper.
Colonne clé : **qui** a détecté.

| Problème | Détecté par | Pourquoi le processus l'a manqué |
|---|---|---|
| Mois en anglais sur la fiche arrivant (`%B` en locale C, 5 sites) | **L'utilisateur, à l'œil** | Aucun contrôle du rendu des documents → **P7** créé, + `tests/test_dates_fr.py` qui interdit `%B` dans `app/` |
| La fiche arrivant n'est jamais transmise au nouvel arrivant | Demande d'examen de l'utilisateur | Aucun test du parcours d'accueil de bout en bout ; **non corrigé à ce jour** |
| Clone local à 16 commits de retard (`main` à 151) | Précaution avant commit | Le pré-check ne regardait que les RPi, jamais le poste de dev → **étape 0a** + `.githooks/pre-commit` |
| Hook committé en `100644` = garde-fou inerte | Demande de relecture de l'utilisateur | Le point 7 ne couvrait que les scripts en prod, pas les modes dans git → **étape 0b** |
| `.active` incohérent → failover neutralisé, site HS ~50 min | Pré-check (manuel, 7 h après le début) | Contrôle ponctuel pour un invariant permanent, et libellé trop vague → **point 2** réécrit, + à automatiser |
| `auto-deploy` de rpi1 franchissant l'anti-split-brain 7 h 30 | Lecture de log a posteriori | Aucune détection de battement manquant → **point 8** étendu |
| Aucune alerte pendant la panne (`Email KO`) | Lecture de log | Alerting mono-canal, qui tombe avec le réseau → **point 13** |
| Faux vert : un `grep -c` à `0` sur une sortie vide (sudo muet en SSH) | Demande de vérification | **Le pré-check lui-même** était en cause → **règle 1** |
| Faux positif « image API périmée » | Vérification avant d'alarmer | Point 12 ne bornait pas le périmètre → **règle 3** + point 12 corrigé |
| Point 12 en FAIL après une MEP du seul front (04/10/2026, #1658 puis v2.102.1) | Le « borné au périmètre » ci-dessus n'avait jamais été écrit dans le code : il comparait le conteneur de l'API au dernier commit du DÉPÔT | `verdict_image_service` (`lib-images-servies.sh`) : chaque conteneur face au dernier commit de SON répertoire, auto-testé |
| Version périmée servie à un onglet resté ouvert (footer bloqué en v2.22.8 après la MEP v2.23.0) | **L'utilisateur, en lisant le footer** | Le cache d'une PWA n'était surveillé par rien, et P3 lit « la version servie » sur le serveur, pas chez le client → bandeau de mise à jour (v2.24.0) + `test_pwa_maj.py` |
| Service worker plus enregistré du tout (URL relative → 404 hors racine), cache hors ligne cassé en production | **P7**, dans un navigateur réel | P1–P6 ne regardent que des artefacts : image, version du conteneur, code présent dans le bundle — tous corrects pendant que rien ne s'exécutait → encadré P7 « tester sur une route imbriquée » + `npm run lint:sw` sur le bundle construit |

## Surveillance continue — état après le 26/07/2026

> **La détection existait déjà et fonctionnait. C'est la notification qui manquait.**
> `check-reliability.sh` porte un contrôle **C4** (« `.active` cohérent entre les 2 et
> conforme à la réalité terrain ») depuis bien avant l'incident, et il a émis
> `[FAIL] .active divergent — rpi2='rpi2' vs rpi1='rpi1'` **neuf fois** entre 06:53 et
> 09:28, pendant que le failover était neutralisé. Personne ne l'a su : le cron
> redirige toute la sortie vers `/var/log/hostachy-reliability.log`, donc `MAILTO` ne
> reçoit rien, et le script n'avait aucun canal d'alerte propre.
> **Leçon : avant d'ajouter un contrôle, vérifier qu'il n'existe pas — et qu'il a un
> destinataire.** Un contrôle sans destinataire est un contrôle absent.

Corrigé (v2.22.3) :

1. **Alerte sur échec critique** — `check-reliability.sh` envoie désormais un e-mail
   quand `FAILS > 0`, via le module partagé `lib-alert.sh` (cooldown 1 h : à `*/15`,
   un FAIL persistant produirait 96 e-mails par jour). Le mécanisme SMTP, jusqu'ici
   écrit en dur dans `health-watch.sh`, est factorisé dans ce module.
2. **Battement d'`auto-deploy` (C14)** — alerte si les lignes périodiques du standby
   disparaissent. Ne s'applique **qu'au standby** : sur l'actif, `auto-deploy`
   n'écrit rien tant qu'il n'y a pas de changement, le silence y est normal.
3. **Propagation du flag au peer** — `boot-role-guard.sh` (`become_active`) et
   `health-watch.sh` (démotion de l'ancien actif) écrivent maintenant `.active` chez
   le peer joignable, ce qui supprime la cause racine de l'incohérence.

Complété le 30/07/2026 (v2.27.2) — **trois contrôles qui mentaient**, tous corrigés :

4. **Le contrôle du battement (C14) était vert quand le battement était nul.**
   `HB=$(grep -c … || echo 0)` : `grep -c` affiche déjà `0` et sort en 1 quand rien
   ne correspond, donc le `|| echo 0` **ajoutait** une seconde valeur → `"0\n0"` →
   `[ "0\n0" -lt 6 ]` échoue en `integer expression expected`, l'expression passe à
   faux et le contrôle affiche `[ OK ]` — exactement dans le cas qu'il existe pour
   attraper (log vide, illisible ou renommé). Reproduit avant correction. C14 mesure
   désormais l'**âge du dernier battement horodaté** (≤ 20 min), ce qui supprime aussi
   la traîne des tranches horaires : le 30/07 le mail est parti à 02:06 sur les
   compteurs de 01:00-01:59, alors que tout était vert depuis 01:46.
5. **L'alerte décrivait le log, pas son exécution.** Le corps du mail reprenait
   `grep '^\[FAIL\]' /var/log/hostachy-reliability.log | tail -10`, donc l'historique
   de toutes les exécutions passées : un sujet « 1 contrôle en échec » accompagné de
   **six** lignes, dont cinq d'une panne déjà résorbée. Le corps liste maintenant les
   FAIL de l'exécution courante, horodatés.
6. **`curl … || echo 000`** produisait `HTTP 000000` dans les logs et les alertes
   (`-w '%{http_code}'` écrit déjà `000` en cas d'échec). Une seule fonction `http_code()`
   par script, une seule valeur rendue.

> **Leçon, dans le prolongement de la règle 1 (« un contrôle qui ne peut pas
> s'exécuter renvoie INCONNU, jamais OK ») : un contrôle qui compte doit être testé
> sur le cas ZÉRO.** Les trois défauts ci-dessus ont vécu des semaines en produisant
> des lignes vertes plausibles. Aucun n'était visible sans rouvrir le fichier — d'où
> le job CI `test-scripts`.

Reste ouvert :

* **Second canal d'alerte.** Le canal est unique (SMTP) et tombe avec le réseau,
  donc précisément quand on en a besoin — le 26/07, `Email KO: [Errno 101] Network
  is unreachable`. Une alerte WhatsApp via le bridge (le conteneur tourne en local,
  mais son `/status` exige un token, donc il faudrait sortir la clé de `.env`) ou un
  heartbeat sortant vers un service tiers couvriraient le cas. Décision de conception
  à prendre. La panne du 30/07 l'a confirmé une seconde fois : sept alertes perdues
  entre 01:06 et 01:44, la première n'est partie qu'à 02:06, le réseau revenu.
  *(Cette limite est structurelle : un canal qui emprunte le lien en panne ne peut
  pas signaler la panne de ce lien. Le cooldown n'est volontairement pas marqué en
  cas d'échec d'envoi, donc l'alerte est bien retentée — elle arrive en retard, pas
  jamais.)*

*Fait :* la migration de `health-watch.sh` vers `lib-alert.sh` est **terminée** (le
script source le module, avec un repli qui journalise si le fichier manque — le
failover reste opérationnel sans lui, contrainte du chemin critique).
