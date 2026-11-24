# infra-rpi — Monitoring APScheduler, bridge WhatsApp, scripts d'infra en CI (job test-scripts)

Annexe de `SKILL.md`, chargée à la demande (#2910) : le sommaire est dans `SKILL.md`.
Les titres et numéros de section sont ceux de toujours : un renvoi se lit au sommaire.

## Monitoring APScheduler (tourne dans le conteneur API)

🔴 **La liste des jobs se lit dans `api/app/utils/taches.py`** (`TACHES_PERMANENTES`, et
`TACHES_DE_LA_PLATEFORME` pour ceux qui n'appartiennent à aucune copropriété), pas ici —
ni dans `main.py`, qui n'en enregistre qu'une partie (#2931). Le tableau qui occupait cette place en citait **quatre sur six** : le
préchauffage du manuel PDF (au démarrage puis chaque nuit) et la relève des
courriels (toutes les 10 min) n'y figuraient pas — et il donnait `backup` à 03:00
alors que l'heure est **configurable** (`cfg.heure_execution`). Trois erreurs dans
quatre lignes (#1051).

**La sauvegarde depuis v2.179.0 (#2058) — le rythme ne change pas, sa mécanique si :**

| | Avant | Depuis #2058 |
|---|---|---|
| tâche `backup` | un `cron` à `heure_execution`, lue UNE fois au démarrage | un `cron` à chaque heure pile, qui ne sauvegarde qu'à `heure_execution` (`backup.sauvegarder_si_c_est_l_heure`) |
| sauvegardes par jour | une | **une** — 23 passages sur 24 ne font rien (`test_la_tache_horaire_sauvegarde_une_fois_par_jour_a_son_heure`) |
| changer l'heure dans Maintenance | effet au redémarrage de l'API | effet dès l'heure suivante |
| `BACKUP_HOUR` du `.env` | repli sans ligne en base | **retiré** ; la ligne `config_sauvegarde` est posée par le seed |
| journal de l'API | une ligne par nuit | une ligne `tache backup — copropriete principale : faite` par heure, la sauvegarde elle-même une fois |
| archives, dossier, nom, rotation, copie hors site, rattrapage | — | **inchangés** (installation propre : la racine de `/backups`) |

⚠️ Au changement d'heure de mars, 02:00 n'existe pas : une `heure_execution` à 2
n'a pas de passage ce jour-là, la sauvegarde est sautée et refaite la nuit suivante
(`backup_rattrapage` ne joue qu'au démarrage de l'API). Le défaut est 3, qui existe
toujours ; le contrôle de 06:00 signale une sauvegarde de plus de 25 h.

Ce qu'il faut savoir et qui ne se lit pas dans le code : **quel job alerte**.
`health_check` (06:00) est le seul à envoyer un courriel de lui-même — WhatsApp
déconnecté, sauvegarde de plus de 25 h, disque sous 15 %, et le canari de l'assistant
IA (`canari_ia`, 05:40, #2369) qui a vu le modèle obéir ou n'a rien mesuré. `whatsapp_scheduled`
alerte quand sa fenêtre de rattrapage s'épuise sans envoi réussi.

🔒 `npm run lint:consignes` refuse qu'une consigne en énumère une partie.

## WhatsApp bridge
- Reconnexion QR : Admin → WhatsApp → **bouton Statut** (affiche le QR si déconnecté)
- Session corrompue (`creds.json` vide) : vider le volume + redémarrer le bridge
  ```bash
  cd /opt/5hostachy && . scripts/lib/lib-image-utilitaire.sh
  docker run --rm -v 5hostachy_whatsapp_auth:/data "$(image_utilitaire)" sh -c 'rm -rf /data/*'
  cd /opt/5hostachy && docker compose up -d whatsapp-bridge
  ```
- `bascule.sh` ne propage jamais un `creds.json` vide vers le peer
- **Arrêt propre** (#1590, 03/10/2026) : le bridge traite `SIGTERM` et `SIGINT` (`arret.js`) —
  il ferme le socket, attend les écritures de `creds.json` et des clés, puis sort en 0,
  borné à 8 s ; `stop_grace_period: 20s` dans `docker-compose.yml`. Un **exit 137** sur
  `hostachy_whatsapp` est désormais une anomalie : `docker inspect hostachy_whatsapp
  --format '{{.State.ExitCode}}'` doit rendre 0 après un arrêt.
- **La clé du bridge** (#1596, 02/10/2026) : une seule source, `WHATSAPP_API_KEY`
  dans `.env`, lue par le bridge (`WA_API_KEY`) **et** par l'API
  (`utils/whatsapp.entetes_bridge`) — plus rien ne se saisit à l'écran. Le bridge
  **refuse de démarrer** si elle est vide, vaut la valeur d'exemple ou fait moins de
  16 caractères (`docker logs hostachy_whatsapp` le dit, sans la valeur), et ne la
  lit qu'en en-tête `x-api-key`. Après toute modification de `.env` :
  `docker compose up -d api whatsapp-bridge` — sinon l'API garde l'ancienne, et
  Admin › WhatsApp › Statut répond « le bridge refuse la clé de l'API »

#### 🔴 Blocage du compte WhatsApp — la panne qui ne se répare pas (#1061, 26/09/2026)

Le bridge repose sur **Baileys**, un client non officiel de WhatsApp Web : c'est
le seul moyen de publier dans un groupe, et c'est un choix assumé. Son prix :
WhatsApp peut **déconnecter d'office**, voire **bloquer le numéro** appairé. Un
blocage n'est pas un incident technique — ni un redémarrage, ni une bascule, ni
un nouveau QR ne le lèvent.

**Deux pannes qui se ressemblent** (« déconnecté ») et que tout oppose :

| Signe (`GET /status` du bridge) | Lecture | Conduite |
|---|---|---|
| `dernier_code` 428, hors ligne quelques minutes | la boucle ordinaire (~4 h 45) | rien : il se rétablit seul |
| `dernier_code` **401** ou **403** | WhatsApp a fermé la session : appairage perdu, ou **numéro bloqué** | ci-dessous |
| hors ligne depuis **≥ 6 h** (`hors_ligne_depuis`) | au-delà de toute coupure ordinaire | ci-dessous |

Le contrôle de 06:00 (`utils/health_monitor` → `utils/verdict_whatsapp`) porte
ce verdict distinct dans l'alerte e-mail — le seul canal qui reste quand
WhatsApp tombe (`standards/07` §2).

**Conduite à tenir :**

1. **Ne pas ré-appairer en boucle.** Un QR rescanné sur un numéro bloqué ne sert
   à rien, et des appairages répétés sont précisément ce que WhatsApp surveille.
   Un seul essai, depuis Admin → WhatsApp → Statut.
2. **Regarder le téléphone du numéro appairé** : WhatsApp y affiche le blocage
   (« Ce compte n'est pas autorisé… ») et, le cas échéant, le formulaire de
   recours.
3. **Prévenir les résidents par courriel** — il touche les mêmes personnes :
   une actualité dont la Diffusion coche le courriel, qui dit que le groupe est
   momentanément muet.
4. **Blocage durable** : décider du repli — second canal (#1060, rendre le canal
   remplaçable) ou courriel seul.

⚠️ **Le numéro appairé et son détenteur ne s'écrivent PAS ici** : c'est une
donnée personnelle, et un dépôt git la conserve (`standards/14`). Ils se lisent
sur le téléphone lui-même et chez le gestionnaire du site.

#### Lire l’historique des envois — trois verdicts, pas deux (19/08/2026)

`Admin → WhatsApp → Historique des envois` ne dit **pas** « parti / pas parti » :
il en distingue **trois**, et la nuance est ce qui protège du doublon.

| Verdict | Ce qu’on sait | Rejouable ? |
|---|---|---|
| **envoyé** | le serveur WhatsApp a acquitté | — |
| **incertain** | le message a **pu** être remis | 🔴 **jamais** |
| **échec** | on sait que rien n’est sorti (connexion refusée, 4xx) | oui, sans risque |

🔴 **« incertain » n’est pas un échec.** Rejouer un envoi dont on ignore le sort
fabrique un doublon dans le groupe des copropriétaires — et un doublon ne se
retire pas. C’est le triple envoi du 14/08/2026.

⚠️ **Deux causes très différentes produisent « incertain », et il faut les lire :**

- **« message émis, accusé de réception non observé »** — `sendMessage()` a rendu
  la main, donc **le message est parti** ; seul l’accusé du serveur WhatsApp a
  tardé (15 s). Il a très probablement été remis : **vérifier dans WhatsApp avant
  toute action**, c’est le cas le plus fréquent ;
- **« réponse 500 du bridge »** — le bridge a échoué en cours de route sans dire
  de quel côté de l’envoi. Là, on ne sait vraiment pas.

**Why** : jusqu’au 19/08/2026 le bridge répondait `500` dans les DEUX cas — son
`catch` était commun. L’utilisateur a comparé son fil WhatsApp et l’écran : deux
messages **remis** (double coche) y figuraient en « incertain — réponse 500 du
bridge ». Le bridge rend désormais **`202 Accepted`** avec `envoye: true` quand
le message est parti sans accusé, et l’API le traduit en clair. Verrouillé par
`api/tests/test_whatsapp_verdict_envoi.py`, qui éprouve les trois verdicts côte
à côte — un test qui ne vérifierait qu’un seul ne prouverait pas qu’il distingue —,
et par la table `test_classification_des_reponses_du_bridge`
(`api/tests/test_whatsapp_scheduler.py`), qui exige que la raison d’un 202 dise
« émis » et jamais « 500 ».

#### Incident du 24/07/2026 — bridge bloqué 2h23, message mensuel manqué
Le message WhatsApp planifié du 4ᵉ samedi (18h00) a échoué : le bridge était en
boucle `stream:error conflict:replaced` ininterrompue depuis 14h28, sans jamais
revenir à `state: open`. Deux causes cumulées, corrigées :

1. **`bascule.sh` synchronisait `5hostachy_whatsapp_auth` « à chaud » (Phase 1,
   conteneur source encore actif et en train d'écrire `creds.json` + fichiers de
   clés)** → snapshot multi-fichiers potentiellement déchiré propagé au peer à
   chaque bascule nocturne. **Corrigé** : le sync se fait désormais en Phase 2,
   après `docker compose stop` (0 writer), avec vérification que
   `creds.json` est un JSON valide avant de l'installer sur le peer
   (`standards/06` §1 : un état multi-fichiers tenu ouvert ne se copie pas à chaud).
2. **`whatsapp-bridge/index.js` ne supervisait pas sa propre reconnexion** :
   `setTimeout(startBaileys, 5_000)` appelait une fonction `async` sans
   `.catch()` → une reconnexion qui rejette (ex. timeout réseau) tue la chaîne
   silencieusement, sans aucun log. C'est ce qui a laissé le bridge mort de
   16h18 à 18h41 sans la moindre tentative. **Corrigé** : verrou anti-concurrence
   (`starting`), `.catch()` systématique sur chaque relance, backoff exponentiel
   (5s → 60s max), et un watchdog (`setInterval` 60s) qui force une reconnexion
   si l'état reste hors `open`/`connecting`/`waiting_qr` sans reconnexion en cours.
3. Le job `whatsapp_scheduled` ne tentait l'envoi **qu'une fois, à 18h00 pile**
   — un échec ponctuel du bridge à cette seconde précise perdait le message du
   mois. **Corrigé** : fenêtre de rattrapage 18h00→21h45 toutes les 15 min (la
   déduplication existante empêche tout doublon), alerte email si la fenêtre se
   ferme sans envoi réussi.

## Les scripts d'infra en CI — job `test-scripts` (venu de `CLAUDE.md`, #2709)

Le job vérifie la syntaxe (`bash -n`) de tous les `.sh` versionnés, les modes git (0b), et
exécute les **self-tests**. **Toute nouvelle logique de décision d'infra** s'isole en fonction
**pure** (aucun SSH, docker, écriture ni `sudo`), expose `--selftest`, et s'ajoute au job —
le seul moyen de tester une décision de bascule sans les deux RPi. Lancer : `bash
<script>.sh --selftest`.

- **Un processus par fichier est interdit dans ce job** (#2231) : les scans d'octets passent par
  `scripts/ci/scans_fichiers.py`, les self-tests de l'étape « Self-tests des fonctions de
  décision » se jouent côte à côte par `scripts/ci/lancer_en_parallele.py` (la liste reste
  écrite dans `ci.yml`, une commande par ligne — c'est elle que lit
  `verifier-selftests-branches.sh`). Un self-test est donc pur et indépendant : il n'écrit que
  dans son dossier jetable.
- **Un autotest ne lit pas l'horloge réelle contre une date posée** (#2261, #2232) :
  `scripts/ci/horloge_autotests.py` refuse une constante datée dans un script qui lit `date +%F`
  (la date s'injecte : `${AUJOURDHUI:-$(date +%F)}`) et un âge calculé à la main ; l'âge se
  demande à `age_min_epoch` (`lib-horodatage.sh`). Côté pytest, une ancienneté en jours se pose
  par `tests/aides_horloge.il_y_a_jours(N)` et le fichier se rejoue à l'heure hostile (fixture
  `heure_hostile`) ; 🔒 `test_anciennete_jours_civils.py`.
- **Une décision ne se prend jamais sur `producteur | grep -q motif`** (#2298) : sous
  `pipefail`, grep qui sort au premier appariement tue le producteur (141) et le test dit
  « non » au hasard. Lire le producteur (`_s=$(… || true)`), puis `grep -q motif <<<"$_s"` —
  sans le `|| true`, `set -e` tue le script quand le producteur sort non nul.
  `python scripts/ci/pipe_grep_quiet.py` refuse les deux formes ; son `--selftest` en prouve le
  mécanisme.
