# infra-rpi — Copie hors site des sauvegardes, et qui reçoit les verdicts de check-reliability (C1 à C40)

Annexe de `SKILL.md`, chargée à la demande (#2910) : le sommaire est dans `SKILL.md`.
Les titres et numéros de section sont ceux de toujours : un renvoi se lit au sommaire.

## Copie hors site des sauvegardes (v2.37.0 — 04/08/2026)

Avant cette date, **100 % des archives vivaient sur les deux RPi**, au même domicile,
sur la même box et la même alimentation. Les deux nœuds protègent de la panne d'**un**
nœud — jamais d'un `docker volume rm`, d'un rançongiciel ou d'un sinistre, qui
emportent base + uploads + toutes les sauvegardes d'un coup
(`standards/06-donnees-et-integrite.md` §6).

- **Lancement : MANUEL depuis le poste** — double-clic sur `scripts/poste/export-hors-site.command` (Mac ;
  `.cmd` sous Windows), ou `bash scripts/poste/export-hors-site.sh`. Destination par défaut : celle du poste
  (`/Volumes/Data/Backup` sur le Mac, `C:\Backup` sous Windows — `EXPORT_DEST`), **2 versions** (`EXPORT_KEEP`) — réduit de 14 à 2 le 12/09/2026 : on ne
  restaure que la dernière ou l'avant-dernière, et quatorze archives de ~100 Mo pesaient
  1,4 Go. La rotation efface donc les plus anciennes **à chaque export** ; le rattrapage
  sur l'autre nœud et le relevé des jours manquants suivent la même valeur. La valeur
  fait foi dans le script (commentaire de `EXPORT_KEEP`), pas ici.
- Le script choisit sa source par **comportement** (qui répond sur `/api/health` en
  LAN), pas en lisant `.active` — et **s'abstient** en cas de split-brain : deux nœuds
  qui servent = deux bases divergentes, en copier une au hasard puis faire tourner la
  rotation détruirait la bonne.
- Il ne lit que des `.tar.gz` clos, jamais la base d'un RPi ; la vérification porte
  sur la copie extraite **sur le poste**.
- Vérifications avant de déclarer la copie bonne : empreinte SHA-256 identique à la
  source, puis l'**export vérifié** de l'archive (chaque table compte les lignes de
  son manifeste, `relire_export`). Une copie non
  validée est renommée `.invalide` — elle ne doit pas se présenter comme une
  sauvegarde disponible. **Intégrité non vérifiable = échec, pas succès.**
- Chez la référence, il copie aussi la dernière archive du **registre des installations**
  (`plateforme/`, sous `EXPORT_DEST/plateforme`, #1896). Son verdict ne touche pas celui
  de la copropriété : il part dans `archive_plateforme`/`integrite_plateforme`, que juge le
  contrôle de la **plateforme** (`registre/sauvegarde.probleme_copie_hors_site`, tâche
  `sante_plateforme`), à destination de l'opérateur.
- Il poste son rapport sur le canal cron existant (`POST /admin/maintenance/rapport`,
  `tache=export_hors_site`) → visible dans **Admin → Maintenance**, et le contrôle de
  06:00 alerte au-delà de **7 jours** (seuil hebdomadaire assumé : le poste n'est pas
  allumé en permanence, et une alerte quotidienne ignorée est un contrôle mort).
- Le contrôle distingue **deux** questions : « l'export a-t-il tourné ? » et « la copie
  est-elle fraîche ? ». Un export fidèle qui recopie chaque jour la même archive
  périmée est un faux vert — verrouillé par `api/tests/test_sauvegarde_hors_site.py`.

⚠️ **Portée** : le poste est au même domicile que les RPi. Cette copie couvre la perte
d'un nœud, le `docker volume rm` et le rançongiciel visant les RPi — **pas l'incendie
ni le vol**. Une destination réellement distante (S3 UE chiffré, disque tournant) reste
à ajouter ; `EXPORT_DEST` et la boucle de vérification sont écrits pour l'accueillir.

## Qui reçoit les verdicts de `check-reliability.sh` (#449 — 19/08/2026)

**Deux canaux, deux rythmes**, et la fréquence se règle par le **cooldown**, jamais
en coupant le canal :

| Verdict | Canal | Cooldown |
|---|---|---|
| au moins un **FAIL** | alerte e-mail « ❌ contrôle(s) en échec » | 1 h |
| aucun FAIL, au moins un **WARN** | digest e-mail « ⚠️ point(s) de vigilance » | 24 h |
| tout vert | rien | — |

La décision est **pure** (`verdict_notification`, `lib-verdicts.sh`, couverte par
`--selftest`) ; l’envoi vit dans `lib-notification.sh`.

**Troisième destinataire depuis le 27/09/2026 : l'écran.** Chaque nœud rend compte
de ses constats à **Admin › Maintenance** (tâche `reliability`, carte « Contrôles de
fiabilité ») — seulement quand l'ensemble des constats **change**, et au moins une
fois par 23 h : ce battement est ce qui fait dire « Exécution manquante » d'un
contrôleur mort. WARN seuls → statut `avertissement`, lu **« Points de vigilance »**.
Décision pure `decision_rapport_ecran` (`lib-notification.sh --selftest`) ; le
plafond est exigé par `test_taches_planifiees.py`. Et le contrôle de 06:00 reprend
les tâches manquantes ou en échec, sauf ce qu'un autre canal signale déjà
(`DEJA_SIGNALE`, `sante_taches.py`).

**Deux heures, et chaque constat une fois** (#1396, 27/09/2026). L'écran affichait
l'heure du dernier **changement**, et « rapport de 17:06 » lu à 17:29 a fait croire
le contrôleur mort. Le passage qui n'a rien de neuf envoie désormais un
**battement** (`POST /admin/maintenance/battement`) : il avance `terminee_le`
(« dernier contrôle ») de la ligne existante, sans en créer — `cree_le` reste
« constats depuis ». Il porte aussi les constats et l'erreur **du passage**, qui
remplacent ceux de la ligne (#1805) : la signature ignore les chiffres, et l'écran
a affiché « 1 erreur sur 965 requêtes » quand le contrôle en comptait 3 sur 1904.
Et chaque nœud contrôlant les deux, tout s'affichait deux fois :
`portee_constat` range chaque ligne — celle qui ne nomme que ce nœud sous lui, celle
qui ne nomme que le pair est laissée au pair, les communes sont dites par l'**actif**
seul (`porte_communs`). Pair muet → ce nœud porte tout.

**Le courriel suit la même répartition** (#1402, 27/09/2026). Il gardait tout, et
un fait vu par les deux nœuds partait deux fois — rpi1 et rpi2 ont envoyé la même
alerte à 16:36:06. `repartir_constats` calcule une fois ce que CE nœud dit, et
l'écran comme le courriel le lisent : un fait, un envoi, par le nœud qu'il concerne
(ou l'actif, s'il concerne les deux). Ce qui garde la promesse « un nœud mort a
toujours quelqu'un pour parler de lui », c'est le **pair muet** : le survivant
porte alors tout. Un nœud vivant dont le contrôleur s'est tu se voit par
« Exécution manquante », par nœud, et au courriel de 06:00. Deux courriels peuvent
encore partir le même jour — les constats propres de chaque nœud —, mais plus
jamais pour le même fait. `lib-notification.sh --selftest` éprouve la réunion des
deux nœuds, et la faute injectée (le pair repris alors qu'il répond) y est vue.

🔴 **Un constat propre à un nœud reste sous ce nœud** (arbitrage de Philippe, #1401).
La règle ne tient que si le message **nomme** son nœud : un constat qui n'en nomme
aucun est lu comme commun et n'est dit que par l'actif — écrit « Disque à 81 % »
au lieu de « Disque $n à 81 % », il disparaîtrait de la carte du standby.
🔒 `api/tests/test_constats_nomment_leur_noeud.py` exige `$n` dans chaque `warn`/`fail`
des boucles qui parcourent les deux nœuds.

🔴 **Pourquoi le digest existe.** L’alerte ne partait que sur `FAILS > 0`. Or **cinq**
contrôles rendent WARN par choix assumé — C16 (cache de build), C17 (maintenance en
retard), C19 (journal ⇆ base), C20 (sudo), C22 (points d’entrée), et depuis le
01/09/2026 **C1** dans ses deux cas non concluants et **C24** (surface sudo ⇆ dépôt)
— au motif qu’un FAIL
à un passage par quart d'heure enverrait un mail par heure. Le raisonnement était juste sur la **fréquence**
et faux sur la **conclusion** : on en a déduit « pas de mail » là où il fallait « pas
ce mail-là ». Ces cinq contrôles n’avaient donc **aucun destinataire**.

Ce que ça a coûté : le **16/08/2026 à 03:02**, le rapport de la maintenance a été
refusé (HTTP 422). **C19 l’a vu** et a rendu WARN. Personne n’a été prévenu ; le défaut
a été trouvé le **18** à l’œil, sur l’écran d’administration, **par l’utilisateur**.
L’écran affichait « À jour » sur un rapport vieux de cinq jours.

⚠️ **Un WARN sans destinataire est un contrôle mort** — `standards/04` §7. Poser un
nouveau contrôle en WARN est légitime ; le laisser sans canal ne l’est pas.

### C24 — la surface sudo INSTALLÉE doit être celle du dépôt (01/09/2026)

Le 31/08, `NOPASSWD: /usr/bin/rsync` — un rsync privilégié **sans borne de
chemin**, donc une escalade root complète — a été retiré du dépôt (#582), avec un
commentaire disant *« c’est la fin du chantier »*. Il est resté installé sur les
**deux** machines : `scripts/installation/durcir-sudoers.sh` n’avait jamais été rejoué. Vingt-quatre
heures, et vingt-trois contrôles au vert à chaque quart d’heure.

⚠️ **Ni C20 ni C21 ne pouvaient le voir.** C20 compare les deux nœuds **entre
eux** — deux nœuds identiquement périmés lui paraissent parfaits. C21 regarde si
la cible d’une permission est réinscriptible par son appelant : `/usr/bin/rsync`
ne l’est pas. C’est le même trou que **C22** comble pour les points d’entrée, un
objet plus loin : *comparer au dépôt, et pas seulement au voisin.*

C24 compare la surface `NOPASSWD` réellement accordée à celle que
`sudoers_regle()` compose, et nomme les écarts dans les deux sens :

| Écart | Verdict | Ce que ça veut dire |
|---|---|---|
| permission **en trop** | WARN | le dépôt ne l’accorde plus, la machine si — rejouer `durcir-sudoers.sh` |
| permission **manquante** | WARN | un geste de la bascule échouera au prochain passage |
| surface non mesurée | WARN | INCONNU, jamais un vert |

📎 **`durcir-sudoers.sh --appliquer` ne peut PAS tourner depuis une session non
interactive** : il valide par `sudo -n visudo -cf`, et `visudo` n’est pas dans la
surface NOPASSWD — il échoue en « a password is required », proprement, sans rien
modifier. La voie employée le 01/09 est celle du reste du projet : un conteneur
jetable montant `/etc/sudoers.d`, une écriture sous un nom **commençant par un
point** (que sudo ignore), puis un `mv` atomique. Le contenu installé est vérifié
avant le `mv` : rsync absent, `systemctl start cloudflared` présent — sans quoi la
bascule casserait.

### C25 — un script TIERS est-il servi dans la page publique ? (02/09/2026)

Le relevé CSP a trouvé `static.cloudflareinsights.com/beacon.min.js` chargé sur
chaque page. **Aucun `<script>` du dépôt ne le référence** : Cloudflare l'injecte
à l'arête, APRÈS notre origine.

C'est ce qui rend ce contrôle particulier : ni une relecture du code, ni
`curl http://localhost/` ne pouvaient le voir. Il mesure donc l'**URL publique**,
avec un `Accept: text/html` et un UA de navigateur — Cloudflare n'injecte que dans
du HTML rendu à un navigateur.

⚠️ **Sur l'ACTIF seulement.** Depuis le standby, la même URL publique répond (elle
sort par le WAN et revient sur l'actif) : le contrôle passerait deux fois sur le
même fait (`standards/04` §33).

⚠️ Le motif porte sur des **hôtes nommés**, pas sur « toute URL absolue » : le
site en sert légitimement (polices Google, déclarées dans la CSP). Un contrôle qui
crie sur du légitime finit désarmé.

Décision de l'utilisateur (02/09/2026) : **couper** Web Analytics côté Cloudflare.
Ce contrôle est ce qui rend la décision durable — sans lui, réactiver l'option
d'un clic remettrait un tiers sur le chemin de chaque résident.

### C23 bis — la CSP bloquante porte-t-elle ses directives ? (01/09/2026)

C23 vérifie que l'en-tête `Content-Security-Policy` est **présent**. Il l'était
déjà quand la politique ne portait que quatre directives inoffensives, et il le
resterait si l'une d'elles disparaissait du `Caddyfile` : *présent* ne dit rien de
ce qu'il **contient**.

`connect-src 'self'` est passée en mode bloquant le 01/09/2026 (#536), sur la foi
du relevé (`Admin → CSP`, retiré le 01/10/2026) : aucune violation la concernant sur 104 rapports. C'est
la directive qui empêche l'**exfiltration** — même si un XSS s'exécutait, il ne
pourrait rien envoyer vers un domaine tiers. La perdre en silence retirerait la
moitié utile de la politique.

⚠️ **Présence, jamais valeur.** Une attente de valeur exacte a déjà tué un contrôle
d'en-têtes ici : `check-stack.sh` exigeait `X-Frame-Options: SAMEORIGIN` là où le
Caddyfile dit `DENY`, il échouait 144 fois par jour, on l'a retiré du cron — et
plus rien n'a regardé les en-têtes pendant quinze jours.

📎 **Deux défauts commis en l'écrivant, et corrigés dans l'heure.** Ils valent
d'être lus, parce qu'ils sont tous deux de la famille « le contrôle ne mesure
rien » :

1. **il s'exécutait AVANT sa mesure.** `ENTETES_RECUS` est calculé par C23 ; C23
   bis était placé au-dessus, donc il lisait une variable vide et rendait INCONNU
   à chaque passage. Un INCONNU se lit « pas cette fois », jamais « mort depuis
   toujours » (`standards/04` §23) ;
2. **il ignorait le RÔLE.** Le standby ne sert rien : il y rendait WARN tous les
   quarts d'heure, sur la moitié du parc, et le digest quotidien l'emportait.
   C'est exactement le défaut que le commentaire de C23, juste à côté, décrit et
   corrige depuis le 20/08/2026 — *écrire un contrôle voisin sans relire ce que
   son voisin a appris, c'est refaire son défaut*.

Les deux sont couverts par `--selftest`, y compris le cas « standby avec une
réponse parasite » : ce n'est pas le site, donc rien à constater.

### C27 — auto-deploy a-t-il RÉUSSI son build ? (21/09/2026, #1103)

La bascule nocturne a mis rpi1 en standby, et son `auto-deploy` n'a pas pu lire
`/opt/5hostachy/.env` : **root:root** là-bas, **ptressard:ptressard** sur rpi2.
Le code s'est aligné, **les images non**.

> 🔴 **La parité git n'est pas la parité d'image.** Le point **10** du pré-check
> (« parité de code actif ⇆ standby ») restait **vert** — il dit vrai, et il
> rassure à tort. Seul le point **18** l'a attrapé, et seulement en MEP.

L'alerte qui devait le dire est morte de la **même cause** : `lib-alert.sh`
cherche sa configuration SMTP dans ce `.env` illisible. Un canal d'alerte muet
précisément quand il a quelque chose à dire — la famille de
`canal_alerte_verifiable`.

| Ce que C27 rend | Conduite |
|---|---|
| **OK** | le dernier passage a construit, ou n'avait rien à construire |
| **FAIL** | le code est à jour, **pas les images** — comparer `ls -l /opt/5hostachy/.env` sur les deux nœuds |
| **INCONNU** | aucune ligne horodatée lisible ; son silence ne prouve rien |

⚠️ Il regarde le **comportement** (le build a-t-il abouti), pas la cause connue
(les droits du `.env`) : un contrôle sur les droits serait vert le jour où le
build échouera pour une autre raison — disque plein, registre injoignable,
Dockerfile cassé. C13 fait l'inverse pour le **log**, et c'est cohérent : là-bas
la cause est unique et connue (la rotation re-chown).

🔴 **C'est la troisième divergence rpi1/rpi2** du dépôt, après les sudoers
(09/08) et un cron en trop sur rpi2 (06/08). Le point 17 compare les points d'entrée, crons compris —
**il ne compare pas les droits des fichiers dont les scripts dépendent**, et c'est par là que l'écart est passé.

⚠️ Le correctif demande `sudo`, refusé en `-n` sur les **deux** nœuds depuis le
durcissement : il n'est pas automatisable depuis une session.

```bash
sudo chown ptressard:ptressard /opt/5hostachy/.env && sudo chmod 600 /opt/5hostachy/.env
```

C'est un **durcissement** : le fichier passe de `660 root:root` (lisible par le
groupe root) à `600 ptressard` — root continue de le lire, personne d'autre.

### C26 — le verrou a-t-il été posé AVANT la première action ? (12/09/2026, #915)

#915 se terminait sur une phrase gênante : *« le verrou est la coordination ;
elle tient tant que la bascule le pose avant sa première action — ce que les
tests vérifient **par la forme du script, pas par son exécution** »*.

🔴 Et la forme était fausse : `bascule.sh` arrêtait les conteneurs du peer
**puis** posait le verrou dix lignes plus bas. Corrigé le 12/09.

C26 lit le journal de la **dernière bascule réellement exécutée** et vérifie
l'ordre sur les faits — c'est la différence entre *« le script est écrit ainsi »*
et *« il s'est comporté ainsi »* : un chemin conditionnel ou une modification
future peuvent séparer les deux.

| Ce que C26 rend | Conduite |
|---|---|
| `verrou posé AVANT la première action` | — |
| **`posé APRÈS une action`** (FAIL) | une modification a déplacé `verrou_poser` : le remettre avant le bloc « Peer sans conteneurs actifs », et relire `test_verrou_bascule.py` qui aurait dû le refuser |
| `INCONNU` | journal absent, tronqué par la rotation, ou bascule sans pose relevée |

⚠️ Deux formulations coexistent dans l'historique — « posé sur le peer » (avant
#916) et « posé sur les DEUX nœuds » (après). Le contrôle accepte les deux :
n'en reconnaître qu'une le rendrait INCONNU sur tout l'historique, et on
prendrait l'habitude de l'ignorer.

### C12 — une bascule a-t-elle été TUÉE ? L'ACTE, pas l'objet (12/09/2026, #915)

Ce contrôle lisait l'**âge du verrou** `.bascule-lock`. Il ne pouvait donc
**jamais** alerter : `health-watch` **efface** le verrou orphelin au-delà de
`VERROU_STALE_S` (15 min), et C12 ne passe que toutes les 15 min — son propre
seuil étant en plus de 20 min, le fichier avait toujours disparu **cinq minutes
avant** de devenir signalable. Fenêtre d'alerte vide, et un OK rendu sans avoir
rien pu regarder : le **cas zéro** de `standards/04` §2.

🔴 Il observe désormais la **trace datée du nettoyage** dans
`/var/log/hostachy-health-watch.log`, qui subsiste — et non le fichier, qui
disparaît. Même retournement que le point 13 du pré-check, qui se vérifie par
« Alerte envoyée » plutôt que par « Email KO ».

| Ce que C12 rend | Ce que ça veut dire | Conduite |
|---|---|---|
| `Aucune bascule tuée … depuis 24 h` | rien à signaler, **mesuré** | — |
| `Bascule/MAJ TUÉE sur <nœud> il y a N min` | une bascule ou une MAJ est morte entre la pose et la libération du verrou — coupure, `kill -9`, **gel** (récurrent sur rpi2) | lire le journal de bascule autour de l'heure ; vérifier `.active` sur les **deux** nœuds et l'absence de split-brain |
| `INCONNU — journal illisible` | le contrôle **n'a pas pu** mesurer | vérifier la présence et les droits de `/var/log/hostachy-health-watch.log` |

⚠️ **Le seuil de péremption est écrit UNE fois** : `VERROU_STALE_S` dans
`scripts/lib/lib-verrou.sh`, avec la décision pure `verrou_recent()`. Il était
recopié trois fois (`LOCK_MAX_AGE_S` à 900 s, `LOCK_STALE_MIN` à 20 min, et le
paramètre de `bascule_en_cours`) — et `auto-deploy.sh` n'en avait **aucune**, si
bien qu'un verrou orphelin le figeait **indéfiniment**, sans plus aucun
déploiement et en silence. `api/tests/test_verrou_bascule.py` refuse une
quatrième copie.

### C31 — health-watch, qui décide du failover, sonde-t-il encore ? (02/10/2026, #1586)

`health-watch.sh` ne disait **rien** quand le site répondait : le 02/10/2026, la
dernière ligne de son journal datait de 34 h sur les deux nœuds, pour un cron
qui tourne toutes les quelques minutes (horaire : `infra/points-entree/`). Rien ne distinguait ce calme d'un script mort — cron perdu, bit x, module
absent avant la sonde, verrou bloqué —, donc d'un failover automatique
inexistant, et aucun contrôle ne mesurait son passage.

Il écrit désormais une ligne datée à **chaque sonde**, avant toute décision
(`Site OK (HTTP 200) — RPi: rpi1`, ou `⚠ Site HS (HTTP …)`). C31 mesure l'âge de
la dernière sur les **deux** nœuds — c'est la ligne de la **sonde** qui compte, pas
n'importe quelle ligne datée : « Autre instance en cours » n'a rien sondé. Écriture,
collecte et verdict vivent ensemble dans `scripts/lib/lib-health-watch.sh`.

| Ce que C31 rend | Ce que ça veut dire | Conduite |
|---|---|---|
| `health-watch sonde sur <nœud> : dernier passage il y a N min` | il tourne et va jusqu'à la sonde, **mesuré** | — |
| `health-watch ne sonde plus sur <nœud>` (FAIL, > 20 min) | plus de failover automatique **par ce nœud** | `sudo crontab -l` (ligne `health-watch.sh`), bit x, `tail /var/log/hostachy-health-watch.log` : une erreur non datée juste avant le trou dit la cause ; un « Autre instance en cours » répété dit un verrou `/tmp/health-watch.lock` tenu |
| `health-watch INCONNU sur <nœud>` (FAIL) | aucune sonde datée lisible — journal absent, illisible, ou format changé | présence et droits du journal ; jamais lu comme un vert |

Le constat ne nomme qu'un nœud : il est dit **une fois**, par lui — ou par l'autre
s'il est muet (#1402). Pair injoignable : C31 se tait sur lui, C15 et « Peer
injoignable » le disent.

**Côté auto-deploy (#1587)**, chaque ligne est datée **à son écriture** (`log`,
`scripts/lib/lib-journal.sh`) : « Déployé » porte l'heure de la fin et sa durée
(`Déployé: <sha> (en N s)`). Un `git fetch` en échec écrit `⚠ git fetch
impossible (…) — déploiement reporté` (C27 : WARN), toute autre sortie imprévue
`⚠ ÉCHEC inattendu (code N, dernière commande : …)` (C27 : FAIL). Toutes deux
font battre C14 — le script tourne — et c'est C27 qui dit qu'il n'a rien déployé.

### C1 — « site public KO » demande DEUX sondes, pas une (01/09/2026)

Une alerte critique est partie à 01:21 pour un `HTTP 503` qui a duré moins de
quinze minutes : `auto-deploy.sh` recréait les conteneurs entre 01:18 et 01:23, et
Caddy rend 503 pendant que son amont redémarre. **Une seule occurrence dans 1,8 Mo
de journal**, l’exécution suivante verte, et tous les autres contrôles au vert dans
la même exécution — y compris « pas de split-brain » et « code aligné ».

🔴 **La preuve que le contrôle avait tort existait déjà, chez le voisin.**
`health-watch.sh` sonde la MÊME URL, re-sonde à 30 s avant de conclure, et a écarté
un 503 identique à 05:42 le même jour : *« Site revenu entre les deux checks
(HTTP 200) — faux positif, pas d’action »*. Deux contrôles du même fait, deux
fiabilités — et c’est le plus bruyant qui écrivait à l’exploitant.

C1 rend donc désormais quatre verdicts, décidés par `verdict_site_public`
(`lib-verdicts.sh`, pure, couverte par `--selftest`) :

| Sondes | Verrou de build sur l’actif | Verdict |
|---|---|---|
| 200 | — | **OK** |
| ≠200 puis 200 | — | **WARN** — hoquet, pas une panne |
| ≠200 deux fois | tenu | **WARN** — build en cours, revérifié dans 15 min |
| ≠200 deux fois, la seconde **à la résolution du nom**, puis 200 par un autre résolveur | — | **WARN** — le résolveur du nœud, pas le site (20/10/2026, 22:36) |
| ≠200 deux fois | libre | **FAIL** — le chemin critique est inchangé |

⚠️ **Ce n’est pas un assouplissement de seuil.** La leçon du point 10 (#448) est
que la tolérance masque ; ici on ajoute une **seconde mesure**, et les deux cas
non concluants sortent en WARN — donc dans le digest, jamais en silence. Un build
qui échoue laisse le site KO : le verrou est relâché, et l’exécution suivante
alerte.

🔴 **Le résolveur du nœud n'est pas le site** (21/10/2026). Le 20/10 à 22:36, C1 a
écrit FAIL sur deux `000` qui avaient expiré à la **résolution** du nom — rpi2
recevait un 200 à la même minute. Quand la seconde sonde échoue ainsi
(`echec_de_resolution`, `lib-sonde.sh`), une troisième rejoue la requête avec le nom
résolu en DNS sur HTTPS (`RESOLVEUR_INDEPENDANT`, une adresse IP : hors de
`/etc/resolv.conf`). Un 200 → WARN ; un échec reste le FAIL : une panne de DNS ou
de lien du domicile coupe aussi le tunnel.

Le verrou est lu **sur le nœud qui porte la prod**, jamais sur celui qui observe —
un build sur le standby ne fait pas tomber le site public. Il est remonté par le
champ `deploiement` de `lib-collecte.sh`, qui prend et relâche un verrou *partagé*
sur `.auto-deploy.lock` : il échoue face à l’exclusif du build sans jamais bloquer
un build qui démarrerait pile à cet instant.

📎 Au passage : `http_code` existait en **trois** exemplaires — ici, dans
`lib-verdicts.sh` et dans `precheck-mep.sh` — et la troisième avait perdu le
correctif du 30/07/2026 (garde sur la sortie vide). Elle vit maintenant dans
`scripts/lib/lib-sonde.sh`, et nulle part ailleurs.
