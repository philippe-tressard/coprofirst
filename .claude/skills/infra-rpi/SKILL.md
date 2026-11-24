---
name: infra-rpi
description: "Infrastructure HA 5Hostachy sur 2 Raspberry Pi : serveurs et rôle actif, bascule, règle d'or de la base (PostgreSQL : primaire, réplique, promotion, reconstruction), distinction panne de chemin public / panne de nœud, crons et points d'entrée, monitoring APScheduler, bridge WhatsApp, audit de sécurité nocturne (S1–S6) et durcissement, scripts d'infra en CI (self-tests). À charger : intervenir sur un RPi, basculer, diagnostiquer un site HS ou un incident, deux primaires ou une réplique en retard, reconnecter WhatsApp, analyser une coupure de courant, écrire un script d'infra."
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
- **RPi 1** `192.168.1.222` (PhT-RB5) · **RPi 2** `192.168.1.223` (PhT-RB5i2) — dans un script, la table hôte ⇄ rôle ⇄ adresse est `scripts/lib/lib-role.sh` (`noeud_ssh`, `role_of`, `role_ip`, `role_peer`), jamais recopiée — elle l'était dans sept scripts
- RPi actif : `cat /opt/5hostachy/.active` — ⚠️ ce fichier peut disparaître, le recréer si absent
- Conteneurs **applicatifs** uniquement sur le RPi actif ; le standby porte toujours `hostachy_postgres`, sa réplique (`docker ps` la montre : ce n'est pas un split-brain)
- En cas de split-brain (conteneurs **applicatifs** sur les 2) : arrêter l'application du nœud qui ne doit pas servir par `docker compose stop $SERVICES_APPLICATIFS` (`lib-applicatifs.sh`) — jamais un `stop` sans liste, qui arrêterait sa réplique — puis recréer `.active`
- `MaJ-Hostachy.sh` refuse de tourner sur le standby ; en root (`sudo bash`), il pose le verrou de bascule sur les DEUX nœuds et prend celui du déploiement (#1999)
- En cas de site HS : la procédure et sa commande sont au paragraphe « Site HS » de `CLAUDE.md`, seule écriture (lisible seule en urgence). L'ordre et le `--no-recreate` y sont ceux de `servir_images` : la base n'est que démarrée, jamais recréée (#2706)
  — le `env_role_appliquer` pose `ORIGIN` public et retire `COOKIE_SECURE` ; démarrer la stack sur un nœud resté en rôle standby sert le public avec une origine locale et un cookie sans drapeau `Secure` (« gap .env du 15/07/2026 », #1077). La règle vit dans `scripts/lib/lib-env-role.sh`, jamais recopiée. Depuis #1751, `ORIGIN` dit aussi quel nom l'API sert : un actif resté sur son IP répondrait **421** au public. Les quatre chemins de prise de main (bascule, failover, garde au démarrage, reprise en main) passent par `env_role_appliquer`.

## ⚠️ Règle d'or des données — PostgreSQL : primaire, réplique, promotion (DI-7b, #1781)

La base est un PostgreSQL par nœud, dans le conteneur `hostachy_postgres` : un
**primaire** sur l'actif, une **réplique** en flux sur le standby. Les interdits
sont écrits dans `CLAUDE.md` (« Règle d'or des données »), seule liste ; voici la
conduite à tenir.

| Question | Où, comment |
|---|---|
| La réplication va-t-elle bien ? | **C37** (`check-reliability`, `lib-replication.sh`) et le **point 22** du pré-check — deux primaires, réplique absente, déconnectée, en retard, rôles inversés |
| Le rôle de la base d'un nœud ? | `docker exec hostachy_postgres psql -U coprofirst -d coprofirst -Atc "select pg_is_in_recovery()"` — `t` réplique, `f` primaire |
| Refaire la réplique du standby | `sudo bash /opt/5hostachy/scripts/exploitation/reconstruire-replique.sh` (simulation), puis `--oui` — efface la base LOCALE et la copie du primaire (`pg_basebackup -R`) ; refuse sur l'actif, sans primaire joignable |
| Changer d'actif | la bascule promeut la réplique du pair (phases 3-4), le failover et `boot-role-guard` aussi ; l'ancien primaire est reconstruit en réplique — tout passe par `lib-promotion.sh` |
| La bascule échoue après la promotion (#2318) | le rollback ISOLE le pair (application, tunnel, base promue), RELIT sa base, puis relance la base locale (`--no-recreate`) et l'application — `decider_base_au_rollback` (`lib-promotion.sh`). Journal : `→ Conteneurs locaux relancés (base, puis application)` ; ou `⛔ Base locale NON relancée` — le pair porte encore un primaire, ou il est illisible : site coupé, la ligne donne les gestes (isoler chez le pair, puis relancer ici) |
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

**Changer le jeton** : `sudo bash /opt/5hostachy/scripts/exploitation/changer-jeton-tunnel.sh`, l'**actif** d'abord (jeton éprouvé
par un connecteur temporaire), puis le secours (tunnel laissé arrêté) ; jamais `cloudflared service install` sur le standby.
Le jeton se **colle à l'invite masquée**, jamais en argument, nœud neuf compris (`lire_jeton_saisi`, 🔒 `test_jeton_tunnel_saisi.py`).

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
verdict, jamais un extrait de l'unité. Les **droits** du fichier, chaque nœud
ne juge que les siens, en root : WARN « INCONNUS » s'il ne les lit pas, jamais OK
(#2199) — même règle pour le cache de build (C16). Ce qui ne se mesure que chez
soi se lit dans `MESURES_PAR_SOI` (`api/tests/test_controles_mesures_par_soi.py`). ⚠️ Ne jamais afficher `systemctl cat
cloudflared` tel quel dans une réponse, un ticket ou un journal : masquer d'abord
(`sed -E 's/(--token[= ]+)[^ ]+/<MASQUÉ>/'`).

## Risques connus
- **Build OOM** : `npm run build` peut saturer la RAM du RPi → préférer `--nocache` en cas de build lourd
- **health-watch failover** → peut créer un split-brain ; toujours vérifier `docker ps` sur les 2 RPi
- **Sauvegardes** : le volume `backups` n'est **pas** répliqué par `bascule.sh` (qui ne
  transfère que les volumes `uploads` et `whatsapp_auth` ; `app_data` n'est transféré par
  aucun script). Le rôle alternant chaque
  nuit, chaque nœud n'accumule qu'un jour sur deux, et `_rotate_backups()` ne voit que
  ses fichiers locaux → 7 versions ≈ 14 jours **à trous**, aucun nœud n'ayant celle de
  la veille. Copie hors site : `scripts/poste/export-hors-site.sh` (voir ci-dessous)
- **Le nom d'une archive dit l'heure de PARIS** (#1611, 05/10/2026) :
  `<préfixe>AAAAMMJJ_HHMMSS_paris.tar.gz`. Avant, l'horloge UTC y était écrite
  sans le dire (`…_020000` pour une sauvegarde prise à 04:00) ; les anciennes archives
  (sans suffixe) restent en UTC jusqu'à leur rotation. `backup.nom_archive` écrit,
  `backup.horodatage_archive` relit les deux formats en UTC naïf — c'est le seul parseur.
  « Restaurer celle de 02:00 » se lit donc au suffixe : sans `_paris`, ajouter deux
  heures (une l'hiver) pour l'heure de Paris.
- **Le préfixe ne nomme pas la résidence** (#2653) : écrit `backup.PREFIXE_ARCHIVE`,
  l'ancien `hostachy_backup_` reste LU (`PREFIXES_LUS`) jusqu'à la rotation de la
  dernière archive qui le porte (#2659). Deux préfixes mêlés : l'ordre des noms n'est
  plus celui du temps — on trie par l'horodatage lu (`backup.archives`, `trier_archives`
  côté poste), jamais par `sorted(glob(…))` ni `ls | sort`.
  Depuis #2667, le nom dit aussi la RÉSIDENCE : `<préfixe><qui>_<horodatage>`, `<qui>`
  = `site_nom` réduit (`backup.qui_nomme_l_archive`), sinon l'identifiant du contexte
  (`principale` sur les RPi). Ni tri ni rotation ne le lisent (`cle_archive` côté poste) :
  une résidence renommée garde ses anciennes archives dans la même série.
  ⚠️ La copie hors site n'est PAS planifiée : Philippe la lance à la main, par le
  raccourci du Bureau — un lien vers `scripts/poste/export-hors-site.command` du
  **clone principal** (`/Volumes/Data/Dev/5hostachy`, branche `dev` ; `C:\Dev\5hostachy`
  sous Windows). Elle exécute donc le script de ce clone, jamais celui d'un worktree :
  après une MEP qui change un nom lu par elle, le geste qui la met à jour est
  `git -C /Volumes/Data/Dev/5hostachy fetch origin && git -C /Volumes/Data/Dev/5hostachy merge --ff-only origin/dev`.
  Le point 17 du pré-check vérifie que ce lien vise le lanceur du clone principal, et
  qu'il existe (`lib-lien-bureau.sh`, #2708) : un worktree retiré ou un lanceur déplacé
  rend l'écart ; un lien absent, INCONNU.
  Un clone resté en arrière ne lit que l'ancien préfixe : il recopie une archive
  vieillissante, puis n'en trouve plus — la santé le dit (« périmée » au-delà de
  7 j + 6 h, `sante_taches`).
- **`.active` peut disparaître** → le recréer manuellement sur les 2 RPi si absent
- **Clé d'hôte du pair non épinglée** (#1598, 02/10/2026) : le SSH inter-nœuds
  (`scripts/lib/lib-ssh-noeuds.sh`, seule source) exige `StrictHostKeyChecking=yes`
  contre `/root/.ssh/known_hosts_bascule`. Fichier absent, vide, ou nœud réinstallé
  (nouvelle clé d'hôte) → bascule arrêtée en phase 0, `check-reliability` en FAIL
  « Peer injoignable », et le message porte la commande d'épinglage. Ce n'est **pas**
  un nœud figé : épingler (procédure `docs/restauration-complete.md`, étape 7),
  jamais repasser à `no` — `scripts-ci-ssh-noeuds.sh` le refuse en CI

## Sommaire — les annexes

Cette skill passait 1 250 lignes (#2910). Ce qui se lit en intervention — serveurs, règle d'or, panne de chemin ou de nœud, risques connus — reste ici ; le reste est en annexe, chargée à la demande.

| Annexe | Ce qu'elle porte |
|---|---|
| `SAUVEGARDES-ET-VERDICTS.md` | Copie hors site des sauvegardes, et qui reçoit les verdicts de check-reliability (C1 à C40) |
| `CRONS-ET-STANDBY.md` | Banc des volumes, crontabs et unité systemd, standby qui s'aligne, noyau, allègement d'un nœud, cloudflared |
| `SECURITE.md` | Correctifs de sécurité (C30, C32 à C36, C38), sortie en liste blanche, audit de sécurité nocturne (S1 à S6, C40) |
| `APSCHEDULER-WHATSAPP-CI.md` | Monitoring APScheduler, bridge WhatsApp, scripts d'infra en CI (job test-scripts) |
