# Installer CoproFirst — le déploiement standard

Ce dossier décrit une **installation CoproFirst** à partir des images publiées,
sans rien construire sur la machine. C'est l'installation d'une **réplique** :
elle suit les versions promues sur la branche `replica`
(`specs/architecture/multi-coproprietes.md` §4.10).

> 5Hostachy, la résidence où le produit est né, en est le **maître** : ses deux
> Raspberry Pi suivent `main` et portent leur propre outillage de haute
> disponibilité (bascule, `health-watch`, crontabs — `scripts/exploitation/`,
> `infra/points-entree/`). Cet outillage reste dans le dépôt et **ne fait pas
> partie** d'une installation standard : rien ici n'en a besoin.

⚠️ **Aujourd'hui, une installation sert UNE copropriété.** Plusieurs copropriétés
isolées dans une même installation, c'est la phase 2 du chantier (en cours).

**Une installation tient sur un seul serveur** (cloud ou hébergeur — décision D15) :
il n'y a ni nœud de secours ni bascule. Une mise à jour coupe le service le temps
de redémarrer, et une panne du serveur l'interrompt jusqu'à sa remise en route.
Le filet, ce sont le retour à la version précédente et une sauvegarde copiée
**hors de la machine** (voir « Sauvegarder »).

## Ce qu'il faut

- Docker et Docker Compose **2.24 ou plus récent** (pour `!reset`) ;
- une machine `amd64` ou `arm64` ;
- un accès HTTPS devant le port 80 : Caddy écoute en HTTP et suppose un frontal
  (tunnel ou proxy inverse) qui termine le TLS. Le `Caddyfile` livré fait
  confiance à l'en-tête `Cf-Connecting-Ip` d'un tunnel Cloudflare : l'adapter si
  le frontal est un autre ;
- une adresse d'envoi de courriels (SMTP).

## Les fichiers

Chaque version promue publie, dans ses notes de version (onglet *Releases* du
dépôt), l'archive `coprofirst-deploiement-X.Y.Z.tar.gz`. Elle contient,
**dans l'état exact de cette version** :

| Fichier | Rôle |
|---|---|
| `docker-compose.yml` | les services, volumes et variables — le même que le maître |
| `deploiement/standard/compose.images.yml` | remplace chaque construction par l'image publiée |
| `Caddyfile` | le frontal HTTP (en-têtes de sécurité, routage `/api`) |
| `.env.example` | le gabarit de configuration, commenté |
| `deploiement/standard/LISEZMOI.md` | ce mode d'emploi |
| `deploiement/standard/mise-a-jour.sh` | la mise à jour nocturne, réversible seule |
| `deploiement/standard/postgresql/pg_hba.conf` | qui peut se connecter à PostgreSQL, s'il est choisi : l'API seule |
| `LICENSE` | AGPL-3.0-or-later |

## Installer

1. Décompresser l'archive dans un dossier dédié, par exemple `/opt/coprofirst`.
2. `cp .env.example .env`, puis renseigner au moins `SECRET_KEY` (32 caractères
   au minimum), `WHATSAPP_API_KEY` (16 au minimum, même si le service WhatsApp
   n'est pas employé), `ORIGIN` (l'adresse publique) et la configuration SMTP.
   ⚠️ Le site ne répond qu'au nom de `ORIGIN` : un autre nom reçoit une erreur 421 (« requête mal dirigée »). Un second nom — un alias, un ancien domaine — se
   déclare dans `HOTES_COPROPRIETE`, séparé par des virgules.
3. Ajouter **la version à installer** dans `.env` :
   ```
   COPROFIRST_VERSION=2.119.1
   ```
4. Vérifier la provenance des images (facultatif, recommandé) :
   ```bash
   gh attestation verify oci://ghcr.io/philippe-tressard/coprofirst-api:2.119.1 --owner philippe-tressard
   ```
5. Démarrer :
   ```bash
   docker compose -f docker-compose.yml -f deploiement/standard/compose.images.yml up -d
   ```
6. Le premier lancement crée un compte administrateur dont le mot de passe
   s'affiche une fois dans les journaux :
   ```bash
   docker compose logs api | grep "ADMIN INITIAL"
   ```
   Le changer dès la première connexion, puis régler l'identité de la résidence
   (nom, adresse, logo) dans l'administration. *Administration › Maintenance* dit
   « Réplique — suit replica » : la surcouche pose ce rôle d'office. Pour y voir si
   la version est à jour, activer le service *Vérification de la version*.

## Mettre à jour

Changer `COPROFIRST_VERSION` dans `.env` pour la version promue suivante, puis :

```bash
docker compose -f docker-compose.yml -f deploiement/standard/compose.images.yml pull
docker compose -f docker-compose.yml -f deploiement/standard/compose.images.yml up -d
```

Les migrations de la base s'appliquent au démarrage de l'API. Lire d'abord les
notes de la version : elles listent les migrations et les réglages ajoutés ou
retirés.

**Revenir à la version précédente** : remettre l'ancienne `COPROFIRST_VERSION`
et relancer `up -d`. C'est sûr parce qu'une migration reste compatible avec la
version précédente du code (on ajoute, puis on retire à la version suivante —
`api/tests/test_migrations_compatibles.py`).

## La mise à jour automatique, chaque nuit

`deploiement/standard/mise-a-jour.sh` suit la branche `replica` : quand une
version y est promue, il l'installe, et revient seul en arrière si elle ne
démarre pas. Il ne touche **à rien** tant que tout n'est pas prêt :

1. il lit la version de `replica` et décide : déjà à jour, épinglée, trop tôt
   (échelonnement), ou à installer ;
2. il télécharge l'archive de la version, tire ses images et vérifie leur
   signature — le site tourne toujours ;
3. il arrête l'API, **sauvegarde** les volumes dans `COPROFIRST_SAUVEGARDES`
   et vérifie la sauvegarde (archive lisible, intégrité de la base) ;
4. il pose les fichiers et la version, redémarre, et sonde `/api/health` ;
5. en échec, il revient aux fichiers et aux images précédents — la base
   migrée se sert sans migrer —, et si la santé reste mauvaise, il **restaure
   la sauvegarde** ;
6. il rend compte à l'administration (*Administration › Maintenance*), et le
   contrôle de 06:00 envoie un courriel si la nuit a échoué.

**Réglages** (dans `.env`) :

| Réglage | Rôle |
|---|---|
| `COPROFIRST_SAUVEGARDES` | **obligatoire** — le dossier des sauvegardes d'avant mise à jour, à monter **hors de la machine** : sans lui, rien n'est installé |
| `MAINTENANCE_KEY` | la clé qui permet au script de rendre compte à l'administration |
| `COPROFIRST_DELAI_JOURS` | `0` pour l'installation pilote (dès la promotion), `1` par défaut (la nuit suivante) |
| `COPROFIRST_EPINGLEE` | `oui` pour rester sur la version installée |
| `COPROFIRST_SIGNATURE` | `exigee` pour refuser une image dont la signature n'a pas pu être vérifiée (il faut `gh`, connecté) ; `si-possible` par défaut |

**Le lancer chaque nuit**, à une heure creuse — une mise à jour coupe le site
le temps de redémarrer (crontab de l'utilisateur qui pilote Docker) :

```
30 4 * * * /opt/coprofirst/deploiement/standard/mise-a-jour.sh >> /var/log/coprofirst-maj.log 2>&1
```

## Choisir PostgreSQL plutôt que SQLite

Par défaut, la base est un fichier **SQLite** : rien à installer. **PostgreSQL**
— celui du maître depuis le 10/10/2026 — s'allume dans `.env`, **avant le
premier démarrage** :

```
COMPOSE_PROFILES=postgresql
POSTGRES_PASSWORD=<openssl rand -hex 32>
DATABASE_URL=postgresql+psycopg://coprofirst:<POSTGRES_PASSWORD>@postgres:5432/coprofirst
```

Le premier démarrage crée la base et y pose le schéma courant. Le serveur
n'écoute que sur le réseau de Compose : la surcouche retire son port et le
réglage de réplication du maître (une réplique n'a pas de second nœud).

La mise à jour nocturne le sait : sous PostgreSQL, elle **exporte** la base avant
d'installer (`…-base.tar.gz`, à côté de l'archive des volumes, dans
`COPROFIRST_SAUVEGARDES`), la **réimporte dans une base jetable** pour la déclarer
bonne, et, si la version précédente elle-même ne repart pas, la restaure.

Passer une installation **existante** de SQLite à PostgreSQL est une opération,
pas un réglage : l'API arrêtée, exporter la base
(`docker compose … run --rm --no-deps --entrypoint python api -m app.utils.export_copropriete exporter sqlite:////app/data/app.db /backups/vers-postgresql.tar.gz`),
allumer le profil comme ci-dessus, poser le schéma (`… -m app.utils.schema_initial`),
importer (`… -m app.utils.export_copropriete importer /backups/vers-postgresql.tar.gz env:DATABASE_URL`),
puis démarrer. L'import vérifie chaque table et refuse au moindre écart.

## Sauvegarder

Les données vivent dans des volumes Docker : `app_data` (la base SQLite),
`pg_data` (la base PostgreSQL, si elle est choisie), `uploads` (les fichiers),
`whatsapp_auth`, et `backups`, où l'application range ses sauvegardes
planifiées (Administration › Sauvegarde). Copier ces archives **hors de la
machine** : une sauvegarde qui vit à côté de ce qu'elle protège disparaît avec.

🔴 Sous SQLite, ne jamais ouvrir le fichier de la base depuis un autre processus
tant que l'API tourne, même en lecture : arrêter l'API d'abord (`docker compose
stop api`). Sous PostgreSQL, ne jamais copier le volume `pg_data` d'un serveur
qui tourne : passer par l'export, comme la mise à jour.
