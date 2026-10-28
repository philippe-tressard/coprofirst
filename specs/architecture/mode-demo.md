# Mode démo — l'installation de démonstration publique

> 🧭 **Spécification de CIBLE, en conception** (13/10/2026). Comme
> [`multi-coproprietes.md`](multi-coproprietes.md), et contrairement au reste de
> `specs/`, ce document décrit **où le produit va**. Le **travail** vit dans les
> tickets (§10) ; ce document en porte les **décisions** et leurs raisons, et se met
> à jour **à chaque arbitrage**, daté. Toute décision qui n'y figure pas n'est pas
> prise. Les décisions M1 à M9 et les six questions du §11 sont arbitrées le
> 13/10/2026.

## 1. L'objectif et l'exigence

Offrir à **n'importe quel visiteur** de la page d'accueil de CoproFirst
(`coprofirst.fr`) un essai du produit **sans inscription** : un clic sur un rôle
(résident, conseil syndical, administrateur), et il se trouve dans une résidence
fictive, peuplée, où chaque écran a du contenu.

L'exigence, de **rang 1** (sécurité et conformité) :

1. **Aucun envoi réel ne part** : ni courriel, ni message WhatsApp, ni appel à une
   IA, ni requête vers un service tiers. Pas « presque aucun » : le visiteur saisit
   ce qu'il veut, y compris une adresse qui n'est pas la sienne.
2. **Aucun visiteur ne peut détourner l'installation** : ni ses réglages (serveur
   d'envoi, clés, URL), ni les comptes des autres visiteurs, ni la machine.
3. **Rien de ce qu'un visiteur saisit ne survit à la nuit.**
4. **Le mode démo est un réglage de l'installation, pas une variante du code** :
   un seul chemin de code (D13 de `multi-coproprietes.md`), une installation
   standard (`deploiement/standard/`) à laquelle on ajoute `MODE_DEMO=oui`.

Le critère qui départage les solutions, repris de `multi-coproprietes.md` :
**combien de lignes faut-il oublier pour qu'un envoi réel parte ?** Une démo où
chaque route doit penser à vérifier le mode n'est pas sûre, elle n'est que
disciplinée. Les gardes se posent **aux portes** (§4), jamais route par route.

## 2. L'infrastructure en place (13/10/2026)

| Élément | État |
|---|---|
| Machine | Oracle Cloud *Always Free*, Ampere A1 (arm64), Paris : 1 OCPU, 6 Go, 100 Go — agrandissable à 2 OCPU / 12 Go sans frais |
| Système | Ubuntu 24.04, Docker 29.9, Compose 5.6, mises à jour de sécurité appliquées |
| Exposition | tunnel Cloudflare `coprofirst-demo` → `http://localhost:80` (le Caddy de CoproFirst) ; **aucun port entrant** ouvert |
| Adresse | **`demo.coprofirst.fr`** — sous-domaine, pas `coprofirst.fr/demo` : le produit ne sait pas tourner sous un chemin, et un chemin partagerait l'origine du navigateur avec la page d'accueil (même raison que D27, règle 1) |
| DNS | `coprofirst.fr` délégué à Cloudflare, messagerie OVH conservée |
| Coût | nul dans les limites *Always Free* ; compte en paiement à l'usage (pour la capacité ARM), budget d'alerte au premier centime |

Le site vitrine (projet `C:\Dev\CoproFirst-Site`) porte une page « Démo » qui
**publie les identifiants** des trois comptes de démonstration et renvoie au
formulaire de connexion de `demo.coprofirst.fr` (§5, révisé le 13/10/2026).

## 3. Les décisions (arbitrées le 13/10/2026)

| # | Sujet | Décision | Conséquence |
|---|---|---|---|
| M1 | Activation | **`MODE_DEMO=oui` dans `.env`**, absent = non. Un seul lecteur, `utils/demo.est_demo()`, sur le modèle de `utils/installation.role_installation()` | §4.1 ; le réglage ne s'écrit **jamais** depuis l'interface |
| M2 | Zéro envoi | **les portes d'envoi refusent** en mode démo — moteur de courriel, bridge WhatsApp, appel à l'IA, relève IMAP, requête GitHub —, quelle que soit la configuration en base | §4.2 ; un administrateur de démo ne peut rien rallumer |
| M3 | Gestes fermés | **un registre unique des gestes fermés en démo** (`utils/demo.GESTES_FERMES`), appliqué par **une** garde à l'entrée des requêtes ; réponse 403 « Indisponible en démonstration » | §4.3 ; une route oubliée se voit dans un test, pas en production |
| M4 | Entrée | ~~une adresse par personnage, sans mot de passe~~ — **révisé le 13/10/2026 (#1932)** : le **formulaire de connexion**, avec trois identifiants publiés sur la page « Démo » du site vitrine ; l'administrateur n'est pas public — **révisé le 15/10/2026 (#1985)** : il est séparé de l'opérateur, et l'auteur **peut** le publier ; l'opérateur ne l'est jamais | §5 |
| M5 | Comptes | **comptes partagés** : tous les visiteurs qui se connectent en `user-copro` sont le même compte | §5 ; §11, question 1 |
| M10 | Fichiers | **aucun téléversement** de visiteur ; le jeu de démo apporte ses images et ses documents | §4.3 ; §11, question 2 |
| M11 | Plafond du registre | la démo **s'inscrit au registre** comme toute réplique dès qu'il l'accepte ; d'ici là, une **exception déclarée** au plafond de 5 utilisateurs (D18), lue sous `est_demo()` | §9 ; §11, question 3 |
| M6 | Données | **un générateur** (`app/demo/`), qui fabrique la résidence fictive **avec des dates relatives à aujourd'hui** — jamais une archive figée | §6 |
| M7 | Remise à zéro | **chaque nuit**, API arrêtée : base vidée, fichiers vidés, générateur rejoué | §7 |
| M8 | Interface | **bandeau permanent** sur tous les écrans, connexion comprise ; le formulaire de connexion reste, sans inscription ni mot de passe oublié (révisé par #1932) ; **pas d'indexation** | §8 |
| M9 | Conformité | mentions légales et politique de confidentialité **propres à la démo** ; avertissement « ne saisissez aucune donnée réelle » ; effacement sous 24 h | §9 |

## 4. Les gardes

### 4.1 Le réglage — un seul lecteur

- `Settings.mode_demo: bool = False` (`api/app/config.py`), documenté dans
  `.env.example` (🔒 `test_env_exemple_coherent.py` l'exige).
- **Un seul lecteur** : `utils/demo.est_demo()`. 🔒 Un test calqué sur
  `test_installation.py` (`test_le_role_ne_se_lit_qu_ici`) refuse toute autre
  lecture de `mode_demo`.
- Le front l'apprend par `GET /config` : une clé **calculée** `mode_demo`, ajoutée
  à la liste blanche publique (`routers/config.py`, `_PUBLIC_KEYS`) et **refusée en
  écriture** (`utils/reglages.REFUSEES`, #2055). Pas de variable `PUBLIC_MODE_DEMO` côté front :
  ce serait une seconde source.
- `compose.images.yml` ne la pose pas : une réplique ordinaire n'est jamais une
  démo par accident.

### 4.2 Les portes d'envoi

Relevé du 13/10/2026 : il n'existe aucun interrupteur global, et chaque
interrupteur existant (`smtp_enabled`, `whatsapp_enabled`, `llm_actif`,
`imap_enabled`) **se réécrit par `PUT /config`** — donc par le personnage
administrateur. La garde se pose donc dans le code, à la porte, sous `est_demo()` :

| Porte | Où | En démo |
|---|---|---|
| Courriel (moteur et bouton de test) | `utils/email.envoi_actif()` — lu par `send_email`, `send_email_group` et `POST /config/smtp-test` | rend **faux** ; le courriel est **inscrit** dans `HistoriqueEmail` avec le statut « non envoyé (démonstration) », pour que l'administrateur voie ce qui serait parti |
| WhatsApp | `utils/whatsapp._poster_au_bridge` et les deux lectures `GET /status`, `GET /qr` | refus avant tout appel réseau ; et **pas de conteneur `whatsapp-bridge`** sur la machine de démo |
| IA | `utils/llm._appeler`, `llm_modeles`, `tarif_sources` | refus avant tout appel réseau |
| Relève IMAP | `utils/courriel_boite.relever`, `POST /config/imap-test` | refus |
| Vérification de la version | `utils/installation.verifier` | refus |

Règles :

1. **Le puits rend faux, jamais un faux succès.** `send_email` rend `True` quand
   le message est parti, et des appelants en déduisent un état : la purge des
   comptes inactifs n'inscrit l'avertissement que sur `True`, et **supprimerait**
   les comptes trente jours plus tard sur un faux succès.
2. **Les courriels de sécurité ne font pas exception en démo.** Hors démo, aucun
   interrupteur de service ne les coupe (§4.8 de `multi-coproprietes.md`) ; en
   démo, la garde n'est **pas** un service du registre mais une propriété de
   l'installation, au niveau de l'infrastructure — c'est pourquoi elle vit dans
   `envoi_actif()` et non dans `utils/services`. 🔒
   `test_courriels_securite_hors_service.py` reste vrai : le moteur n'importe pas
   `utils/services`.
3. **Les services se lisent éteints** : en démo, `service_actif()` rend faux pour
   l'IA, la diffusion, les réponses par courriel et la vérification de version, et
   l'onglet *Administration › Services* les montre éteints avec la mention
   « indisponible en démonstration ».
4. 🔒 **Un test par porte** : le mode démo posé, une configuration en base qui
   allume tout, et un faux serveur qui échoue s'il est contacté
   (`tests/test_mode_demo_envois.py`).
5. **Restent permis, exprès** (13/10/2026) : les échanges avec le **registre des
   installations** (`app/inscription/` — inscription, bail, rapport nocturne), puisque
   la démo s'y inscrit (M11) ; et les **alertes de plateforme** à l'opérateur
   (`utils/sante_plateforme`, disque plein), qui passent par leur propre canal SMTP et
   qu'aucun visiteur ne déclenche.

### 4.3 Les gestes fermés

`utils/demo.GESTES_FERMES` déclare, **par familles**, les routes refusées en
démo ; une garde unique, posée à côté de `contexte.ResolutionCopropriete`
(`main.py`), répond 403 avec un message lisible. Hors démo, elle ne fait rien.

| Famille | Routes (relevé du 13/10/2026) | Pourquoi |
|---|---|---|
| Inscription et comptes anonymes | `POST /auth/register`, `/auth/renvoyer-verification`, `/auth/mot-de-passe-oublie`, `/auth/reinitialiser-mot-de-passe` | un visiteur ne crée pas de compte : il entre par un personnage |
| Identité des comptes partagés | `POST /auth/change-password`, `PATCH /auth/me` (adresse), `PATCH /admin/utilisateurs/{id}` (adresse, activation), `DELETE /admin/utilisateurs/{id}`, `ajouter-role`, `retirer-role`, `ban-communaute` | un visiteur fermerait le personnage aux autres |
| Réglages et secrets | `PUT /config`, `POST`/`DELETE /config/logo`, `PATCH /copropriete`, `/perimetres` (écriture), `PATCH /admin/modeles-email/*` et réinitialisations | l'installation ne se reconfigure pas |
| Tests de canaux | `POST /config/smtp-test`, `/imap-test`, `/whatsapp-test`, `/llm-test`, `/llm-tarif`, `PUT /config/whatsapp-scheduled/{id}`, `GET /config/whatsapp-qr`, `/whatsapp-status` | appels sortants ; doublés par §4.2 |
| Exploitation | `/admin/sauvegardes/*` (écriture), `/admin/maintenance/*`, `/admin/db/*`, `/admin/export-copropriete*` | charge, disque, et export de la base entière |
| Téléversements (M10) | **la porte unique** `utils/fichiers.enregistrer_fichier_recu` refuse en démo — photos, documents, pièces jointes, logo ; et les routes d'import `/admin/imports/*`, `/admin/imports-vigik/*`, imports de télécommandes | un site public où n'importe qui dépose un fichier visible des autres héberge du contenu non modéré, même 24 h |
| Partage par courriel | `POST /partage` (envoi vers une adresse libre) | doublé par §4.2 |

🔒 Un test parcourt **toutes** les routes montées et exige que chaque route
d'une famille ci-dessus (reconnue à son préfixe et à sa méthode) figure au
registre — une route ajoutée plus tard sous `/admin/sauvegardes` ou `/config/`
est refusée par défaut d'être déclarée. Une route ouverte **exprès** dans une
famille fermée se déclare avec sa raison.

Ce qui **reste ouvert**, et c'est voulu : créer, commenter, archiver, voter,
publier — tout ce qui montre le produit. Un visiteur peut donc défaire le travail
d'un autre jusqu'à la nuit ; c'est le prix des comptes partagés (§11, question 1).

### 4.4 Les tâches planifiées

`utils/taches` déclare `TACHES_HORS_DEMO`, chacune avec sa raison ; le démarrage
ne les enregistre pas en démo, et 🔒 `test_taches_planifiees_declarees.py`
l'étend.

| Tâche | En démo | Raison |
|---|---|---|
| `purge_comptes_inactifs` | coupée | supprime des comptes ; la remise à zéro la remplace |
| `backup`, `backup_rattrapage` | coupées | rien à sauvegarder : la démo se régénère — son rapport nocturne le déclare (`Sauvegarde.attendue`), et la référence ne s'en alarme pas (#1982) |
| `courriel_reponses`, `synthese_affaires`, `whatsapp_scheduled` | coupées | IMAP, IA, WhatsApp |
| `health_check` (06:00) | coupée | son seul effet est un courriel |
| `telemetry_aggregation`, `manuel_pdf_*` | gardées | internes, sans envoi |
| `bail_installation`, `sante_plateforme`, `sauvegarde_plateforme` | gardées | le registre (M11) et l'opérateur ; la dernière ne tourne que chez la référence |

## 5. L'entrée : le formulaire, trois comptes publiés

Révisé le 13/10/2026 par l'auteur (#1932). L'entrée en un clic par personnage
(`/api/demo/entrer/{personnage}`, livrée par #1903) est **retirée** : on se connecte
par le formulaire habituel, avec des identifiants publiés.

### 5.1 Les comptes publics

| Identifiant | Mot de passe | Qui |
|---|---|---|
| `user-cs@demo.coprofirst.fr` | `PSWD-user-cs1` | copropriétaire résident, membre du conseil syndical |
| `user-copro@demo.coprofirst.fr` | `PSWD-user-copro1` | copropriétaire résident |
| `user-loc@demo.coprofirst.fr` | `PSWD-user-loc1` | locataire |

- Ils vivent dans `app/demo/personnages.py`, et le générateur (§6) les crée :
  `actif`, adresse vérifiée, **mot de passe publié** — public et versionné, exprès,
  et seulement en démo : le générateur refuse ailleurs. Chacun passe par la règle
  de robustesse du produit (`verifier_robustesse`) avant d'être haché.
  🔒 `test_demo_comptes_publics.py`.
- `demo.coprofirst.fr` n'a pas de serveur de courrier : rien n'y serait livré, et
  aucune porte d'envoi n'est ouverte en démo (§4.2). Les autres habitants du jeu
  gardent une adresse en `.invalid` (RFC 2606).
- Un visiteur ne peut pas fermer un compte aux autres : changer de mot de passe ou
  d'adresse est fermé en démo (§4.3), et aucun verrouillage après des échecs
  n'existe (la limite de débit de `/auth/*` est par adresse IP).
- La page « Démo » du site vitrine publie ces identifiants et renvoie à
  `https://demo.coprofirst.fr/auth/connexion`.

### 5.2 L'administrateur et l'opérateur

Aucun compte du jeu n'est administrateur : le seed crée les **deux comptes
techniques** d'une installation standard (#1985, 15/10/2026), dont les mots de
passe ne paraissent que dans les journaux du serveur, à chaque remise à zéro —
sauf si le `.env` du serveur les fixe :

| Compte | Rôles | En démo | Mot de passe fixe |
|---|---|---|---|
| `admin@localhost` | admin | **publiable** par l'auteur | `DEMO_ADMIN_MOT_DE_PASSE` |
| `operateur@localhost` | admin + opérateur | **jamais publié** | `DEMO_OPERATEUR_MOT_DE_PASSE` |

Pourquoi deux : jusqu'au 15/10, un seul compte portait les deux rôles, et le
publier aurait livré l'opérateur — dont les routes du registre
(`POST /admin/installation/inscription`, `/bail`) restent **ouvertes** en démo
(M11) : un visiteur aurait accepté le contrat au nom de l'auteur ou réécrit le
bail. L'opérateur reste administrateur, car ses écrans vivent sous `/admin`
(#1750).

Vérifié avant de séparer (#1985) : ce qu'un administrateur lit en démo ne contient
aucune donnée réelle de visiteur (§9) ; un administrateur seul ne prend pas la
main sur l'opérateur (rôles, suppression, modification de compte et
réinitialisation de mot de passe sont fermés, §4.3) ; la délégation n'élève pas
(l'aidant n'hérite que du statut, `utils/statuts_lus`).

Les comptes techniques ne se montrent **à aucun visiteur** dans un choix de
personne : `GET /admin/utilisateurs` les tait au conseil syndical, et
`GET /bailleur/search-locataire` à tous (`utils/comptes.condition_hors_comptes_techniques`).

### 5.3 Ce qui reste de l'entrée en un clic

`auth/session_ouverte.ouvrir_session` : la pose des jetons et des cookies,
extraite pour elle (#1903), reste la fonction unique de `login` et `refresh`.

### 5.4 Le syndic

S'il devient un compte de la démo, il porte `roles_json="externe"` : le parcours
d'inscription écrit aujourd'hui `role=externe` mais `roles_json="syndic"`, que
`has_role` ne lit pas comme externe (relevé du 13/10/2026, #1911).

## 6. Le jeu de données fictif

### 6.1 Un générateur, pas une archive

L'export d'une copropriété (`utils/export_copropriete`) sait réimporter une
archive dans une base neuve, mais une archive **vieillit** : dans un mois, le
calendrier, les échéances de contrats et les sondages n'afficheraient que du
passé, et une table retirée par une migration ferait refuser l'archive. Le jeu de
démo est donc **fabriqué** à chaque remise à zéro par `python -m app.demo.charger`,
avec le code de la version installée : il ne peut pas être en retard sur le schéma.

- Il vit dans `api/app/demo/` (il part dans l'image), découpé par domaine
  (`patrimoine.py`, `comptes.py`, `affaires.py`, `vie_collective.py`,
  `prestataires.py`, `acces.py`…) — aucun fichier au-delà de 500 lignes.
- Les dates se calculent depuis `horloge.aujourd_hui()` : une affaire « ouverte il
  y a trois jours », une AG « dans trois semaines », un contrat « échu dans deux
  mois ».
- Il **passe par les modèles et les fonctions du domaine** (création d'affaire,
  rattachement à un lot…), jamais par du SQL : une règle métier qui change
  s'applique d'elle-même au jeu de démo.
- 🔒 Un test charge le jeu dans une base en mémoire et vérifie que chaque écran
  principal a du contenu (au moins N affaires ouvertes, une actualité, un
  événement à venir, un sondage, un contrat, un document).
- Livré en lot D4 (#1904) : `python -m app.demo.charger` rend **0** (chargé), **2**
  (pas en démo) ou **3** (base non vierge — rien n'est écrit). Les PDF passent par
  le moteur du projet (`pdf_theme.html_to_pdf`) et sont rendus **avant** toute
  écriture : un moteur absent laisse la base vierge. Le seed tourne au milieu, entre
  le patrimoine (qu'il lit pour l'arbre des périmètres) et le reste ; le personnage
  « Administrateur » tient lieu d'administrateur initial ; le seed crée aussi
  l'opérateur (§5.2).

### 6.2 Le contenu

| Écran | Contenu minimal |
|---|---|
| Identité | une résidence **inventée** (nom, adresse fictive, logo dessiné pour la démo), « Résidence de démonstration » en sous-titre |
| Patrimoine | 2 à 3 bâtiments, une trentaine de lots, l'arbre des périmètres |
| Annuaire | une vingtaine de résidents, le conseil syndical, un syndic fictif |
| Affaires | une quinzaine, toutes catégories et tous statuts, avec suites, photos et échanges |
| Actualités, calendrier | des actualités récentes, une AG et des interventions à venir — dont une coupure à venir sur le bâtiment du compte `user-loc` (#2027) |
| Vie collective | sondages (ouverts et clos), idées, petites annonces |
| Prestataires, contrats | quelques prestataires, des contrats d'entretien actifs — le carnet d'entretien s'en déduit |
| Accès | badges et télécommandes rattachés aux lots ; un bail sur le lot de `user-loc`, qui lui confie un badge (#2027) |
| Documents | règlement de copropriété et procès-verbal **rédigés pour la démo** |

Ce que le site vitrine promet à chaque compte public se lit dans ses écrans : 🔒
`test_demo_jeu.py` le vérifie par les routes, avec la session du compte —
pour `user-loc`, un badge confié par son bail et une coupure à venir dans son
bâtiment.

### 6.3 Ce qui est interdit dans le jeu

- **Aucune donnée réelle** : ni nom, ni adresse, ni photo de personne. Les noms
  viennent de la liste blanche de `test_identites_fictives.py` (`FICTIFS`), et le
  dossier `app/demo/` est ajouté à `DONNEES` pour que 🔒 le contrôle les juge.
- Jamais `import-data/` (données réelles de 5Hostachy, hors dépôt).
- Images et documents **produits pour le projet**, déclarés dans `REUSE.toml` ; une
  image reprise d'ailleurs se déclare dans `CONTENUS_TIERS` (🔒
  `contenus_tiers.py`).

## 7. La remise à zéro nocturne

`deploiement/demo/reinitialiser.sh`, lancé par la crontab de l'utilisateur qui
pilote Docker, **après** la mise à jour nocturne (`mise-a-jour.sh`, 04:30) — par
exemple à 05:15 —, pour que le jeu soit fabriqué par la version qui vient d'être
installée :

1. arrêter l'API (aucune écriture pendant la remise à zéro) ;
2. vider la base et le volume `uploads` ;
3. poser le schéma (`utils/schema_initial`), puis `python -m app.demo.charger`
   (le seed, puis le jeu), en conteneur ponctuel (`run --rm --no-deps`) ;
4. relancer l'API, sonder `/api/health`, rendre compte à l'administration
   (`POST /admin/maintenance/rapport`) ;
5. en échec : le rapport le dit, et la démo reste arrêtée plutôt que de servir une
   base à moitié chargée.

- **Moteur** : PostgreSQL pour la démo de CoproFirst (§11, question 4) — vider la
  base, c'est supprimer et recréer le schéma `public` dans le serveur qui tourne,
  jamais le volume `pg_data` (`commande_vidage`). Éprouvé le
  13/10/2026 sur la machine de démo : PostgreSQL 17, chargement, refus d'une base
  pleine, vidage, rechargement.
- `mise-a-jour.sh` exige `COPROFIRST_SAUVEGARDES` : en démo, un dossier local
  suffit, puisque rien n'est à préserver ; le script de remise à zéro le vide.
- 🔒 La logique de décision (faut-il recharger, la santé est-elle bonne) s'isole en
  fonctions pures avec `--selftest`, branché au job `test-scripts`, comme les
  autres scripts d'infrastructure.

## 8. L'interface

Livrée par #1906. `GET /config` porte la clé calculée `mode_demo` ; le front la lit
par `modeDemoStore` (`#lib/stores/pageConfig`) et rien d'autre.

- **Bandeau permanent** (`BandeauDemo`) : « Démonstration — résidence fictive. Ce
  que vous saisissez est visible des autres visiteurs et effacé chaque nuit. Aucun
  courriel, message WhatsApp ni appel à l'IA n'est réellement envoyé. » Purement
  informatif (`role="note"`, rien de focalisable), teinte d'`EncartAvertissement`.
  ⚠️ Il vit **dans le squelette `(app)`**, en tête de la colonne de contenu, et
  **sur la page de connexion** — pas dans le layout racine, comme prévu d'abord :
  là, la barre fixe du mobile l'aurait recouvert. Les autres pages publiques
  (inscription, mot de passe oublié) sont fermées au serveur en démo.
- **Page de connexion** : en démo, le **formulaire reste** (§5, révisé le
  13/10/2026 — les liens par personnage de #1906 sont retirés par #1932) ;
  « Créer un compte » et « Mot de passe oublié » disparaissent.
- **Gestes fermés** : le serveur refuse (§4.3) ; l'écran affiche le message du
  403 par le canal d'erreur existant. Les onglets d'administration entièrement
  fermés (SMTP, IA, WhatsApp, Sauvegardes) portent l'encart `EncartDemo`.
- **Pas d'indexation** : en démo, `X-Robots-Tag: noindex, nofollow` posé au rendu
  serveur (`routes/+layout.server.ts`) et la balise `<meta name="robots">` dans le
  layout racine. ⚠️ **Pas** de `robots.txt` qui interdit tout, contrairement à ce
  que prévoyait ce paragraphe : un robot à qui l'exploration est interdite ne lit
  jamais le `noindex`, et une page découverte par un lien externe peut alors
  s'indexer sans contenu. `front/static/robots.txt` reste commun à toutes les
  installations.
- Le **manuel** (encadré « Vous visitez la démonstration ? » du guide express) et
  le **README** disent ce qu'est la démo et ce qui y est fermé.

## 9. La conformité

Livrée par #1907.

- **Mentions légales et politique de confidentialité de la démo** :
  `app/demo/legal.py`, posées par le générateur après le seed — donc reposées à
  chaque remise à zéro. Elles nomment les hébergeurs (Oracle France S.A.S., région
  de Paris ; Cloudflare, Inc. pour le DNS et le tunnel). L'**éditeur** et le
  **contact** se lisent dans `DEMO_EDITEUR` et `DEMO_CONTACT` : le dépôt public ne
  nomme personne. Sans éditeur, la démo se déclare éditée à titre non
  professionnel (LCEN art. 6, III, 2) ; sans contact, le chargement le signale.
- **Données traitées** : ce que le visiteur saisit (finalité : essayer le
  produit ; conservation : jusqu'à la remise à zéro, **moins de 24 h**, sans
  sauvegarde) ; l'**adresse IP** n'est écrite nulle part — le journal d'accès de
  Caddy est anonyme (#1588), uvicorn n'en tient pas (#1300), la base n'en a pas —,
  seulement tenue en mémoire par la limitation de débit, et vue par Cloudflare ;
  les cookies de session (strictement nécessaires : pas de consentement).
- **Avertissement à la saisie** : le bandeau le dit, et **chaque boîte de
  formulaire** (`FormulaireCreation`, création et correction) le rappelle
  (`EncartDemo saisie`).
- **Télémétrie** : rattachée aux personnages partagés, elle ne désigne personne ;
  elle ne stocke aucune adresse IP, et s'efface avec la base chaque nuit.
- **Registre des installations** : le plafond de 5 utilisateurs du mode limité
  (D18) n'est **pas appliqué** (mode constat) — la démo s'affiche « limitée — non
  inscrite », sans effet. Elle s'inscrit à l'installation, par l'opérateur de
  l'installation ordinaire qui précède le passage en démo — ses personnages ne
  le sont pas —, et l'inscription survit aux remises à zéro ; l'exemption sous
  `est_demo()` s'écrit avec l'application du plafond (R6, #1882).

## 10. Le découpage en lots

| Lot | Contenu | Dépend de | Ticket |
|---|---|---|---|
| **D1** — socle | `MODE_DEMO`, `est_demo()`, clé `mode_demo` de `GET /config`, garde des gestes fermés et son registre, test « toute route d'une famille fermée est déclarée » | — | #1901 |
| **D2** — zéro envoi | gardes aux portes (§4.2), courriel inscrit « non envoyé », services lus éteints, tâches hors démo, tests par porte | D1 | #1902 |
| **D3** — entrée | extraction de `ouvrir_session`, route `/api/demo/entrer/{personnage}`, limite, journal | D1 | #1903 |
| **D4** — jeu de données | générateur `app/demo/`, personnages, images et documents de démo, test de contenu, test des identités | D3 (personnages) | #1904 |
| **D5** — remise à zéro | `deploiement/demo/` (script, `LISEZMOI.md`, crontab), `--selftest` | D4 | #1905 |
| **D6** — interface | bandeau, connexion par personnage, encarts, `noindex`, manuel et README | D1, D3 | #1906 |
| **D7** — mise en service | mentions légales, installation sur la machine Oracle, adresses transmises à la page d'accueil | D1 à D6 | #1907 |
| **D8** — entrée par le formulaire | trois comptes publiés (§5), administrateur du seed, retrait de l'entrée en un clic et des boutons de la connexion | D3, D4, D6 | #1932 |

Relevés **hors démo** faits pendant l'étude, à traiter pour eux-mêmes :
le rendu PDF (WeasyPrint) sans `url_fetcher` restreint peut aller chercher une
image externe (#1908) ; `SERVICE_VERIF_VERSION` absent de `__all__` (`utils/services.py`),
donc invisible du contrôle du registre (#1909) ; `UPLOADS` écrit en dur dans
`utils/backup.py` malgré la lecture unique de `uploads_dir` (#1910) ; le syndic inscrit
avec `roles_json="syndic"` (§5.3, #1911).

## 11. Les questions — arbitrées le 13/10/2026

1. ~~**Comptes partagés ou isolés ?**~~ — **partagés** (M5). Un visiteur peut
   défaire ce qu'un autre regarde jusqu'à la nuit ; une copie par visiteur serait
   un chantier d'un autre ordre (une base par session).
2. ~~**Téléversements des visiteurs ?**~~ — **refusés** (M10), à la porte unique
   des fichiers reçus ; le jeu apporte ses images et ses documents.
3. ~~**Inscription au registre ?**~~ — **la démo s'inscrit** comme toute
   réplique dès que le registre l'accepte ; d'ici là, **exception déclarée** au
   plafond de 5 utilisateurs, sous `est_demo()` (M11).
4. ~~**Moteur de la base ?**~~ — **PostgreSQL** (arbitré par l'auteur le
   13/10/2026, au moment de l'installation).
5. ~~**Personnages**~~ — **quatre** : résident (copropriétaire occupant),
   locataire, conseil syndical, administrateur. Le syndic attend #1911.
6. ~~**Fréquence de remise à zéro**~~ — **chaque nuit** (retenu par défaut, sans
   objection de l'auteur) ; plus souvent si l'usage montre des dégradations.
