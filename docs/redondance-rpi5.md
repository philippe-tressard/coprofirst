# Redondance RPi5 — Bascule quotidienne automatique

> **Statut** : En production depuis avril 2026
>
> **Objectif** : Alternance quotidienne entre deux RPi5 identiques pour équilibrer l'usure et assurer une continuité de service en cas de panne de l'un des deux.

---

## Architecture

```
RPi5 #1 — PhT-RB5 (192.168.1.222)      RPi5 #2 — PhT-RB5i2 (192.168.1.223)
├── Docker Compose (actif J, J+2…)      ├── Docker Compose (actif J+1, J+3…)
├── PostgreSQL primaire                  ├── PostgreSQL réplique (en continu, promue à la bascule)
├── uploads/                             ├── uploads/ (rsync à chaud toutes les nuits)
├── cloudflared (tunnel Cloudflare)      └── cloudflared (tunnel Cloudflare)
└── .active = "rpi1"                         .active = "rpi2"
         ↓
   https://5hostachy.fr  (Cloudflare Zero Trust Tunnel)
```

Un seul RPi est actif à la fois. Le tunnel Cloudflare du RPi actif achemine tout le trafic public.

---

## Scripts d'exploitation

Tous dans `scripts/exploitation/`. **Quand** chacun tourne ne s'écrit pas ici : la
cadence se lit dans [`infra/points-entree/`](../infra/points-entree/LISEZMOI.md),
seule source versionnée des crons et de l'unité systemd, comparée à l'installé par
le point 17 du pré-check. Ce tableau en recopiait une partie, et elle avait dérivé
(#1049).

| Script | Rôle | Lancé par |
|---|---|---|
| `bascule.sh` | Bascule quotidienne rpi1 ↔ rpi2 | cron root, sur chaque RPi |
| `health-watch.sh` | Surveillance et failover automatique | cron root, sur chaque RPi |
| `check-reliability.sh` | Contrôles de fiabilité, alerte e-mail sur `FAIL` | cron root, sur chaque RPi |
| `maintenance.sh` | Purges, rotation des logs | cron root, sur chaque RPi |
| `auto-deploy.sh` | Déploiement (actif) ou alignement du code et des images (standby) | cron `ptressard`, sur chaque RPi |
| `boot-role-guard.sh` | Garde-fou anti-split-brain au démarrage | unité `hostachy-role-guard.service` |
| `MaJ-Hostachy.sh` | Reprise en main d'une mise en production — le même geste qu'auto-deploy, verrous posés sur les deux nœuds | Manuel, `sudo`, sur l'actif |
| `changer-jeton-tunnel.sh` | Rotation du jeton du tunnel Cloudflare (refuse ce qui n'est pas un jeton, l'éprouve sur l'actif avant de l'installer) ; `--migrer` le range dans `/etc/cloudflared/jeton` (root 600) sans le changer | Manuel, `sudo`, l'actif puis le secours (`--migrer` : le secours d'abord) |

---

## Bascule quotidienne (`bascule.sh`)

Tourne chaque nuit sur chaque RPi (heure : `infra/points-entree/`). Le RPi qui n'est **pas** actif (flag `.active`) sort immédiatement. Le RPi actif exécute la séquence complète :

### Séquence (7 phases)

| Phase | Action |
|---|---|
| 0 | Pre-flight : peer joignable, espace disque, lock bascule posé |
| 1 | Sync uploads à chaud (prod reste UP) — ni la base, ni l'état WhatsApp |
| 2 | Arrêt cloudflared local + conteneurs locaux, puis copie de l'état WhatsApp **à froid** (à chaud, il arrivait déchiré : panne du 24/07/2026) |
| 3 | La réplique du pair rattrape le primaire local, qui s'arrête |
| 4 | La réplique du pair est **promue** primaire |
| 5 | Démarrage conteneurs peer + health check API (60s max) |
| 6 | Démarrage cloudflared peer + vérification URL publique (90s max) |
| 7 | Mise à jour flags `.active` ; l'ancien primaire est reconstruit en réplique (`reconstruire-replique.sh`) |

### Rollback automatique

En cas d'échec phases 2–6 : les conteneurs locaux sont relancés, cloudflared local redémarré, conteneurs peer arrêtés, email d'alerte envoyé.

### Email d'alerte

Envoyé via **Python3 standalone** (lit la config SMTP depuis `.env`) — fonctionne même si les conteneurs sont arrêtés.

---

## Surveillance et failover automatique (`health-watch.sh`)

Tourne sur les deux RPi, à la cadence de `infra/points-entree/`. Chaque RPi détermine son rôle au runtime via `.active`.

### Comportement

**RPi actif** → sort immédiatement sans action. Si ce RPi est gelé, il ne peut plus exécuter le script — c'est le standby qui prend le relais.

**RPi standby** → surveille l'URL publique `https://5hostachy.fr/api/health` :

1. Si HTTP 200 → rien à faire, reset cooldown email
2. Si pas 200 → attend 30s, re-vérifie (évite les faux positifs sur micro-coupure réseau)
3. Si toujours HS, et si les sondes LAN + edge désignent bien le nœud actif → **failover automatique**
   (l'ordre vit dans `scripts/lib/lib-failover.sh`, `prendre_la_main` ; il ne se recopie pas ici) :
   - Pose `.bascule-lock` (bloque la bascule cron en parallèle)
   - `systemctl start cloudflared` **en premier** — s'il ne démarre pas, le failover est
     **abandonné** : aucun conteneur démarré, l'actif n'est pas démoté, alerte avec la
     cause relevée dans le journal (#1318 : un jeton invalide sur les deux nœuds avait
     produit deux bascules inutiles et une API servie sur une base périmée)
   - **Décide** d'après le rôle de la base locale (`decider_prise_de_main`) : une base
     qu'on ne peut pas prendre ne démarre jamais, et rien ne démarre
   - **Isole** l'ancien actif, sous son verrou de déploiement : `.active` réécrit
     d'abord, puis l'application et la base arrêtées par leurs listes de services
   - **Promeut** la réplique locale, puis démarre l'application, `.env` mis au rôle
     actif (`env_role_appliquer`)
   - Re-vérifie l'URL publique, et envoie un email d'alerte (cooldown 30 min)

### Garanties

- **Pas de split-brain** : seul le standby peut déclencher un failover
- **Anti faux-positifs** : double vérification espacée de 30s
- **Anti spam email** : cooldown 30 min entre deux alertes

### Logs

```bash
tail -f /var/log/hostachy-health-watch.log
```

---

## La base : une réplique en continu (DI-7b, #1781)

La base ne se copie pas à la bascule : le standby porte une **réplique en continu**
du primaire PostgreSQL (port lié à l'IP du LAN, `infra/postgresql/pg_hba.conf`).

| Geste | Ce qui arrive à la base |
|---|---|
| Bascule, phases 3-4 | la réplique du pair rattrape, le primaire local s'arrête, le pair est **promu** |
| Bascule, phase 7 | l'ancien primaire est reconstruit en réplique (`reconstruire-replique.sh`) |
| Failover (`health-watch.sh`) | l'ancien actif est isolé, la réplique **promue** — à jour, au retard près |
| Retour d'un nœud (`boot-role-guard.sh`) | sa base, si elle est encore primaire, est isolée puis reconstruite en réplique |
| Surveillance | **C37** et le point 22 : rôle, réplication, retard |

Le standby porte donc **un conteneur** (`hostachy_postgres`) : les comptes « le standby
n'en porte aucun » ne comptent que ceux de l'application (`lib-applicatifs.sh`).

## Délais de rétablissement

| Scénario | Délai |
|---|---|
| Bascule quotidienne réussie | ~40s (fenêtre sans trafic public) |
| Panne RPi actif → failover automatique | une période de `health-watch.sh`, plus ~50s de vérification et de démarrage |
| Panne RPi actif → intervention manuelle | voir ci-dessous |

---

## Intervention manuelle (site HS)

La procédure ne s'écrit pas ici : elle vit dans `CLAUDE.md` (« Infrastructure —
l'essentiel », **Site HS**) et dans la skill `infra-rpi`, tenues à jour avec les
scripts, comme `docs/deploy-rpi5-auto.md` le fait depuis #1049. Une copie de cette
procédure a dérivé ici (#2918) : elle démarrait l'application sans promotion.

Ce qu'elle garantit, et pourquoi on ne l'improvise pas :

- **Avant de suspecter un nœud** : deux sondes indépendantes (`curl
  http://<actif>/api/health` depuis l'autre RPi) — une panne du chemin public ne se
  répare pas par une bascule ;
- la base du standby est une **réplique** : elle ne sert qu'une fois **promue**,
  par `lib-promotion.sh` (`decider_prise_de_main`), jamais démarrée vide ;
- les services se démarrent **par leurs listes** (`$SERVICE_BASE`, puis
  `$SERVICES_APPLICATIFS`, `lib-applicatifs.sh`), après `env_role_appliquer .env
  actif` ; jamais une commande compose sans liste de services ;
- un nœud revenu ne se relance jamais en primaire : sa base est isolée puis
  reconstruite en réplique (`boot-role-guard.sh`, `reconstruire-replique.sh`) ;
  **C37** et le point 22 du pré-check disent deux primaires.

---

## Flag `.active`

Fichier `/opt/5hostachy/.active` présent sur les deux RPi. Contient `rpi1` ou `rpi2`.

- La bascule quotidienne le met à jour sur les **deux** RPi simultanément
- Le health-watch le met à jour **uniquement sur le RPi standby** lors d'un failover
- Si absent : `bascule.sh` et `health-watch.sh` s'arrêtent sans action

---

## L'onglet Maintenance sur la référence (sorti du manuel, #2924)

Le manuel est servi par toute installation : il ne décrit plus ce qui n'existe que
sur la référence. Voici comment l'onglet *Admin › Exploitation › Maintenance* se
lit sur ses deux Raspberry Pi.

- **Tâches planifiées** — une ligne par tâche, détaillée nœud par nœud (`RPI1`,
  `RPI2`, d'après `INSTANCE_ID`). La **copie hors site** fait exception : lancée
  depuis le poste et non par un nœud, elle n'a qu'une ligne, qui nomme le nœud
  d'où vient l'archive du jour. La bascule, la sauvegarde et l'agrégation de
  télémétrie ne tournent que sur le nœud **actif** : après un basculement
  automatique, un nœud peut ne pas avoir été actif deux nuits de suite, et sa
  ligne dit alors *Pas actif à l'heure*, en gris — la tâche a tourné sur l'autre.
  Elle ne passe au rouge que si la tâche elle-même ne tourne plus, ou si le nœud
  se tait plus de trois nuits.
- **Contrôles de fiabilité** — `check-reliability`, toutes les 15 minutes sur
  chaque nœud (site public, split-brain, tunnel, parité du code, disque, mises à
  jour système…). Les constats qui portent sur les deux nœuds s'affichent une
  fois, sous **Les deux nœuds**, rapportés par le nœud actif.
- **Audit de sécurité nocturne** — `audit-securite`, chaque nuit sur chaque nœud ;
  les sondes de scanners et les forçages de comptes ne se lisent que sur l'actif.
- **Version au pied de page** — courte, suivie du nœud qui sert : « v3.122.5 · RPi1 ».
- **Archives de conservation des affaires** — la sauvegarde hors site les copie
  sur le poste, sous `archives-affaires/` de sa destination
  (`scripts/poste/export-hors-site.sh` : `/Volumes/Data/Backup` sur le Mac,
  `C:\Backup` sous Windows) ; le serveur retire sa copie 30 jours après.
- **Bâtiments** — la légende du kanban de l'accueil et les périmètres disent
  « Bât. 1 (D) » à « Bât. 4 (A) » : la lettre de l'acte, saisie dans *Imports ›
  État descriptif*.

Sur une installation à **un seul serveur** sans `INSTANCE_ID`, ce que le code
affiche (lu dans le code, non observé) : les tâches enregistrent un nœud vide —
la colonne *Nœud* dit « non enregistré », sans sous-ligne par nœud ; les cartes
*Contrôles de fiabilité* et *Audit de sécurité nocturne* disent *Aucun rapport
reçu* (leurs scripts sont des crons de la référence, `infra/points-entree/`, que
l'installation standard ne pose pas) ; le bloc **Les deux nœuds** n'apparaît pas.

## Adresses réseau

| Machine | Hostname | IP locale | Rôle |
|---|---|---|---|
| RPi5 #1 | PhT-RB5 | 192.168.1.222 | actif ou standby : `.active` le dit |
| RPi5 #2 | PhT-RB5i2 | 192.168.1.223 | actif ou standby : `.active` le dit |

Accès SSH : `ssh ptressard@192.168.1.222` (ou `.223`)
Projet : `/opt/5hostachy/`
Logs bascule : `/var/log/hostachy-bascule.log`
Logs health-watch : `/var/log/hostachy-health-watch.log`
