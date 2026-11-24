# mep-precheck — Post-check P1 à P12 après la MEP : déploiement constaté, version servie, clôture des tickets, retour arrière

Annexe de `SKILL.md`, chargée à la demande (#2910) : le sommaire est dans `SKILL.md`.
Les titres et numéros de section sont ceux de toujours : un renvoi se lit au sommaire.

## Post-check obligatoire après MEP

La MEP se termine par ces contrôles, pas par le merge. Un merge déclenche
`auto-deploy.sh` dans les 5 min ; **il n'y a aucune notification de fin de
déploiement**, donc rien ne garantit spontanément que le code est réellement servi.
Attendre le tick, puis :

| # | Vérification | Commande | Attendu |
|---|---|---|---|
| P1 | Le déploiement a eu lieu **et est terminé** | `precheck-mep.sh --post-mep` (lit l'actif) | Ligne `Déployé: <hash>` avec le hash attendu — ou, actif issu d'une bascule, marqueur d'images = hash et conteneur API sur le manifeste de l'image étiquetée (#1474, #1684) |
| P2 | Site debout | `curl -s -o /dev/null -w '%{http_code}' https://5hostachy.fr/api/health` | 200 |
| P3 | Version servie = version bumpée | Voir « P3 » ci-dessous — l'ancienne commande ne pouvait **pas** fonctionner | La version de `front/package.json`, ou `INCONNU` (jamais vide) |
| P3b | Version publiée par l'API = version bumpée | `GET /api/config`, clé `version_logicielle` (#2833) : ce que les apps lisent pour juger « au moins vX.Y.Z » | La release de l'image de l'API, ou `INCONNU` (clé absente, mesure impossible) |
| P3c, P3d | Les fichiers d'association des apps (`apple-app-site-association`, `assetlinks.json`), sur la production (P3c) et la démo (P3d) | `--post-mep` : chaque hôte jugé contre SA version (`GET /config`, puis le tag `v<version>`), #2860 | 200, `application/json`, sans redirection, identique au fichier de sa version ; version illisible → INCONNU |
| P4 | Image du service touché reconstruite | Point 12 (`--post-mep` le rejoue) : images bâties avec le commit du service, conteneur sur le manifeste de l'image étiquetée | Les deux faits vrais pour chaque service |
| P5 | Migrations appliquées | `docker logs hostachy_api --since 10m \| grep -iE 'alembic\|revision'` | Pas d'erreur ; head atteint |
| P6 | Aucune régression visible en logs | `docker logs hostachy_api --since 10m \| grep -cE "<MOTIF_ERREURS_API>"` — le motif se lit dans `precheck-mep.sh`, jamais recopié : il compte aussi les erreurs de bibliothèque sans niveau (#1066) | 0 |
| P7 | **Le correctif est effectivement observable** | Vérifier le comportement corrigé sur le site réel | Le bug ne se reproduit plus |
| P8 | Redondance intacte après MEP | Point 2 (rôle cohérent sur les 2 nœuds) | Inchangé et cohérent |
| P9 | Parité du standby | Point 10 | HEAD identiques, **ou** noter que le standby s'alignera seul au prochain passage d'`auto-deploy` (≤ 5 min, #448) |
| P10 | **Bilan mémoire du lot** — 🟡 priorité 3 | Relire les activités de la PR : qu'a-t-on appris qui n'est écrit nulle part ? Voir « P10 » | Chaque leçon est **écrite** (socle ou banque projet), ou explicitement écartée |
| P11 | **Clore les tickets du lot** — après P7, jamais avant | `gh issue close <n> --comment "…"` avec la preuve observée | Chaque ticket du lot est clos **ou** dit ce qu'il attend encore |
| P12 | **Retirer la copie de travail du lot** — en dernier | Depuis le clone principal : `bash scripts/poste/retirer-worktree.sh ../5hostachy-<lot>` — voir « P12 » | `RETIRÉE`, ou `GARDÉE` avec son motif, traité ou dit dans le compte rendu |

> **⏱ Attendre la BONNE condition (constaté le 26/07/2026, en utilisant ce
> post-check pour la première fois).** Ne pas attendre que `HEAD` change : dans
> `auto-deploy.sh`, `git reset --hard` a lieu **au début**, avant `docker compose
> build`. Un post-check déclenché sur le changement de HEAD s'exécute donc pendant
> le build et voit des images encore anciennes et pas de ligne `Déployé` — j'ai
> conclu à tort à un déploiement partiel. La condition de fin est la ligne
> **`Déployé: <hash>`** :
> ```bash
> until ssh <actif> "grep -q 'Déployé: <hash>' /var/log/hostachy-deploy.log"; do sleep 20; done
> ```

**P3 — l'ancienne commande renvoyait toujours du vide (corrigé le 03/08/2026).**
`curl -s https://5hostachy.fr/ | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'` ne pouvait pas
marcher : la racine **redirige vers `/auth/connexion`**, et le pied de page versionné
vit dans le layout `(app)`, donc derrière l'authentification. Le `grep` ne trouvait
rien et rendait la main sans un mot — un `$(…)` vide qu'on lit comme « rien à
signaler ». C'est la règle 1 (« une sortie vide n'est pas un vert ») dans le
post-check lui-même.

La version **est** publique : Vite intègre `front/package.json` dans le chunk du
layout `(app)`. On l'y lit sans authentification et sans rien exposer de nouveau —
c'est aussi le seul point de mesure qui reflète ce qu'un **navigateur reçoit
vraiment**, là où lire `package.json` dans le conteneur ne décrirait que l'image.

```bash
node front/scripts/check-version-servie.mjs --site https://5hostachy.fr
```

La version sur la sortie standard (code 0), ou `INCONNU: <raison>` et **code 2**.
Jamais une sortie vide — c'est la règle 1 de cette skill.

🔴 **Le script ne vit plus dans ce fichier, et c'est la leçon du 30/08/2026.**

Il y a été recopié deux fois, avec deux ancrages successifs, et les deux se sont
périmés en silence :

| Ancrage | Périmé par | Constaté |
|---|---|---|
| `[0-9]+\.[0-9]+\.[0-9]+` sur la racine | la racine redirige vers `/auth/connexion` | 03/08/2026 |
| `"hostachy-front",VAR="x.y.z"` | Rollup élague l'import JSON : le **nom du paquet** a disparu du bundle, qui ne porte plus que `const fn="3.20.0",hn={version:fn}` | 30/08/2026, MEP v3.20.0 |
| `{version:"x.y.z"}` entre **guillemets** | Rolldown (Vite 8) écrit ses chaînes en gabarits à **accents graves** : `` var e=`hostachy-front`,t=`3.13.9`,n={name:e,version:t,…`` | 24/10/2026, essai Vite 8 (#2205) — lu en essai, avant toute MEP |

Le second avait été choisi *parce que* le nom « survit à la minification,
contrairement aux noms de variables ». C'était vrai, et insuffisant : ce n'est pas
la minification qui l'a effacé, c'est l'élagage.

⚠️ **Le défaut n'est pas l'ancrage, c'est qu'aucun contrôle ne regardait s'il
marchait encore.** Le premier à l'apprendre était le post-check, en production,
une fois la MEP faite — trop tard pour que cela serve. Un script recopié dans une
documentation ne s'exécute que le jour où l'on en a besoin.

**L'extracteur est donc versionné**, et la CI l'exerce à chaque PR sur le build
local (`npm run lint:version-servie`, job `build-frontend`) : il doit y retrouver
exactement la version de `package.json`. La prochaine évolution de la chaîne
d'outils échouera **là**, avant la MEP.

C'est `standards/04` §2 retourné contre le contrôle lui-même — *ce qui est
critique ne se vérifie pas seulement en MEP* — et la règle que #498 énonce pour
l'aperçu des e-mails : **la fonction qui vérifie doit être celle qui sert.**

Le module rend `null` plutôt qu'une version quand deux formes du bundle
**divergent** : `package.json` peut être partiellement élagué et la version d'une
dépendance traîner dans le même chunk. Trancher au hasard entre deux candidates,
c'est mentir une fois sur deux. Son `--selftest` couvre les deux formes, les deux
cas ambigus et le renvoi arrière qui les distingue.

⚠️ **P3 mesure le serveur, pas le client.** Un onglet PWA resté ouvert peut servir
l'ancienne version depuis son cache — c'est ce qui s'est produit le 26/07/2026, le
pied de page bloqué en v2.22.8 après la MEP v2.23.0, alors que P3 était vert. Le
bandeau de mise à jour (v2.24.0) couvre ce cas, et `api/tests/test_pwa_maj.py` le
verrouille.

> 🔒 **La version servie est publique, et c'est voulu** (#2833) : `GET /config`, sans
> authentification, publie `version_logicielle` — les apps la lisent (P3b). Le
> `version` de `/api/health` est celui du CONTRAT de l'API (`contrat.VERSION_CONTRAT`),
> pas celui de l'application. La réserve écrite le 03/08/2026 (« ne pas divulguer la
> version ») a été levée par cette décision ; elle ne se rétablit pas sans la rouvrir.

**P7 — pourquoi :** c'est le seul contrôle qui teste ce que la MEP était censée
apporter. Le 26/07, le bug du mois en anglais n'a été trouvé par **aucun** contrôle
automatique ou manuel : il a été vu à l'œil sur un document. Les points P1–P6
confirment qu'on a déployé *quelque chose*, jamais qu'on a déployé *ce qu'il
fallait*. Pour un correctif de rendu, ouvrir le document concerné (fiche arrivant,
annonce de hall) et regarder.

> **🌐 Le comportement se vérifie dans un navigateur, sur une route imbriquée
> (constaté le 26/07/2026, v2.24.0 → v2.24.1).** La v2.24.0 ajoutait un bandeau
> « nouvelle version disponible » à la PWA. P1–P6 étaient **tous verts** — image
> reconstruite, version 2.24.0 dans le conteneur, hash du commit et code du bandeau
> présents dans le bundle servi — et la fonctionnalité était morte : elle avait de
> surcroît **cassé l'existant**, plus aucun service worker n'était enregistré, donc
> plus de cache hors ligne. Cause : `vite-plugin-pwa` hérite du `base` de Vite, vide
> sous SvelteKit, et génère `new Workbox('./sw.js', { scope: './' })` ; ce chemin
> **relatif** est résolu depuis la page courante, donc `/auth/sw.js` → 404 sur toute
> route autre que la racine. Trois règles en sortent :
> - **Tester ailleurs qu'à la racine.** Un chemin relatif, un cookie de portée, une
>   règle Caddy fonctionnent souvent sur `/` et nulle part ailleurs.
> - **Les artefacts ne prouvent rien sur le comportement.** Bundle, `sw.js`, image
>   Docker, version du conteneur : tout était correct pendant que la fonctionnalité
>   ne s'exécutait pas. Ouvrir la page et regarder l'état réel
>   (`navigator.serviceWorker.getRegistrations()`, console, requêtes réseau).
> - **Un composant qui reprend un mécanisme fourni par un plugin hérite de ses
>   valeurs par défaut.** Ici `injectRegister` masquait le défaut depuis toujours ;
>   le reprendre à la main l'a exposé. Quand on remplace un mécanisme automatique,
>   vérifier ce qu'il faisait *en plus* de ce qu'on voulait.
>
> Et brancher les callbacks d'erreur (`onRegisterError` ici) : l'échec n'a produit
> **aucun log**, ni côté serveur ni côté navigateur. Ce qui échoue en silence ne se
> découvre qu'à P7, ou jamais.

> **🧪 Une vérification locale ne vaut que pour le chemin d'erreur qu'elle emprunte
> (26/07/2026, v2.26.0 → v2.26.1).** La conservation du lien d'origine à travers
> l'authentification a été vérifiée dans un navigateur, sur le build de production
> servi en local : elle marchait. En production, elle ne marchait pas. En local il
> n'y a **pas de backend** : `auth.me()` échoue en **erreur réseau** et c'est la
> garde du layout qui redirige ; en production l'API répond **401**, et c'est
> `#lib/api.ts` qui redirige en premier — un troisième chemin, non corrigé. Avant de
> conclure d'un test local, se demander **quel chemin de code il a réellement
> exercé**, et si la production en emprunte un autre (API absente vs 401/403,
> cookies, HTTPS, service worker, reverse proxy). Quand un même effet a plusieurs
> points de déclenchement, les chercher tous — ici, un test qui interdit toute
> redirection en dur vers `/auth/connexion` dans `front/src` aurait trouvé le
> troisième du premier coup, là où la relecture en avait vu deux.

**P11 — clore les tickets, et surtout pas par mot-clé GitHub (11/08/2026).**
Écrire `Closes #299` dans le corps d'une PR fait fermer le ticket **au merge**.
C'est la mauvaise date : ce soir-là, #299 aurait été clos pendant qu'une
régression était en vol — quatre colonnes disparues de l'écran, trouvées par
l'utilisateur *après* la fusion. Et le matin même, un merge avait livré un
`check-reliability.sh` incapable de démarrer. **Fusionner n'est pas déployer,
déployer n'est pas vérifier.**

Un ticket se ferme quand le comportement qu'il décrit est **observé corrigé en
production** — donc après P7, et avec la preuve dans le commentaire :

```bash
gh issue close 299 --comment "Vérifié en production après la MEP v2.52.2 : <ce qui a été observé, et comment>."
```

Un ticket dont la vérification est **différée** (elle dépend d'un événement à
venir : un passage hebdomadaire, une bascule) **reste ouvert**, et reçoit un
commentaire disant ce qu'il attend et à quelle date. Le fermer « parce que le
code est livré » revient à confondre le correctif et sa preuve.

Le corps de la PR continue de **nommer** les tickets en français (« Ferme #299 »)
— c'est de la lisibilité pour le relecteur, pas un mécanisme. À ne pas confondre :
le français n'est pas reconnu par GitHub, donc cette mention ne ferme rien, et
c'est très bien ainsi. Les tickets **ouverts** par le lot se listent aussi, pour
qu'un relecteur voie ce qui a été découvert sans être traité.

**Rollback si P1–P6 échoue :** le retour arrière qui TIENT est une PR `revert` vers
`main` (voir plus bas) : tant que `main` porte le commit fautif, `auto-deploy.sh`
ramène le nœud à `origin/main` à chaque passage (`git reset --hard origin/main`, toutes
les 5 minutes) — un retour arrière posé à la main sur l'actif est défait au passage
suivant. Le nœud TIRE les images de la CI (#1758, `sha-<commit>`) : le revert redéploie
l'image du commit précédent, sans construire ; il ne construit qu'en secours. Seule
l'application change d'image, la base ne se relance pas (#2706).

Ce retour au code précédent tient **sans restaurer la base** parce que les
migrations sont compatibles sur une version (#1757, `test_migrations_compatibles.py`) :
l'ancien code lit et écrit le schéma que la version fautive a migré.

🔴 **Jamais de `git reset --hard <commit-précédent>` sur l'actif.** Il ne tiendrait
pas (`auto-deploy.sh` le défait au passage suivant), et le hook global
`garde-git-destructif.py` le **refuse** depuis l'outil Bash — y compris glissé dans
un `ssh … '… && git reset --hard …'` —, parce que rien n'en défait l'effet et qu'il
a déjà détruit du travail non committé ; il ne se contourne que sur l'accord de
Philippe, demandé dans la conversation. La voie : une PR `revert` vers `main`, qui
suit le cycle normal (CI, images, fusion, `auto-deploy.sh`) — plus lente, et c'est
le prix d'un retour arrière qui reste en place.

**P10 — bilan mémoire du lot (🟡 priorité 3, ajouté le 03/08/2026).** Une MEP réussie
n'est pas une MEP close : ce qui a été appris pendant le lot disparaît si personne ne
l'écrit. Ce point est le **dernier** du post-check, et le seul qui ne regarde pas la
production — il regarde le lot.

Ce point **ne bloque pas** la MEP (priorité 3, après la sécurité et la fiabilité des
contrôles) : il la **termine**. Une leçon écartée doit l'être explicitement, pas par
omission.

Relire les activités de la PR — pas le diff, les **surprises** — et se poser les
quatre questions dans cet ordre :

1. **Un défaut a-t-il été trouvé par l'utilisateur plutôt que par un contrôle ?**
   C'est le signal le plus fort : le contrôle manquant est la vraie leçon, pas le
   défaut. → charger la skill globale `retrospective-incident`.
2. **Cela pouvait-il arriver sur un autre projet ?** Si oui, ça monte dans le socle
   `~/.claude/standards/`, et **nulle part ailleurs** (règle de placement,
   `~/.claude/CLAUDE.md` §1). Une pratique générique recopiée dans un projet est déjà
   une divergence.
3. **Sinon, est-ce propre à 5Hostachy ?** → banque `~/.claude/projects/C--Dev-5hostachy/memory/`,
   un fichier = un fait, plus une ligne dans `MEMORY.md`.
4. **Une mémoire existante est-elle devenue fausse ?** Une mémoire périmée est pire
   qu'une mémoire absente : elle est citée avec assurance. La corriger ou la
   supprimer — ne jamais empiler une exception par-dessus.

Vérifier aussi que la documentation *visible* a suivi : manuel utilisateur mis à jour
(il ne porte plus de version ni de date à bumper depuis le 23/10/2026 —
`test_le_manuel_ne_porte_pas_de_numero_de_version` en refuse le retour), `specs/` si un
contrat d'API a changé.

**Pourquoi ce point existe :** sur le lot des pièces jointes (03/08/2026), quatre
constats n'auraient été écrits nulle part sans un rappel explicite — la version du
manuel jamais bumpée, les fins de ligne cassées par `sed -i` puis « réparées » d'une
façon qui ne restaure pas un fichier mixte, les endpoints devenus orphelins, et le
drapeau `fichiers` des e-mails calculé sur l'intention plutôt que sur la pièce jointe
réelle. Trois d'entre eux ont été soulevés **par l'utilisateur**, pas par le
processus : c'est exactement la question 1.

**P12 — retirer la copie de travail du lot (#1890, 13/10/2026).** Chaque lot
travaille dans sa copie à soi, et aucun ne la retirait : **134** s'étaient
accumulées en deux semaines. La copie se retire une fois la MEP vérifiée — la
branche reste, rien ne se perd. Le script refuse ce qui perdrait quelque chose
(modification non committée, commits sur aucune branche), retire d'abord les
**jonctions** vers le clone principal (sinon le retrait vide ses
`node_modules`, `standards/13` §10), et refuse le répertoire courant de
l'appelant : sous Windows, un répertoire tenu ouvert fait échouer le retrait **à
moitié** (`.git` parti, fichiers restés). Le lancer donc **depuis le clone
principal**, jamais depuis la copie elle-même. `GARDÉE` sort en code 1 avec son
motif. Le stock d'une session qui n'a pas fini proprement :
`bash scripts/poste/retirer-worktree.sh --inactifs` (24 h par défaut ; `--voir`
liste sans retirer).
