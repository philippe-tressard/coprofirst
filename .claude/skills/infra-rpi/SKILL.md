---
name: infra-rpi
description: "Infrastructure HA 5Hostachy sur 2 Raspberry Pi : serveurs et rôle actif, règle d'or des données (PostgreSQL : primaire, réplique, promotion, reconstruction), distinction panne de chemin public / panne de nœud, crontabs, monitoring APScheduler, bridge WhatsApp. Use when: intervenir sur un RPi, basculer, diagnostiquer un site HS, deux primaires ou une réplique en retard, reconnecter WhatsApp, analyser un incident ou une coupure de courant."
argument-hint: "Décrire l'intervention ou le symptôme (ex. « site HS depuis 20 min », « reconnecter le bridge WhatsApp », « C37 en FAIL : deux primaires »)"
---

# Infrastructure & Monitoring — 5Hostachy

Instanciation 5Hostachy de `standards/06-donnees-et-integrite.md` et
`standards/07-observabilite-et-alertes.md`. La **règle d'or des données**
(PostgreSQL) est écrite dans `CLAUDE.md` et rappelée par
`.claude/5hostachy-preflight.md` : elle ne doit jamais dépendre de ce chargement.
La conduite à tenir est ci-dessous.

> 📖 **Le générique n'est pas recopié ici** — l'ouvrir en parallèle :
> `standards/06-donnees-et-integrite.md` §1 (un état multi-fichiers tenu ouvert ne
> se copie pas à chaud — l'authentification WhatsApp), §2 (copier une base), §6 (sauvegardes : restauration testée, et **où** elles vivent)
> · `standards/04-fiabilite-des-controles.md` §10 (deux sondes indépendantes avant
> toute décision destructive : panne de nœud ≠ panne de chemin) ·
> `standards/07-observabilite-et-alertes.md` §2 (un canal qui emprunte le lien en
> panne ne peut pas signaler cette panne), §5 (échec silencieux), §6–8 (rotation,
> maintenance sur tous les nœuds, hygiène).

## Serveurs
- **RPi 1** `192.168.1.222` (PhT-RB5) · **RPi 2** `192.168.1.223` (PhT-RB5i2)
- RPi actif : `cat /opt/5hostachy/.active` — ⚠️ ce fichier peut disparaître, le recréer si absent
- Conteneurs uniquement sur le RPi actif — vérifier les 2 en cas de doute (`docker ps`)
- En cas de split-brain (conteneurs sur les 2) : stopper le standby + recréer `.active`
- `MaJ-Hostachy.sh` refuse de tourner sur le standby ; en root (`sudo bash`), il pose le verrou de bascule sur les DEUX nœuds et prend celui du déploiement (#1999)
- En cas de site HS : SSH sur le RPi actif → `cd /opt/5hostachy && . scripts/lib/lib-env-role.sh && env_role_appliquer .env actif && docker compose up -d`
  — le `env_role_appliquer` pose `ORIGIN` public et retire `COOKIE_SECURE` ; démarrer la stack sur un nœud resté en rôle standby sert le public avec une origine locale et un cookie sans drapeau `Secure` (« gap .env du 15/07/2026 », #1077). La règle vit dans `scripts/lib/lib-env-role.sh`, jamais recopiée.

## ⚠️ Règle d'or des données — PostgreSQL : primaire, réplique, promotion (DI-7b, #1781)

La base est un PostgreSQL par nœud, dans le conteneur `hostachy_postgres` : un
**primaire** sur l'actif, une **réplique** en flux sur le standby. Les interdits
— deux primaires, une base absente démarrée sur un nœud qui prend la main,
`docker compose stop` sans liste sur le standby, `docker volume rm` du volume de la
base — sont écrits dans `CLAUDE.md` ; voici la conduite à tenir.

| Question | Où, comment |
|---|---|
| La réplication va-t-elle bien ? | **C37** (`check-reliability`, `lib-replication.sh`) et le **point 22** du pré-check — deux primaires, réplique absente, déconnectée, en retard, rôles inversés |
| Le rôle de la base d'un nœud ? | `docker exec hostachy_postgres psql -U coprofirst -d coprofirst -Atc "select pg_is_in_recovery()"` — `t` réplique, `f` primaire |
| Refaire la réplique du standby | `sudo bash /opt/5hostachy/scripts/exploitation/reconstruire-replique.sh` (simulation), puis `--oui` — efface la base LOCALE et la copie du primaire (`pg_basebackup -R`) ; refuse sur l'actif, sans primaire joignable |
| Changer d'actif | la bascule promeut la réplique du pair (phases 3-4), le failover et `boot-role-guard` aussi ; l'ancien primaire est reconstruit en réplique — tout passe par `lib-promotion.sh` |
| Le failover (#1997, #2000) | `lib-failover.sh` : s'abstient tant que l'actif **se redéploie** (son verrou d'auto-deploy, borné à 15 min) ; DÉCIDE de la base locale avant tout geste (illisible ou absente : l'ancien actif n'est pas touché) ; ISOLE l'ancien actif en un appel, sous son verrou de déploiement (attente 5 min), `.active` réécrit avant l'arrêt de l'application, de la base et du tunnel ; renonce si l'actif sert en LAN sans pouvoir être isolé (deux primaires sinon) ; PUIS promeut. Le courriel nomme `reconstruire-replique.sh` sur l'ancien actif |
| L'ancien actif après un failover | sa base est ARRÊTÉE : `boot-role-guard` la reconstruit à son redémarrage (`decider_base_au_retrait`, primaire OU absente) ; sans redémarrage, C37 dit FAIL et le geste est `sudo bash /opt/5hostachy/scripts/exploitation/reconstruire-replique.sh --oui` sur lui |
| La santé des tâches après un failover (#2072) | un nombre impair de changements de rôle laisse un nœud hors du rôle actif deux nuits de suite : sur la bascule, la sauvegarde et la télémétrie, sa sous-ligne dit **« Pas actif à l'heure »** (gris) — attendu, rien à faire. Rouge seulement si la tâche elle-même ne tourne plus, ou si le nœud se tait plus de trois nuits (`_TACHES_DE_L_ACTIF`, `sante_taches.py`) |
| Deux primaires (C37 FAIL) | isoler celui qui ne sert PAS (`docker compose stop postgres` sur le standby), puis `reconstruire-replique.sh --oui` sur lui ; ses écritures depuis la promotion sont perdues — c'est le prix, et C37 le dit |
| L'intégrité | sommes de contrôle de pages (`--data-checksums` à l'initialisation) ; `GET /admin/db/integrite` lit `pg_stat_database.checksum_failures` |
| La sauvegarde | `backup.py` met l'**export vérifié** (`base-export.tar.gz`, P2-7) dans l'archive, réimporté dans une base jetable avant d'être déclaré réussi ; l'export hors site relit chaque table sur le poste |
| La maintenance | pas d'arrêt de l'API : l'autovacuum compacte en ligne |
| L'image `postgres:<version>` | re-tirée le dimanche sur les **deux** nœuds avec les images de base (`lib-images-base.sh`, #1872) — **sans** redémarrer le primaire ni la réplique. Le conteneur la prend à sa prochaine recréation : la bascule de 02:00 (`demarrer_conteneurs` sur le nouvel actif, la réplique reconstruite sur l'autre). `auto-deploy` ne recrée que l'application, la base n'y est que démarrée si elle manque (`up -d --no-recreate`). L'ancienne image, qu'un conteneur tient encore, se retire au passage suivant (`/var/lib/hostachy/images-base-a-retirer`). Une **mineure** arrive par Dependabot (`docker-compose`) ; une **majeure** jamais — c'est un `pg_upgrade`, un lot à elle |
| Les DEUX nœuds perdus (#1921) | le premier renaît actif de la copie hors site : `sudo bash /opt/5hostachy/scripts/exploitation/restaurer-copie-hors-site.sh <archive>` (simulation), puis `--oui` — base **neuve** en primaire, import vérifié, fichiers inventoriés. Avant les crons ; refuse si le pair sert. Chez la référence, `--registre <plateforme_backup_*>` est exigé (#1972). L'épreuve se rejoue sans risque par `--banc <archive> [--registre <archive>]` sur le standby. Procédure entière : `docs/restauration-complete.md`, « Les deux nœuds perdus » |

🔑 Ces outils se lancent **en root** (`sudo bash …`, depuis une session SSH
`ptressard`) : ils joignent le pair par la clé inter-nœuds, que seul root lit, et
`ssh_noeud_exiger_root` refuse sinon, en le disant. Lancé en ptressard le
09/10/2026, `reconstruire-replique.sh` lisait la base du pair « illisible » et
refusait sans dire pourquoi (#1781). Une session Claude n'a pas ce sudo : la
commande se donne à l'utilisateur.

⚠️ La réplication passe par le LAN : port lié à `PG_ECOUTE` (l'IP du nœud, jamais
`0.0.0.0`), `infra/postgresql/pg_hba.conf` (scram partout, rôle `replication` depuis
l'autre nœud seulement), `PG_REPLICATION_PASSWORD` identique sur les deux `.env`.

## ⚠️ Panne de CHEMIN public ≠ panne de NŒUD (incident du 30/07/2026)

Entre 00:52 et 01:46, une panne DNS/WAN a coupé le tunnel des **deux** nœuds
(`lookup _v2-origintunneld._tcp.argotunnel.com on 1.0.0.1:53: server misbehaving`,
`Email KO: [Errno 101] Network is unreachable`). Aucun RPi n'avait redémarré ni gelé.

`health-watch.sh` ne sondait que l'**URL publique**. Chaque nœud a donc conclu que
l'autre était mort : **12 failovers croisés en 55 min**, stack arrêtée et redémarrée
alternativement sur les deux, rôle actif déplacé 12 fois, et à trois reprises `systemctl start cloudflared` a échoué sur le nouvel actif *avant*
que l'ancien soit démoté → **cloudflared inactif sur aucun nœud**. Aucune de ces
bascules n'a rétabli quoi que ce soit : le nœud actif servait parfaitement en LAN.

**Correctif (v2.27.2)** — avant de basculer, le standby doit établir que la panne
vient bien du nœud actif, via deux sondes indépendantes de l'URL publique :

| API de l'actif en LAN | Edge Cloudflare depuis le standby | Décision |
|---|---|---|
| KO | — | **Failover** (nœud réellement mort — chemin critique inchangé) |
| OK | KO | **Abstention** + alerte : panne de chemin, basculer ne rétablirait rien |
| OK | OK, et l'URL publique a RÉPONDU (503, 530…) | **Failover** : l'edge n'atteint plus l'origine (25/09/2026) |
| OK | OK, aucune réponse (`000`) | selon le **tunnel de l'actif**, mesuré chez lui (#2073) : cassé → **failover** · sain → **abstention**, sans alerte · illisible → **abstention** + alerte |

La sonde LAN est `http://<actif>/api/health` (via Caddy — le port 8000 n'est **pas**
publié). La sonde d'edge (`cdn-cgi/trace`) exerce DNS + TLS, c'est-à-dire exactement la chaîne
dont le tunnel dépend : « pourrais-je seulement servir ? ». Logique isolée en
fonction pure `decide_failover()` + `./health-watch.sh --selftest`, vérifiée en CI.

### Un `000` n'est pas un tunnel cassé (17/10/2026, #2073)

Le 17/10 à 15:42, deux `000` à 30 s d'écart, l'actif vivant en LAN et l'edge
joignable : la dernière ligne de la table disait alors « tunnel cassé », et rpi2 a
promu sa base. Même motif le 15/10 à 20:02, dans l'autre sens. Le tunnel de rpi1
tenait ses quatre connexions, et les `000` ont continué toute la soirée avec rpi2
actif.

- **Un tunnel coupé ne rend pas `000`** : l'edge répond, par une erreur (503 le
  25/09). `000`, c'est que le sondeur n'a rien reçu en 10 s.
- **La requête n'atteint pas l'origine** : chaque créneau de health-watch compte
  deux `/api/health` dans le journal d'accès de Caddy (un par nœud, même minute) ;
  à chaque `000`, seul celui de l'autre nœud est arrivé, servi en 7 ms.
- Le tunnel se lit donc **chez l'actif**, par le SSH des nœuds, sans sudo :
  `systemctl is-active cloudflared` et `curl -s http://127.0.0.1:20241/ready`
  (`readyConnections`, le serveur de métriques de cloudflared) —
  `etat_tunnel_sh`/`etat_tunnel` dans `lib-failover.sh`. « Sain » exige la preuve :
  unité active ET au moins une connexion.
- Pas d'alerte sur l'abstention « tunnel sain » : ces `000` durent une minute. Une
  panne publique qui **dure** est l'affaire de **C1**, qui alerte avec ses deux sondes.
- La seconde sonde est journalisée avec **où** la requête s'est perdue
  (`http_detail`, `lib-sonde.sh`) : `dns=… connexion=… tls=…` et le message de curl.

**La cause des `000`** (relevé du 18/10/2026) :

| Hypothèse | Verdict | Sur quoi |
|---|---|---|
| tunnel de l'actif | **écartée** | quatre connexions, aucune erreur de cloudflared jusqu'à l'isolement ; les `000` continuent après le changement d'actif |
| origine lente | **écartée** | la requête n'arrive pas au Caddy ; celle de l'autre nœud, à la même seconde, est servie en 7 ms |
| délai de sonde trop court | **écartée** | rien n'arrive en 10 s ; allonger ne changerait que l'heure du `000` |
| chemin du domicile aux heures chargées | **établie** | 14 h–23 h seulement (pic à 17 h), sur les deux nœuds, parfois à la même minute ; de 1–3 par jour à 5–9 depuis le 15/10 |
| la résolution DNS, dans ce chemin | **établie** (20/10) | du 18 au 20/10, 33 `Site HS` de health-watch sur les deux nœuds disent `Resolving timed out`, un seul `Connection timed out` ; cloudflared journalise `lookup region1.v2.argotunnel.com: i/o timeout` aux mêmes heures |

🔎 Tranché le 20/10/2026 par la ligne `Sonde : dns=… connexion=… <erreur curl>`
que health-watch écrit sous chaque `⚠ Site HS` (`grep -A1 "Site HS"
/var/log/hostachy-health-watch.log`) : c'est la **résolution**, pas le lien. Le même
hoquet a rendu C25 (scripts tiers) « non mesurable » le 20/10 à 15:51 : sa sonde se
reprend désormais une fois (`page_html`, `lib-sonde.sh`) et le WARN nomme l'erreur de curl.
Il a fait écrire à C1 « Site public KO » le 20/10 à 22:36 : C1 rejoue désormais sa
sonde par un autre résolveur (« Le résolveur du nœud n'est pas le site », ci-dessous, #2093).

⚠️ Les résolveurs viennent de la **box** (DHCP, `/etc/resolv.conf` réécrit le
08/10/2026) : la glibc n'en lit que les **trois premiers**. Relevé du 21/10 sur les
deux nœuds : `9.9.9.9`, `1.1.1.2`, `192.168.1.254` (la box), puis deux ignorés —
le `194.242.2.4` qui répondait `REFUSED` n'y est plus. Chaque serveur a 5 s par
défaut : deux qui se taisent suffisent à épuiser les 10 s de la sonde. Corriger
cette liste est un réglage de la box, pas du dépôt.

**Réflexe de diagnostic** au prochain « site public KO » : avant de suspecter un
nœud, `curl http://<actif>/api/health` depuis l'autre RPi. S'il répond 200, le
problème est sur le chemin (box, DNS, Cloudflare) — ne pas basculer, ne pas
redémarrer la stack.

### Un failover dont le tunnel ne démarre pas s'abandonne (25/09/2026, #1318)

Rotation du jeton du tunnel : l'**identifiant** du tunnel (`91d1afa9-…`) a été collé à
la place du **jeton** (`eyJ…`) sur les deux nœuds. Chacun a basculé à son tour
(19:27, 19:32) : `⚠ Échec démarrage cloudflared` était journalisé **puis ignoré**, les
conteneurs démarraient, l'actif était démoté. Pendant cinq minutes, rpi1 a servi l'API
sur la base de la veille, et son planificateur a **renvoyé le message WhatsApp du
mois** — un seul est arrivé dans le groupe, par chance (l'envoi de rpi2 était
« incertain »).

Depuis, `health-watch.sh` démarre le tunnel **avant** les conteneurs et
s'abstient s'il n'est pas `active` (`decide_suite_tunnel`, `--selftest`). Un tunnel
qui ne démarre pas sur le standby a souvent une cause **commune** — jeton, config,
compte : basculer ne peut rien réparer.

**Changer le jeton** : `sudo bash /opt/5hostachy/scripts/exploitation/changer-jeton-tunnel.sh`,
l'**actif** d'abord (le jeton est éprouvé par un connecteur temporaire avant de
toucher à celui qui sert), puis le secours (tunnel laissé arrêté). Jamais
`cloudflared service install` sur le standby : il démarre et active l'unité.

🔴 **Le jeton vit dans un FICHIER, jamais dans l'unité** (#2115, 22/10/2026).
`ExecStart` ne porte que `--token-file /etc/cloudflared/jeton` (root 600 ; le
chemin s'écrit une fois, `JETON_FICHIER` de `lib-jeton-tunnel.sh`). Avant cette date
les deux nœuds avaient `--token <valeur>` en clair — lisible par tout compte local
(`ps`, `systemctl cat`) —, parce que `cloudflared service install <jeton>` et le
`sed` de la rotation l'y écrivaient. Un nœud encore à l'ancienne forme se
migre SANS changer le jeton : `sudo bash …/changer-jeton-tunnel.sh --migrer`, le
**standby d'abord** (rien ne redémarre), puis l'actif (le tunnel redémarre, retour
arrière si le site public ne répond pas 200). La rotation vient ensuite
(tableau de bord Cloudflare, puis le script sans argument). Les sauvegardes de
`/root` qui portent un secret sont détruites par le script (`shred -u`).
**C39** (`lib-jeton-tunnel-clair.sh`) échoue (FAIL) si `systemctl cat cloudflared`
contient un jeton en clair sur l'un des nœuds — la collecte ne remonte qu'un
verdict, jamais un extrait de l'unité. ⚠️ Ne jamais afficher `systemctl cat
cloudflared` tel quel dans une réponse, un ticket ou un journal : masquer d'abord
(`sed -E 's/(--token[= ]+)[^ ]+/<MASQUÉ>/'`).

## Risques connus
- **Build OOM** : `npm run build` peut saturer la RAM du RPi → préférer `--nocache` en cas de build lourd
- **health-watch failover** → peut créer un split-brain ; toujours vérifier `docker ps` sur les 2 RPi
- **Sauvegardes** : le volume `backups` n'est **pas** répliqué par `bascule.sh` (qui ne
  synchronise que `uploads`, `whatsapp_auth` et `app_data`). Le rôle alternant chaque
  nuit, chaque nœud n'accumule qu'un jour sur deux, et `_rotate_backups()` ne voit que
  ses fichiers locaux → 7 versions ≈ 14 jours **à trous**, aucun nœud n'ayant celle de
  la veille. Copie hors site : `scripts/poste/export-hors-site.cmd` (voir ci-dessous)
- **Le nom d'une archive dit l'heure de PARIS** (#1611, 05/10/2026) :
  `hostachy_backup_AAAAMMJJ_HHMMSS_paris.tar.gz`. Avant, l'horloge UTC y était écrite
  sans le dire (`…_020000` pour une sauvegarde prise à 04:00) ; les anciennes archives
  (sans suffixe) restent en UTC jusqu'à leur rotation. `backup.nom_archive` écrit,
  `backup.horodatage_archive` relit les deux formats en UTC naïf — c'est le seul parseur.
  « Restaurer celle de 02:00 » se lit donc au suffixe : sans `_paris`, ajouter deux
  heures (une l'hiver) pour l'heure de Paris.
- **`.active` peut disparaître** → le recréer manuellement sur les 2 RPi si absent
- **Clé d'hôte du pair non épinglée** (#1598, 02/10/2026) : le SSH inter-nœuds
  (`scripts/lib/lib-ssh-noeuds.sh`, seule source) exige `StrictHostKeyChecking=yes`
  contre `/root/.ssh/known_hosts_bascule`. Fichier absent, vide, ou nœud réinstallé
  (nouvelle clé d'hôte) → bascule arrêtée en phase 0, `check-reliability` en FAIL
  « Peer injoignable », et le message porte la commande d'épinglage. Ce n'est **pas**
  un nœud figé : épingler (procédure `docs/restauration-complete.md`, étape 7),
  jamais repasser à `no` — `scripts-ci-ssh-noeuds.sh` le refuse en CI

## Copie hors site des sauvegardes (v2.37.0 — 04/08/2026)

Avant cette date, **100 % des archives vivaient sur les deux RPi**, au même domicile,
sur la même box et la même alimentation. Les deux nœuds protègent de la panne d'**un**
nœud — jamais d'un `docker volume rm`, d'un rançongiciel ou d'un sinistre, qui
emportent base + uploads + toutes les sauvegardes d'un coup
(`standards/06-donnees-et-integrite.md` §6).

- **Lancement : MANUEL depuis le poste** — double-clic sur `scripts/poste/export-hors-site.cmd`, ou
  `bash /c/Dev/5hostachy/scripts/poste/export-hors-site.sh`. Destination par défaut : `C:\Backup`
  (`EXPORT_DEST`), **2 versions** (`EXPORT_KEEP`) — réduit de 14 à 2 le 12/09/2026 : on ne
  restaure que la dernière ou l'avant-dernière, et quatorze archives de ~100 Mo pesaient
  1,4 Go. La rotation efface donc les plus anciennes **à chaque export** ; le rattrapage
  sur l'autre nœud et le relevé des jours manquants suivent la même valeur. La valeur
  fait foi dans le script (commentaire de `EXPORT_KEEP`), pas ici.
- Le script choisit sa source par **comportement** (qui répond sur `/api/health` en
  LAN), pas en lisant `.active` — et **s'abstient** en cas de split-brain : deux nœuds
  qui servent = deux bases divergentes, en copier une au hasard puis faire tourner la
  rotation détruirait la bonne.
- Il ne lit que des `.tar.gz` clos, jamais la base d'un RPi ; la vérification porte
  sur la copie extraite **sur le poste**.
- Vérifications avant de déclarer la copie bonne : empreinte SHA-256 identique à la
  source, puis l'**export vérifié** de l'archive (chaque table compte les lignes de
  son manifeste, `relire_export`). Une copie non
  validée est renommée `.invalide` — elle ne doit pas se présenter comme une
  sauvegarde disponible. **Intégrité non vérifiable = échec, pas succès.**
- Chez la référence, il copie aussi la dernière archive du **registre des installations**
  (`plateforme/`, sous `EXPORT_DEST/plateforme`, #1896). Son verdict ne touche pas celui
  de la copropriété : il part dans `archive_plateforme`/`integrite_plateforme`, que juge le
  contrôle de la **plateforme** (`registre/sauvegarde.probleme_copie_hors_site`, tâche
  `sante_plateforme`), à destination de l'opérateur.
- Il poste son rapport sur le canal cron existant (`POST /admin/maintenance/rapport`,
  `tache=export_hors_site`) → visible dans **Admin → Maintenance**, et le contrôle de
  06:00 alerte au-delà de **7 jours** (seuil hebdomadaire assumé : le poste n'est pas
  allumé en permanence, et une alerte quotidienne ignorée est un contrôle mort).
- Le contrôle distingue **deux** questions : « l'export a-t-il tourné ? » et « la copie
  est-elle fraîche ? ». Un export fidèle qui recopie chaque jour la même archive
  périmée est un faux vert — verrouillé par `api/tests/test_sauvegarde_hors_site.py`.

⚠️ **Portée** : le poste est au même domicile que les RPi. Cette copie couvre la perte
d'un nœud, le `docker volume rm` et le rançongiciel visant les RPi — **pas l'incendie
ni le vol**. Une destination réellement distante (S3 UE chiffré, disque tournant) reste
à ajouter ; `EXPORT_DEST` et la boucle de vérification sont écrits pour l'accueillir.

## Qui reçoit les verdicts de `check-reliability.sh` (#449 — 19/08/2026)

**Deux canaux, deux rythmes**, et la fréquence se règle par le **cooldown**, jamais
en coupant le canal :

| Verdict | Canal | Cooldown |
|---|---|---|
| au moins un **FAIL** | alerte e-mail « ❌ contrôle(s) en échec » | 1 h |
| aucun FAIL, au moins un **WARN** | digest e-mail « ⚠️ point(s) de vigilance » | 24 h |
| tout vert | rien | — |

La décision est **pure** (`verdict_notification`, `lib-verdicts.sh`, couverte par
`--selftest`) ; l’envoi vit dans `lib-notification.sh`.

**Troisième destinataire depuis le 27/09/2026 : l'écran.** Chaque nœud rend compte
de ses constats à **Admin › Maintenance** (tâche `reliability`, carte « Contrôles de
fiabilité ») — seulement quand l'ensemble des constats **change**, et au moins une
fois par 23 h : ce battement est ce qui fait dire « Exécution manquante » d'un
contrôleur mort. WARN seuls → statut `avertissement`, lu **« Points de vigilance »**.
Décision pure `decision_rapport_ecran` (`lib-notification.sh --selftest`) ; le
plafond est exigé par `test_taches_planifiees.py`. Et le contrôle de 06:00 reprend
les tâches manquantes ou en échec, sauf ce qu'un autre canal signale déjà
(`DEJA_SIGNALE`, `sante_taches.py`).

**Deux heures, et chaque constat une fois** (#1396, 27/09/2026). L'écran affichait
l'heure du dernier **changement**, et « rapport de 17:06 » lu à 17:29 a fait croire
le contrôleur mort. Le passage qui n'a rien de neuf envoie désormais un
**battement** (`POST /admin/maintenance/battement`) : il avance `terminee_le`
(« dernier contrôle ») de la ligne existante, sans en créer — `cree_le` reste
« constats depuis ». Il porte aussi les constats et l'erreur **du passage**, qui
remplacent ceux de la ligne (#1805) : la signature ignore les chiffres, et l'écran
a affiché « 1 erreur sur 965 requêtes » quand le contrôle en comptait 3 sur 1904.
Et chaque nœud contrôlant les deux, tout s'affichait deux fois :
`portee_constat` range chaque ligne — celle qui ne nomme que ce nœud sous lui, celle
qui ne nomme que le pair est laissée au pair, les communes sont dites par l'**actif**
seul (`porte_communs`). Pair muet → ce nœud porte tout.

**Le courriel suit la même répartition** (#1402, 27/09/2026). Il gardait tout, et
un fait vu par les deux nœuds partait deux fois — rpi1 et rpi2 ont envoyé la même
alerte à 16:36:06. `repartir_constats` calcule une fois ce que CE nœud dit, et
l'écran comme le courriel le lisent : un fait, un envoi, par le nœud qu'il concerne
(ou l'actif, s'il concerne les deux). Ce qui garde la promesse « un nœud mort a
toujours quelqu'un pour parler de lui », c'est le **pair muet** : le survivant
porte alors tout. Un nœud vivant dont le contrôleur s'est tu se voit par
« Exécution manquante », par nœud, et au courriel de 06:00. Deux courriels peuvent
encore partir le même jour — les constats propres de chaque nœud —, mais plus
jamais pour le même fait. `lib-notification.sh --selftest` éprouve la réunion des
deux nœuds, et la faute injectée (le pair repris alors qu'il répond) y est vue.

🔴 **Un constat propre à un nœud reste sous ce nœud** (arbitrage de Philippe, #1401).
La règle ne tient que si le message **nomme** son nœud : un constat qui n'en nomme
aucun est lu comme commun et n'est dit que par l'actif — écrit « Disque à 81 % »
au lieu de « Disque $n à 81 % », il disparaîtrait de la carte du standby.
🔒 `api/tests/test_constats_nomment_leur_noeud.py` exige `$n` dans chaque `warn`/`fail`
des boucles qui parcourent les deux nœuds.

🔴 **Pourquoi le digest existe.** L’alerte ne partait que sur `FAILS > 0`. Or **cinq**
contrôles rendent WARN par choix assumé — C16 (cache de build), C17 (maintenance en
retard), C19 (journal ⇆ base), C20 (sudo), C22 (points d’entrée), et depuis le
01/09/2026 **C1** dans ses deux cas non concluants et **C24** (surface sudo ⇆ dépôt)
— au motif qu’un FAIL
à un passage par quart d'heure enverrait un mail par heure. Le raisonnement était juste sur la **fréquence**
et faux sur la **conclusion** : on en a déduit « pas de mail » là où il fallait « pas
ce mail-là ». Ces cinq contrôles n’avaient donc **aucun destinataire**.

Ce que ça a coûté : le **16/08/2026 à 03:02**, le rapport de la maintenance a été
refusé (HTTP 422). **C19 l’a vu** et a rendu WARN. Personne n’a été prévenu ; le défaut
a été trouvé le **18** à l’œil, sur l’écran d’administration, **par l’utilisateur**.
L’écran affichait « À jour » sur un rapport vieux de cinq jours.

⚠️ **Un WARN sans destinataire est un contrôle mort** — `standards/04` §7. Poser un
nouveau contrôle en WARN est légitime ; le laisser sans canal ne l’est pas.

### C24 — la surface sudo INSTALLÉE doit être celle du dépôt (01/09/2026)

Le 31/08, `NOPASSWD: /usr/bin/rsync` — un rsync privilégié **sans borne de
chemin**, donc une escalade root complète — a été retiré du dépôt (#582), avec un
commentaire disant *« c’est la fin du chantier »*. Il est resté installé sur les
**deux** machines : `scripts/installation/durcir-sudoers.sh` n’avait jamais été rejoué. Vingt-quatre
heures, et vingt-trois contrôles au vert à chaque quart d’heure.

⚠️ **Ni C20 ni C21 ne pouvaient le voir.** C20 compare les deux nœuds **entre
eux** — deux nœuds identiquement périmés lui paraissent parfaits. C21 regarde si
la cible d’une permission est réinscriptible par son appelant : `/usr/bin/rsync`
ne l’est pas. C’est le même trou que **C22** comble pour les points d’entrée, un
objet plus loin : *comparer au dépôt, et pas seulement au voisin.*

C24 compare la surface `NOPASSWD` réellement accordée à celle que
`sudoers_regle()` compose, et nomme les écarts dans les deux sens :

| Écart | Verdict | Ce que ça veut dire |
|---|---|---|
| permission **en trop** | WARN | le dépôt ne l’accorde plus, la machine si — rejouer `durcir-sudoers.sh` |
| permission **manquante** | WARN | un geste de la bascule échouera au prochain passage |
| surface non mesurée | WARN | INCONNU, jamais un vert |

📎 **`durcir-sudoers.sh --appliquer` ne peut PAS tourner depuis une session non
interactive** : il valide par `sudo -n visudo -cf`, et `visudo` n’est pas dans la
surface NOPASSWD — il échoue en « a password is required », proprement, sans rien
modifier. La voie employée le 01/09 est celle du reste du projet : un conteneur
jetable montant `/etc/sudoers.d`, une écriture sous un nom **commençant par un
point** (que sudo ignore), puis un `mv` atomique. Le contenu installé est vérifié
avant le `mv` : rsync absent, `systemctl start cloudflared` présent — sans quoi la
bascule casserait.

### C25 — un script TIERS est-il servi dans la page publique ? (02/09/2026)

Le relevé CSP a trouvé `static.cloudflareinsights.com/beacon.min.js` chargé sur
chaque page. **Aucun `<script>` du dépôt ne le référence** : Cloudflare l'injecte
à l'arête, APRÈS notre origine.

C'est ce qui rend ce contrôle particulier : ni une relecture du code, ni
`curl http://localhost/` ne pouvaient le voir. Il mesure donc l'**URL publique**,
avec un `Accept: text/html` et un UA de navigateur — Cloudflare n'injecte que dans
du HTML rendu à un navigateur.

⚠️ **Sur l'ACTIF seulement.** Depuis le standby, la même URL publique répond (elle
sort par le WAN et revient sur l'actif) : le contrôle passerait deux fois sur le
même fait (`standards/04` §33).

⚠️ Le motif porte sur des **hôtes nommés**, pas sur « toute URL absolue » : le
site en sert légitimement (polices Google, déclarées dans la CSP). Un contrôle qui
crie sur du légitime finit désarmé.

Décision de l'utilisateur (02/09/2026) : **couper** Web Analytics côté Cloudflare.
Ce contrôle est ce qui rend la décision durable — sans lui, réactiver l'option
d'un clic remettrait un tiers sur le chemin de chaque résident.

### C23 bis — la CSP bloquante porte-t-elle ses directives ? (01/09/2026)

C23 vérifie que l'en-tête `Content-Security-Policy` est **présent**. Il l'était
déjà quand la politique ne portait que quatre directives inoffensives, et il le
resterait si l'une d'elles disparaissait du `Caddyfile` : *présent* ne dit rien de
ce qu'il **contient**.

`connect-src 'self'` est passée en mode bloquant le 01/09/2026 (#536), sur la foi
du relevé (`Admin → CSP`, retiré le 01/10/2026) : aucune violation la concernant sur 104 rapports. C'est
la directive qui empêche l'**exfiltration** — même si un XSS s'exécutait, il ne
pourrait rien envoyer vers un domaine tiers. La perdre en silence retirerait la
moitié utile de la politique.

⚠️ **Présence, jamais valeur.** Une attente de valeur exacte a déjà tué un contrôle
d'en-têtes ici : `check-stack.sh` exigeait `X-Frame-Options: SAMEORIGIN` là où le
Caddyfile dit `DENY`, il échouait 144 fois par jour, on l'a retiré du cron — et
plus rien n'a regardé les en-têtes pendant quinze jours.

📎 **Deux défauts commis en l'écrivant, et corrigés dans l'heure.** Ils valent
d'être lus, parce qu'ils sont tous deux de la famille « le contrôle ne mesure
rien » :

1. **il s'exécutait AVANT sa mesure.** `ENTETES_RECUS` est calculé par C23 ; C23
   bis était placé au-dessus, donc il lisait une variable vide et rendait INCONNU
   à chaque passage. Un INCONNU se lit « pas cette fois », jamais « mort depuis
   toujours » (`standards/04` §23) ;
2. **il ignorait le RÔLE.** Le standby ne sert rien : il y rendait WARN tous les
   quarts d'heure, sur la moitié du parc, et le digest quotidien l'emportait.
   C'est exactement le défaut que le commentaire de C23, juste à côté, décrit et
   corrige depuis le 20/08/2026 — *écrire un contrôle voisin sans relire ce que
   son voisin a appris, c'est refaire son défaut*.

Les deux sont couverts par `--selftest`, y compris le cas « standby avec une
réponse parasite » : ce n'est pas le site, donc rien à constater.

### C27 — auto-deploy a-t-il RÉUSSI son build ? (21/09/2026, #1103)

La bascule nocturne a mis rpi1 en standby, et son `auto-deploy` n'a pas pu lire
`/opt/5hostachy/.env` : **root:root** là-bas, **ptressard:ptressard** sur rpi2.
Le code s'est aligné, **les images non**.

> 🔴 **La parité git n'est pas la parité d'image.** Le point **10** du pré-check
> (« parité de code actif ⇆ standby ») restait **vert** — il dit vrai, et il
> rassure à tort. Seul le point **18** l'a attrapé, et seulement en MEP.

L'alerte qui devait le dire est morte de la **même cause** : `lib-alert.sh`
cherche sa configuration SMTP dans ce `.env` illisible. Un canal d'alerte muet
précisément quand il a quelque chose à dire — la famille de
`canal_alerte_verifiable`.

| Ce que C27 rend | Conduite |
|---|---|
| **OK** | le dernier passage a construit, ou n'avait rien à construire |
| **FAIL** | le code est à jour, **pas les images** — comparer `ls -l /opt/5hostachy/.env` sur les deux nœuds |
| **INCONNU** | aucune ligne horodatée lisible ; son silence ne prouve rien |

⚠️ Il regarde le **comportement** (le build a-t-il abouti), pas la cause connue
(les droits du `.env`) : un contrôle sur les droits serait vert le jour où le
build échouera pour une autre raison — disque plein, registre injoignable,
Dockerfile cassé. C13 fait l'inverse pour le **log**, et c'est cohérent : là-bas
la cause est unique et connue (la rotation re-chown).

🔴 **C'est la troisième divergence rpi1/rpi2** du dépôt, après les sudoers
(09/08) et un cron en trop sur rpi2 (06/08). Le point 8 compare les crons, le 17
les points d'entrée — **aucun ne compare les droits des fichiers dont les
scripts dépendent**, et c'est par là que l'écart est passé.

⚠️ Le correctif demande `sudo`, refusé en `-n` sur les **deux** nœuds depuis le
durcissement : il n'est pas automatisable depuis une session.

```bash
sudo chown ptressard:ptressard /opt/5hostachy/.env && sudo chmod 600 /opt/5hostachy/.env
```

C'est un **durcissement** : le fichier passe de `660 root:root` (lisible par le
groupe root) à `600 ptressard` — root continue de le lire, personne d'autre.

### C26 — le verrou a-t-il été posé AVANT la première action ? (12/09/2026, #915)

#915 se terminait sur une phrase gênante : *« le verrou est la coordination ;
elle tient tant que la bascule le pose avant sa première action — ce que les
tests vérifient **par la forme du script, pas par son exécution** »*.

🔴 Et la forme était fausse : `bascule.sh` arrêtait les conteneurs du peer
**puis** posait le verrou dix lignes plus bas. Corrigé le 12/09.

C26 lit le journal de la **dernière bascule réellement exécutée** et vérifie
l'ordre sur les faits — c'est la différence entre *« le script est écrit ainsi »*
et *« il s'est comporté ainsi »* : un chemin conditionnel ou une modification
future peuvent séparer les deux.

| Ce que C26 rend | Conduite |
|---|---|
| `verrou posé AVANT la première action` | — |
| **`posé APRÈS une action`** (FAIL) | une modification a déplacé `verrou_poser` : le remettre avant le bloc « Peer sans conteneurs actifs », et relire `test_verrou_bascule.py` qui aurait dû le refuser |
| `INCONNU` | journal absent, tronqué par la rotation, ou bascule sans pose relevée |

⚠️ Deux formulations coexistent dans l'historique — « posé sur le peer » (avant
#916) et « posé sur les DEUX nœuds » (après). Le contrôle accepte les deux :
n'en reconnaître qu'une le rendrait INCONNU sur tout l'historique, et on
prendrait l'habitude de l'ignorer.

### C12 — une bascule a-t-elle été TUÉE ? L'ACTE, pas l'objet (12/09/2026, #915)

Ce contrôle lisait l'**âge du verrou** `.bascule-lock`. Il ne pouvait donc
**jamais** alerter : `health-watch` **efface** le verrou orphelin au-delà de
`VERROU_STALE_S` (15 min), et C12 ne passe que toutes les 15 min — son propre
seuil étant en plus de 20 min, le fichier avait toujours disparu **cinq minutes
avant** de devenir signalable. Fenêtre d'alerte vide, et un OK rendu sans avoir
rien pu regarder : le **cas zéro** de `standards/04` §2.

🔴 Il observe désormais la **trace datée du nettoyage** dans
`/var/log/hostachy-health-watch.log`, qui subsiste — et non le fichier, qui
disparaît. Même retournement que le point 13 du pré-check, qui se vérifie par
« Alerte envoyée » plutôt que par « Email KO ».

| Ce que C12 rend | Ce que ça veut dire | Conduite |
|---|---|---|
| `Aucune bascule tuée … depuis 24 h` | rien à signaler, **mesuré** | — |
| `Bascule/MAJ TUÉE sur <nœud> il y a N min` | une bascule ou une MAJ est morte entre la pose et la libération du verrou — coupure, `kill -9`, **gel** (récurrent sur rpi2) | lire le journal de bascule autour de l'heure ; vérifier `.active` sur les **deux** nœuds et l'absence de split-brain |
| `INCONNU — journal illisible` | le contrôle **n'a pas pu** mesurer | vérifier la présence et les droits de `/var/log/hostachy-health-watch.log` |

⚠️ **Le seuil de péremption est écrit UNE fois** : `VERROU_STALE_S` dans
`scripts/lib/lib-verrou.sh`, avec la décision pure `verrou_recent()`. Il était
recopié trois fois (`LOCK_MAX_AGE_S` à 900 s, `LOCK_STALE_MIN` à 20 min, et le
paramètre de `bascule_en_cours`) — et `auto-deploy.sh` n'en avait **aucune**, si
bien qu'un verrou orphelin le figeait **indéfiniment**, sans plus aucun
déploiement et en silence. `api/tests/test_verrou_bascule.py` refuse une
quatrième copie.

### C31 — health-watch, qui décide du failover, sonde-t-il encore ? (02/10/2026, #1586)

`health-watch.sh` ne disait **rien** quand le site répondait : le 02/10/2026, la
dernière ligne de son journal datait de 34 h sur les deux nœuds, pour un cron
qui tourne toutes les quelques minutes (horaire : `infra/points-entree/`). Rien ne distinguait ce calme d'un script mort — cron perdu, bit x, module
absent avant la sonde, verrou bloqué —, donc d'un failover automatique
inexistant, et aucun contrôle ne mesurait son passage.

Il écrit désormais une ligne datée à **chaque sonde**, avant toute décision
(`Site OK (HTTP 200) — RPi: rpi1`, ou `⚠ Site HS (HTTP …)`). C31 mesure l'âge de
la dernière sur les **deux** nœuds — c'est la ligne de la **sonde** qui compte, pas
n'importe quelle ligne datée : « Autre instance en cours » n'a rien sondé. Écriture,
collecte et verdict vivent ensemble dans `scripts/lib/lib-health-watch.sh`.

| Ce que C31 rend | Ce que ça veut dire | Conduite |
|---|---|---|
| `health-watch sonde sur <nœud> : dernier passage il y a N min` | il tourne et va jusqu'à la sonde, **mesuré** | — |
| `health-watch ne sonde plus sur <nœud>` (FAIL, > 20 min) | plus de failover automatique **par ce nœud** | `sudo crontab -l` (ligne `health-watch.sh`), bit x, `tail /var/log/hostachy-health-watch.log` : une erreur non datée juste avant le trou dit la cause ; un « Autre instance en cours » répété dit un verrou `/tmp/health-watch.lock` tenu |
| `health-watch INCONNU sur <nœud>` (FAIL) | aucune sonde datée lisible — journal absent, illisible, ou format changé | présence et droits du journal ; jamais lu comme un vert |

Le constat ne nomme qu'un nœud : il est dit **une fois**, par lui — ou par l'autre
s'il est muet (#1402). Pair injoignable : C31 se tait sur lui, C15 et « Peer
injoignable » le disent.

**Côté auto-deploy (#1587)**, chaque ligne est datée **à son écriture** (`log`,
`scripts/lib/lib-journal.sh`) : « Déployé » porte l'heure de la fin et sa durée
(`Déployé: <sha> (en N s)`). Un `git fetch` en échec écrit `⚠ git fetch
impossible (…) — déploiement reporté` (C27 : WARN), toute autre sortie imprévue
`⚠ ÉCHEC inattendu (code N, dernière commande : …)` (C27 : FAIL). Toutes deux
font battre C14 — le script tourne — et c'est C27 qui dit qu'il n'a rien déployé.

### C1 — « site public KO » demande DEUX sondes, pas une (01/09/2026)

Une alerte critique est partie à 01:21 pour un `HTTP 503` qui a duré moins de
quinze minutes : `auto-deploy.sh` recréait les conteneurs entre 01:18 et 01:23, et
Caddy rend 503 pendant que son amont redémarre. **Une seule occurrence dans 1,8 Mo
de journal**, l’exécution suivante verte, et tous les autres contrôles au vert dans
la même exécution — y compris « pas de split-brain » et « code aligné ».

🔴 **La preuve que le contrôle avait tort existait déjà, chez le voisin.**
`health-watch.sh` sonde la MÊME URL, re-sonde à 30 s avant de conclure, et a écarté
un 503 identique à 05:42 le même jour : *« Site revenu entre les deux checks
(HTTP 200) — faux positif, pas d’action »*. Deux contrôles du même fait, deux
fiabilités — et c’est le plus bruyant qui écrivait à l’exploitant.

C1 rend donc désormais quatre verdicts, décidés par `verdict_site_public`
(`lib-verdicts.sh`, pure, couverte par `--selftest`) :

| Sondes | Verrou de build sur l’actif | Verdict |
|---|---|---|
| 200 | — | **OK** |
| ≠200 puis 200 | — | **WARN** — hoquet, pas une panne |
| ≠200 deux fois | tenu | **WARN** — build en cours, revérifié dans 15 min |
| ≠200 deux fois, la seconde **à la résolution du nom**, puis 200 par un autre résolveur | — | **WARN** — le résolveur du nœud, pas le site (20/10/2026, 22:36) |
| ≠200 deux fois | libre | **FAIL** — le chemin critique est inchangé |

⚠️ **Ce n’est pas un assouplissement de seuil.** La leçon du point 10 (#448) est
que la tolérance masque ; ici on ajoute une **seconde mesure**, et les deux cas
non concluants sortent en WARN — donc dans le digest, jamais en silence. Un build
qui échoue laisse le site KO : le verrou est relâché, et l’exécution suivante
alerte.

🔴 **Le résolveur du nœud n'est pas le site** (21/10/2026). Le 20/10 à 22:36, C1 a
écrit FAIL sur deux `000` qui avaient expiré à la **résolution** du nom — rpi2
recevait un 200 à la même minute. Quand la seconde sonde échoue ainsi
(`echec_de_resolution`, `lib-sonde.sh`), une troisième rejoue la requête avec le nom
résolu en DNS sur HTTPS (`RESOLVEUR_INDEPENDANT`, une adresse IP : hors de
`/etc/resolv.conf`). Un 200 → WARN ; un échec reste le FAIL : une panne de DNS ou
de lien du domicile coupe aussi le tunnel.

Le verrou est lu **sur le nœud qui porte la prod**, jamais sur celui qui observe —
un build sur le standby ne fait pas tomber le site public. Il est remonté par le
champ `deploiement` de `lib-collecte.sh`, qui prend et relâche un verrou *partagé*
sur `.auto-deploy.lock` : il échoue face à l’exclusif du build sans jamais bloquer
un build qui démarrerait pile à cet instant.

📎 Au passage : `http_code` existait en **trois** exemplaires — ici, dans
`lib-verdicts.sh` et dans `precheck-mep.sh` — et la troisième avait perdu le
correctif du 30/07/2026 (garde sur la sortie vide). Elle vit maintenant dans
`scripts/lib/lib-sonde.sh`, et nulle part ailleurs.

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

🔴 **Ne pas les recopier ici.** La table qui vivait à cet endroit citait **trois
scripts sur quatre** — `check-reliability.sh`, celui qui décide d'alerter, n'y
figurait pas — et donnait une cadence « toutes les 5 minutes » là où l'installé écrit des minutes
décalées (pour ne pas empiler les deux sondes) — l'horaire ne s'écrit donc plus
que dans le fichier versionné (#1562). Une table recopiée se périme, et celle-ci
décrivait un parc qui n'existait plus (#1051).

**La source est versionnée** : `infra/points-entree/cron-root.crontab` (root) et
`cron-ptressard.crontab` (utilisateur, `auto-deploy.sh`). Le **point 17** du
pré-check compare l'installé au dépôt avant chaque livraison.

🔒 `npm run lint:consignes` refuse désormais qu'une consigne en énumère une partie.

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

## Correctifs de sécurité en attente — lire C30 (#1441, 28/09/2026)

Un correctif en attente n'est pas un défaut : `apt-daily-upgrade` passe une fois
par jour (06:00 + 60 min aléatoires), donc un correctif publié après le passage
attend jusqu'à 25 h. C30 criait « unattended-upgrades ne les a pas posés » dès la
publication — le 28/09, pour un libheif paru quatre heures après le passage.

Chaque nœud relève désormais, **par paquet**, depuis quand il attend
(`/var/lib/hostachy/apt-secu-vu`, écrit par sa collecte root) :

| C30 dit | Ce qui a été mesuré | Conduite |
|---|---|---|
| OK « posé(s) au prochain (HH:MM) » | publié après le début du dernier passage | rien |
| WARN « vus par le passage … sans être posés » | un passage les a eus sous les yeux | `sudo unattended-upgrade -v` dit pourquoi — souvent un fichier de configuration modifié (`initramfs-tools-core` sur rpi2) |
| WARN « … au-delà des 25 h » | attente plus longue qu'un passage, aucun ne les a vus | `systemctl status apt-daily-upgrade.timer` |

Collecte et décision : `scripts/lib/lib-apt.sh` (`--selftest`). Messages : la
boucle par nœud de `lib-mises-a-jour.sh`.

## Ce que C30 et C32 à C36 ajoutent (02/10/2026, #1591 #1592 #1593 #1609 #1610 #1648 #1588)

Tous **en lecture seule et en WARN** (jamais FAIL, donc jamais d'e-mail immédiat :
le digest quotidien). Chaque constat nomme son nœud ; la décision est une fonction
pure à `--selftest`, la mesure vit dans un module de `scripts/lib/`.

| Contrôle | Ce qu'il dit | Module |
|---|---|---|
| C30, passage en cours | un passage `apt-daily-upgrade` tourne : la mesure est **différée** (ligne `ok` dite « INCONNU, revérifié au prochain passage », bornée à 2 h) — jamais un WARN sur un fait résolu vingt secondes plus tard | `lib-apt.sh`, `lib-mises-a-jour.sh` |
| C30, paquets | hors sécurité en attente au-delà d'un seuil, paquets « retenus » (hors noyau), **parité** des paquets de `PAQUETS_PARITE` et de la valeur effective de `Unattended-Upgrade::Mail` (`apt-config dump`, #1677) entre les deux nœuds | `lib-paquets.sh` |
| C32 | ports TCP à l'écoute sur toutes les interfaces, hors liste blanche (celle de `docker-compose.yml`, SSH, 80, 443, 8080) ; dit si le port est aussi sur l'autre nœud | `lib-ports-ecoute.sh` |
| C33 | copie de `.env*` laissée à côté de `.env` et `.env.example` à la racine du dépôt déployé | `lib-fichiers-parasites.sh` |
| C34 | copie de base (`*.db*`) laissée dans le volume de données, hors de toute règle de conservation, par un **listage de répertoire** | `lib-fichiers-parasites.sh` |
| C35 | la **pile de bureau est revenue** : paquet de la liste proscrite installé (avec ce qui l'a tiré), cible systemd redevenue `graphical.target`, `APT::Install-Recommends` ≠ 0. La liste s'écrit **une fois** (`PAQUETS_PROSCRITS`) et `scripts/exploitation/alleger-noeud.sh` la source — jamais recopiée. Retour causé par une mise à jour, un paquet recommandé ou une réinstallation depuis l'image (`docs/restauration-complete.md`, étape 12) | `lib-paquets-proscrits.sh` |
| C36 | le **journal d'accès de Caddy** est-il écrit (dernière ligne < 1 h) et combien d'erreurs **500/504** en 24 h ? Les 502/503 sont comptés à part : ce sont les redémarrages d'un déploiement. **Sur l'actif seulement** | `lib-journal-acces.sh` |

Ces contrôles **signalent**, ils ne corrigent rien : supprimer une copie de base ou
de `.env` sur un nœud, fermer `rpcbind`, mettre à jour docker restent des gestes
root de Philippe, le standby d'abord.

## C38 — chaque nœud refuse-t-il le mot de passe SSH ? (#1941, 14/10/2026)

D'avril à octobre 2026, les deux nœuds l'acceptaient : `50-cloud-init.conf`
l'emportait sur le durcissement, et ce qu'on relisait était le **fichier**, pas ce
que sshd sert (#1918). C38 le mesure **par le comportement**, à chaque quart
d'heure : une sonde qui ne demande que la méthode `none` (`ssh_noeud_sonde_auth_cmd`,
`lib-ssh-noeuds.sh` — aucune clé présentée, aucun mot de passe tenté, clé d'hôte
épinglée), à laquelle sshd répond en nommant ce qu'il accepte. Chaque nœud sonde
son pair **et lui-même** (sa clé d'hôte lue localement), par l'adresse du LAN ;
le pair est sondé même muet, parce qu'un nœud réinstallé depuis l'image est
justement muet. Le jugement est celui du durcissement (`DURCISSEMENT_SSH_METHODES_PROSCRITES`,
`lib-durcissement.sh`) ; sonde et constats : `lib-ssh-mot-de-passe.sh`.

| Ce que C38 rend | Conduite |
|---|---|
| OK « mot de passe refusé — méthode(s) offerte(s) : … » | rien |
| **FAIL** « le MOT DE PASSE est accepté » | `sudo bash /opt/5hostachy/scripts/installation/durcir-noeud.sh --etat` sur le nœud nommé, puis `--appliquer` (seconde session SSH ouverte, le standby d'abord) |
| WARN « NON MESURÉ » | lire la cause : nœud injoignable, ou clé d'hôte non vérifiée — après une réinstallation, la clé du nœud a changé : la ré-épingler (`docs/restauration-complete.md`, étape 7), **jamais** en désarmant la vérification de clé d'hôte (`lib-ssh-noeuds.sh`) |

FAIL et non WARN : c'est une porte ouverte, pas une hygiène. fail2ban ne compte
pas la sonde en mode `normal` (mesuré) ; ne jamais en raccourcir la cadence, un
bannissement de l'IP du pair couperait la bascule.

### Le journal d'accès de Caddy (#1588, 05/10/2026)

Avant ce jour, les accès HTTP s'écrivaient sur la sortie standard du conteneur
`hostachy_caddy`, que `docker compose up -d` recrée à chaque déploiement : aucun
5xx de la veille n'était observable. Ils vont dans un **fichier du volume
`caddy_logs`** (`/var/log/caddy/access.log`, JSON), roulé par taille (10 Mo × 5) et
par âge (7 jours). Il est **anonyme** : ni adresse, ni en-têtes, ni chaîne de
requête (`?token=…`) — même arbitrage que #1300 pour uvicorn, et c'est ce qui
dispense de déclarer sa durée dans la politique de confidentialité.
🔒 `api/tests/test_journal_acces_caddy.py`. Il n'est **pas répliqué** par la
bascule : chaque nœud garde les jours où il a été actif.

```bash
# les erreurs serveur inattendues, avec chemin et heure (nœud actif)
docker exec hostachy_caddy grep -E '"status":(500|504)' /var/log/caddy/access.log
```

⚠️ Il n'y a **plus** de journal d'accès sur la sortie standard : un second `log` par
site est ignoré par Caddy (éprouvé en 2.11), et l'ancien portait les adresses.

## Monitoring APScheduler (tourne dans le conteneur API)

🔴 **La liste des jobs se lit dans `api/app/main.py`** (`scheduler.add_job`), pas
ici. Le tableau qui occupait cette place en citait **quatre sur six** : le
préchauffage du manuel PDF (au démarrage puis chaque nuit) et la relève des
courriels (toutes les 10 min) n'y figuraient pas — et il donnait `backup` à 03:00
alors que l'heure est **configurable** (`cfg.heure_execution`). Trois erreurs dans
quatre lignes (#1051).

**La sauvegarde depuis v2.179.0 (#2058) — le rythme ne change pas, sa mécanique si :**

| | Avant | Depuis #2058 |
|---|---|---|
| tâche `backup` | un `cron` à `heure_execution`, lue UNE fois au démarrage | un `cron` à chaque heure pile, qui ne sauvegarde qu'à `heure_execution` (`backup.sauvegarder_si_c_est_l_heure`) |
| sauvegardes par jour | une | **une** — 23 passages sur 24 ne font rien (`test_la_tache_horaire_sauvegarde_une_fois_par_jour_a_son_heure`) |
| changer l'heure dans Maintenance | effet au redémarrage de l'API | effet dès l'heure suivante |
| `BACKUP_HOUR` du `.env` | repli sans ligne en base | **retiré** ; la ligne `config_sauvegarde` est posée par le seed |
| journal de l'API | une ligne par nuit | une ligne `tache backup — copropriete principale : faite` par heure, la sauvegarde elle-même une fois |
| archives, dossier, nom, rotation, copie hors site, rattrapage | — | **inchangés** (installation propre : la racine de `/backups`) |

⚠️ Au changement d'heure de mars, 02:00 n'existe pas : une `heure_execution` à 2
n'a pas de passage ce jour-là, la sauvegarde est sautée et refaite la nuit suivante
(`backup_rattrapage` ne joue qu'au démarrage de l'API). Le défaut est 3, qui existe
toujours ; le contrôle de 06:00 signale une sauvegarde de plus de 25 h.

Ce qu'il faut savoir et qui ne se lit pas dans le code : **quel job alerte**.
`health_check` (06:00) est le seul à envoyer un courriel de lui-même — WhatsApp
déconnecté, sauvegarde de plus de 25 h, disque sous 15 %. `whatsapp_scheduled`
alerte quand sa fenêtre de rattrapage s'épuise sans envoi réussi.

🔒 `npm run lint:consignes` refuse qu'une consigne en énumère une partie.

## WhatsApp bridge
- Reconnexion QR : Admin → WhatsApp → **bouton Statut** (affiche le QR si déconnecté)
- Session corrompue (`creds.json` vide) : vider le volume + redémarrer le bridge
  ```bash
  docker run --rm -v 5hostachy_whatsapp_auth:/data alpine sh -c 'rm -rf /data/*'
  cd /opt/5hostachy && docker compose up -d whatsapp-bridge
  ```
- `bascule.sh` ne propage jamais un `creds.json` vide vers le peer
- **Arrêt propre** (#1590, 03/10/2026) : le bridge traite `SIGTERM` et `SIGINT` (`arret.js`) —
  il ferme le socket, attend les écritures de `creds.json` et des clés, puis sort en 0,
  borné à 8 s ; `stop_grace_period: 20s` dans `docker-compose.yml`. Un **exit 137** sur
  `hostachy_whatsapp` est désormais une anomalie : `docker inspect hostachy_whatsapp
  --format '{{.State.ExitCode}}'` doit rendre 0 après un arrêt.
- **La clé du bridge** (#1596, 02/10/2026) : une seule source, `WHATSAPP_API_KEY`
  dans `.env`, lue par le bridge (`WA_API_KEY`) **et** par l'API
  (`utils/whatsapp.entetes_bridge`) — plus rien ne se saisit à l'écran. Le bridge
  **refuse de démarrer** si elle est vide, vaut la valeur d'exemple ou fait moins de
  16 caractères (`docker logs hostachy_whatsapp` le dit, sans la valeur), et ne la
  lit qu'en en-tête `x-api-key`. Après toute modification de `.env` :
  `docker compose up -d api whatsapp-bridge` — sinon l'API garde l'ancienne, et
  Admin › WhatsApp › Statut répond « le bridge refuse la clé de l'API »

#### 🔴 Blocage du compte WhatsApp — la panne qui ne se répare pas (#1061, 26/09/2026)

Le bridge repose sur **Baileys**, un client non officiel de WhatsApp Web : c'est
le seul moyen de publier dans un groupe, et c'est un choix assumé. Son prix :
WhatsApp peut **déconnecter d'office**, voire **bloquer le numéro** appairé. Un
blocage n'est pas un incident technique — ni un redémarrage, ni une bascule, ni
un nouveau QR ne le lèvent.

**Deux pannes qui se ressemblent** (« déconnecté ») et que tout oppose :

| Signe (`GET /status` du bridge) | Lecture | Conduite |
|---|---|---|
| `dernier_code` 428, hors ligne quelques minutes | la boucle ordinaire (~4 h 45) | rien : il se rétablit seul |
| `dernier_code` **401** ou **403** | WhatsApp a fermé la session : appairage perdu, ou **numéro bloqué** | ci-dessous |
| hors ligne depuis **≥ 6 h** (`hors_ligne_depuis`) | au-delà de toute coupure ordinaire | ci-dessous |

Le contrôle de 06:00 (`utils/health_monitor` → `utils/verdict_whatsapp`) porte
ce verdict distinct dans l'alerte e-mail — le seul canal qui reste quand
WhatsApp tombe (`standards/07` §2).

**Conduite à tenir :**

1. **Ne pas ré-appairer en boucle.** Un QR rescanné sur un numéro bloqué ne sert
   à rien, et des appairages répétés sont précisément ce que WhatsApp surveille.
   Un seul essai, depuis Admin → WhatsApp → Statut.
2. **Regarder le téléphone du numéro appairé** : WhatsApp y affiche le blocage
   (« Ce compte n'est pas autorisé… ») et, le cas échéant, le formulaire de
   recours.
3. **Prévenir les résidents par courriel** — il touche les mêmes personnes :
   une actualité dont la Diffusion coche le courriel, qui dit que le groupe est
   momentanément muet.
4. **Blocage durable** : décider du repli — second canal (#1060, rendre le canal
   remplaçable) ou courriel seul.

⚠️ **Le numéro appairé et son détenteur ne s'écrivent PAS ici** : c'est une
donnée personnelle, et un dépôt git la conserve (`standards/14`). Ils se lisent
sur le téléphone lui-même et chez le gestionnaire du site.

#### Lire l’historique des envois — trois verdicts, pas deux (19/08/2026)

`Admin → WhatsApp → Historique des envois` ne dit **pas** « parti / pas parti » :
il en distingue **trois**, et la nuance est ce qui protège du doublon.

| Verdict | Ce qu’on sait | Rejouable ? |
|---|---|---|
| **envoyé** | le serveur WhatsApp a acquitté | — |
| **incertain** | le message a **pu** être remis | 🔴 **jamais** |
| **échec** | on sait que rien n’est sorti (connexion refusée, 4xx) | oui, sans risque |

🔴 **« incertain » n’est pas un échec.** Rejouer un envoi dont on ignore le sort
fabrique un doublon dans le groupe des copropriétaires — et un doublon ne se
retire pas. C’est le triple envoi du 14/08/2026.

⚠️ **Deux causes très différentes produisent « incertain », et il faut les lire :**

- **« message émis, accusé de réception non observé »** — `sendMessage()` a rendu
  la main, donc **le message est parti** ; seul l’accusé du serveur WhatsApp a
  tardé (15 s). Il a très probablement été remis : **vérifier dans WhatsApp avant
  toute action**, c’est le cas le plus fréquent ;
- **« réponse 500 du bridge »** — le bridge a échoué en cours de route sans dire
  de quel côté de l’envoi. Là, on ne sait vraiment pas.

**Why** : jusqu’au 19/08/2026 le bridge répondait `500` dans les DEUX cas — son
`catch` était commun. L’utilisateur a comparé son fil WhatsApp et l’écran : deux
messages **remis** (double coche) y figuraient en « incertain — réponse 500 du
bridge ». Le bridge rend désormais **`202 Accepted`** avec `envoye: true` quand
le message est parti sans accusé, et l’API le traduit en clair. Verrouillé par
`api/tests/test_whatsapp_verdict_envoi.py`, qui éprouve les trois verdicts côte
à côte — un test qui ne vérifierait qu’un seul ne prouverait pas qu’il distingue —,
et par la table `test_classification_des_reponses_du_bridge`
(`api/tests/test_whatsapp_scheduler.py`), qui exige que la raison d’un 202 dise
« émis » et jamais « 500 ».

#### Incident du 24/07/2026 — bridge bloqué 2h23, message mensuel manqué
Le message WhatsApp planifié du 4ᵉ samedi (18h00) a échoué : le bridge était en
boucle `stream:error conflict:replaced` ininterrompue depuis 14h28, sans jamais
revenir à `state: open`. Deux causes cumulées, corrigées :

1. **`bascule.sh` synchronisait `5hostachy_whatsapp_auth` « à chaud » (Phase 1,
   conteneur source encore actif et en train d'écrire `creds.json` + fichiers de
   clés)** → snapshot multi-fichiers potentiellement déchiré propagé au peer à
   chaque bascule nocturne. **Corrigé** : le sync se fait désormais en Phase 2,
   après `docker compose stop` (0 writer), avec vérification que
   `creds.json` est un JSON valide avant de l'installer sur le peer
   (`standards/06` §1 : un état multi-fichiers tenu ouvert ne se copie pas à chaud).
2. **`whatsapp-bridge/index.js` ne supervisait pas sa propre reconnexion** :
   `setTimeout(startBaileys, 5_000)` appelait une fonction `async` sans
   `.catch()` → une reconnexion qui rejette (ex. timeout réseau) tue la chaîne
   silencieusement, sans aucun log. C'est ce qui a laissé le bridge mort de
   16h18 à 18h41 sans la moindre tentative. **Corrigé** : verrou anti-concurrence
   (`starting`), `.catch()` systématique sur chaque relance, backoff exponentiel
   (5s → 60s max), et un watchdog (`setInterval` 60s) qui force une reconnexion
   si l'état reste hors `open`/`connecting`/`waiting_qr` sans reconnexion en cours.
3. Le job `whatsapp_scheduled` ne tentait l'envoi **qu'une fois, à 18h00 pile**
   — un échec ponctuel du bridge à cette seconde précise perdait le message du
   mois. **Corrigé** : fenêtre de rattrapage 18h00→21h45 toutes les 15 min (la
   déduplication existante empêche tout doublon), alerte email si la fenêtre se
   ferme sans envoi réussi.
