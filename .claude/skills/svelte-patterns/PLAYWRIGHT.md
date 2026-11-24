# svelte-patterns — Tests de navigateur (Playwright)

Annexe de `SKILL.md`, chargée à la demande (#2910) : avant d'écrire ou de corriger un
test sous `front/e2e/`.

### Tests de navigateur (Playwright) — `front/e2e/`, job `e2e-frontend`

Venu de `CLAUDE.md` (#2709). Lancer : `cd front && npm run e2e`.

- Profils **bureau ET mobile**. En CI, quatre tranches Chromium (`--shard`) et une WebKit ;
  le check requis « Tests de navigateur (Playwright) » est l'agrégat `e2e-verdict` (#2632).
- **Un test qui mesure la mise en page se joue aussi sous WebKit** (#2640) : son titre finit
  par `@mise-en-page` (`e2e/mise-en-page.ts`) ; une mesure du défilement sans elle est
  refusée (`npm run lint:e2e-mise-en-page`). Le profil se lit par
  `info.project.use.isMobile` ou `hasTouch`, jamais par son nom.
- **Un `import()` a toujours un destinataire** (#2683) : rattrapé (`.catch`, `try`) ou rendu à
  qui y répond (`charger={() => import(…)}` de `ChargementDiffere`) — sous WebKit, un rejet
  sans destinataire devient une exception de la page. `npm run lint:imports-rattrapes` ;
  `e2e/import-interrompu.spec.ts` (`@moteur`). Les `ECONNREFUSED` du journal viennent du proxy
  de `/telemetry/collect`, sans API derrière.
- **Un test ne quitte un écran qu'à son état final** (#2807) : une lecture lancée pendant un
  `page.goto` fait écrire à WebKit `Fetch API cannot load … due to access control checks.`,
  que Playwright compte comme exception de la page — même rejet rattrapé. Attendre ce que
  l'écran affiche une fois chargé, jamais filtrer le message ni rattraper dans le client
  (`e2e/admin-a-traiter.spec.ts`, `LECTURES_TARDIVES`).
- Un écran authentifié se rend avec l'**API simulée** (`e2e/depot-fichier.spec.ts`,
  `e2e/ligne-pastilles.spec.ts`) ; le motif d'interception vise le chemin `/api/` du serveur
  seulement, sinon il attrape `/src/lib/api/…` (`standards/05` §13).
- Position ou taille lue juste après l'ouverture d'une boîte : `boiteStable` (`e2e/aides.ts`),
  jamais `boundingBox()` seul (#1625).
- « La page ne défile pas en largeur » : `attendreSansDefilementHorizontal`
  (`e2e/defilement.ts`), précédée d'`elargirLeTexte` pour un tableau ou une longue rangée
  (#2437, `npm run lint:defilement`).
- Un spec prend `test` et `expect` dans `./aides`, jamais dans `@playwright/test` (`npm run
  lint:e2e-test`) : ce `test`-là fait échouer toute exception de la page (#1475). Une réponse
  simulée qui ne se devine pas au chemin se déclare dans `REPONSES_PAR_DEFAUT` (`e2e/aides.ts`).
- Une lecture qui ne réessaie pas (`count()`, `allTextContents`, `textContent()`,
  `innerText()`, `isVisible()`) suivie d'un `expect` vit dans un `expect.poll`, ou se déclare
  dans `DECLAREES` (`npm run lint:e2e-lectures`, #1830).
- Le serveur des tests écoute sur `127.0.0.1`, et les tests le visent là, jamais `localhost`
  (#1732, `npm run lint:e2e-serveur`).
- Aucun rechargement de Vite pendant les tests (#1421) : une dépendance chargée par un
  `import()` dynamique se déclare dans `optimizeDeps.include` (`vite.config.ts`) — `npm run
  lint:optimize-deps`.
- Un délai d'hydratation dépassé se lit au bilan **⏱ hydratation** en fin de sortie
  (`test-results/hydratation.json`).
