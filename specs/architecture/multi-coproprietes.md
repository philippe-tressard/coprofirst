# Multi-copropriétés — architecture cible

> 🧭 **Spécification de CIBLE, en conception — la phase 1 en découle (v2.113.0
> à v2.117.0), la phase 2 et la distribution sont découpées en lots (§8 bis,
> §8 ter).** Contrairement aux autres fichiers de `specs/`, qui décrivent le produit
> tel qu'il a été conçu à l'origine, celui-ci décrit **où le produit va**. Il est
> rédigé le 07/10/2026, à partir des arbitrages de l'auteur pris le même jour.
>
> Le **travail** vit dans les tickets : phase 1 à partir de #1718, phase 2 de #1743
> à #1751, distribution de #1753 à #1759 et #1761, registre des installations de
> #1876 à #1884, accès à une copropriété #1894. Ce document en
> porte les **décisions** et leurs raisons. Il se met à jour **à chaque arbitrage**,
> daté. Toute décision qui n'y figure pas n'est pas prise.

## 1. L'objectif et l'exigence

Rendre le site capable de servir **plusieurs dizaines de copropriétés**, réparties
sur autant d'installations que nécessaire — le cloud compris —, chacune dans un
**caisson étanche**. 5Hostachy, sur ses Raspberry Pi, reste la **référence** sur laquelle
le produit se développe, et converge vers CoproFirst (§4.10).

**Caisson étanche** = aucune donnée, aucun fichier, aucun courriel, aucune session,
aucun coût d'IA d'une copropriété ne peut être lu, modifié ou déduit depuis une
autre — **ni par un bug applicatif oublié**. C'est une exigence de **sécurité, de
rang 1** : en cas de conflit avec la factorisation ou la simplicité d'exploitation,
l'étanchéité tranche.

Le critère qui départage les architectures : **combien de lignes de code faut-il
oublier pour qu'une fuite se produise ?** Une architecture où un seul `WHERE`
oublié suffit n'est pas étanche, elle n'est que *disciplinée*.

## 2. Les décisions prises (07 au 13/10/2026)

| # | Sujet | Décision | Conséquence directe |
|---|---|---|---|
| D1 | Échelle | **plusieurs dizaines** de copropriétés | une installation par copro (option A) devient inexploitable comme modèle général |
| D2 | Hébergement | **cloud** pour les installations CoproFirst ; **révisée le 08/10/2026** par D11 : la référence, 5Hostachy, reste sur les Raspberry Pi | la haute disponibilité maison (bascule, verrou, réplication) reste celle de la référence ; une installation dans le cloud s'appuie sur celle de son hébergeur |
| D3 | Architecture | **option B** : une application, **une base par copropriété** | §3 et §4 |
| D4 | Moteur de base | **PostgreSQL**, une base **et un rôle** par copropriété | §4.3 ; SQLite est abandonné pour la plateforme |
| D5 | Opérateur de plateforme | **aucun accès aux données** d'une copropriété, même pour l'assistance | §4.7 ; l'assistance passe par l'administrateur de la copro |
| D6 | Canaux et services | **par copropriété**, et **chaque service se désactive** | §4.8 ; premier lot : #1718 |
| D7 | Licence | **GNU AGPLv3 pure**, sans clause commerciale — appliquée en v2.116.0 | §7 |
| D8 | Une personne dans deux copros | le cas existe, **rare** : **deux comptes indépendants**, un par caisson — confirmé le 08/10/2026 | §4.7 |
| D9 | Nom de la plateforme (07/10/2026, revu le 09/10/2026) | **CoproFirst** — « CoproConnect » du 07 au 09/10/2026, abandonné : une startup du même domaine porte déjà ce nom (#1772) ; la résidence garde le sien, « 5Hostachy » | §8, phase 1 : le nom de la **plateforme** (attribution, lien vers le source) et celui de la **résidence** (administrable) sont deux réglages distincts |
| D10 | Variante de la licence (07/10/2026) | **`AGPL-3.0-or-later`** | §7 |
| D11 | Référence et canaux (08/10/2026) | **5Hostachy est la référence**, sur les Raspberry Pi : le développement s'y fait, il suit `main` (canal continu). Une branche **`replica`** reçoit les versions de `main` **choisies** par l'auteur ; les installations CoproFirst — les **répliques** — la suivent. Le nom `replica` est arbitré le 08/10/2026 (et non `stable`) | §4.10 ; `replica` n'a **aucun commit propre** |
| D12 | Ce qui est distribué (08/10/2026) | des **images construites et signées par la CI**, une par version taggée — jamais un `git pull` suivi d'un build sur la machine | §4.10 ; #1753, #1758 |
| D13 | Un seul produit (08/10/2026) | **un seul chemin de code** (5Hostachy est un CoproFirst à une copropriété) et **un seul moteur de base**, PostgreSQL, référence comprise ; le produit se sépare de l'exploitation des RPi | §4.10 ; #1755, #1759 |
| D14 | Mise à jour des installations (08/10/2026) | **chaque nuit, automatique, réversible seule** : sauvegarde, migrations base par base, santé, retour à l'image précédente ; migrations **compatibles sur une version** | §4.10 ; #1756, #1757 |
| D15 | Serveurs d'une réplique (08/10/2026) | **un seul serveur par défaut**, cloud ou hébergeur — « les instances replica ne seront installées par défaut que sur un seul serveur ». La haute disponibilité à deux nœuds reste **propre à la référence** | §4.10, règle 12 ; la réversibilité d'une mise à jour (D14) et la sauvegarde **hors de la machine** (§4.9) deviennent le seul filet d'une réplique |
| D16 | PostgreSQL sur les RPi (09/10/2026) | **réplication en continu** vers le standby (un PostgreSQL en réplique, promu au basculement), plutôt que la copie à la bascule ; données sur la **carte SD**, réglages qui limitent les écritures sans céder la durabilité ; livré en **trois lots** (7a, 7b, 7c) | §8 ter ; #1759, #1781, #1782 |
| D17 | Registre des installations (12/10/2026) | la **référence tient le registre** de toutes les installations CoproFirst ; il reste **sur les Raspberry Pi**, dans une base `plateforme` distincte de celle de la résidence, réservée à l'opérateur de plateforme | §4.11 ; il hérite de la réplication de la référence (D16) ; les installations le joignent par un **nom dédié** |
| D18 | Inscription (12/10/2026) | déclarée **automatiquement** au premier lancement ; la **référence attribue l'ID** ; sans inscription valide, l'installation tourne en **mode limité** : pas de mise à jour automatique, aucun service supplémentaire, **5 utilisateurs au plus** | §4.11 ; révise §4.10 règle 9 |
| D19 | Bail (12/10/2026, recommandation acceptée) | l'inscription vaut par un **bail signé** par la référence, valable **30 jours**, renouvelé chaque nuit ; un bail échu ramène au mode limité, **jamais** à la lecture seule | §4.11 ; une panne de la référence ne coupe aucune installation |
| D20 | Suspension (12/10/2026, recommandation acceptée) | décision **explicite et signée** de l'opérateur : l'installation passe en **lecture seule, export ouvert** ; jamais d'arrêt sec ni d'effacement | §4.11 ; les données appartiennent aux syndicats des copropriétaires |
| D21 | Canaux (12/10/2026, recommandation acceptée) | un canal est un **pointeur vers un tag de `main`** : `main` (la référence seule), `replica` (défaut), `special-<nom>` (épinglage ou avant-première) ; jamais de commit propre | §4.11 ; le bail porte la **version cible** |
| D22 | IA d'une installation (12/10/2026) | **tous les paramètres de l'IA sont propres à l'installation** (clé, modèles, plafonds) ; la référence ne fournit pas l'IA | §4.11 ; la consommation remontée est **déclarative** |
| D23 | Images (12/10/2026, recommandation acceptée) | les images restent **publiques** ; le levier est le bail, pas l'accès aux images | §4.11 ; pas de jeton de registre d'images |
| D24 | Transfert du rôle de référence (12/10/2026) | le rôle de référence se **transfère** vers une installation déjà déployée, **à l'initiative de la référence en place** ; **il ne peut y avoir deux références** | §4.11 ; époque de référence et chaîne de clés |
| D25 | Vocabulaire (12/10/2026) | **« maître » devient « référence »** — l'installation de référence, le rôle de référence —, à la demande de l'auteur : le mot évoquait l'esclavage. Dans le code, le rôle s'écrit `reference` ; `maitre`, l'ancien nom, reste lu tant que le `.env` des deux Raspberry Pi le porte (`utils/installation.ANCIENS_NOMS`) | partout : spec, contrat d'inscription, administration, code ; les citations de l'auteur restent mot pour mot |
| D26 | Conditions d'inscription (12/10/2026) | un **contrat d'engagements réciproques** : l'exploitant d'une installation s'engage à respecter la licence, la marque et le registre ; l'exploitant de la référence, à garder CoproFirst libre et à maintenir les services standards. Accepté par l'administrateur quand il valide l'inscription, il est **archivé dans le registre, rattaché à l'ID de l'installation** — texte exact, empreinte, date, qui l'a accepté. Les engagements portent sur le **service d'inscription**, jamais sur les droits de la licence | §4.11 ; `api/app/registre/conditions/` (une version par fichier, figée par son empreinte) ; #1876 |
| D27 | Accès à une copropriété (13/10/2026) | **un seul code**, deux façons de l'héberger : une copropriété peut avoir **sa propre installation**, comme 5Hostachy, qui s'ouvre par son URL directement sur la connexion ; ou être **hébergée avec d'autres** dans une installation commune. Elle y est alors joignable par **son propre domaine** si elle en a un, sinon par une **adresse dérivée de l'URL commune et de `code-postal` + nom**, que l'hébergeur lui attribue sans frais ; l'URL commune elle-même **aiguille** (code postal, nom) puis redirige. Adresse dérivée et aiguillage ne résolvent rien eux-mêmes : la règle 1 du §4.1 reste entière | §4.1 bis, §4.2 ; #1894, phase 3 |

## 3. Les trois architectures comparées

| | **A — une instance par copro** | **B — une application, une base par copro** | **C — une base partagée, colonne `copropriete_id`** |
|---|---|---|---|
| Étanchéité | 🟢 totale (processus, base, fichiers, secrets séparés) | 🟢 données ; 🟠 **mémoire du processus** partagée (§4.5) | 🔴 un filtre oublié sur 82 tables = une fuite |
| Changement du code | faible | moyen : un **contexte de copropriété** résolu à l'entrée de chaque requête | massif : toutes les tables, toutes les requêtes |
| Exploitation | 🔴 N piles à déployer, migrer, superviser | 🟠 N bases à migrer et sauvegarder, une seule pile | 🟢 une base |
| Restaurer ou rendre **une** copro | 🟢 | 🟢 une base + un préfixe de fichiers | 🔴 extraction ligne à ligne |
| Échelle | quelques copros | quelques dizaines à quelques centaines | des milliers |

**B est retenue** (D1, D3). Elle est la seule à combiner l'étanchéité des données et
une exploitation tenable à plusieurs dizaines. Son point faible, la mémoire du
processus partagée, se ferme par les règles du §4.5.

**A et B se combinent** (D11, 08/10/2026) : chaque installation CoproFirst
sert plusieurs copropriétés (B), et l'on installe CoproFirst **autant de fois
que nécessaire** (A) — par hébergeur, par exploitant, ou pour une copropriété qui
exigerait un hébergement dédié. Un code propre pour B l'est aussi pour A.
**C est écartée** : elle repose sur la discipline, pas sur la structure.

## 4. L'architecture cible

### 4.1 Le contexte de copropriété

Chaque requête est rattachée à **une seule** copropriété, résolue **à l'entrée**, et
toute ressource s'obtient de ce contexte :

```
requête ── nom d'hôte (residence.domaine) ──► registre de la plateforme
                                                   │
                     ┌─────────────────────────────┼──────────────────────────────┐
                     ▼                             ▼                              ▼
          base PostgreSQL + rôle        préfixe de stockage objet       secret de signature,
          de CETTE copro                de CETTE copro                  expéditeur, services
```

Règles :
1. **Résolution par nom d'hôte**, jamais par un paramètre, un en-tête libre ou un
   champ de formulaire. Une copro = un sous-domaine : cookies, stockage du
   navigateur et CSP sont alors cloisonnés **par le navigateur**, sans code.
2. **Un hôte inconnu ne résout rien** : réponse d'erreur, jamais de copropriété
   « par défaut ».
3. **Aucune ressource ne se construit depuis la configuration globale** : base,
   fichiers, secret, expéditeur, clé d'IA viennent tous du contexte.

**Livré en phase 2 (#1751, 10/10/2026)** — l'intergiciel `app/contexte.ResolutionCopropriete` lit
`Host` à l'entrée et `app/contexte.resoudre` le cherche au registre : le nom d'`ORIGIN`
et ceux de `HOTES_COPROPRIETE`. Un hôte inconnu reçoit **421**. Deux tolérances,
déclarées et bornées :
- une **IP privée** ou un **nom interne** (`localhost`, `api`) désigne la copropriété
  *tant qu'elle est seule* — scripts et sondes des nœuds, rendu côté serveur du front ;
  avec deux copropriétés, ils ne désignent plus personne, et ces appels devront
  nommer leur copropriété ;
- **`/health`** répond à tout hôte : une question sur la plateforme.

### 4.1 bis L'accès à une copropriété (D27, 13/10/2026)

**Un seul code**, deux façons de l'héberger (D13) : une copropriété peut avoir
**sa propre installation**, comme 5Hostachy, ou être **hébergée avec d'autres**
dans une installation commune. Une copropriété hébergée n'a pas à posséder un
nom de domaine : l'hébergeur lui en dérive un du sien.

| Hébergement | On arrive par | On aboutit à |
|---|---|---|
| **sa propre installation** (5Hostachy) | son URL | l'écran de connexion, directement |
| **installation commune**, la copropriété a son domaine | son domaine (`residence.example`) | son écran de connexion |
| **installation commune**, sans domaine propre | l'**adresse dérivée** : `75015-les-tilleuls.<domaine commun>` | son écran de connexion |
| **installation commune**, par l'URL commune | `<domaine commun>/75015-les-tilleuls`, ou `<domaine commun>` puis aiguillage (code postal, nom) | une **redirection** vers l'adresse de la copropriété, puis son écran de connexion |

Règles :
1. **L'adresse dérivée est un sous-domaine, pas un chemin.** `75015-les-tilleuls`
   se pose **devant** le domaine commun, sans frais ni démarche pour la
   copropriété : un enregistrement DNS générique et un certificat générique de
   l'hébergeur les couvrent toutes. Servir la copropriété sous un **chemin** de
   l'URL commune la ferait partager avec toutes les autres l'**origine** du
   navigateur : stockage local, cache du service worker de la PWA, CSP. Le
   navigateur ne les séparerait plus, et le code devrait le faire à sa place,
   sans filet (règle 1 du §4.1).
2. **L'URL commune redirige, elle ne résout pas.** Le chemin
   `/75015-les-tilleuls` et l'aiguillage ne servent aucune donnée de copropriété,
   ne posent aucun cookie de copropriété, et renvoient à l'adresse de la
   copropriété. L'hôte commun n'est l'hôte d'**aucune** copropriété (règle 2 du
   §4.1).
3. **Code postal + nom identifient une copropriété dans l'installation**, sous
   la forme d'un **alias** normalisé (accents, casse, ponctuation, espaces →
   tiret ; jamais de `_`, interdit dans un nom d'hôte) : deux « Les Tilleuls »
   au même code postal sont refusés dès l'inscription, et l'hébergeur leur fait
   choisir un nom qui les distingue.
4. **L'alias est une clé de recherche, pas une identité.** L'identifiant interne
   ne change pas quand le nom change ; l'ancien alias **redirige** vers le
   nouveau, et les liens déjà envoyés restent valables.
5. **Pas d'énumération.** L'aiguillage exige une correspondance **exacte**, sans
   autocomplétion ni liste, et limite le nombre de tentatives. Un échec reçoit
   le même message dans tous les cas. Une copropriété **suspendue** n'est jamais
   une destination.
6. **Une installation propre à une copropriété n'a ni aiguillage ni adresse
   dérivée** : son URL est la sienne.

### 4.2 Le registre de la plateforme

La seule donnée **commune** : la liste des copropriétés et de quoi résoudre leur
contexte (identifiant, sous-domaine, état actif ou suspendu, références vers les
secrets), et l'**alias** de chaque copropriété — code postal et nom normalisés,
unique, anciens alias conservés — dont se déduit son adresse dérivée (§4.1 bis). Il ne contient **aucune donnée personnelle** de résident ; les secrets
eux-mêmes vivent dans le coffre de l'hébergeur, pas dans le registre.

### 4.3 Les données — PostgreSQL, une base et un rôle par copropriété (D4)

- **Un rôle PostgreSQL par base**, qui n'a de droits que sur sa base : un contexte
  mal résolu **échoue à la connexion** au lieu de lire la mauvaise copro.
  L'étanchéité descend jusque dans le moteur.
- **Connexions** : plusieurs dizaines de bases avec un pool chacune → un regroupeur
  de connexions (type PgBouncer), ou des pools paresseux et bornés.
- **Migrations** : la même migration s'applique à toutes les bases, avec la version
  **suivie par base**, un **arrêt au premier échec**, et une copro en échec isolée
  sans bloquer les autres en lecture.
- **Bascule depuis SQLite** : repartir d'une **migration initiale PostgreSQL** qui
  pose le schéma actuel, plutôt que de rejouer l'historique écrit pour SQLite.
  Les données de la résidence actuelle se reprennent par un export / import
  **vérifié** (comptes de lignes par table, sommes de contrôle).
- **Tests** : la CI tourne **sur PostgreSQL**. Des tests sous SQLite masqueraient
  les écarts de typage, de casse et de transactions.

### 4.4 Les fichiers

Stockage objet, **un préfixe ou un compartiment par copropriété**, avec des droits
d'accès qui l'imposent. Un chemin de fichier ne se construit **jamais** à partir
d'une donnée de la requête.

### 4.5 La mémoire du processus — le point faible de B

Avec une seule application pour toutes les copros, tout état gardé **en mémoire**
et indexé par un simple identifiant fuit d'une copro à l'autre : l'utilisateur
n° 12 de la copro A lirait le cache de l'utilisateur n° 12 de la copro B.

- **Règle** : tout état mutable de module est **indexé par la copropriété**, ou
  n'existe pas.
- **Garde-fou** : un contrôle statique refuse tout nouvel état de module qui ne
  l'est pas — `api/tests/test_etat_module_par_copropriete.py` (#1743, 08/10/2026).
  Il précède tout le reste, puisqu'il ne coûte rien tant qu'il n'y a qu'une
  copropriété.
- **Recensés le 08/10/2026 par ce contrôle — neuf, et non quatre** comme l'écrivait
  le relevé de la veille, fait à la main. La liste fait foi **dans le test**, et
  ne se recopie pas ici. Deux familles :
  - **à indexer par copropriété** (lot P2-2, **soldé le 10/10/2026** : ils
    vivent dans `contexte.etat(nom)`, la seule porte) — dont le cache de l'**arbre des
    périmètres** et le quota horaire de l'IA par personne, que le relevé à la main
    n'avait pas vus ;
  - **du processus**, sans donnée de copropriété (configuration de la plateforme,
    catalogue d'icônes, repli d'un caractère pour la recherche, diagnostic du
    dernier rendu PDF). Le `lru_cache` de `config.py` y est rangé : ce qui est
    propre à une copropriété sort de `settings` au lot P2-2, et le cache qui reste
    est celui de la plateforme.

### 4.6 Les tâches planifiées

Sauvegarde, maintenance, relances, rattrapages : chaque tâche s'exécute **par
copropriété**, dans le contexte de celle-ci, et **l'échec d'une copro ne bloque
pas les autres**. Chaque exécution est journalisée par copro.

### 4.7 Les identités, les rôles et l'opérateur

- **Un compte appartient à une copropriété.** Le même courriel peut exister dans
  deux copros sous la forme de **deux comptes indépendants** (D8, confirmée le 08/10/2026).
  Aucun pont, aucun sélecteur entre caissons.
- **Deux niveaux d'administration** : l'**administrateur de copro**, qui gère sa
  résidence, et l'**opérateur de plateforme**, qui crée, suspend et supervise les
  copropriétés. Le rôle `admin` actuel mêle les deux : il se scinde.
- **L'opérateur ne lit aucune donnée d'une copro** (D5). Sa supervision (santé,
  volumes, erreurs) ne contient **aucune donnée personnelle** : ni nom, ni
  courriel, ni contenu d'affaire dans les journaux qu'il lit.

### 4.8 Les canaux et les services (D6)

- **Un registre unique des services**, chacun activable par copropriété : IA,
  diffusion WhatsApp, réception des réponses par courriel… C'est le **premier
  lot** (#1718), utile dès aujourd'hui avec une seule copro. Un réglage rangé en
  base y est cloisonné **gratuitement** par B.
- 🔴 **Les courriels de sécurité ne sont pas un service** : mot de passe oublié,
  vérification d'adresse, alertes d'administration. Aucun interrupteur ne les
  coupe. Le registre sépare le **service**, qui se coupe, de l'**infrastructure**
  (SMTP), qui ne se coupe pas.
- **Courriel** : un sous-domaine d'envoi par copro (SPF et DKIM propres), et une
  adresse de réception (`affaire@`) qui identifie la copro **sans ambiguïté**.
- **WhatsApp** : un compte par copro. La passerelle repose sur une bibliothèque non
  officielle, avec un risque de blocage du compte : c'est un service désactivable.
- **IA** : clé, plafonds et coûts **par copro**. Le registre des usages de l'IA
  (`utils/llm_usages.py`) en est déjà la forme.

### 4.9 Les sauvegardes et la réversibilité

- Une sauvegarde **par base**, chiffrée, **restaurable seule**, sans toucher aux
  autres copros.
- Avec D5, la clé de chiffrement ne doit pas permettre à l'opérateur de lire les
  données **en routine**. Le mécanisme reste à concevoir.
- **Départ d'une copropriété** : elle repart avec sa base et ses fichiers, puis
  ceux-ci sont supprimés de la plateforme.
- **La base `plateforme`** (registre des installations, §4.11) a sa propre
  sauvegarde, à part de celles des copropriétés : chaque nuit, chez la référence,
  le même export vérifié par réimport, sur les métadonnées du registre
  (`app/registre/sauvegarde.py`, tâche de la plateforme, #1892). Un échec va à
  l'opérateur, jamais à une copropriété.

### 4.10 La distribution — une référence, une branche `replica`, N installations (D11 à D14)

Arbitré le 08/10/2026, à la demande de l'auteur : *« 5hostachy est le master
(hébergé sur les RPi), le dev est fait dessus, il converge petit à petit vers
CoproFirst. CoproFirst pourra être installé autant de fois que nécessaire et
gérera plusieurs copropriétés de façon isolée ; les installations se
synchronisent chaque nuit sur une branche qui reçoit des versions choisies et
stables de main. »*

```
        développement (sessions, PR)
                  │
                  ▼
   main ── chaque version vX.Y.Z (tag) ──► 5Hostachy sur les RPi (canal continu)
                  │                                  │ rodage de N jours sans incident
                  │     promotion, décidée par l'auteur
                  ▼
   branche « replica » (avance rapide seulement, aucun commit propre)
                  │  images de la version : construites et signées par la CI
                  ▼
   registre d'images ── chaque nuit ──► installation CoproFirst n° 1 (copros A, B…)
                                     ──► installation CoproFirst n° 2 (copros C, D…)
```

**Les règles :**

1. **`replica` est un pointeur, pas une branche de travail.** Elle n'avance qu'en
   avance rapide vers un tag de `main`, et ne porte aucun commit propre. Un
   correctif urgent passe par `main`, puis se promeut. Le jour où un correctif se
   ferait sur `replica`, il y aurait deux produits.
2. **Un seul chemin de code.** 5Hostachy est un CoproFirst à **une**
   copropriété (le registre de §4.2 n'a qu'une entrée), jamais un « mode mono »
   à côté d'un « mode multi » : sinon le canal des répliques livrerait du code que la
   production de la référence n'a jamais exécuté. C'est l'objet de la phase 2.
3. **Un seul moteur de base**, PostgreSQL, référence comprise (#1759) : un moteur
   que seul le canal des répliques exercerait ne serait éprouvé nulle part.
4. **On distribue des images, pas des sources.** La CI construit une fois les
   images d'une version taggée, les signe et les publie (#1753) ; une
   installation les tire **par empreinte** — ni build, ni git, ni clé de dépôt
   sur la machine. La référence fait de même (#1758). Le lien vers le source exigé
   par l'AGPL (§7) pointe vers le tag de la version.
5. **La promotion est une décision de l'auteur, appuyée sur des faits** (#1754) :
   CI verte, version en production sur la référence depuis N jours sans incident,
   post-check vert. Elle publie des notes de version pour exploitants tiers.
6. **La mise à jour nocturne revient en arrière seule** (#1756) : sauvegarde par
   copropriété, image vérifiée, migrations base par base avec arrêt au premier
   échec, contrôle de santé, et retour à l'image précédente sinon. Déploiement
   **échelonné** (une installation pilote d'abord) ; une installation peut
   **épingler** sa version.
7. **Les migrations sont compatibles sur une version** (#1757) : une version
   ajoute, la suivante retire. L'image précédente tourne alors sur le schéma
   migré, et le retour arrière n'est qu'un changement d'image — sans quoi il
   faudrait restaurer la sauvegarde et perdre les écritures de la nuit.
   ⚠️ La compatibilité ne suffit pas seule (constaté le 08/10/2026, #1756) :
   l'ancienne image ne connaît pas la révision que la nouvelle a posée, et son
   `alembic upgrade head` arrêtait le conteneur en boucle. `api/start.sh` saute
   donc les migrations d'une base **en avance** sur le code
   (`api/app/utils/revision_base.py`), et le dit.
8. **Le produit se sépare de l'exploitation des RPi** (#1755) : la bascule,
   `health-watch`, les points d'entrée et les crontabs restent dans le dépôt, mais
   ne partent pas avec une installation ; celle-ci a son déploiement standard.
9. **Une installation n'envoie rien par défaut** — ni version, ni santé — sans
   l'accord de son exploitant (RGPD, D5). **Révisée le 12/10/2026 (D18)** : une
   installation se déclare à la référence au premier lancement et lui adresse un
   rapport chaque nuit (§4.11). L'accord devient une **condition de
   l'inscription**, écrite (#1876) ; la refuser reste possible, au prix du mode
   limité. Rien de ce qui part ne concerne un résident (D5).
10. **Le canal des répliques est une porte vers toutes les installations à la fois** :
    tags protégés, images signées, seule la CI publie. Une compromission de
    `replica` les compromettrait toutes en une nuit.
11. **L'administration dit le rôle de l'installation** (#1761, exigence du
    08/10/2026) : **Référence** — suit `main` —, **Réplique** — suit `replica` —, ou
    **Inconnu**, avec la version qui tourne et son écart à la branche suivie. Le
    rôle appartient à l'**installation**, pas à l'image (une version promue est la
    même image partout) : il se déclare dans sa configuration, et une
    déclaration absente se lit « Inconnu », jamais « Référence ». Il ne se confond
    pas avec le rôle d'un nœud dans la haute disponibilité (actif / standby) : les
    deux RPi sont **ensemble** la référence.
12. **Une réplique tient sur un seul serveur** (D15). Rien de la bascule de la
    référence ne s'y transpose : pas de standby, donc pas de failover, et une mise
    à jour coupe le service le temps de redémarrer. Son filet, ce sont le
    retour arrière par image (règle 7, #1757) et une sauvegarde copiée **hors
    de la machine** — sur un seul serveur, une sauvegarde locale disparaît
    avec ce qu'elle protège. La mise à jour nocturne (#1756) se cale donc sur
    une heure creuse, et vérifie la sauvegarde **avant** de toucher à quoi que
    ce soit.

### 4.11 Le registre des installations (D17 à D24)

Demandé par l'auteur le 12/10/2026 : *« l'instance master (5hostachy) possède un
onglet d'admin des futures instances déployées »* — déclaration au premier
lancement, identifiant attribué par la référence, branche de référence, paramètres
remontés chaque nuit, installation désactivable, *« non détournable »* ; puis :
*« Prévoir aussi le transfert du master sur une instance déjà déployée (sous la
responsabilité du master). Il ne peut y avoir 2 masters distincts »*. Arbitré le
même jour.

**Ce que « non détournable » peut vouloir dire sous l'AGPL.** Le code est public
et chacun a le droit de le modifier (§7) : un exploitant peut retirer l'appel à la
référence, le plafond d'utilisateurs ou la vérification du bail, et la licence
interdit d'ajouter une restriction qui l'en empêcherait. Aucun verrou écrit dans
une installation ne tient contre son exploitant. Ce qui ne se détourne pas tient
à ce que **la référence détient** : la **clé qui signe les baux** — la seule pièce
secrète ; tout le reste doit tenir avec le code lu —, la **mise à jour
automatique**, et la **marque** : une installation modifiée pour échapper au
registre n'est plus CoproFirst non modifié (`MARQUE.md` §3). Le dispositif guide
l'exploitant de bonne foi et rend le détournement **visible** ; il ne prétend pas
l'empêcher.

**Les états d'une installation**

| État | Comment on y entre | Ce qu'elle peut |
|---|---|---|
| **Limitée** | jamais inscrite, inscription en attente de validation, ou bail échu | tout le cœur, **5 utilisateurs actifs au plus** ; aucun service du registre (§4.8) ; pas de mise à jour automatique |
| **Active** | inscription validée par l'opérateur, bail valide | ce que son canal et ses services autorisés ouvrent |
| **Suspendue** | décision de l'opérateur, portée par un bail signé | **lecture seule**, export ouvert à l'administrateur de chaque copropriété |

Le registre garde en plus la trace des installations **résiliées** : le bail
cesse, l'installation retombe en mode limité, et l'effacement de ses données
revient à son exploitant — la référence n'y a aucun accès.

**Les règles :**

1. **Inscription automatique** au premier lancement : l'installation génère sa
   paire de clés (Ed25519), son administrateur saisit ses coordonnées et accepte
   les conditions (D26), la déclaration part à la référence, qui **archive le
   contrat accepté** avec l'installation. La référence attribue l'**ID**,
   unique pour toutes les installations ; la paire de clés l'attache à une
   machine — deux installations qui présentent le même ID avec deux clés sont un
   **clone**, signalé.
2. **Le mode limité ne prend rien en otage.** Le plafond refuse le **sixième**
   compte actif ; il ne désactive, ne masque ni n'efface aucun compte existant.
   Les courriels de sécurité ne sont pas un service (§4.8) : ils restent.
3. **Le bail**, signé par la référence, porte l'ID, l'état, le canal, la version
   cible, les services autorisés, l'**époque de référence** et son échéance
   (30 jours). Il se renouvelle chaque nuit ; sans renouvellement depuis 3 jours,
   l'administrateur d'installation et la référence sont alertés. Un bail illisible
   vaut « limitée », jamais un arrêt.
4. **Une panne de la référence ne coupe personne** : elle est sur deux Raspberry Pi
   derrière une box résidentielle (D17), et 30 jours couvrent toute panne
   vraisemblable. Un bail échu n'ôte que la croissance et les services, jamais
   la lecture ni l'écriture.
5. **L'installation tire, la référence ne pousse jamais** : aucun accès entrant à
   une installation, aucune commande à distance (D5). Ses décisions — valider,
   suspendre, changer de canal, épingler une version — voyagent dans le bail.
6. **Les canaux** (D21) : la version cible portée par le bail permet un
   déploiement **par vagues** (une part des installations d'abord), l'épinglage
   et le retour à une version. Ce qu'un client a de spécifique passe par le
   registre des services (§4.8), jamais par une branche — la règle 1 de §4.10
   vaut pour tout canal.
7. **Le registre n'est pas une donnée de la résidence** : base `plateforme`, rôle
   PostgreSQL distinct, onglet réservé à l'**opérateur de plateforme** (§4.7),
   jamais à l'administrateur de la copropriété 5Hostachy. La référence y figure,
   canal `main`, et ne passe jamais en mode limité.
8. **Le point d'inscription est exposé** sur la référence, donc sur la production
   de la résidence : requêtes signées, taille et débit plafonnés, rien de la
   résidence derrière. Il répond sous un **nom dédié**, ce qui permet au
   registre de déménager sans toucher aux installations.
9. **Les installations d'essai** — CI, tests de navigateur, poste de
   développement, workflow « Essai de mise à jour » — se déclarent comme telles :
   elles n'appellent pas la référence et ne sont pas limitées. Ce mode n'est admis
   que pour un hôte local ou une base jetable.
10. **Le transfert du rôle de référence** (D24). La référence, c'est trois choses : la base
    `plateforme`, la **clé qui signe les baux** et le **nom dédié**. Le transfert
    les déplace vers une installation **active** déjà déployée, **à l'initiative
    de la référence en place** — la cible ne peut pas se proclamer référence. Il se fait
    dans une fenêtre : registre gelé en lecture seule, export vérifié, import sur
    la cible, puis un **acte de transfert** signé par l'ancienne clé, qui désigne
    la nouvelle et porte l'**époque n+1**, et le nom dédié repointé. L'ancienne
    référence se **rétrograde elle-même** en réplique et détruit sa clé. La
    copropriété de la résidence n'en fait pas partie : son caisson ne bouge pas.
11. **Jamais deux références** : chaque installation retient la plus haute époque
    reçue et **refuse** tout bail d'une époque inférieure ou d'une clé révoquée.
    Une ancienne référence qui reviendrait ne signerait plus rien d'accepté ; deux
    installations qui se déclarent référence sont une alerte du registre. Le retour
    arrière d'un transfert diffusé est un **nouveau transfert** (n+2), jamais la
    réactivation de l'ancienne clé.

**Ce que remonte une installation** — un **contrat de données versionné**, un seul
schéma partagé par la référence et les installations ; un champ s'y ajoute avec sa
finalité.

| Famille | Contenu | Quand |
|---|---|---|
| Identité | ID, empreinte de clé, canal, version qui tourne, version cible, révision de la base, résultat de la dernière mise à jour | chaque nuit |
| Administrateur d'installation | prénom, nom, courriel, téléphone ; contact technique et de facturation s'ils diffèrent | à l'inscription, puis quand il change |
| Hébergement | hébergeur et **pays des données**, architecture, mémoire et disque (capacité, occupation), moteur et taille des bases, échéance du certificat TLS, erreurs 5xx sur 24 h | chaque nuit |
| Sauvegarde | dernière sauvegarde réussie, copie hors de la machine, dernier essai de restauration | chaque nuit |
| Posture | oui/non : documentation d'API coupée, cookie sécurisé, secret assez long, **lien vers le source présent** (AGPL §13) | chaque nuit |
| Copropriétés | par copropriété : identifiant (préfixé par l'ID de l'installation), nom, nombre de lots, d'utilisateurs actifs et inscrits, volume stocké, services activés | chaque nuit |
| Consommation | appels et coût de l'IA, messages de diffusion, courriels envoyés, serveurs | chaque nuit |

- **Aucune donnée de résident** (D5) : des comptes, jamais un nom, un courriel ni
  un contenu.
- Les coordonnées de l'**administrateur d'installation** sont une donnée
  personnelle traitée par la référence : finalité, base légale, durée et purge,
  droits — fixées par #1876 ; rectifiables depuis l'administration de
  l'installation.
- La **consommation est déclarative** (D22) : signée par la clé de
  l'installation, elle est attribuée et datée, pas prouvée. Une facturation non
  détournable supposerait que la référence fournisse elle-même le service mesuré ;
  le modèle économique (§9, question 6) le dira.

**La référence alerte** sur : installation muette depuis plus de 48 h, mise à jour
revenue en arrière, sauvegarde trop ancienne ou sans copie hors de la machine,
disque plein à plus de 80 %, certificat proche de l'échéance, retard de version,
clone, deux références déclarées. Chaque décision de l'opérateur — valider,
suspendre, rétablir, changer de canal, résilier, transférer — s'inscrit à un
**journal des décisions** (qui, quand, pourquoi).

## 5. Les garde-fous

1. **Test d'étanchéité permanent** : deux copropriétés aux **identifiants
   identiques** (même `user.id`, même `ticket.id`). Chaque route est appelée avec
   la session de A sur les objets de B → refus partout. Il comporte un **cas zéro**
   et un **témoin** qui doit servir. Un test qui ne peut pas s'exécuter rend
   **INCONNU**, jamais OK.
2. **Contrôle statique de la mémoire du processus** (§4.5).
3. **Jeton de A présenté à B** : refusé, puisque le secret de signature diffère.
4. **Hôte inconnu** : aucune copropriété résolue (§4.1, règle 2).
5. **Journaux de l'opérateur** : un contrôle refuse l'apparition d'une donnée
   personnelle (§4.7).
6. **Rapport sans donnée de résident** : un contrôle refuse un champ du contrat de
   données qui en porterait une (§4.11).
7. **Bail** : self-test de la vérification — signature, échéance, époque
   inférieure, clé révoquée, clone ; un bail illisible rend le mode limité,
   jamais l'arrêt.
8. **Référence éteinte** : un essai prouve qu'une installation active le reste
   pendant toute la durée de son bail.
9. **Transfert** : essai complet entre deux installations jetables avant tout
   transfert réel ; après lui, l'ancienne clé est refusée partout.

## 6. Ce que le code suppose aujourd'hui (relevé le 07/10/2026)

Le produit a été pensé **réutilisable par une autre copropriété, une installation
chacune** : le patrimoine et l'arbre des périmètres sont administrables, *« une
autre copropriété n'a ni AFUL, ni quatre bâtiments »* (`models/perimetre.py`). Il
n'a **jamais** été pensé pour plusieurs copropriétés dans une même installation.
Le relevé ci-dessous **vieillit avec le code** : le revérifier avant de s'en servir.

| Hypothèse mono-copropriété | Où | Ce qu'il faudra en faire |
|---|---|---|
| `Copropriete` est un singleton | `select(Copropriete).first()` dans `seed/__init__.py`, `routers/flux/sante.py`, `routers/uploads.py`, `utils/syndic.py`, `utils/synthese_affaire/rassemblement.py` | rester un singleton **dans sa base** : B n'y change rien |
| 2 tables sur 82 portent `copropriete_id` | `Batiment`, `ContratEntretien` | sans objet avec B (c'est C qui l'exigerait) |
| `Lot.batiment_id` est nullable (parkings) | `models/copropriete.py` | sans objet avec B ; un piège direct pour C |
| `Utilisateur.email` unique globalement, rôles globaux | `models/core.py`, `models/roles.py` | unique **dans sa base** (D8) ; scission de `admin` (§4.7) |
| Une base, un dossier de fichiers, un secret de signature | `config.py` : `database_url`, `uploads_dir`, `secret_key` | passent au contexte de copropriété (§4.1) |
| Domaine, adresses et nom en dur | `5hostachy.fr` 14 fois dans `api/` et `front/`, `contact@`, `noreply@`, « Hostachy » dans 14 fichiers du front | configuration de la copropriété (phase 1) |
| État en mémoire du processus | voir §4.5 | indexé par copro ou supprimé |
| Tâches planifiées globales | `add_job` dans `main.py`, `utils/maintenance.py`, `utils/backup.py`, `utils/taches.py`, `utils/rattrapage.py` | par copro (§4.6) |
| Adhérence à SQLite | ~~39 fichiers d'`api/app` citent `sqlite` ou `PRAGMA`~~ — regroupée dans `app/dialecte.py` (P2-5) ; restent les migrations historiques en mode `batch` (non rejouées : schéma initial) et les scripts d'exploitation | scripts réécrits avec DI-7 (§4.3) |
| Un compte WhatsApp, une boîte de réception, une configuration d'IA | `whatsapp-bridge/`, `utils/courriel_ingestion.py`, `config_llm` | par copro (§4.8) |

## 7. La licence — GNU AGPLv3 (D7)

**Fait le 08/10/2026 en v2.116.0 (#1726).** La clause d'usage commercial de
l'ancienne licence a disparu : le projet est sous la **GNU AGPLv3**, une licence
libre reconnue par l'OSI et la FSF. ⚠️ Ce qui suit n'est pas un avis juridique.

- **Assumé** : n'importe qui peut héberger le logiciel et le proposer comme service,
  y compris contre paiement, **à condition de publier ses modifications**. La
  seule protection qui reste est la **marque** : la clause « nom et logo » sort de
  la licence et devient une politique de marque séparée.
- **Obligation pour la plateforme** (AGPLv3 §13) : chaque utilisateur qui se sert
  du site par le réseau se voit **proposer le code source** de la version qui
  tourne. Un lien vers le source figure donc dans l'interface de chaque copro.
- **Aucune condition additionnelle** (AGPLv3 §7) — arbitré le 08/10/2026 :
  « AGPLv3 pure ». L'attribution se limite aux mentions de copyright.
- **Les versions déjà publiées** restent sous l'ancienne licence.
- **Tranché le 07/10/2026 (D10)** : **`AGPL-3.0-or-later`**. Les versions ultérieures
  de l'AGPL publiées par la FSF s'appliqueront au choix de qui reçoit le code ;
  c'est l'identifiant SPDX à écrire dans `LICENSE`, `REUSE.toml` et les en-têtes.
- **La marque** porte le nom de la **plateforme**, **CoproFirst** (D9), pas celui
  de la résidence. Une recherche web du 07/10/2026 n'a trouvé aucun produit de ce
  nom. **Déposée le 09/10/2026** : demande INPI n° 5307183, marque française
  **verbale**, classes 9, 36 et 42 ; publication prévue le 30/10/2026, opposition
  ouverte aux tiers jusqu'au 30/12/2026 (CPI art. L.712-4) — c'est elle qui dira si
  un droit antérieur s'y oppose. Ni le logo ni « 5Hostachy » ne sont déposés.
- **Vérifié avant le changement** (08/10/2026) : un seul auteur humain dans tout
  l'historique, aucun contributeur extérieur ; les cinq exceptions « à valider »
  de `docs/licences-tierces.md` analysées compatibles, analyse validée par
  l'auteur (motifs : `scripts/ci/licences_politique.py`).
- **La politique de marque** : [`MARQUE.md`](../../MARQUE.md) (#1736, 10/10/2026), à faire relire.

## 8. Le phasage

Chaque phase apporte de la valeur **seule**, même si le chantier s'arrête après
elle.

| Phase | Contenu | Prérequis |
|---|---|---|
| 0 | Décisions restantes (§9) | — |
| 1 | **Mono-copro propre** : services activables (#1718, v2.113.0) ; identité de la copropriété en configuration et nom de la plateforme, CoproFirst, avec le lien vers le source (#1725, v2.114.0) ; consignes de la fiche arrivant administrables (#1727, v2.115.0) ; licence AGPL (#1726, v2.116.0) ; logo de la résidence téléversable (#1728, v2.117.0) ; politique de marque (#1736, `MARQUE.md`, marque déposée le 09/10/2026) | aucun |
| 2 | **Contexte de copropriété** dans le processus (§4.1, §4.5, §4.6), en production avec **une seule** copro, le test d'étanchéité déjà actif sur deux copros factices. Neuf lots, §8 bis (#1743 à #1751) | phase 1 |
| 2 bis | **Distribution** (§4.10, §8 ter) : tags et images signées, branche `replica` et promotion, déploiement standard, migrations compatibles sur une version ; la référence tire son image et passe sous PostgreSQL | phase 2 en partie (§8 ter) |
| 2 ter | **Registre des installations** (§4.11, §8 quater) : inscription, bail, rapport nocturne, onglet de la référence, canaux, mode limité et suspension, transfert du rôle de référence | phase 2 bis |
| 3 | **Première installation CoproFirst** : hébergeur, PostgreSQL (§4.3), stockage objet (§4.4), mise à jour nocturne réversible (§4.10), outillage d'installation (créer, migrer, sauvegarder et restaurer **une** copro), supervision sans donnée personnelle ; adresses dérivées et aiguillage de l'installation commune (§4.1 bis, #1894) | hébergeur choisi |
| 4 | **Copropriété pilote** : une seconde résidence réelle et volontaire | phase 3 |
| 5 | Accueil autonome des copropriétés ; facturation selon le modèle économique | modèle économique |

## 8 bis. La phase 2 en lots (proposition du 08/10/2026)

**Le chemin retenu : transformer 5Hostachy en CoproFirst, pas migrer.** Le même
dépôt devient le code de la plateforme ; la résidence en est la **référence**, sur ses
Raspberry Pi (D11, question 7 tranchée). C'est la suite logique de B (§3) : un code propre
pour B l'est aussi pour A, et la licence (§7) est déjà celle de la plateforme.

La phase 2 se mène **entièrement sur les Raspberry Pi, avec SQLite et une seule
copropriété**. Chaque lot a une valeur seul, et diminue le coût de la phase 3
quel que soit l'hébergeur. Proposée et validée le 08/10/2026 (« consigne la
proposition dans la spec et ouvre les tickets ») ; le code de chaque lot reste
soumis à accord, lot par lot.

| Lot | Contenu | Taille | Prérequis | Ticket |
|---|---|---|---|---|
| P2-1 | **Contrôle de la mémoire du processus** : tout nouvel état mutable de module est refusé ; les existants sont déclarés, à indexer ou du processus (§4.5). **Livré en v2.119.1** | S | — | #1743 |
| P2-2 | **Un seul accès aux ressources** d'une copropriété — base, fichiers, secret, expéditeur, services — par un module `contexte` qui lit `settings` tant qu'il n'y a qu'une copro ; garde-fou contre l'accès direct (§4.1, règle 3). Les états « à indexer » de P2-1 s'y soldent. **Livré le 10/10/2026** : `app/contexte.py` — `moteur()`, `nouvelle_session()`, `courante()` (URL de base, racine des fichiers, secret, expéditeur) et `etat(nom)`, le registre des états de processus indexé par la copropriété ; les six états à indexer y sont passés (plafond à zéro) ; 🔒 `test_contexte_source_unique.py` refuse `engine`, `SessionLocal` et les cinq réglages hors du contexte. Les services vivent déjà en base (E1) : ils suivent la base. Laissé exprès aux lots suivants : les racines de fichiers sont lues **une fois, au chargement** du module (P2-6 les résoudra à la requête), et le dossier des sauvegardes reste global (P2-3, §4.9) | L | P2-1 | #1744 |
| P2-3 | **Tâches planifiées par copropriété** : une enveloppe, un journal par copro, l'échec de l'une ne bloque pas les autres (§4.6). **Livré le 10/10/2026** : `contexte.pour_chaque_copropriete(tache, id)` enveloppe les onze enregistrements (neuf permanents, deux rattrapages) ; `contexte.dans(copro)` pose la copropriété servie dans une variable de contexte ; `TACHES_DE_LA_PLATEFORME` (vide : toutes les tâches d'aujourd'hui lisent la base d'une copropriété) ; 🔒 `test_taches_planifiees_declarees.py` refuse un `add_job` nu, et le démarrage journalise `HORS COPROPRIETE`. Le disque est sorti du contrôle des copropriétés à partir de la deuxième (`utils/sante_plateforme`, tâche `sante_plateforme`, #1814) ; son destinataire est l'opérateur de l'installation, un **réglage de l'installation** (`COURRIEL_OPERATEUR`, arbitré le 13/10/2026), joint par le SMTP de l'installation (`MAIL_*`) — jamais les comptes des copropriétés (D5). Reste pour la phase 3 : le dossier des sauvegardes est commun | M | P2-2 | #1745 |
| P2-4 | **Test d'étanchéité** sur deux copros factices aux identifiants identiques, avec cas zéro et témoin (§5.1, §5.3). **Livré le 10/10/2026** : la copropriété d'une requête se résout à l'ENTRÉE (`contexte.ResolutionCopropriete`, intergiciel ASGI le plus extérieur ; `contexte.resoudre` rend l'unique en phase 2) ; `contexte.moteur()` sert une base par copropriété, construite par la recette unique `database.creer_moteur` ; `test_etancheite_coproprietes.py` sème deux bases (administrateur et affaire de même numéro), balaie chaque route GET pour B et refuse toute réponse qui porte le témoin de A — cas zéro (routes appelées, réponses 200, lectures de B), témoin (un cache de module indexé par `user_id` est vu, `contexte.etat` ne l'est pas), jeton de A refusé par B. Vérifié par mutation : B servi par la base de A → `/admin/utilisateurs` le dénonce. Hors de sa portée, et dit dans le test : les écritures, les fichiers (P2-6), l'hôte inconnu (P2-9) | M | P2-2 | #1746 |
| P2-5 | **CI sur PostgreSQL** (informative, puis requise) ; adhérence à SQLite regroupée dans un module de dialecte ; migration initiale PostgreSQL préparée (§4.3). **Livré en v2.125.0** : la suite est VERTE sur PostgreSQL et le workflow devient un check requis (pilote psycopg, clés au régime de SQLite, migrations historiques non rejouées) ; toute l'adhérence vit dans `app/dialecte.py`, refusée ailleurs sur l'AST — les 39 « fichiers » comptaient la prose, il y en avait 14 ; une base neuve reçoit le schéma d'un coup, marqué à la tête (`utils/schema_initial`, `start.sh`) | M | — | #1747 |
| P2-6 | **Stockage des fichiers** derrière une interface, disque local puis stockage objet, préfixe par copro (§4.4). Décision à y prendre : `/uploads/*` n'est plus servi en statique par Caddy. **Arbitrage du 10/10/2026 : « Reporter »** — le service reste à Caddy (`forward_auth`) ; service par l'API ou URL signées se choisiront en phase 3, avec l'hébergeur dont ils dépendent. **Livré le 10/10/2026** : `utils/stockage` — l'interface `Stockage` et `StockageDisque`, une racine par copropriété lue au contexte à chaque appel, toute clé bornée sous elle ; les quatre racines figées au chargement (`RACINE_UPLOADS`, `REPERTOIRE_PRIVE`, `UPLOADS_ROOT`, `PDF_DIR`) et les trois traductions `"/app" + url` (pièces jointes, PDF, images d'affiche) passent par lui ; une écriture ne crée jamais la racine (volume non monté → erreur). 🔒 `test_stockage_source_unique.py`, et `test_televersement_source_unique.py` : seuls `enregistrer_fichier_recu` et les fichiers produits déclarés appellent l'écriture. Les chemins ABSOLUS gardés en base sont devenus des **clés** (#1816, migration 0283 : `document.fichier_cle`, `diagnostic_rapport.fichier_cle`, `annonce_hall.pdf_cle`) ; le chemin reste écrit le temps d'une version pour le retour arrière, son retrait est un second temps (`CONTRACTIONS`) | M | P2-2 | #1748 |
| P2-7 | **Export / import vérifié** d'une copro (comptes et sommes de contrôle par table) : sauvegarde vérifiée aujourd'hui, passage à PostgreSQL demain, réversibilité ensuite (§4.3, §4.9). **Livré en v2.125.0** : `utils/export_copropriete` — archive tar.gz au format neutre (manifeste, une table JSONL par modèle avec son empreinte SHA-256, fichiers du volume) ; l'import réécrit dans une base CIBLE neuve et refuse tout écart de compte ou d'empreinte ; *Admin › Maintenance › Export vérifié* prouve la restauration dans une base jetable | M | — | #1749 |
| P2-8 | **Scission du rôle `admin`** : administrateur de copro et opérateur de plateforme, sans donnée personnelle (§4.7, §5.5). **Arbitrages du 10/10/2026** : l'opérateur est un **rôle porté par un compte** (cumulable avec `admin`, il quittera la base pour le registre en phase 3) ; la **supervision technique** (installation, tâches planifiées, contrôles de fiabilité, contrôle de santé, purges) et la **base de données** (`/admin/db/*`) passent à lui seul. **Livré le 10/10/2026** : `ROLE_OPERATEUR` (`models/roles.py`, dans `roles_json` seulement, jamais la colonne `role`), `require_operateur` et `est_operateur` (`auth/deps.py`) sur neuf routes ; la migration 0276 l'accorde aux administrateurs d'alors, le seed à l'administrateur initial ; 🔒 `test_operateur_sans_donnee_personnelle.py` (§5.5) appelle chaque route de l'opérateur sur une base dont chaque donnée personnelle porte un témoin. Restent à l'administrateur : sauvegardes, export vérifié, consommation de l'IA — ils portent des données de la résidence | M | — (D8 confirmée le 08/10/2026) | #1750 |
| P2-9 | **Résolution par nom d'hôte** (§4.1, règles 1 et 2). ⚠️ Le standby est servi par son IP locale (`ORIGIN`) : le registre rattache **plusieurs hôtes** à une même copro. En dernier | S | P2-2 | #1751 — **livré** (421) |

**Ce que la phase 2 ne fait pas, exprès :**

- **aucune colonne `copropriete_id`** : ce serait l'option C, écartée (§3) ;
- ~~**pas de PostgreSQL en production sur les Raspberry Pi**~~ — **révisé le
  08/10/2026** (D13) : la référence restant durablement sur les RPi, il passe lui aussi
  sous PostgreSQL, **après** la phase 2 (#1759), pour qu'un seul moteur soit
  exercé en production ;
- **pas d'outillage de flotte** (créer, migrer, sauvegarder N copros) avant le
  choix de l'hébergeur : il en dépend.

## 8 ter. La distribution en lots (arbitrage du 08/10/2026)

Consignée et ouverte le 08/10/2026 (« consigne l'architecture dans la spec et
ouvre les tickets ») ; le code de chaque lot reste soumis à accord, lot par lot.

| Lot | Contenu | Taille | Prérequis | Ticket |
|---|---|---|---|---|
| DI-1 | **Un tag par version**, posé par la CI ; images construites, **signées**, publiées avec leur SBOM. **Livré en v2.120.0** | M | — | #1753 |
| DI-2 | **Branche `replica`** protégée, avance rapide seulement ; **geste de promotion** avec critères affichés et notes de version. **Livré en v2.120.0** | S | DI-1 | #1754 |
| DI-3 | **Déploiement standard** d'une installation, séparé de l'exploitation des RPi ; aucune donnée de la résidence dans une image. **Livré en v2.120.0** | M | DI-1 | #1755 |
| DI-4 | **Mise à jour nocturne réversible** : sauvegarde, signature, migrations base par base, santé, retour arrière ; échelonnée, épinglable. **Livré en v2.120.0** ; **sous PostgreSQL** (10/10/2026) : sauvegarde par l'export réimporté dans une base jetable, restauration par schéma initial + import, PostgreSQL d'une réplique sans réplication ni port (surcouche, `pg_hba` propre), et un essai de bout en bout sur machine jetable, SQLite et PostgreSQL (workflow « Essai de mise à jour ») | L | DI-1, DI-2, DI-3, DI-5 | #1756 |
| DI-5 | **Migrations compatibles sur une version** (ajouter, puis retirer), avec son garde-fou `test_migrations_compatibles.py`. **Livré en v2.119.1** | S | — | #1757 |
| DI-6 | **La référence tire son image** au lieu de la construire sur les RPi ; construction locale en secours, avec alerte. **Livré en v2.122.0** | M | DI-1 | #1758 |
| DI-7a | **L'image et le compose savent tourner sur PostgreSQL** — service `postgres` sous profil, éteint par défaut ; pilote psycopg dans l'image ; `start.sh` attend la base et ne migre jamais une base illisible. **Livré en v2.127.0** | S | P2-5, P2-7 | #1759 |
| DI-7b | **L'exploitation sous PostgreSQL** : réplication en continu vers le standby, bascule et failover par promotion, sauvegarde par l'**export vérifié** (P2-7, réimporté dans une base jetable), maintenance, contrôles (C37, point 22), règle d'or réécrite — éprouvés avant la bascule (D16). **Livré en v2.127.0–v2.129.1** ; réplique réelle posée le 09/10/2026, première **promotion réelle** par la bascule du 10/10 à 02:00 (rpi2 → rpi1, ancien primaire reconstruit en réplique en 10 s) | L | DI-7a | #1781 |
| DI-7c | **La résidence passe à PostgreSQL** : fenêtre choisie, export vérifié de `app.db`, import vérifié, retour arrière gardé 7 jours (`retour-sqlite.sh`). **Fait le 10/10/2026 à 08:56** (v2.130.2) : 82 tables, 16 196 lignes, 27 s de coupure. Une première tentative (09/10, 23:52) a été refusée à l'import — tables en cycle, puis séparateurs Unicode trouvés en répétant l'import sur l'archive réelle — et l'application est revenue sur SQLite d'elle-même (v2.129.1). Après la bascule, un filtre d'énumération que seul PostgreSQL refuse a cassé le fil d'accueil 18 min (v2.130.3, garde-fou `test_enum_valeurs_comparees`) | M | DI-7b | #1782 |
| DI-8 | **Le rôle de l'installation dans l'administration** : référence (`main`), réplique (`replica`) ou inconnu ; version, écart à la branche suivie (règle 11) | S | — ; DI-1 pour l'écart à `replica`. **Livré en v2.125.0** : `ROLE_INSTALLATION`, service *Vérification de la version* coupé par défaut | #1761 |

**Ordre conseillé** : DI-5 dès maintenant (il sert aussi au retour arrière de la
référence) ; DI-1 puis DI-6, qui suppriment les builds sur les RPi ; DI-2 et DI-3 ;
DI-7 après la CI PostgreSQL ; DI-4 en dernier, avec la première installation
(phase 3).

## 8 quater. Le registre des installations en lots (arbitrage du 12/10/2026)

Ouverts le 12/10/2026 ; le code de chaque lot reste soumis à accord, lot par lot.

| Lot | Contenu | Taille | Prérequis | Ticket |
|---|---|---|---|---|
| R0 | **Conditions de l'inscription** et information de l'administrateur d'installation (finalité, durée, purge, droits) ; relecture juridique. **Rédigé le 12/10/2026** en contrat d'engagements réciproques (D26, `api/app/registre/conditions/v1.md`), lu et accepté par l'auteur ; la relecture juridique reste à faire | S | — | #1876 |
| R1 | **Base `plateforme` et contrat de données** versionné ; point d'inscription signé et plafonné, sous un nom dédié ; aucun effet côté installation. **Livré en v2.143.0**, éteint tant que le `.env` de la référence ne déclare ni sa base ni son nom (`scripts/exploitation/creer-base-plateforme.sh`) | M | — | #1877 |
| R2 | **Inscription et bail** côté installation, en **mode constat** : l'état est calculé et affiché, jamais appliqué ; mode essai | M | R1 | #1878 |
| R3 | **Rapport nocturne**, joint à la mise à jour de la nuit (#1756) | S | R2 | #1879 |
| R4 | **L'onglet « Installations » de la référence** : liste, fiche, validation, canal, suspension, alertes, journal des décisions | M | R1, R3 | #1880 |
| R5 | **Canaux et version cible** portés par le bail ; déploiement par vagues, épinglage | M | R2, R4 | #1881 |
| R6 | **Mode limité et suspension appliqués** — seulement après plusieurs semaines de R2 sans faux positif | M | R0, R2 à R5 | #1882 |
| R7 | **Relevé de consommation**, déclaratif | S | R3 ; modèle économique | #1883 |
| R8 | **Transfert du rôle de référence** : acte signé, époque, chaîne de clés ; jamais deux références | L | R1, R2, R5 | #1884 |

**Ordre conseillé** : R0 et R1 en parallèle ; R2, R3, R4 ; R5 ; R6 seulement sur
constat mesuré — un contrôle qui bloque se prouve d'abord en observation ; R8
avant tout déménagement de la référence ; R7 quand le modèle économique sera choisi.

## 9. Les questions encore ouvertes

1. **RGPD** : vis-à-vis de chaque syndicat des copropriétaires (responsable de
   traitement), l'opérateur devient **sous-traitant**. Il faudra un contrat de
   sous-traitance, un registre, des mentions légales et une politique de
   confidentialité **par copro**, et un hébergeur conforme. À faire valider.
   S'y ajoutent les conditions de l'inscription d'une installation et le contact
   de son administrateur (§4.11, #1876).
2. **Hébergeur** des installations CoproFirst : PostgreSQL géré, stockage objet,
   coffre à secrets, localisation des données. Et le **registre d'images** (#1753).
3. ~~**Nom du produit**~~ — tranché le 07/10/2026, revu le 09/10/2026 : **CoproFirst** (D9 ; CoproConnect était déjà pris). Marque
   déposée le 09/10/2026 (§7) ; l'opposition se clôt le 30/12/2026.
4. ~~**D8**~~ — confirmée le 08/10/2026 : **deux comptes indépendants**.
5. ~~**Licence**~~ — AGPL-3.0-or-later (D10) depuis la v2.116.0 (#1726) ; politique
   de marque dans `MARQUE.md` (#1736), à faire relire (§7).
6. **Modèle économique** : gratuit ou facturé. L'AGPLv3 permet de facturer
   l'hébergement ; elle interdit seulement d'en fermer le code. Toujours ouvert
   au 12/10/2026 ; il conditionne le relevé de consommation (#1883).
7. ~~**La résidence actuelle**~~ — tranché le 08/10/2026 (D11) : elle **reste sur
   les Raspberry Pi**, comme **référence** du produit ; sa haute disponibilité est
   conservée.
8. **Durée de rodage** avant qu'une version soit proposée à la promotion (§4.10) :
   N jours à fixer.
