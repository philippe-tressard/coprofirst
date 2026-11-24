# infra-rpi — Banc des volumes, crontabs et unité systemd, standby qui s'aligne, noyau, allègement d'un nœud, cloudflared

Annexe de `SKILL.md`, chargée à la demande (#2910) : le sommaire est dans `SKILL.md`.
Les titres et numéros de section sont ceux de toujours : un renvoi se lit au sommaire.

## Éprouver l'installation d'un volume — `banc-volumes.sh`

`bascule.sh` installe les volumes sur le peer par `lib-volumes.sh`. Son
`--selftest` (job CI `test-scripts`) vérifie la **forme** de la commande — pas de
`sudo`, source en lecture seule, purge avant copie — mais ne peut rien dire de
son **effet** : il n'a ni Docker ni volume (`standards/04` §11).

`scripts/exploitation/banc-volumes.sh` comble l'écart : il crée un volume
jetable `banc_volume_dst`, y installe un contenu par la commande réellement
produite, compare, puis les détruit — même après un échec. **Sur le STANDBY
uniquement** : il refuse de démarrer si des conteneurs `hostachy` tournent.

    scp scripts/exploitation/banc-volumes.sh scripts/lib/lib-volumes.sh \
        ptressard@<standby>:/tmp/ && ssh ptressard@<standby> 'cd /tmp && bash banc-volumes.sh'

À rejouer après toute modification de `lib-volumes.sh`. Il n'était cité nulle
part jusqu'au #1050 : un banc qu'on ne retrouve pas ne se rejoue pas, et on le
réécrit de mémoire — ce qui est arrivé deux jours après le premier (28/08/2026).

## Crontabs et unité systemd — **source versionnée : `infra/points-entree/`**

Depuis le 15/08/2026, les six points d'entrée (4 crons root, 1 cron utilisateur,
et l'unité `hostachy-role-guard.service`) sont décrits dans le dépôt. Vérifier
qu'un nœud y est conforme :

    bash scripts/poste/verifier-points-entree.sh

C'est le **point 17** du pré-check. À la différence de C18 — qui compare les deux
nœuds *entre eux* et laisse donc passer la dérive commune — il compare au **dépôt**.
Rien n'est posé automatiquement : installer reste un geste explicite, un nœud à la
fois.

## Crontabs (sudo root — identiques sur les 2 RPi)

**Quand** chacun tourne se lit dans `infra/points-entree/cron-root.crontab` (root) et
`cron-ptressard.crontab` (`auto-deploy.sh`, seul cron utilisateur), jamais ici : les minutes y
sont décalées exprès (#1562). Ce que chacun fait :

- `bascule.sh` (quotidien, de nuit) : bascule active/standby, puis le nouveau standby pose sa
  révision de noyau et toutes ses autres mises à jour — Docker, cloudflared, Node.js…, sauf
  celles qui ramèneraient un paquet retiré (C35) — et redémarre (`noyau-standby.sh`, #1395,
  #2198). Une nouvelle série de noyau reste manuelle : C30 la signale avec la commande.
- `maintenance.sh` (hebdomadaire) : purges demandées à l'API (`POST
  /admin/maintenance/purges` — jamais `docker exec … python`, #1232) ; sur les deux nœuds,
  images de base re-tirées — les `FROM` des Dockerfile et les `image:` du compose, PostgreSQL
  compris (#1379, #1872) : tirer ne redémarre rien, la base prend sa nouvelle image à la
  bascule, et `auto-deploy` ne la recrée jamais (`--no-recreate`) — et rotation des logs.
- `health-watch.sh` (toutes les quelques minutes) : failover automatique si le site est HS, et
  une ligne datée à chaque sonde, site OK compris — son battement, que C31 mesure (#1586).
- `check-reliability.sh` (quart d'heure) : contrôles numérotés, alerte sur `FAIL`, digest
  quotidien sur `WARN`, chaque fait envoyé une fois par le nœud qu'il concerne (#1402) ;
  constats dans Admin › Maintenance (battement à chaque passage, #1805 ; un constat affiché une
  fois, #1396). Au premier passage après 04:00, il lance l'audit de sécurité nocturne
  (`audit-securite.sh`, S1–S6, plus bas). La moitié des contrôles vit dans `scripts/lib/` : où
  vit chacun, `grep -rn "── C[0-9]" scripts/`.

« Identique sur les 2 nœuds » est un invariant, pas un constat (faux jusqu'au 06/08/2026) : le
vérifier fait partie du point 17 du pré-check (points d'entrée). `auto-deploy.sh` (cron `ptressard`) relève du
point 11. 🔒 `npm run lint:consignes` refuse qu'une consigne en énumère une partie.

## Le standby s'aligne tout seul (#448 — 19/08/2026)

`auto-deploy.sh` (cron **utilisateur** `ptressard`, horaire dans `infra/points-entree/cron-ptressard.crontab`) tourne sur les **deux**
nœuds. Il sortait jusqu'ici avant le `git fetch` sur le standby : son code et ses
images restaient figés au jour où il a cessé d'être actif.

Le 19/08/2026, rpi2 était ainsi resté à **v2.90.0** pendant que la production
servait **v2.102.2** — 13 commits, et la migration **0154 absente de son code**,
alors que sa base est synchronisée à chaque bascule. Un failover cette nuit-là
aurait servi du code v2.90.0 sur une base migrée en 0154.

**Ce que fait le standby désormais** : `git reset --hard origin/main` puis
`obtenir_images` (`lib-images-ci.sh`, #1758) — il **tire** les images que la CI
a publiées pour ce commit (`ghcr.io/philippe-tressard/coprofirst-*:sha-<commit>`)
et ne les construit (`construire_images`, `lib-parite.sh`, qui exporte
`GIT_HASH`, #1684) qu'en **secours**, 30 min après le commit, avec une alerte. Et rien d'autre — **aucun conteneur démarré** (ce serait
le split-brain), **aucune migration appliquée** (sa base est une copie que la
bascule écrase ; migrer ici divergerait en silence).

⚠️ **La bascule de 02:00 n'a jamais aligné que le nœud ENTRANT.** La tolérance du
point 10 du pré-check disait « le standby se resynchronise à la bascule » : c'était
faux dans les deux sens — quand la bascule échoue, mais aussi quand elle réussit,
puisque le sortant repart avec le retard. C'est pour cela que le retard revenait
après chaque déploiement.

🔒 **Verrou `flock`** posé au passage (`.auto-deploy.lock`) : un build de front sur
RPi dépasse volontiers cinq minutes, donc le cron suivant tombait dans le
précédent — le remède était noté depuis l'incident du 17/07/2026 sans avoir été
posé. Le chemin « déjà en cours » écrit sa ligne datée : le CONTRAT DE BATTEMENT
lu par C14 exige qu'aucun chemin ne soit muet.

Si le build du standby échoue, une alerte part (cooldown 6 h) : c'est l'état le
plus trompeur, la parité **git** devenant verte alors que les **images** sont
restées vieilles — distinction que le point 10 ne sait pas faire.

**L'actif recrée l'API seule, puis le reste** (#1662, `servir_images` dans
`lib-servir.sh`, partagé avec `MaJ-Hostachy.sh` depuis #1999) : il attend le 200
de `http://localhost/api/health` avant de recréer le front, borné par
`API_PRETE_MAX_S`. « Le reste », c'est `SERVICES_APPLICATIFS` : la base n'est que
démarrée si elle manque, jamais recréée en pleine MEP (#1872). 🔴 **Le rôle est
RELU avant chaque démarrage** (#1997) : rétrogradé pendant le tirage des images,
le nœud écrit « ⛔ Rôle changé pendant le passage » et ne relance ni
l'application ni la base — le 15/10/2026, faute de cette relecture, un
déploiement a relancé un primaire sur l'ancien actif. Au journal, « API prête en N s »
ou « ⚠ API sans réponse 200 … le reste est recréé quand même » — la seconde ne
bloque jamais le déploiement, elle dit qu'il faut lire `docker logs hostachy_api`.

### Les images viennent de la CI (#1758, 08/10/2026)

| Ce que dit `/var/log/hostachy-deploy.log` | Ce que ça veut dire | Conduite |
|---|---|---|
| `… en attente des images de la CI` | le workflow « Images » n'a pas encore publié ce commit | rien : le passage suivant réessaie |
| `Déployé: <sha> (images tirees, …)` | servi depuis le registre | — |
| `⚠ Secours : … construites localement` + alerte | 30 min sans images | regarder le run « Images » (Actions), puis la visibilité **publique** des paquets `coprofirst-*` |
| `⚠ ÉCHEC du build` | le secours lui-même a échoué | comme avant : C27 le dit FAIL |

⚠️ **Les paquets doivent être PUBLICS** (arbitrage du 08/10/2026) : un paquet ghcr.io
privé se refuse au `docker pull` anonyme, et chaque déploiement tomberait dans le
secours. `MaJ-Hostachy.sh` (reprise en main) construit toujours localement.

## Le noyau du standby se met à jour seul (#1395 — 27/09/2026)

Le 27/09/2026, rpi1 tournait en 6.12.62 et rpi2 en 6.12.75 : `unattended-upgrades`
ne pose pas le noyau (le dépôt `archive.raspberrypi.com` n'est pas dans ses
origines), et personne ne redémarrait (#1393).

**Ce qui se passe désormais** : à la fin de chaque bascule réussie, le nœud qui
vient de devenir standby lance `scripts/exploitation/noyau-standby.sh`. Il tourne
en root, sans sudo, et :

1. s'abstient s'il n'est pas standby, si un conteneur **5Hostachy** y tourne, ou
   si l'actif ne répond pas 200 sur `/api/health` en LAN. Les conteneurs d'un
   **autre projet** (List-dons vit sur rpi2) ne l'arrêtent pas : arbitrage du
   28/09/2026 — « tu peux arrêter List-dons, mais vérifie qu'il redémarre ». Le
   premier passage réel s'était abstenu pour lui, et l'aurait fait une nuit sur deux ;
2. pose la dernière **révision** de sa série (6.18.50 → 6.18.5x), avec le
   micrologiciel : `NOYAU_PAQUETS` dans `lib-mises-a-jour.sh`, la seule liste ;
2 bis. pose **toutes les autres mises à jour** en attente (#2198) — Docker,
   containerd, cloudflared, Node.js, Raspberry Pi, qu'`unattended-upgrades` ignore.
   Une mise à jour qui **tirerait un paquet proscrit** (la pile de bureau retirée le
   03/10, liste de C35) ou qui **en retirerait un** est écartée, les autres posées,
   et l'écart part par courriel. Fichiers de configuration : les nôtres sont gardés
   (`--force-confold`). Si Docker ou containerd change, le moteur redémarre : la
   réplique repart seule (`unless-stopped`, C37), List-dons est relevé et C30
   vérifie son retour. Un cloudflared que sa mise à jour aurait allumé est arrêté.
   Décision : `lib-maj-paquets.sh` ;
3. redémarre s'il tourne sur un noyau plus ancien que l'installé — ou, noyau à
   jour, si une mise à jour l'exige (`/run/reboot-required`) —, après avoir attendu
   qu'`auto-deploy` relâche son verrou.

Les rôles alternent : chaque nœud suit en 48 h au plus, toujours comme standby, et
il est mis à l'épreuve comme actif la nuit suivante pendant que l'autre reste en
repli.

| Situation | Ce qui se passe |
|---|---|
| nouvelle **série** (6.18 → 6.x) | rien d'automatique : C30 rend WARN « Nouvelle SÉRIE », avec la commande manuelle, le standby d'abord |
| pendant le redémarrage | le standby a posé `.redemarrage-noyau` sur l'actif : check-reliability y lit un pair injoignable en **WARN** pendant 10 min |
| le pair ne revient pas | au-delà de 10 min, **FAIL** « il ne repart pas » → alerte. Le Pi n'a pas de menu de démarrage : accès physique |
| redémarré, mais toujours sur l'ancien noyau | pas de nouvelle tentative (`/var/lib/hostachy/noyau-tente`) : alerte. Supprimer ce fichier pour retenter |
| installation en échec | pas de redémarrage, alerte avec la fin de la sortie d'apt |
| une mise à jour ramènerait la pile de bureau, ou retirerait un paquet | ce paquet-là est **écarté**, les autres posés ; courriel « Mises à jour écartées » avec le verdict. Il reste en attente, et C30 le compte (seuil `APT_HORS_SECU_MAX`) |
| simulation illisible (verrou, dépôt) | rien n'est posé, courriel, retenté à la bascule suivante |
| un autre projet tournait sur le standby | relevé avant le redémarrage (`CONTENEURS_ETRANGERS`, `lib-mises-a-jour.sh`) ; C30 dit **OK** quand chacun tourne de nouveau et que son healthcheck n'est ni `unhealthy` ni `starting`, **WARN** jusqu'à 10 min, **FAIL** au-delà → alerte. Le relevé cesse de compter après 6 h |

Journal : `/var/log/hostachy-bascule.log`, lignes `[noyau]`. Banc sans effet :
`noyau-standby.sh --dry-run` (avec `REPO=` pour une copie dans `/tmp`).

## Mettre à jour puis alléger un nœud — `alleger-noeud.sh` (#1648, 04/10/2026)

Les deux nœuds étaient des Pi OS **Desktop** (navigateurs, VNC, CUPS, `rpcbind` sur le LAN) :
`scripts/exploitation/alleger-noeud.sh` retire cette pile **et elle seule** ; la liste s'écrit
une fois, dans `lib-paquets-proscrits.sh`, que **C35** relit pour dire si elle est revenue.
La pile **caméra** (`libcamera*`, `rpicam-apps*`, `libpisp*`, `libtensorflow-lite*`) y est
aussi depuis #2692 : sans caméra, elle restait « retenue » (C30) à chaque version de libcamera,
dont le paquet change de nom. ⚠️ Le script est resté mort de v2.127.0 au 11/11/2026 (`ICI` lu
avant d'être posé) : 🔒 `test_alleger_noeud.py` l'exécute désormais en simulation.
Au moindre doute un composant reste : tous les noyaux, `plymouth` (l'initramfs ne doit pas bouger),
`nodejs`, `build-essential`, `mkvtoolnix`, `bluez`. Le principe générique et son incident :
`standards/04-fiabilite-des-controles.md` §51 (une simulation lit TOUTE la transaction).

L'ordre qui a fonctionné, **sur le STANDBY seulement** (le script refuse un nœud qui sert) :
1. `Install-Recommends "0"` : `/etc/apt/apt.conf.d/99-hostachy-sans-recommends` (C35 le mesure) ;
2. **mettre le nœud à jour AVANT** (`sudo flock /opt/5hostachy/.auto-deploy.lock apt-get
   -o Dpkg::Options::=--force-confold full-upgrade`) : un « + » est un ordre d'installation, donc
   de mise à jour — le script refuse désormais tant qu'un paquet gardé le serait ;
3. `sudo bash scripts/exploitation/alleger-noeud.sh` (`SIM=1` pour simuler sans root) ;
4. **comparer l'initramfs à celui de l'autre nœud** avant tout redémarrage
   (`lsinitramfs /boot/firmware/initramfs_2712 | sort | diff`) : seuls des écarts de versions de
   bibliothèques sont bénins ;
5. poser la marque `.redemarrage-noyau` **sur l'actif** (`<epoch> <noyau>`, valable 10 min) PUIS
   `sudo reboot` — sans elle, le redémarrage se lit « pair injoignable ».

Pièges : **ne pas lancer `apt autoremove`** ensuite (il retirerait `rpd-plym-splash` et
régénérerait l'initramfs) ; `sudo` demande un mot de passe sur les deux nœuds (geste manuel) ;
le redémarrage de `dockerd` coupe **List-dons** (rpi2) quelques secondes — constater son retour ;
une simulation faite sur un nœud n'éprouve pas l'autre tant qu'ils ne sont pas à la même version.

## cloudflared : mesurer le binaire qui tourne, pas `dpkg`

Le 04/10/2026, rpi1 avait le paquet apt (2026.9.3) et rpi2 un binaire **posé à la main**
(`scripts/installation/install-cloudflared.sh` → `/usr/local/bin`, 2026.3.0), que `apt` ne met
jamais à jour : C30 le disait « absent ». Il lit maintenant la version du binaire quand `dpkg` ne
connaît pas le paquet. Les deux nœuds passent depuis par le dépôt apt de Cloudflare
(`/etc/apt/sources.list.d/cloudflared.list` et sa clé) — et `install-cloudflared.sh` aussi (#1591) :
il retire un ancien binaire de `/usr/local/bin`, et `test_paquets_systeme_par_apt.py` refuse qu'un
script pose à nouveau un composant de `PAQUETS_PARITE` hors apt.
