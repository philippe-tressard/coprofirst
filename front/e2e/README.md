# Tests de navigateur (Playwright)

Ce dossier porte les tests qui vérifient **ce qui se voit** — le comportement au
clavier, la responsivité, le rendu réel d'un écran. Le reste du projet vérifie
autre chose : `api/tests/` le serveur, les `lint:*` la **source**, `svelte-check`
les types. Aucun d'eux ne peut dire quel élément prend le focus au premier Tab,
ni si une page déborde horizontalement sur un téléphone.

```bash
cd front
npm run e2e            # tous les tests, profils bureau ET mobile
npm run e2e:ui         # le mode interactif, pour écrire un test
npx playwright test --project=bureau e2e/squelette.spec.ts
```

Le serveur de développement démarre tout seul (`webServer` dans
`playwright.config.ts`) et est réutilisé s'il tourne déjà.

## Ce que ces tests couvrent — et ce que l'API simulée ne prouve pas

**Deux familles, et la différence compte.**

1. **Les écrans publics, pour de vrai** — `/auth/*`, les mentions légales, la
   politique de confidentialité : le serveur de développement les rend sans
   session, et le test lit ce qu'un visiteur lit (`squelette.spec.ts`).
2. **Les écrans authentifiés, sur une API simulée.** Tout le site applicatif est
   derrière une connexion, et un test qui chercherait l'écran sans compte serait
   _sauté_ — un faux vert. On rend donc le VRAI écran, avec le VRAI navigateur et
   le VRAI CSS, en interceptant `/api/*` : `simulerApi` (`e2e/aides.ts`) répond
   `MEMBRE_CS` à `/api/auth/me`, la forme déclarée dans `REPONSES_PAR_DEFAUT` pour
   les chemins dont la forme ne se devine pas, un objet vide pour une
   configuration et une liste vide pour le reste ; un test qui veut autre chose
   le déclare à l'appel. La plupart des specs de ce dossier sont de cette
   famille — leur nombre se lit par `ls`, il ne s'écrit pas ici.

⚠️ **Ce que l'API simulée ne prouve PAS** — et c'est ce qui borne ces tests :

- **le serveur** : un droit, un filtre de lecture, une règle d'accès. Le compte
  simulé est un membre du conseil syndical (`MEMBRE_CS`), qui voit tout : un
  test qui le prend ne dit rien de ce qu'un résident ne doit PAS voir — c'est
  l'affaire de `api/tests/` ;
- **la forme réelle des réponses** : le simulateur rend celle qu'on lui a
  déclarée. Si le serveur la change, le test reste vert. C'est pourquoi chaque
  entrée de `REPONSES_PAR_DEFAUT` nomme le type du client qu'elle imite, et
  pourquoi une réponse mal formée fait désormais échouer le test (exception de
  page, voir `e2e/aides.ts`) au lieu de passer en silence (#1475) ;
- **la connexion elle-même** : cookies de session, renouvellement, expiration
  (`api/tests/` pour le serveur ; ici, seul le comportement de l'écran à la
  réponse 401 est éprouvé) ;
- **les données réelles** : listes longues, contenus riches, caractères
  inattendus.

Ce qui est couvert est donc **le comportement de l'interface**, pas celui de
l'application de bout en bout. Un test de bout en bout — avec un compte de test
dans une base de développement, ses identifiants **hors du dépôt** (`standards/03`
§2 : un historique git conserve ce qu'on y a mis) et l'API lancée sur
`localhost:8000` — reste une décision non prise, et rien dans ce dossier ne la
suppose.

⚠️ **Le lien d'évitement « Aller au contenu »** vit dans le squelette `(app)` :
son ancre `#contenu` n'existe pas sur les écrans publics (voir
`routes/+layout.svelte`). Ce que les écrans publics couvrent est la moitié qui
avait réellement cassé — les bandeaux flottants qui volaient le premier Tab
(#802).

### Un exemple de ce que ça coûte (07/09/2026) — et de ce que l'API simulée change

L'infobulle des boutons icône a été signalée à l'écran : elle s'affichait **sous**
l'icône, là où le pointeur la masquait. Le correctif l'a ancrée au-dessus — puis
l'arbitrage suivant, **de nouveau à l'écran**, l'a supprimée au profit de la bulle
native du navigateur. Un test avait été écrit pour vérifier la position rendue,
puis **retiré** : les boutons `btn-icon` étaient tous derrière la connexion, et
il n'existait alors aucun moyen de rendre un écran authentifié. Depuis
l'introduction de `simulerApi`, ce moyen existe.

🔴 Ce qu'un test sans navigateur atteint : `npm run lint:infobulles` tient le nom
accessible et l'absence de résidu `data-info`. **Ce qu'il n'atteint pas** : à quoi
la bulle ressemble, et si elle se lit. Cette question-là a été tranchée deux fois
en une journée par un coup d'œil humain, et c'est exactement le genre de
vérification que ces tests existent pour automatiser.

## En CI : le job `e2e-frontend` (depuis le 08/09/2026, #839)

Ils tournent à chaque PR, dans un job **à part** de `.github/workflows/ci.yml`
(`e2e-frontend`, « Tests de navigateur (Playwright) ») : Chromium seul — les deux
profils, bureau et mobile, l'emploient — installé par
`npx playwright install --with-deps chromium`, puis `npm run e2e`. Job séparé et
non une étape de `build-frontend`, pour ne pas faire payer l'installation des
navigateurs à chaque lint de style.

⚠️ Cette section a dit « Ces tests ne sont pas encore dans la CI » jusqu'au
24/09/2026, seize jours après le branchement du job (#1045) : une consigne fausse
est pire qu'absente. Sur le poste, ils se lancent par `npm run e2e` (ou
`bash scripts/poste/rejouer-ci.sh e2e-frontend`), et `.gitignore` tient leurs
sorties à l'écart (`e2e-rapport/`, `test-results/`).

🔴 **Chaque exécution lance SON serveur, sur SON port** (#1150, 25/09/2026). Le
port était 5173 — celui de `npm run dev` — et un serveur trouvé là était
réutilisé sans un mot : celui du poste, ou celui d'une autre session dans un
autre worktree. Le test lisait alors le code de qui avait lancé ce serveur, et
tombait en `ERR_CONNECTION_REFUSED` quand celui-ci s'arrêtait — un test
différent à chaque fois, jamais en isolé, jamais en CI. Le port se **demande
au système** (`portLibre`, `playwright.config.ts`) — jamais déduit du pid :
la plage d'avant couvrait 5432, le PostgreSQL du poste (#2051) ; 🔒
`npm run lint:e2e-serveur` refuse un port déduit. Deux exécutions dans le
**même** dossier sont refusées d'emblée : elles partagent `test-results/` et
s'effaçaient leurs traces. Le message donne le pid de celle qui tourne.

Une étape en échec de `rejouer-ci.sh` garde sa sortie **complète** dans
`.git/rejeu-ci-echecs/` (chemin affiché) : la queue montrée à l'écran n'est
souvent que le bruit `ECONNREFUSED` du proxy `/api`.

🔴 **Un test d'interface qui échoue pour une raison étrangère à l'interface finit
désarmé.** C'est pourquoi le contrôle des erreurs de console écarte explicitement
les échecs de chargement de ressource : sans API lancée, `/api/*` répond 500, et
cela ne dit rien de la page. Ce qui reste couvert est ce qui compte — une
exception JavaScript ou un `console.error` de l'application.
