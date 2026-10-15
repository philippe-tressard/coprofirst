# Redondance RPi5 — Bascule quotidienne automatique

> **Statut** : En production depuis avril 2026
>
> **Objectif** : Alternance quotidienne entre deux RPi5 identiques pour équilibrer l'usure et assurer une continuité de service en cas de panne de l'un des deux.

---

## Architecture

```
RPi5 #1 — PhT-RB5 (192.168.1.222)      RPi5 #2 — PhT-RB5i2 (192.168.1.223)
├── Docker Compose (actif J, J+2…)      ├── Docker Compose (actif J+1, J+3…)
├── SQLite app.db                        ├── SQLite app.db (synchro via rsync à la bascule)
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
| `maintenance.sh` | Purges, VACUUM API arrêtée, rotation des logs | cron root, sur chaque RPi |
| `auto-deploy.sh` | Déploiement (actif) ou alignement du code et des images (standby) | cron `ptressard`, sur chaque RPi |
| `boot-role-guard.sh` | Garde-fou anti-split-brain au démarrage | unité `hostachy-role-guard.service` |
| `MaJ-Hostachy.sh` | Reprise en main d'une mise en production — le même geste qu'auto-deploy, verrous posés sur les deux nœuds | Manuel, `sudo`, sur l'actif |
| `changer-jeton-tunnel.sh` | Rotation du jeton du tunnel Cloudflare (refuse ce qui n'est pas un jeton, l'éprouve sur l'actif avant de l'installer) | Manuel, `sudo`, l'actif puis le secours |

---

## Bascule quotidienne (`bascule.sh`)

Tourne à 02h00 sur chaque RPi. Le RPi qui n'est **pas** actif (flag `.active`) sort immédiatement. Le RPi actif exécute la séquence complète :

### Séquence (7 phases)

| Phase | Action |
|---|---|
| 0 | Pre-flight : peer joignable, espace disque, lock bascule posé |
| 1 | Sync uploads + WhatsApp auth à chaud (prod reste UP) |
| 2 | Arrêt cloudflared local + conteneurs locaux |
| 3 | WAL checkpoint SQLite + integrity check DB locale |
| 4 | Rsync DB → peer + integrity check sur peer |
| 5 | Démarrage conteneurs peer + health check API (60s max) |
| 6 | Démarrage cloudflared peer + vérification URL publique (90s max) |
| 7 | Mise à jour flags `.active` |

### Rollback automatique

En cas d'échec phases 2–6 : les conteneurs locaux sont relancés, cloudflared local redémarré, conteneurs peer arrêtés, email d'alerte envoyé.

### Email d'alerte

Envoyé via **Python3 standalone** (lit la config SMTP depuis `.env`) — fonctionne même si les conteneurs sont arrêtés.

---

## Surveillance et failover automatique (`health-watch.sh`)

Tourne toutes les **5 minutes** sur les deux RPi. Chaque RPi détermine son rôle au runtime via `.active`.

### Comportement

**RPi actif** → sort immédiatement sans action. Si ce RPi est gelé, il ne peut plus exécuter le script — c'est le standby qui prend le relais.

**RPi standby** → surveille l'URL publique `https://5hostachy.fr/api/health` :

1. Si HTTP 200 → rien à faire, reset cooldown email
2. Si pas 200 → attend 30s, re-vérifie (évite les faux positifs sur micro-coupure réseau)
3. Si toujours HS, et si les sondes LAN + edge désignent bien le nœud actif → **failover automatique** :
   - Pose `.bascule-lock` (bloque la bascule cron en parallèle)
   - `systemctl start cloudflared` **en premier** — s'il ne démarre pas, le failover est
     **abandonné** : aucun conteneur démarré, l'actif n'est pas démoté, alerte avec la
     cause relevée dans le journal (#1318 : un jeton invalide sur les deux nœuds avait
     produit deux bascules inutiles et une API servie sur une base périmée)
   - Met `.env` en mode production (`ORIGIN=https://5hostachy.fr`)
   - `docker compose up -d`
   - Démote l'ancien actif, met à jour `.active`
   - Re-vérifie l'URL publique après 20s
   - Envoie un email d'alerte (cooldown 30 min)

### Garanties

- **Pas de split-brain** : seul le standby peut déclencher un failover
- **Anti faux-positifs** : double vérification espacée de 30s
- **Anti spam email** : cooldown 30 min entre deux alertes

### Logs

```bash
tail -f /var/log/hostachy-health-watch.log
```

---

## Sous PostgreSQL : la réplique en continu (DI-7b, #1781)

Quand `.env` désigne PostgreSQL (après la bascule des données, DI-7c), la base ne se
copie plus à la bascule : le standby porte une **réplique en continu** du primaire
(port lié à l'IP du LAN, `infra/postgresql/pg_hba.conf`).

| Geste | SQLite | PostgreSQL |
|---|---|---|
| Bascule, phases 3-4 | `wal_checkpoint`, `integrity_check`, copie `app.db` vers le pair | la réplique du pair rattrape, le primaire local s'arrête, le pair est **promu** |
| Bascule, phase 7 | — | l'ancien primaire est reconstruit en réplique (`reconstruire-replique.sh`) |
| Failover (`health-watch.sh`) | base du standby = dernière copie de la nuit | l'ancien actif est isolé, la réplique **promue** — à jour, au retard près |
| Retour d'un nœud (`boot-role-guard.sh`) | arrêt de ses conteneurs | sa base, si elle est encore primaire, est isolée puis reconstruite en réplique |
| Surveillance | point 4 (WAL d'`app.db`) | **C37** et le point 22 : rôle, réplication, retard |

Le standby porte donc **un conteneur** (`hostachy_postgres`) : les comptes « le standby
n'en porte aucun » ne comptent que ceux de l'application (`lib-applicatifs.sh`).

## Délais de rétablissement

| Scénario | Délai |
|---|---|
| Bascule quotidienne réussie | ~40s (fenêtre sans trafic public) |
| Panne RPi actif → failover automatique | < 5 min (health-watch détecte en ≤ 5 min + 50s de vérification/démarrage) |
| Panne RPi actif → intervention manuelle | voir ci-dessous |

---

## Intervention manuelle (site HS)

### 1. Identifier le RPi actif

```bash
cat /opt/5hostachy/.active          # sur rpi1 ou rpi2
```

### 2. Si le RPi actif est injoignable → basculer sur le standby

```bash
ssh ptressard@192.168.1.222         # ou .223 selon lequel répond
cd /opt/5hostachy

# Passer en mode prod
sed -i "s|^ORIGIN=.*|ORIGIN=https://5hostachy.fr|" .env
sed -i "/^COOKIE_SECURE=/d" .env

# Démarrer
docker compose up -d
sudo systemctl start cloudflared

# Mettre à jour le flag
echo "rpi1" > .active               # adapter selon le RPi
```

### 3. Vérifier

```bash
curl -s https://5hostachy.fr/api/health
```

### 4. Après retour du RPi défaillant

La bascule automatique reprendra le soir à 02h00 si les deux RPi sont joignables. Vérifier que les données ne divergent pas (la DB du failover est celle du standby au moment du failover — pas de perte si le RPi actif était gelé depuis peu).

---

## Flag `.active`

Fichier `/opt/5hostachy/.active` présent sur les deux RPi. Contient `rpi1` ou `rpi2`.

- La bascule quotidienne le met à jour sur les **deux** RPi simultanément
- Le health-watch le met à jour **uniquement sur le RPi standby** lors d'un failover
- Si absent : `bascule.sh` et `health-watch.sh` s'arrêtent sans action

---

## Adresses réseau

| Machine | Hostname | IP locale | Rôle |
|---|---|---|---|
| RPi5 #1 | PhT-RB5 | 192.168.1.222 | Actif les jours pairs |
| RPi5 #2 | PhT-RB5i2 | 192.168.1.223 | Actif les jours impairs |

Accès SSH : `ssh ptressard@192.168.1.222` (ou `.223`)
Projet : `/opt/5hostachy/`
Logs bascule : `/var/log/hostachy-bascule.log`
Logs health-watch : `/var/log/hostachy-health-watch.log`
