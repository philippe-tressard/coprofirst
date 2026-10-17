# Une installation commune à plusieurs copropriétés

Un seul code, deux façons d'héberger une copropriété (spec
`specs/architecture/multi-coproprietes.md`, D27 et §4.1 bis) :

- **sa propre installation** — comme 5Hostachy : on arrive par son URL,
  directement sur la connexion. Rien de ce dossier ne sert ;
- **une installation commune** : plusieurs copropriétés, chacune dans sa base,
  servies par les mêmes conteneurs. Ce dossier décrit cette seconde façon.

> ⚠️ **Livré en deux lots.** Le premier (#1894) pose le registre des
> copropriétés, leurs adresses et l'aiguillage. Le second — migrations de chaque
> base au démarrage, fichiers `/uploads/*` par copropriété, configuration lue par
> le rendu serveur selon l'hôte, outillage « créer une copropriété » — est suivi
> dans #2053. **Avant lui, une installation commune ne se met pas en
> service.**

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
   docker compose exec api python -m app.installation_commune.verifier
   ```

   Il liste chaque copropriété, son alias et son adresse — ou les règles violées.
   Une déclaration invalide **ne sert rien** (503) : l'API ne se replie jamais sur
   la copropriété de sa configuration, qu'elle servirait alors à tous les hôtes.
4. Importer la garde des pages dans le `Caddyfile`, en tête du dernier `handle`
   (le mode d'emploi est en tête de `garde-des-pages.caddy`).

Le fichier est relu quand il change : ajouter une copropriété ne demande pas de
redémarrer l'API.

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
