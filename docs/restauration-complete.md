# Réinstaller un nœud — Raspberry Pi 5

> **Objectif** : reconstruire de zéro **un** des deux nœuds de production (carte SD
> morte, Raspberry remplacé, réinstallation propre) pendant que **l'autre sert le
> site**. C'est le cas normal de la paire : le nœud réinstallé la rejoint comme
> **standby**, avec une réplique PostgreSQL du primaire — jamais comme actif.
>
> **Durée estimée** : ~45 min, dont la copie de la base (`pg_basebackup`).
>
> 🔴 **C'est la seule procédure d'installation.** `scripts/installation/setup-rpi5.sh`
> l'a doublée jusqu'au 20/09/2026 et a été **supprimé** (#1029) : il datait de
> l'époque mono-RPi et son `.env` empêchait la stack de démarrer. Un autre script de
> réinstallation, d'avril 2026, n'a jamais été versionné et écrivait les secrets de
> production en clair : il a été retiré du poste (#1917). Ce document n'en reprend
> **que** le durcissement système, devenu `scripts/installation/durcir-noeud.sh`.
>
> 🔒 **Aucun secret ne s'écrit dans un script ni dans le dépôt.** Le `.env` se
> **recopie depuis l'autre nœud** (étape 6) ; le jeton du tunnel se colle à l'étape 10.

**Si les DEUX nœuds sont perdus**, le premier renaît de la copie hors site : voir la
section [Les deux nœuds perdus](#les-deux-nœuds-perdus) en fin de page.

---

## Prérequis

| Élément | Détail |
|---|---|
| **Matériel** | Raspberry Pi 5 — **Raspberry Pi OS Lite 64 bits** (Debian 13 « trixie », comme les deux nœuds au 13/10/2026) |
| **L'autre nœud** | En service et **actif** (`cat /opt/5hostachy/.active` y donne son propre nom) : il porte le primaire PostgreSQL et le `.env` |
| **Réseau** | IP fixe `192.168.1.222` (rpi1) ou `192.168.1.223` (rpi2) — `infra/postgresql/pg_hba.conf` n'admet la réplication que depuis ces deux adresses |
| **Poste** | Accès SSH par clé ed25519 aux deux nœuds (Git Bash) |
| **GitHub** | Dépôt `philippe-tressard/coprofirst` (branche `main`) |
| **Jeton Cloudflare** | Jeton du tunnel (gestionnaire de mots de passe, ou tableau de bord Cloudflare) |

---

## Étape 1 — Préparer le système

Flasher **Raspberry Pi OS Lite 64 bits** avec **Raspberry Pi Imager**, et y régler :

- le **nom d'hôte** : `PhT-RB5` (rpi1) ou `PhT-RB5i2` (rpi2) — **exactement**. Les
  scripts d'exploitation déduisent le rôle du nom (`scripts/lib/lib-role.sh`) et
  s'arrêtent sur un nom inconnu ;
- l'utilisateur `ptressard`, et **la clé publique du poste** (« Autoriser
  l'authentification par clé publique ») : l'étape 4 coupe le mot de passe SSH, et
  refuse de le faire s'il n'y a aucune clé autorisée ;
- SSH activé, puis l'IP fixe sur la box.

```bash
ssh ptressard@192.168.1.222   # ou .223
```

---

## Étape 2 — Docker et dépendances

```bash
sudo apt-get update -qq && sudo apt-get upgrade -y -qq
sudo apt-get install -y -qq \
  curl wget git ca-certificates gnupg lsb-release \
  ufw fail2ban unattended-upgrades \
  cron rsync python3

# Docker Engine (ARM64)
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable --now docker
sudo usermod -aG docker ptressard
exit   # se reconnecter : le groupe docker n'est pris qu'à la connexion suivante
```

Rien d'autre ne s'installe sur l'hôte : ni Node, ni PostgreSQL — tout tourne en
conteneur, et les **images** sont tirées du registre de la CI (`lib-images-ci.sh`).

---

## Étape 3 — Cloner le dépôt

```bash
# Clé de déploiement — sa partie publique va dans GitHub > Settings > Deploy keys
ssh-keygen -t ed25519 -C "hostachy-rpi5-deploy" -f ~/.ssh/hostachy_deploy -N ""
cat ~/.ssh/hostachy_deploy.pub

cat >> ~/.ssh/config << 'EOF'
Host github.com
    IdentityFile ~/.ssh/hostachy_deploy
EOF
# Au premier clonage, ssh affiche l'empreinte de github.com : la comparer à
# celle que GitHub publie (docs.github.com, « GitHub's SSH key fingerprints »)
# AVANT de répondre yes. Jamais de confiance d'office (#1598).

sudo mkdir -p /opt/5hostachy && sudo chown ptressard:ptressard /opt/5hostachy
git clone git@github.com:philippe-tressard/coprofirst.git /opt/5hostachy
```

---

## Étape 4 — Durcissement système

sshd, ufw, fail2ban et mises à jour automatiques sont posés par **un** script,
idempotent, qui juge la configuration **effective** (`sshd -T`, `ufw show added`,
`fail2ban-client`, `apt-config dump`) et jamais le fichier posé :

```bash
sudo bash /opt/5hostachy/scripts/installation/durcir-noeud.sh --etat       # lecture seule
sudo bash /opt/5hostachy/scripts/installation/durcir-noeud.sh --appliquer  # pose ce qui manque
```

| | Ce qui est posé |
|---|---|
| sshd | `sshd_config.d/01-hostachy-durcissement.conf` : mot de passe et clavier interactif coupés, root refusé, X11 coupé, 3 essais |
| ufw | entrant refusé par défaut ; SSH depuis `192.168.1.0/24` **seulement** (posée en premier), 80/tcp, 443/tcp, 443/udp |
| fail2ban | prison `sshd` : 5 essais, 1 h |
| apt | `20auto-upgrades` : listes et installation chaque jour, origines Debian par défaut |

⚠️ Garder une **seconde session SSH** ouverte jusqu'à la fin, et vérifier qu'une
nouvelle connexion par clé passe. Puis, **depuis le poste**, la preuve par le
comportement — la réponse doit nommer `publickey` **seul** :

```bash
ssh -o BatchMode=yes -o PreferredAuthentications=none -o PubkeyAuthentication=no ptressard@<IP> true
```

> 🔴 **Pourquoi `01-`** (#1918) : l'image pose `50-cloud-init.conf` avec
> `PasswordAuthentication yes`, et sshd retient la **première** valeur lue. Le
> `hardening.conf` d'avril, lu après lui, était sans effet sur les deux nœuds.

Le script n'installe pas le noyau ni le firmware Raspberry Pi : ils sont hors des
origines d'`unattended-upgrades`, C30 le signale, la mise à jour reste manuelle
(skill `infra-rpi`).

---

## Étape 5 — Règle sudo

La **même** règle sudo sur les deux nœuds, posée **depuis le poste**, ce nœud seul :

```bash
bash scripts/installation/durcir-sudoers.sh --noeud <IP> --etat
bash scripts/installation/durcir-sudoers.sh --noeud <IP> --appliquer
```

Mode d'emploi, ordre et garde-fous : l'en-tête du script (#302, #582).

---

## Étape 6 — Le `.env`, recopié de l'autre nœud

Le `.env` **ne s'écrit jamais dans un script**. Il se recopie depuis le nœud en
service, sans passer par le disque du poste :

```bash
# Depuis le poste — <PAIR> : le nœud en service ; <IP> : le nœud réinstallé
ssh ptressard@<PAIR> 'cat /opt/5hostachy/.env' \
  | ssh ptressard@<IP> 'umask 077 && cat > /opt/5hostachy/.env'
```

Puis, **sur le nœud réinstallé**, ajuster ce qui lui est propre et lui donner le
rôle de standby :

```bash
cd /opt/5hostachy
nano .env    # INSTANCE_ID=rpi1|rpi2 · PG_ECOUTE=<IP de CE nœud>
. scripts/lib/lib-env-role.sh && env_role_appliquer .env standby <IP de CE nœud>
chmod 600 .env && ls -l .env   # ptressard:ptressard, -rw-------
```

`env_role_appliquer` pose `ORIGIN` sur l'IP du nœud et `COOKIE_SECURE=false` : la
règle vit dans `scripts/lib/lib-env-role.sh` (#1077), jamais recopiée. La bascule
la rejouera en sens inverse le jour où ce nœud prendra la main.

`PG_REPLICATION_PASSWORD` est **le même** sur les deux nœuds : c'est lui qui ouvre
la copie de l'étape 9. Toute variable vient de `.env.example`, que
`api/tests/test_env_exemple_coherent.py` confronte au code à chaque PR.

---

## Étape 7 — Clé inter-nœuds et épinglage

La bascule, le failover et la reconstruction de la réplique joignent le pair par une
clé dédiée, chez root.

```bash
# Sur le nœud réinstallé (en root)
sudo ssh-keygen -t ed25519 -C "hostachy-bascule" -f /root/.ssh/id_ed25519_bascule -N ""
sudo cat /root/.ssh/id_ed25519_bascule.pub
# → l'ajouter à ~ptressard/.ssh/authorized_keys DU PAIR (et réciproquement :
#   la clé publique du pair, lue chez lui, dans ~ptressard/.ssh/authorized_keys d'ici)

# Épingler la clé d'HÔTE du pair — ici, sur rpi1 (sur rpi2 : 192.168.1.222)
sudo sh -c 'ssh-keyscan -t ed25519 192.168.1.223 2>/dev/null > /root/.ssh/known_hosts_bascule'
sudo ssh-keygen -lf /root/.ssh/known_hosts_bascule
# …et comparer cette empreinte à celle que le pair donne de lui-même, lue SUR lui :
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub        # sur 192.168.1.223

# Tester — exactement les options des scripts (`scripts/lib/lib-ssh-noeuds.sh`)
sudo ssh -i /root/.ssh/id_ed25519_bascule -o BatchMode=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/root/.ssh/known_hosts_bascule -o GlobalKnownHostsFile=/dev/null \
  ptressard@192.168.1.223 "echo ok"
```

> 🔒 **Pourquoi épingler (#1598).** La clé `id_ed25519_bascule` authentifie le
> nœud qui se connecte, jamais celui qui répond. Les scripts d'exploitation
> (`bascule.sh`, `health-watch.sh`, `boot-role-guard.sh`, `check-reliability.sh`,
> `noyau-standby.sh`, `reconstruire-replique.sh`) n'acceptent que la clé d'hôte
> écrite dans `/root/.ssh/known_hosts_bascule` : sans elle, ils **échouent** au lieu
> de parler à quiconque a pris l'IP du pair.
>
> ⚠️ **Un nœud réinstallé change de clé d'hôte** : refaire l'épinglage **sur le
> pair aussi**, empreinte comparée — sinon la bascule de la nuit s'arrête en phase 0
> (« clé d'hôte non épinglée ») et `check-reliability` le signale.

---

## Étape 8 — `.active` : l'actif, c'est l'autre

`.active` contient le nom du nœud **actif**, sur les **deux** nœuds. Sur le nœud
réinstallé, c'est donc le nom du pair :

```bash
ssh ptressard@<PAIR> cat /opt/5hostachy/.active     # ex. rpi2
echo rpi2 > /opt/5hostachy/.active                   # la MÊME valeur
```

C'est ce qui fait de ce nœud un standby aux yeux de `reconstruire-replique.sh`, de
`boot-role-guard.sh` et de `health-watch.sh`.

---

## Étape 9 — La base : réplique du primaire

🔴 **Jamais `docker compose up -d` sur ce nœud** : il démarrerait l'application à
côté de celle du pair (split-brain), et une base **absente** serait initialisée en
primaire **vide** — deux primaires. La base naît d'une **copie** du primaire :

```bash
sudo bash /opt/5hostachy/scripts/exploitation/reconstruire-replique.sh          # simulation : dit ce qu'il ferait
sudo bash /opt/5hostachy/scripts/exploitation/reconstruire-replique.sh --oui    # pg_basebackup, puis démarrage en réplique
```

Le script refuse d'agir sur l'actif, si le `.env` ne désigne pas PostgreSQL
(`DATABASE_URL`), ou si le pair ne porte pas de primaire joignable. Il finit par
« ✓ … est une réplique de …, en continu ».

Les **images** des services applicatifs sont tirées par `auto-deploy.sh` (étape 11)
pour le commit de `main` : elles attendent là, prêtes pour la prochaine bascule.
Les **fichiers** (`uploads`) et l'état WhatsApp arrivent avec la bascule suivante
(`bascule.sh` synchronise les volumes vers le standby).

---

## Étape 10 — Tunnel Cloudflare, installé et ARRÊTÉ

```bash
sudo bash /opt/5hostachy/scripts/installation/install-cloudflared.sh <JETON_DU_TUNNEL>
# Le script démarre le tunnel. Sur un STANDBY, l'arrêter aussitôt : il enverrait du
# trafic public vers un nœud sans application. La bascule le démarrera.
sudo systemctl disable --now cloudflared
```

Le jeton est dans **Cloudflare Zero Trust > Networks > Tunnels > le tunnel >
Ajouter un connecteur** : la longue chaîne `eyJ…` de la commande d'installation,
**pas** l'« ID du tunnel » (`91d1afa9-…`). Le script refuse l'un pour l'autre (#1318).
Le script range le jeton dans `/etc/cloudflared/jeton` (root 600) : l'unité ne porte
que `--token-file`, jamais le jeton (#2115, contrôle C39).
Changer le jeton d'un nœud déjà installé : `scripts/exploitation/changer-jeton-tunnel.sh`,
l'actif d'abord.

---

## Étape 11 — Points d'entrée : crons et unité systemd

Les tâches cron et l'unité systemd attendues **ne sont pas recopiées ici** : elles
vivent dans [`infra/points-entree/`](../infra/points-entree/LISEZMOI.md), seule
source versionnée, que le point 17 du pré-check compare à l'installé (#1049).

| Fichier du dépôt | À poser |
|---|---|
| `infra/points-entree/cron-root.crontab` | `sudo crontab -e` — les lignes actives, à l'identique |
| `infra/points-entree/cron-ptressard.crontab` | `crontab -e` en `ptressard` (propriétaire du clone) |
| `infra/points-entree/hostachy-role-guard.service` | voir ci-dessous |

```bash
sudo cp /opt/5hostachy/infra/points-entree/hostachy-role-guard.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable hostachy-role-guard.service
```

Conformité, **depuis le poste** :
```bash
bash scripts/poste/verifier-points-entree.sh ptressard@<IP>
```

---

## Étape 12 — Retirer la pile de bureau (#1648)

Une image **Desktop** ramène navigateurs, VNC, impression, `rpcbind`/NFS… que rien
dans le projet n'emploie. Le contrôle **C35** le signale ; la liste des paquets
proscrits s'écrit **une fois**, dans `scripts/lib/lib-paquets-proscrits.sh`.

```bash
echo 'APT::Install-Recommends "0";' | sudo tee /etc/apt/apt.conf.d/99-hostachy-sans-recommends
sudo systemctl set-default multi-user.target
# Sur le STANDBY seulement (le script refuse un nœud qui porte l'application).
SIM=1 bash /opt/5hostachy/scripts/exploitation/alleger-noeud.sh   # simulation
sudo bash /opt/5hostachy/scripts/exploitation/alleger-noeud.sh
```

Redémarrer ensuite : c'est aussi la seule façon d'éprouver l'unité
`hostachy-role-guard` (étape 11) sans risque, puisque ce nœud ne sert rien.

---

## Vérification finale

| Fait à constater | Commande |
|---|---|
| Durcissement effectif | `sudo bash /opt/5hostachy/scripts/installation/durcir-noeud.sh --etat` → quatre `CONFORME` |
| Mot de passe SSH refusé | sonde de l'étape 4, depuis le poste → `(publickey)` seul |
| Seule la base tourne ici | `docker ps --format '{{.Names}}'` → `hostachy_postgres`, rien d'autre |
| Réplique en continu | contrôle **C37** au passage suivant de `check-reliability` (Admin › Maintenance) |
| Tunnel arrêté | `systemctl is-active cloudflared` → `inactive` |
| Crons et unité systemd | `bash scripts/poste/verifier-points-entree.sh ptressard@<IP>` (depuis le poste) |
| Les deux nœuds d'accord | `cat /opt/5hostachy/.active` identique sur les deux |
| Bascule possible | la bascule de la nuit passe (journal de `bascule.sh` sur l'actif), puis ce nœud sert le site |

La vraie preuve est la **première bascule** : jusqu'à elle, ce nœud n'a rien servi.

---

## Les deux nœuds perdus

Sans pair en service, il n'y a ni primaire à copier ni `.env` à recopier : la
résidence renaît de la **copie hors site** du poste (`scripts/poste/export-hors-site.sh`,
destination `C:\Backup` par défaut). Son archive `hostachy_backup_*_paris.tar.gz` porte
l'**export vérifié** de la base (`base-export.tar.gz`) et les **fichiers** téléversés
(`uploads/`). Les gestes vivent dans **un** script,
`scripts/exploitation/restaurer-copie-hors-site.sh` (#1921) — le premier nœud renaît
**actif**, le second le rejoint ensuite par la procédure normale.

### Nœud A — il renaît actif

1. **Étapes 1 à 5** telles quelles (système, Docker, clone, durcissement, sudo).
2. **Le `.env`, reconstruit** — il n'y a plus de pair où le recopier :
   ```bash
   cd /opt/5hostachy && cp .env.example .env && chmod 600 .env
   nano .env   # chaque secret depuis le gestionnaire de mots de passe — jamais d'un fichier du poste
   . scripts/lib/lib-env-role.sh && env_role_appliquer .env actif
   ```
   Une `DATABASE_URL` en `postgresql+psycopg://…` : le script refuse sans elle. ⚠️ `SECRET_KEY` doit être **celle d'avant** si elle est
   conservée : une nouvelle ferme toutes les sessions et invalide les liens en attente
   (voulu, mais à savoir) ; les mots de passe des comptes, eux, sont dans la base.
3. **`.active` nomme CE nœud** : `echo rpi1 > /opt/5hostachy/.active` (son propre nom).
4. **L'archive, du poste vers le nœud** — la plus récente qui ne finit pas par `.invalide` ;
   chez la **référence**, celle du registre aussi (`C:\Backup\plateforme\`) :
   ```bash
   scp C:/Backup/hostachy_backup_<AAAAMMJJ_HHMMSS>_paris.tar.gz ptressard@<IP>:/tmp/
   scp C:/Backup/plateforme/plateforme_backup_<AAAAMMJJ_HHMMSS>_paris.tar.gz ptressard@<IP>:/tmp/
   ```
5. **Restaurer**, **avant** de poser les crons (sinon `auto-deploy` démarrerait
   l'application sur une base vide, et le script refuse) :
   ```bash
   sudo bash /opt/5hostachy/scripts/exploitation/restaurer-copie-hors-site.sh /tmp/hostachy_backup_….tar.gz        # dit ce qu'il ferait
   sudo bash /opt/5hostachy/scripts/exploitation/restaurer-copie-hors-site.sh /tmp/hostachy_backup_….tar.gz --oui  # exécute
   ```
   Chez la **référence** (`PLATEFORME_DATABASE_URL` dans le `.env`), ajouter
   `--registre /tmp/plateforme_backup_….tar.gz` : le rôle et la base du registre sont
   créés, puis l'archive y est restaurée et vérifiée (`python -m app.registre.sauvegarde
   restaurer`), **avant** que l'application démarre — son démarrage y inscrirait la
   référence, et la base ne serait plus neuve. Sans cette option, le script **refuse** :
   le registre renaîtrait vide.
   Il refuse si le pair sert encore (un seul nœud perdu : étapes 6 à 9), si un volume
   de base existe déjà ici, si l'application tourne ou si `.active` nomme l'autre.
   Puis : images du commit · base PostgreSQL **neuve** démarrée en primaire · schéma
   courant · **import vérifié** (chaque table relue contre son empreinte) · fichiers
   installés et inventoriés · application démarrée, qui doit répondre 200. Un échec
   laisse l'application **arrêtée** et dit lequel ; l'import étant transactionnel, la
   base ne porte au plus que le schéma.
6. **Tunnel** (étape 10) — mais laissé **actif** : c'est ce nœud qui sert.
7. **Crons et unité systemd** (étape 11), puis l'étape 12.
8. **WhatsApp** : l'appairage n'est pas dans les sauvegardes — Admin › WhatsApp ›
   Statut, un seul essai (voir `.claude/skills/infra-rpi`).
9. `rm /tmp/hostachy_backup_*.tar.gz /tmp/plateforme_backup_*.tar.gz` : l'archive porte
   les données des résidents, celle du registre les contacts des installations.

### Nœud B — il rejoint la paire

La procédure normale, **étapes 1 à 12**, le nœud A tenant le rôle du « pair en
service » : `.env` recopié de A, clé inter-nœuds épinglée **dans les deux sens**
(A a une nouvelle clé d'hôte), réplique par `reconstruire-replique.sh`.

### L'épreuve — à rejouer, pas à croire

Le même script, en mode `--banc`, rejoue **les mêmes gestes** sur un PostgreSQL, un
réseau et des volumes **jetables** (`banc_restau_*`), détruits en sortie — sur le
**standby**, sans sudo, sans toucher à rien de `5hostachy_*` :

```bash
scp C:/Backup/hostachy_backup_<…>_paris.tar.gz ptressard@<standby>:/tmp/
ssh ptressard@<standby> 'bash /opt/5hostachy/scripts/exploitation/restaurer-copie-hors-site.sh --banc /tmp/hostachy_backup_<…>_paris.tar.gz; rm /tmp/hostachy_backup_*.tar.gz'
```

Éprouvé le **14/10/2026** sur rpi2 avec l'archive du jour : 82 tables et 16 869 lignes
importées et vérifiées, 174 fichiers à l'identique, révision 0286, en 26 s — et une
archive altérée (une date d'une table changée) **refusée**. À rejouer après toute
modification du script, de `lib-restauration.sh`, de l'export ou de l'import.

**Le registre** s'éprouve dans le même passage : ajouter
`--registre /tmp/plateforme_backup_<…>_paris.tar.gz` (copiée elle aussi, et effacée en
sortie) — sa base est créée sur le PostgreSQL jetable, puis restaurée et vérifiée (#1972).

---

## Arborescence de référence

```
/opt/5hostachy/                   ← Dépôt git
├── .env                          ← Secrets (non versionné, 600 ptressard)
├── .active                       ← Nom du nœud ACTIF, identique sur les deux
├── docker-compose.yml            ← Seule description des services
├── boot-role-guard.sh            ← Seul relais gardé : l'unité systemd le désigne
├── scripts/
│   ├── exploitation/             ← Lancés par cron/systemd ou à la main sur un nœud
│   ├── installation/             ← durcir-noeud.sh, durcir-sudoers.sh, install-cloudflared.sh
│   ├── lib/                      ← Bibliothèques partagées
│   └── poste/                    ← Lancés depuis le poste (pré-check…)
├── infra/points-entree/          ← Crons et unité systemd attendus (source unique)
├── infra/postgresql/             ← pg_hba.conf, initialisation de la réplication
└── api/ front/ whatsapp-bridge/ docs/

Volumes Docker :
  pg_data   → base PostgreSQL (primaire sur l'actif, réplique sur le standby)
  uploads   → fichiers téléversés (synchronisés vers le standby à la bascule)
  app_data  → état de l'application hors base
  backups   → sauvegardes de 03:00, sur l'actif
  caddy_*   → configuration Caddy
```

---

## Mise à jour courante

Automatique (`auto-deploy.sh`, cron utilisateur). Reprise en main, **sur l'actif
seulement** : `sudo bash /opt/5hostachy/scripts/exploitation/MaJ-Hostachy.sh`.
