# Notifications push — le relais APNs de la plateforme (#2458)

> 🧭 **Spécification de CIBLE, validée par Philippe le 03/11/2026** (§10). Écrite le
> 02/11/2026 pour le chantier de l'application iOS native (#2460) ; comme
> [`multi-coproprietes.md`](multi-coproprietes.md), elle n'est pas historique et se
> tient à jour **à chaque arbitrage**, daté. Les lots d'implémentation (§9) sont
> ouverts ; ce qu'ils ont livré se lit dans leurs tickets.
>
> **Où la vérité se lit** : l'avancement, dans les tickets (#2458, chapeauté par
> #2460) ; les décisions et leurs raisons, ici ; une fois le code écrit, les règles
> dans les modules qu'il nomme (§8) et les garde-fous qui les tiennent — ce document
> ne recopiera pas leurs listes.

## 1. Le besoin et la difficulté

L'application iOS (stack.md § [Application mobile](stack.md#application-mobile))
reçoit des **notifications push APNs dès sa v1**. Aujourd'hui, rien de tel n'existe :
ni Web Push, ni APNs ; seule la **cloche** de l'application (`models/notifications.py`,
`routers/notifications.py`), alimentée par une seule porte, `utils/cloche` (#1187).

**La difficulté propre au multi-installations** : APNs n'accepte un envoi que signé
par la **clé `.p8`** du compte Apple Developer de CoproFirst (équipe `GUX8KASNTG`,
application `fr.coprofirst.app`). Cette clé ne peut **pas** être confiée aux
installations : le code est public et chaque exploitant le modifie librement (§4.11 de
`multi-coproprietes.md`, « ce que *non détournable* peut vouloir dire sous l'AGPL ») ;
une clé posée chez lui serait une clé donnée — elle permettrait d'écrire à **tous** les
téléphones de toutes les installations.

## 2. Le principe

Un **relais de notifications**, opéré par la plateforme à côté du registre, **seul**
détenteur de la clé `.p8`. Une installation ne parle jamais à Apple : elle demande au
relais d'avertir un appareil, par une requête **signée de sa clé Ed25519** et
**accompagnée de son bail** ; le relais vérifie les deux, compose lui-même la charge,
et la transmet à APNs.

```
[cloche de l'installation] ──▶ utils/cloche._poser ──(après commit)──▶ client du relais
                                                                           │ HTTPS, signé (Ed25519) + bail
                                                                           ▼
                                                [relais — référence, nom dédié du registre]
                                                    vérifie bail, signature, fraîcheur, débit
                                                                           │ HTTP/2, JWT ES256 (.p8)
                                                                           ▼
                                                                    [APNs d'Apple] ──▶ iPhone
                                                                                         │ à l'ouverture
                                                                                         ▼
                                                              GET /notifications sur l'installation
```

**La notification push ne porte rien** : elle dit seulement « il y a du nouveau
dans telle installation ». L'application lit le détail **par l'API**, à l'ouverture,
avec la session de la personne — la même porte que la cloche.

## 3. Les décisions

| # | Sujet | Proposition | Raison |
|---|---|---|---|
| N1 | Détenteur de la clé `.p8` | **la référence seule**, comme la clé des baux (`CLE_SIGNATURE_BAUX`) : un réglage de son environnement (§4.8 bis), créé sur l'actif, jamais sur le poste ni dans le dépôt | la seule pièce secrète ; tout le reste tient avec le code lu |
| N2 | Où répond le relais | sous le **nom dédié du registre**, préfixe `/plateforme/` — `POST /plateforme/notifications` ; un nom propre viendra avec la sortie de l'application (§10, décision 1) | le tunnel n'ouvre déjà que `/api/plateforme/` sous ce nom (règle 8 du §4.11) ; un second nom (`push.coprofirst.fr`) ne s'impose que si le relais déménage — le nom dédié le permet déjà |
| N3 | Qui le relais admet | une installation dont le **bail se croit** (signé par la clé des baux de son époque, non échu, état `active`) et qui **autorise le service** `notifications_push` ; la requête est signée par la clé dont le bail porte l'empreinte | le levier est le bail (D23) ; le relais n'a pas besoin de lire la base `plateforme` : il juge sur pièces, et peut déménager sans elle |
| N4 | La charge | **composée par le relais**, jamais par l'installation : un texte générique fixe et l'**abonnement** opaque (§5) | une installation modifiée ne peut rien glisser vers Apple : la garantie tient chez qui détient la clé, pas dans le code d'autrui |
| N5 | Ce que l'installation envoie | un schéma **fermé** (champs inconnus refusés) : l'appareil (jeton, environnement), l'abonnement, le **niveau** (`normal` ou `urgent`, §10 décision 2), l'horodatage et un nonce — rien d'autre | la minimisation se contrôle par le contrat, pas par la bonne foi ; le niveau est la seule information sur le contenu, et elle est arbitrée |
| N6 | Où naît l'envoi | **une seule porte** : là où se pose une notification de cloche (`utils/cloche._poser`), après le commit de la transaction | la cloche suit déjà le profil (#1187) ; un appel dispersé dans les routeurs recréerait les vingt-deux copies d'avant #1187 |
| N7 | Le service | `notifications_push` dans `utils/services.SERVICES` : **coupé par défaut** partout, et sur une réplique soumis au bail (il n'entre pas dans `SERVICES_HORS_BAIL`) | rien ne sort de l'installation sans accord (§4.8) ; en démo, aucun service ne s'allume (#1902) |
| N8 | Le journal | des **identifiants** : l'installation, l'`appareil.id`, l'`apns-id` rendu par Apple et le statut — **jamais** un jeton d'appareil, même tronqué | un jeton d'appareil est un identifiant d'une personne ; la règle de `utils/journal_securite` (#777) vaut ici |
| N9 | Une panne du relais | la cloche ne perd rien : le push est un **avertissement de plus**, jamais le seul chemin d'une information | la référence est derrière une box résidentielle (§4.11, règle 4) |

## 4. Le relais (côté référence)

**Une route publique, gardée dans cet ordre** — l'ordre du registre
(`registre/routeur.py`), dont le relais reprend les gardes **en les appelant**,
jamais en les recopiant :

1. **Servie seulement ici** : chez la référence dont le relais est configuré, sous
   le nom dédié (`_servi_ici`) ; ailleurs, 404.
2. **Taille et débit plafonnés** : une requête de quelques centaines d'octets ; un
   plafond **par installation** (identifiant du bail) en plus de celui par adresse —
   une installation bavarde ne prive pas les autres.
3. **Le bail se croit** : la fonction qui le juge est **celle de l'installation**,
   `inscription/constat.bail_valide` (clés par époque, clés révoquées, empreinte de la
   clé de l'installation) — une seule règle pour « ce bail est-il bon ? ». Puis : non
   échu, état `active`, `notifications_push` dans `services_autorises`.
4. **La requête est signée** par la clé dont le bail porte l'empreinte, sur les
   octets reçus (`registre/signature.verifier`).
5. **Fraîche et unique** : `emis_le` à moins de 5 minutes de l'horloge du relais, et
   un nonce jamais vu dans cette fenêtre — un envoi rejoué n'avertit pas deux fois.
   Le cache des nonces est un état de **processus** de la plateforme, pas d'une
   copropriété (`DU_PROCESSUS` de `test_etat_module_par_copropriete.py`, avec sa
   raison).

**Puis l'envoi à APNs** : HTTP/2 vers `api.push.apple.com` (ou
`api.sandbox.push.apple.com` pour un appareil de développement), jeton
d'authentification JWT ES256 signé par la clé `.p8`, renouvelé entre 20 et
60 minutes comme Apple l'exige, `apns-topic: fr.coprofirst.app`.

**Ce que le relais répond** à l'installation : `envoye`, `jeton_perime` (APNs a
répondu `410 Unregistered` ou `400 BadDeviceToken` — l'installation retire l'appareil)
ou `refuse` avec un motif en clair, sans rien répéter de la requête.

**Ce que le relais ne garde pas** : aucun jeton d'appareil, aucune table d'appareils.
Il transmet et oublie ; son journal ne porte que ce que N8 admet.

**La référence pour elle-même** : elle n'a pas de bail (elle les signe, règle 7 du
§4.11). Elle passe par la **même fonction de transmission** que le relais, en
processus, sans requête vers elle-même ; seul le contrôle du bail est sans objet.
Son service `notifications_push` reste coupé tant que son administrateur ne l'allume
pas.

## 5. La charge — sans aucune donnée personnelle

`standards/14` §3 bis : ce qui part chez Apple ne dit **ni qui, ni quoi, ni où**.

```json
{ "aps": { "alert": { "title": "CoproFirst", "body": "Vous avez une nouvelle notification." },
           "sound": "default" },
  "a": "<abonnement>" }
```

Pour un avis **urgent** seulement (`Notification.urgente` : fuite, ascenseur bloqué),
`aps` porte en plus `"interruption-level": "time-sensitive"` — il traverse le mode
Concentration (§10, décision 2). Tous les autres partent au niveau normal.

- **L'abonnement** est un identifiant aléatoire **tiré par l'application** à
  l'enregistrement de l'appareil, un par installation où la personne est connectée.
  Il ne signifie rien hors du téléphone : c'est l'application qui sait à quelle
  installation il correspond, et y lit `GET /notifications`.
- **Ni** le nom de la résidence, **ni** son adresse, **ni** le titre de la
  notification, **ni** son type, **ni** l'identifiant d'un utilisateur ou d'une
  notification : Apple apprendrait sinon qu'un téléphone appartient à telle résidence,
  ou ce qui s'y passe.
- **`apns-collapse-id` = l'abonnement** : plusieurs notifications rapprochées ne font
  qu'**une** bannière sur le téléphone (la règle « jamais deux fois le même avis pour
  un même fait » vaut aussi ici).
- Le texte est **fixé par le relais**, en français ; il n'est pas un réglage d'une
  installation (N4).
- **Aucune pastille** (`badge`) : aucun nombre ne part chez Apple ; l'application
  calcule ses non-lues à l'ouverture (§10, décision 3).

## 6. L'installation

### 6.1 La table `appareil`

| Colonne | Sens |
|---|---|
| `id` | identifiant, le seul que le journal écrit |
| `utilisateur_id` | FK `utilisateur.id` — à qui l'appareil sonne |
| `jeton` | le jeton APNs, **en clair** (voir ci-dessous), unique |
| `environnement` | `production` ou `developpement` — l'APNs à viser |
| `abonnement` | l'identifiant opaque tiré par l'application (§5), unique |
| `cree_le`, `vu_le` | `NaiveDatetime` par `horloge.maintenant()` ; `vu_le` se rafraîchit à chaque enregistrement |

⚠️ **Le jeton se garde en clair, et c'est une exception déclarée** à la règle « un
jeton se stocke par son empreinte » (#1389) : celle-ci vise les jetons qu'on
**vérifie** (rafraîchissement, liens), qu'une copie de la base rendrait utilisables. Un
jeton APNs ne s'utilise qu'avec la clé `.p8`, que l'installation n'a pas ; et on doit
le **transmettre**, pas le comparer — une empreinte ne servirait à rien. L'exception
est écrite avec sa raison dans le modèle (`models/appareils.py`), et sa contrepartie
— le jeton n'entre jamais dans un journal — est tenue par un test.

La table est une **donnée de la copropriété** (base de l'installation, §4.3) : elle
part dans l'export (#1749) et dans l'export des données d'une personne, et ne
remonte **jamais** au registre — le rapport nocturne compte au plus des appareils, il
ne les nomme pas.

### 6.2 Les routes

| Route | Dépendance | Geste |
|---|---|---|
| `POST /appareils` | `get_current_user` | enregistre (ou rafraîchit) `{jeton, environnement, abonnement}` pour la personne connectée ; un jeton déjà connu sous un autre compte **change de main** — le téléphone a changé de session |
| `DELETE /appareils/{abonnement}` | `get_current_user` | retire l'appareil de la personne — appelé par l'application à la **déconnexion** ; l'abonnement d'un autre compte rend 404 |

Préfixe au pluriel, tag `appareils`, nommage français (#1056). Client TypeScript : aucun
— la PWA n'enregistre pas d'appareil ; le client Swift se génère du contrat publié
(#2456).

**Aucun réglage par personne** (§10, décision 4) : ni choix « sur mon téléphone »
dans le Profil, ni route pour en écrire un. Le profil de la cloche décide déjà ce qui
sonne (§6.4), et les réglages de notifications d'iOS décident du reste.

### 6.3 Quand un appareil disparaît

L'appareil suit les **sessions** de la personne — une session fermée ne doit pas
laisser un téléphone sonner :

- **déconnexion** : la route ci-dessus ;
- **toutes les sessions fermées** — rejeu d'un jeton de rafraîchissement, mot de
  passe changé ou réinitialisé : la porte qui les ferme,
  `auth/jetons_rafraichissement.revoquer_sessions`, retire aussi ses appareils ;
- **compte supprimé, désactivé ou banni** : `utils/suppression_compte.supprimer_compte`
  et les gestes du cycle de vie du compte ;
- **jeton périmé** : la réponse `jeton_perime` du relais ;
- **abandon** : un appareil que l'application n'a pas ré-enregistré depuis 60 jours
  (`vu_le`) se purge, par la tâche de purge existante (`POST /admin/maintenance/purges`).

### 6.4 La porte d'envoi

L'envoi naît **dans `utils/cloche._poser`, et nulle part ailleurs** — c'est déjà le
seul endroit où une `Notification` se construit (🔒 `test_cloche_porte_unique.py`). Il
hérite donc de ce que la cloche décide déjà : le **profil** (`sonner`) et les **motifs
système** (`sonner_systeme`). Une cloche qui ne sonne pas ne pousse rien.

1. `_poser` note, dans la session SQLAlchemy, le destinataire à avertir.
2. **Après le commit** seulement, l'envoi part, hors de la requête : une
   notification annulée par un `rollback` n'a pas averti un téléphone.
3. Un envoi par **appareil** du destinataire ; un échec est journalisé (N8), jamais
   remonté à la requête qui a posé la notification.
4. Rien ne part si le service est coupé (`service_actif(cfg, SERVICE_PUSH)`)
   — en démo, jamais.
5. Hors requête, l'envoi se fait dans le contexte de la copropriété
   (`contexte.dans(copro)`) : la configuration et les appareils lus sont les siens.
6. Le **niveau** de l'envoi est `urgent` si l'une des notifications du commit pour ce
   destinataire l'est (`urgente`), `normal` sinon — rien d'autre du contenu ne la suit.

### 6.5 Le service

Une entrée de `utils/services.SERVICES` — la liste fait foi là, pas ici :

- libellé : *Notifications sur téléphone (iOS)* ; clé d'activation `push_actif` ;
- **ce qu'on perd** en le coupant : *« Les téléphones ne sonnent plus ; la cloche de
  l'application reste, et l'application iOS la montre à l'ouverture. »* ;
- requis : aucun réglage de l'installation — le relais est celui de la plateforme ;
- sur une **réplique**, `autorise_par_la_reference` exige le service dans le bail ;
  le registre peut l'accorder sans changer le format du bail (`services_autorises`
  est une liste de codes, `SERVICES_AUTORISABLES` s'en déduit).

## 7. Conformité

- **Donnée personnelle** : le jeton d'appareil et l'abonnement sont des identifiants
  pseudonymes d'une personne. Finalité : l'avertir de ce qui la concerne dans sa
  résidence ; base légale : son geste (elle installe l'application, accepte les
  notifications dans iOS et les retire quand elle veut) ; durée : celle de ses
  sessions (§6.3). La **politique de confidentialité** de l'installation le dira
  avant que le service s'allume.
- **Destinataires** : le relais (la plateforme, qui ne garde rien, N8) et **Apple**,
  hors de l'Union, qui reçoit le jeton et la charge générique — c'est le prix d'APNs,
  à déclarer dans la politique et dans la fiche de confidentialité de l'App Store.
- **Opérateur de plateforme** (D5) : par le relais, il voit passer des identifiants
  d'installation et des jetons, jamais un contenu ni un nom ; son journal ne garde que
  les premiers.

## 8. Les garde-fous attendus du code

Chacun naîtra avec son lot, et c'est son **test** qui tiendra la règle — pas cette
liste :

- l'envoi n'est appelé que depuis `utils/cloche` (comme `test_cloche_porte_unique.py`) ;
- la charge envoyée à APNs n'a que les clés de §5, quoi que contienne la requête ;
- le relais refuse : sans bail, bail échu ou d'une clé révoquée, service non accordé,
  signature d'une autre clé, horodatage hors fenêtre, nonce rejoué, champ inconnu ;
- aucune ligne de journal ne contient un jeton d'appareil (comme
  `test_journal_securite.py`, chez la fonction et ses appelants) ;
- `revoquer_sessions` et la suppression d'un compte retirent ses appareils ;
- le service est coupé par défaut, et coupé sur une réplique sans bail qui l'accorde
  (`test_services_registre.py`) ;
- le nouveau routeur est nommé par un test (`test_routeurs_nommes_par_un_test.py`) et
  sa table enregistrée (`test_modeles_enregistres.py`) ;
- une dépendance neuve pour HTTP/2 (`h2`, via `httpx[http2]`) passe la liste blanche
  des licences (`scripts/ci/licences_politique.py`).

## 9. Les lots d'implémentation

Ouverts le 03/11/2026 : P1 #2494, P2 #2493, P4 #2495 ; P3 vit dans le dépôt de
l'application.

| Lot | Contenu | Dépend de |
|---|---|---|
| P1 | **Le relais** côté référence : route, gardes, transmission APNs, réglages de la clé `.p8` dans l'environnement, journal | la clé `.p8` créée par Philippe dans le compte Apple Developer |
| P2 | **L'installation** : table `appareil` et sa migration, routes, porte d'envoi dans `utils/cloche`, service, purges, suppression avec les sessions | P1 (pour l'essai de bout en bout ; le code peut précéder) |
| P3 | **L'application** (dépôt `coprofirst-ios`) : demande d'autorisation, enregistrement à la connexion, retrait à la déconnexion, lecture de `GET /notifications` à l'ouverture | P2 et le contrat publié (#2456) |
| P4 | **Politique de confidentialité** et fiche de l'App Store | P2 |

## 10. Les décisions de Philippe (03/11/2026)

Les quatre questions posées par cette spécification ont été tranchées le
03/11/2026 (#2458), en suivant les recommandations :

1. **Nom du relais** : le **nom dédié du registre** pour l'instant (N2) ; un nom
   propre quand l'application sortira.
2. **Urgence** : le niveau *time-sensitive* d'iOS pour les seuls avis **urgents**
   (fuite, ascenseur bloqué) ; tous les autres au niveau normal (N5, §5, §6.4).
   Apple apprend qu'un avertissement est urgent, rien de plus.
3. **Pastille** : **non** en v1 — l'application la calcule à l'ouverture, aucun
   nombre ne part chez Apple (§5).
4. **Réglage par personne** : **non** — les réglages de notifications d'iOS
   suffisent, pas de doublon avec le profil de la cloche (§6.2).
