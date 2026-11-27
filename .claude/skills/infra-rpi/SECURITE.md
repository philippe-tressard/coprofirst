# infra-rpi — Correctifs de sécurité (C30, C32 à C36, C38), sortie en liste blanche, audit de sécurité nocturne (S1 à S6, C40)

Annexe de `SKILL.md`, chargée à la demande (#2910) : le sommaire est dans `SKILL.md`.
Les titres et numéros de section sont ceux de toujours : un renvoi se lit au sommaire.

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
| C30, paquets | hors sécurité en attente au-delà d'un seuil, paquets « retenus » (hors noyau), **parité** des paquets de `PAQUETS_PARITE` (le **standby en avance** sur l'actif est le geste de #2198 et se dit OK : l'actif suit à la bascule ; l'**actif** en avance, ou un `.active` incohérent, reste WARN) et de la valeur effective de `Unattended-Upgrade::Mail` (`apt-config dump`, #1677) entre les deux nœuds | `lib-paquets.sh` |
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

## La sortie en liste blanche — constat, puis refus (#2367, 01/11/2026)

ufw refusait l'entrant et laissait **tout sortir**. La liste de ce qui a le droit
de sortir s'écrit une fois, `DURCISSEMENT_UFW_SORTANT` (`lib-durcissement.sh`,
portée `hote` ou `tous`, avec ce qui sort par là) ; le pair vient de `ROLE_TABLE`.
Elle se pose sur l'hôte (règles `ufw allow out`) **et** sur les conteneurs : ils
sortent par FORWARD, où Docker accepte avant ufw — seule la chaîne `DOCKER-USER`,
posée par un bloc d'`/etc/ufw/after.rules`, les voit. Décisions et lectures :
`lib-durcissement-sortant.sh` ; S5 juge la configuration **servie** et fait chaque
nuit l'inventaire de ce qui est sorti hors liste (journal du noyau).

| Mode | Ce qui est servi | S5 |
|---|---|---|
| `ouvert` | `allow (outgoing)` — l'état d'avant | WARN « sortie non filtrée » |
| `constat` | idem + `allow out log to any` en dernier, LOG puis RETURN au bout de DOCKER-USER : **rien n'est refusé** | OK « nuit verte » si rien hors liste en 24 h, sinon WARN avec la liste (nombre, destination, port, qui) |
| `refus` | `reject (outgoing)`, LOG puis REJECT au bout de DOCKER-USER | OK, ou WARN avec ce qui a été refusé ; FAIL si la liste servie s'écarte de la déclarée |

Gestes, en root, **un nœud à la fois, le standby d'abord** (les rôles alternent
chaque nuit : un nœud posé passe actif le lendemain) :

```bash
sudo bash /opt/5hostachy/scripts/installation/durcir-noeud.sh --etat               # mode, verdict, hors-liste 24 h
sudo bash /opt/5hostachy/scripts/installation/durcir-noeud.sh --sortant constat    # journaliser, sans refuser
sudo bash /opt/5hostachy/scripts/installation/durcir-noeud.sh --sortant refus      # fermer
sudo bash /opt/5hostachy/scripts/installation/durcir-noeud.sh --sortant ouvert     # retour arrière durable
```

`--sortant refus` **refuse** tant que le nœud n'a pas `DURCISSEMENT_SORTANT_NUITS_VERTES`
nuits de constat vertes de suite (lues dans le journal de l'audit), qu'une sortie
hors liste reste dans les 24 h, ou que le nœud est l'actif — sauf sur un nœud qui
**sert déjà** le refus : il le repose toujours, actif compris, pour réparer un écart
(une règle déclarée depuis : MLDv2, 11/11/2026). Après le refus, et avant
le second nœud : un passage de C30 (`apt`), d'`auto-deploy` (tirage des images), de
la bascule et un courriel d'alerte reçu.

🔴 **Retour arrière immédiat**, une ligne, sans le dépôt :

```bash
sudo ufw default allow outgoing && sudo iptables -F DOCKER-USER
```

Il rouvre l'hôte et les conteneurs jusqu'au prochain rechargement d'ufw ;
`--sortant ouvert` le rend durable (retire le bloc d'after.rules).

⚠️ Ce qu'il faut savoir :
- **ufw ne nomme pas un hôte** : la liste est faite de ports, 443 et 53 restent
  ouverts vers tout. Elle ferme le reste (reverse shell, relais SMTP sur 25, tunnel).
- **`after.rules` en ASCII seulement** : ufw réécrit ses fichiers en ASCII et plante
  (`UnicodeEncodeError`) sur le premier caractère qui ne l'est pas — trouvé au banc,
  un tiret cadratin dans une borne. Le self-test l'exige.
- **`git fetch` passe par HTTPS** (`lib-depot-distant.sh`, dépôt public, aucune clé) :
  le port 22 n'est ouvert vers personne. Il passait par SSH jusqu'au 02/11/2026 ; ufw
  ne nomme pas un hôte, et `github.com` se résout parfois vers l'une des ~55 adresses
  isolées d'`api.github.com/meta` (rpi2 : `20.250.119.67`, 62 sorties hors liste en 24 h) :
  les plages déclarées n'auraient jamais suffi. Le remote d'un nœud se réécrit au
  premier passage d'`auto-deploy` ; la bascule le réécrit chez le pair avant son fetch.
- **Une règle que la liste ne déclare plus** (posée par une version plus ancienne) est
  dite « obsolètes=[…] » par S5 — constat incomplet, WARN, pas une intrusion — et
  `durcir-noeud.sh --sortant constat` la retire (seulement celles qui portent
  notre commentaire `sortie 2367` ; une règle identique SANS ce commentaire reste « hors liste »).
- **L'IGMP est déclaré** (`allow out to 224.0.0.0/24 proto igmp`, portée hôte) : le noyau
  annonce ses adhésions multicast à `224.0.0.22` (TTL 1, protocole 2 — la colonne « port »
  du constat S5 dit `2`, pas un port). Rien n'en dépend, mais le refuser n'apporterait que
  du bruit. Sa forme canonique est lue dans la source d'ufw 0.36.2, pas relevée sur un banc :
  si S5 la dit « manquante » après la pose, c'est que la forme servie diffère.
- **MLDv2 est déclaré, hors d'ufw** (11/11/2026) : le noyau annonce ses adhésions
  multicast IPv6 à `ff02::16` (ICMPv6 type 143, limite de saut 1) ; en refus, S5 en
  comptait une douzaine par nuit (« ff02:…:0016 icmpv6-type143 hôte »). `ufw allow` ne
  sait pas écrire ICMPv6 : la règle vit dans `DURCISSEMENT_ICMPV6_SORTANT`, posée par un
  bloc d'`/etc/ufw/after6.rules` (`ufw6-after-output`, avant le LOG et le REJECT). Un
  nœud dont le bloc manque est dit « icmpv6-manquant » (FAIL en refus) :
  `durcir-noeud.sh --sortant refus` le pose sur un nœud déjà en refus, actif compris.
- **List-dons** vit sur rpi2 : DOCKER-USER filtre aussi ses conteneurs. Son besoin
  se lit dans le constat de rpi2 avant tout refus.
- **Un port publié par Docker, joint depuis l'hôte, sort vers le pont** (05/11/2026) :
  `localhost:8080` (List-dons) est traduit en `172.19.0.2:8080` AVANT la chaîne OUTPUT,
  donc S5 le voit comme une destination hors liste (« 172.19.0.2 8080/tcp hôte »).
  Déclaré : `allow out to 172.16.0.0/12 port 8080 proto tcp`, portée hôte — la plage des
  ponts Docker (l'adresse du conteneur change à sa recréation), injoignable de
  l'extérieur. Un autre port publié joint depuis l'hôte se déclare de même, avec son
  port : la plage ne s'ouvre pas à tout.
- **Le repli DNS-over-TLS de cloudflared** (27/11/2026, #3147) : quand le résolveur du
  nœud échoue la requête SRV de l'edge (`_v2-origintunneld._tcp.argotunnel.com`),
  cloudflared la rejoue en DoT vers une adresse codée en dur, `1.1.1.1:853`
  (`dotServerAddr`, `edgediscovery/allregions/discovery.go`). S5 l'a vue refusée sur
  rpi2 (« 10 1.1.1.1 853/tcp hôte ») : le tunnel redémarrait après un gel (#3148),
  pendant une défaillance du DNS de la box. Déclaré : `allow out to 1.1.1.1 port 853
  proto tcp`, portée hôte — une adresse, un port. Le repli ne rattrape que le SRV : les
  adresses de l'edge restent résolues par le résolveur du nœud, sans qui le tunnel ne
  démarre toujours pas.
- Le banc qui a éprouvé la pose : un conteneur jetable `--cap-add NET_ADMIN` sur le
  standby (son propre espace réseau), ufw installé dedans, `durcir-noeud.sh --sortant`
  joué pour de vrai — refus, comportement (443 passe, 4444 refusé en 1 s), retour.

### Le journal d'accès de Caddy (#1588, 05/10/2026)

Avant ce jour, les accès HTTP s'écrivaient sur la sortie standard du conteneur
`hostachy_caddy`, que `docker compose up -d` recrée à chaque déploiement : aucun
5xx de la veille n'était observable. Ils vont dans un **fichier du volume
`caddy_journal`** (`/var/log/caddy/access.log`, JSON ; `caddy_logs` jusqu'à #2430), roulé par taille (10 Mo × 5) et
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

## L'audit de sécurité NOCTURNE — S1 à S6, et C40 (30/10/2026)

Les contrôles du quart d'heure disent si le service tient et si le nœud est
conforme. L'audit pose l'autre question, celle d'une **intrusion** — menée par un
outil, et depuis 2026 par un agent, qui cherche une brèche, s'y installe et
revient. Il tourne **en root, sur chaque nœud, une fois par jour** : lancé par
`check-reliability.sh` au premier passage après 04:00 (pas un cron de plus à
poser — `lib-audit-securite.sh` dit pourquoi), journal
`/var/log/hostachy-audit-securite.log`, rapport à l'écran sous la tâche
**Audit de sécurité nocturne** (`audit_securite`), FAIL par courriel dans l'heure,
WARN dans le digest. **C40** dit s'il a eu lieu (terminé, jamais, en retard, lancé
et jamais fini).

| Section | La question | Module | Écart |
|---|---|---|---|
| S1 | l'arbre que root exécute (`scripts/`, `infra/`, compose, Caddyfile, Dockerfiles) est-il celui du dépôt ? `git status` sur ces zones | `lib-audit-arbre.sh` | FAIL |
| S2 | un second UID 0, un compte avec shell non déclaré, un mot de passe vide, un membre de plus dans `docker` ou `sudo` ? | `lib-audit-comptes.sh` (listes déclarées en tête) | FAIL |
| S3 | les points de persistance (cron, systemd, `authorized_keys`, sudoers, passwd/shadow, `ld.so.preload`, profile.d, apt) ont-ils changé depuis la **référence acceptée** ? | `lib-audit-persistance.sh` | FAIL (chauds) · WARN (configuration que les mises à jour retouchent) |
| S4 | les conteneurs sont-ils sans privilège, sans la prise Docker, sans montage hors compose, et DURCIS comme le compose les déclare (capacités, `no-new-privileges`, racine en lecture seule — `CONTENEURS_DURCIS`, #2368) ? leurs images sont-elles celles de la CI pour HEAD ? la prise Docker en 660 root:docker ? | `lib-audit-conteneurs.sh` | FAIL · WARN (image de secours ou périmée) |
| S5 | sshd, ufw, fail2ban, apt : la configuration **servie** (`sshd -T`, `ufw show added`, `fail2ban-client`, `apt-config dump`) ; la **sortie** en liste blanche et ce qui est sorti hors liste en 24 h (ci-dessous, #2367) | `lib-durcissement.sh`, `lib-durcissement-sortant.sh` (les mêmes lecteurs que `durcir-noeud.sh`) | FAIL · WARN (sortie ouverte, constat, hors-liste) |
| S6 | actif seul : une sonde de scanner (`/.env`, `/.git`, `wp-login`…) a-t-elle été **servie** en 2xx ? plus de 100 connexions refusées ? le journal de sécurité de l'API a-t-il des gestes à relire (jeton rejoué, rôle ajouté, compte supprimé…) ? | `lib-audit-acces.sh` | FAIL (sonde servie) · WARN |

Conduite :

- **S3 « référence absente »** (première nuit, ou nœud réinstallé) : lire le relevé,
  puis `sudo bash /opt/5hostachy/scripts/exploitation/audit-securite.sh --accepter`.
  Un écart ensuite : lire **chaque fichier nommé** (`+` ajouté, `-` retiré, `~`
  modifié). Voulu (une clé posée, un cron modifié par une livraison) →
  `--accepter <chemin…>` : les écarts sous ces chemins seuls, refusé s'il en reste
  ailleurs ; sans chemin, tout l'état. Chaque acceptation s'inscrit dans le journal
  de l'audit (`[S3] référence …`).
  **Qui écrit, déclare** (#2521, 04/11/2026) : `durcir-noeud.sh --appliquer|--sortant`
  met lui-même la référence à jour pour les chemins qu'il écrit (sshd_config.d,
  `/etc/ufw`, fail2ban, apt.conf.d), à la fin de son passage, et le dit — « référence
  S3 mise à jour ». Avant, chaque pose de la liste de sortie coûtait un `--accepter`
  en root sur chaque nœud le lendemain (02/11, 04/11). Il refuse si un écart existe
  ailleurs, et le nomme : lire, puis `--accepter`. Les écrivains se déclarent dans
  `PERSISTANCE_ECRIVAINS` ; `durcir-sudoers.sh` n'y est pas (poste, sans root ; sudoers
  est CHAUD, sa lecture le lendemain est voulue).
  Le lien d'activation de `cloudflared`, qui suit le rôle à chaque bascule, n'est pas
  un écart tant qu'il pointe vers son unité (`PERSISTANCE_SELON_ROLE`, 01/11/2026).
  Son état selon le rôle est jugé par `check-reliability`.
  Pas voulu → c'est une intrusion : **isoler le nœud** (bascule vers l'autre si
  c'est l'actif, puis couper son réseau), ne rien « nettoyer » avant d'avoir copié
  les journaux. La référence vit chez root (`/var/lib/hostachy/audit-securite/`),
  hors de l'arbre déployé : le compte de déploiement ne peut pas la réécrire.
- **S1** : `git -C /opt/5hostachy status` ; un script modifié là tourne en root la
  nuit. Un fichier voulu se committe ; sinon `git checkout -- <fichier>` **après**
  avoir lu la différence.
- **S4 « capacités=… », « gain-de-privilège-permis », « racine-en-écriture »** : le
  conteneur ne tourne pas comme `docker-compose.yml` le durcit — lancé à la main
  (`docker run`), ou par un compose modifié sur place (S1 le dit) : `docker inspect
  <conteneur>`, puis le recréer par Compose, **avec sa liste de services**. Dans un
  conteneur durci, `docker exec` entre en root SANS `DAC_OVERRIDE` : il lit, mais
  n'écrit plus dans les volumes — `docker exec -u app hostachy_api …`,
  `-u node hostachy_whatsapp`. `hostachy_postgres` tourne, lui, sous `postgres`
  (uid 999, aucune capacité, #2429) : `docker exec` y entre sous ce compte — comme
  `hostachy_caddy` sous `caddy` (uid 10002, aucune capacité, #2430), qui lit donc
  son journal sans rien de plus.
- **Les anciens volumes de Caddy** (`5hostachy_caddy_data`, `_config`, `_logs`,
  écrits par root) ne sont plus montés depuis #2430 : Caddy écrit dans
  `caddy_donnees`, `caddy_configuration`, `caddy_journal`, nés à son compte. Ils
  restent pour le retour à une image d'avant (qui ne s'ouvrirait plus sur des
  volumes rendus à `caddy` — mesuré au banc) ; leur journal d'accès d'avant la MEP
  s'y lit encore (`docker run --rm -v 5hostachy_caddy_logs:/v:ro "$(image_utilitaire)" tail /v/access.log`, l'image par `scripts/lib/lib-image-utilitaire.sh`).
- **S4 sur `hostachy_postgres` seul**, après une livraison qui a touché son
  service : la base n'a pas été RECRÉÉE — `auto-deploy` ne la recrée jamais
  (`--no-recreate`), seules la bascule (promotion, puis reconstruction de
  l'ancien primaire) et `reconstruire-replique.sh` le font. Lire
  `/var/log/hostachy-bascule.log` : la bascule suivante le corrige. La recréer de
  jour, c'est arrêter le primaire quelques secondes (`docker compose up -d
  postgres` sur l'actif) : geste de Philippe, jamais en passant.
- **S4 image « construite-ici »** : le secours de #1758 (alerté par ailleurs) ou
  un nœud qui n'a pas encore tiré ; « AUTRE » : une image d'un autre commit —
  `auto-deploy` n'a pas suivi, ou quelqu'un a poussé une image à la main.
- **S6 sonde servie** : une fuite, pas une hygiène — le chemin est dans le journal
  de Caddy (la commande est dans le constat) ; vérifier ce que Caddy sert sous ce
  chemin, et faire tourner le secret concerné.
- **Tout lire sans rien envoyer** : `sudo bash …/audit-securite.sh --essai`.
- **Un nœud neuf** : rien à poser — le premier passage de check-reliability après
  04:00 le lance ; seule la référence S3 se pose à la main.

Chaque décision est pure et auto-testée sur une faute injectée et son cas zéro
(`--selftest` de chaque module, job `test-scripts`). Hors des nœuds, la **veille
nocturne des vulnérabilités** (`.github/workflows/veille-securite.yml`) rejoue
chaque nuit sur `main` l'audit Python et Node de la CI, Trivy sur les quatre images
publiées et la vérification de leur attestation, et tient UNE issue « Veille
sécurité nocturne » (`securite`) : ouverte au premier rouge, fermée au retour au vert.
