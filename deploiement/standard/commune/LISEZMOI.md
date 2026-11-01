# Une installation commune à plusieurs copropriétés

Un seul code, deux façons d'héberger une copropriété (spec
`specs/architecture/multi-coproprietes.md`, D27 et §4.1 bis) :

- **sa propre installation** — comme 5Hostachy : on arrive par son URL,
  directement sur la connexion. Rien de ce dossier ne sert ;
- **une installation commune** : plusieurs copropriétés, chacune dans sa base,
  servies par les mêmes conteneurs. Ce dossier décrit cette seconde façon.

> Livré en deux lots : le premier (#1894) pose le registre des copropriétés, leurs
> adresses et l'aiguillage ; le second (#2053) les sert réellement — une base
> préparée par copropriété au démarrage, le rendu serveur selon l'hôte, les
> commandes qui nomment leur copropriété, l'outillage « créer une copropriété »,
> les sauvegardes et la mise à jour nocturne par base.

## Les adresses

L'hôte **commun** est celui de l'`ORIGIN` de l'installation (son URL publique).
Avec `ORIGIN=https://exemple.fr` :

| On arrive par | On aboutit à |
|---|---|
| le domaine propre d'une copropriété (`residence-des-chenes.fr`) | son écran de connexion |
| son **adresse dérivée** `69003-residence-des-chenes.exemple.fr` | son écran de connexion |
| `exemple.fr` | l'écran d'**aiguillage** : code postal + nom, puis redirection |
| `exemple.fr/69003-residence-des-chenes` | une redirection vers l'adresse de la copropriété |
| un **ancien** alias `69003-chenes.exemple.fr/…` | une redirection (308) vers l'adresse actuelle, chemin compris |

L'**alias** se forme du code postal et du nom : accents, casse, ponctuation et
espaces normalisés, jamais de `_`. Deux copropriétés au même alias sont refusées ;
l'hébergeur leur fait choisir un nom qui les distingue. L'hôte commun **ne sert
aucune donnée** : toute route de copropriété y répond 421, et l'aiguillage exige la
correspondance exacte, sans liste ni suggestion, avec un nombre de tentatives
limité. Une copropriété **suspendue** n'est jamais une destination.

## Démarrer l'installation

Une installation commune se lance avec une surcouche de plus, qui fait servir au
front l'hôte que le visiteur a demandé (le front ne fixe aucune adresse, l'hôte se lit
dans la requête) :

```bash
docker compose -f docker-compose.yml -f deploiement/standard/compose.images.yml \
    -f deploiement/standard/commune/compose.commune.yml up -d
```

## Ajouter une copropriété — `creer-copropriete.sh`

Depuis le dossier de l'installation, une fois la déclaration posée (ci-dessous) :

```bash
bash deploiement/standard/commune/creer-copropriete.sh tilleuls \
    --code-postal 75015 --nom "Les Tilleuls" --expediteur contact@exemple.fr
```

Il valide la copropriété contre la déclaration en service (un alias déjà pris est
refusé avant tout geste), crée son rôle et sa base PostgreSQL — fermée aux autres
rôles —, écrit l'URL de la base et un secret neuf dans `.env`, **recrée l'API** pour
qu'elle les lise (quelques secondes d'interruption pour toutes les copropriétés),
puis prépare la base, y pose l'administrateur initial — son mot de passe temporaire
s'affiche : à transmettre à l'administrateur de la copropriété —, crée son dossier
de fichiers et, en dernier, l'ajoute à la déclaration. Rien n'est réutilisé en
silence : un rôle, une base ou une variable déjà là arrêtent tout.

## Déclarer les copropriétés

1. Copier `coproprietes.exemple.json` dans le volume des données de l'API
   (par exemple `/app/data/coproprietes.json`) et le remplir — une entrée par
   copropriété :

   | Champ | Rôle |
   |---|---|
   | `identifiant` | interne, stable : minuscules, chiffres, tirets ; ne change jamais |
   | `code_postal`, `nom` | forment l'alias, donc l'adresse dérivée |
   | `anciens_alias` | les alias d'avant un changement de nom : ils redirigent |
   | `hotes` | ses domaines propres, s'il y en a — le premier est son adresse |
   | `suspendue` | `true` : plus une destination de l'aiguillage |
   | `base`, `secret` | le **nom** des variables d'environnement qui portent l'URL de sa base et son secret de signature (32 caractères au moins) — jamais leur valeur |
   | `racine_fichiers` | le dossier de ses fichiers, distinct pour chacune |
   | `expediteur`, `nom_expediteur` | l'adresse qui expédie ses courriels |

2. Dans le `.env` : `ORIGIN` (l'hôte commun), `COPROPRIETES_FICHIER` (le chemin du
   fichier dans le conteneur), et les variables nommées par `base` et `secret`
   (`openssl rand -hex 32` pour un secret).
3. Vérifier, avant de servir :

   ```bash
   docker compose exec -u app api python -m app.installation_commune.verifier
   ```

   Il liste chaque copropriété, son alias et son adresse — ou les règles violées.
   Une déclaration invalide **ne sert rien** (503) : l'API ne se replie jamais sur
   la copropriété de sa configuration, qu'elle servirait alors à tous les hôtes.
4. Importer la garde des pages dans le `Caddyfile`, en tête du dernier `handle`
   (le mode d'emploi est en tête de `garde-des-pages.caddy`), et **les fichiers**
   (`import commune/fichiers.caddy`) dans le bloc de site, AVANT les blocs
   `handle /uploads/…` : sur une installation commune, c'est l'API qui sert les
   fichiers de chaque copropriété, à une session de cette copropriété.

Le fichier est relu quand il change. Une copropriété **neuve** demande pourtant de
recréer l'API, qui ne lit son environnement — l'URL de la base, le secret —
qu'au démarrage : c'est ce que fait `creer-copropriete.sh`, dans le bon ordre.

## Ce qui vaut pour chaque copropriété

| Sujet | Comportement |
|---|---|
| **Démarrage** | chaque base déclarée est attendue, migrée, ou reçoit le schéma si elle est neuve (`app/utils/preparer_bases`) ; une base illisible ou en échec **ne bloque pas les autres**, et sa ligne le dit dans `docker compose logs api` |
| **Une base qui n'est pas prête** | son hôte seul reçoit 503 (« momentanément indisponible ») ; ses tâches planifiées sont sautées ; elle est relue toutes les 30 s — réparée, elle est servie sans redémarrage |
| **Santé** (`/api/health`) | 200 `ok` si toutes sont servies, 200 `degrade` si l'une ne l'est pas, 503 si aucune — ni nom ni nombre : la route répond à tout hôte |
| **Commandes** | `python -m app.seed`, `app.demo.charger`, `export_copropriete verifier` exigent `--copropriete <identifiant>` et refusent sans lui ; aucune ne se replie sur la copropriété de la configuration |
| **Fichiers** (`/uploads/*`) | servis par l'API depuis la racine de la copropriété que l'hôte désigne, à une session de celle-ci ; `prive/` et `annonces-hall/` jamais en direct, comme sur une installation propre |
| **Adresse publique** | celle de la copropriété — son domaine, ou son adresse dérivée — pour les liens de ses courriels et ses pages légales ; elle ne se saisit pas (#2058) |
| **Courriels** | chaque copropriété règle son SMTP dans **Admin › Configuration** ; seule son adresse d'expédition déclarée amorce sa base. Les `MAIL_*` du `.env` sont le SMTP de l'**installation** (alertes à l'opérateur), jamais recopiés chez une copropriété (#2058) |
| **Sauvegardes** | archives et exports sous `BACKUP_DIR/coproprietes/<identifiant>/` : une copropriété ne voit ni ne fait tourner celles d'une autre ; heure et nombre de versions se règlent dans sa **Maintenance**, effet dès l'heure suivante |
| **Mise à jour nocturne** | `mise-a-jour.sh` exporte et vérifie **chaque** base avant de rien changer, et les restaure toutes si la santé reste KO ; une déclaration invalide la refuse. Son rapport reste au journal : il n'appartient à aucune copropriété |

## Le nom de domaine — des gestes de l'hébergeur

Un enregistrement DNS **générique** et un certificat **générique** couvrent toutes
les adresses dérivées, sans démarche pour les copropriétés.

**Derrière Cloudflare** (le tunnel des Raspberry Pi) :

```bash
cloudflared tunnel route dns <nom-du-tunnel> "*.exemple.fr"
```

puis, dans la configuration du tunnel, une règle d'entrée `hostname: "*.exemple.fr"`
vers le même service que l'hôte commun. Le certificat universel de Cloudflare
couvre **un** niveau sous la zone : `*.exemple.fr`, pas `*.acces.exemple.fr`.
L'hôte commun est donc la **racine d'une zone** — sinon il faut le certificat
avancé (payant).

**Sans Cloudflare**, Caddy obtient le certificat générique par un **défi DNS** :
l'image doit embarquer le module DNS du fournisseur (`xcaddy build --with
github.com/caddy-dns/<fournisseur>`), et le bloc de site porte
`tls { dns <fournisseur> {env.JETON_DNS} }`. Le fournisseur se choisit avec
l'hébergeur de la phase 3.
