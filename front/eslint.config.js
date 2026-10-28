// Configuration eslint « à plat » — posée le 17/08/2026 (#419).
//
// Avant ce fichier, `eslint .` ne démarrait pas du tout :
//
//     ESLint couldn't find an eslint.config.(js|mjs|cjs) file.
//
// eslint et @typescript-eslint étaient installés, tenus à jour par Dependabot, et
// n'avaient jamais analysé une seule ligne du dépôt. Un linter installé, à jour et
// inerte ressemble à un linter — c'est tout le sujet du ticket.
//
// Jeu de règles volontairement MINIMAL : les presets « recommended », rien de plus.
// Les règles de style ne se négocient pas dans le lot qui met le linter en place ;
// on mesure d'abord la dette, on la traite ensuite.
//
// ✅ MISE À JOUR DU 20/08/2026 — LE RELEVÉ EST VERT ET LE JOB EST CÂBLÉ.
// `npm run lint:eslint` tourne dans `build-frontend` (point 4 de #419). Il n'y a
// toujours PAS de `--max-warnings <chiffre>` : un seuil posé pour obtenir du vert
// est un contrôle qui ment (`standards/04`). Chaque règle coupée l'est NOMMÉMENT,
// avec son compte et son motif, et la dette est suivie en #549 et #550.
//
// ✅ Prettier est lui aussi en CI : l'étape « Formatage » lance `npm run lint:format`
// (#419 est fermé, `.prettierrc` charge `prettier-plugin-svelte`). `npm run lint`,
// qui enchaîne les deux, n'est qu'un agrégat de poste : la CI nomme chaque étape.

import js from '@eslint/js';
import ts from 'typescript-eslint';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';
import { defineConfig } from 'eslint/config';

export default defineConfig(
	// ── Périmètre : ce qui est écrit à la main, jamais ce qui est produit ────────
	// `build/` et `.svelte-kit/` sont des SORTIES : les analyser triple le relevé et
	// noie les vrais défauts (c'est ce qui était arrivé à prettier, #410 : 734
	// fichiers sur 785 venaient des répertoires de build). `static/` porte les
	// manuels et des ressources tierces, non écrites ici.
	//
	// 🔴 Trois répertoires manquaient, et l'un d'eux a rendu ce lint INTERMITTENT
	// (#1064) : Playwright écrit des bundles minifiés dans `e2e-rapport/` le temps
	// de son exécution, puis les incorpore à `index.html` et les supprime. ESLint
	// y relevait ~2075 `no-unused-expressions` — mais seulement s'il passait
	// pendant cette fenêtre. Un rouge une fois sur deux enseigne à relancer
	// jusqu'au vert, et ce réflexe reste le même le jour où le rouge est vrai.
	//
	// 🔒 `npm run lint:eslint-ignore` exige que tout répertoire de `front/` ignoré
	// par git le soit ici : .gitignore est la liste de ce qui est PRODUIT, donc
	// c'est la source. Une seconde liste tenue à la main diverge au premier outil
	// qui écrit ailleurs — c'est précisément ce qui est arrivé.
	{
		ignores: [
			'build/',
			'.svelte-kit/',
			'node_modules/',
			'static/',
			'e2e-rapport/',
			'test-results/',
			'playwright/.cache/',
		],
	},

	// ── Sources TypeScript et JavaScript ────────────────────────────────────────
	{
		//  `e2e/` rejoint ce bloc plutôt que d'en ouvrir un second : ce sont les
		//  mêmes sources TypeScript, avec les mêmes globals de navigateur (les
		//  callbacks de `page.evaluate` lisent `document`). Un bloc de plus aurait
		//  été une seconde liste de règles, libre de diverger.
		files: ['src/**/*.{js,ts}', 'scripts/**/*.{js,mjs,ts}', 'e2e/**/*.ts'],
		extends: [js.configs.recommended, ts.configs.recommended],
		languageOptions: {
			ecmaVersion: 2022,
			sourceType: 'module',
			globals: { ...globals.browser, ...globals.node },
		},
	},

	// ── Scripts de contrôle (`npm run lint:*`) : Node pur, pas de navigateur ─────
	{
		files: ['scripts/**/*.{js,mjs,ts}'],
		languageOptions: {
			globals: { ...globals.node },
		},
	},

	// ── Fichiers de configuration à la racine ───────────────────────────────────
	// `vite.config.ts` est écrit à la main comme le reste (SvelteKit 3 n'a plus de
	// `svelte.config.js`, #2205) : il entre dans le périmètre. Ajoutés le 20/08/2026 — ils n'étaient couverts
	// par AUCUN bloc, donc analysés avec l'analyseur JavaScript par défaut, qui
	// s'arrête au premier `:` de type. Une erreur d'analyse n'est pas un relevé :
	// ces fichiers n'étaient tout simplement pas mesurés.
	{
		files: ['*.{js,ts}'],
		extends: [js.configs.recommended, ts.configs.recommended],
		languageOptions: {
			ecmaVersion: 2022,
			sourceType: 'module',
			parser: ts.parser,
			globals: { ...globals.node },
		},
	},

	// ── Composants Svelte ───────────────────────────────────────────────────────
	// Le parseur lit `lang="ts"` avec `ts.parser` ; il n'a plus de `svelteConfig` à
	// recevoir (SvelteKit 3 a supprimé `svelte.config.js`, #2205) — Svelte 5 comprend
	// le TypeScript sans préprocesseur.
	// `projectService` n'est PAS activé : aucune règle « type-checked » n'est en
	// service ici, et l'activer coûterait le typage complet du projet à chaque
	// exécution sans rien mesurer de plus.
	{
		files: ['src/**/*.svelte', 'src/**/*.svelte.{js,ts}'],
		extends: [js.configs.recommended, ts.configs.recommended, svelte.configs.recommended],
		languageOptions: {
			globals: { ...globals.browser },
			parserOptions: {
				parser: ts.parser,
				extraFileExtensions: ['.svelte'],
			},
		},
		rules: {
			// ── `no-unused-vars` : la version TypeScript PLANTE sur les .svelte ────────
			// Avec svelte-eslint-parser 1.8.1 et typescript-eslint 8.67.0 (les deux à
			// jour au 17/08/2026), `@typescript-eslint/no-unused-vars` fait tomber
			// eslint tout entier sur le premier composant analysé :
			//
			//   TypeError: Cannot read properties of undefined (reading 'type')
			//   Rule: "@typescript-eslint/no-unused-vars"
			//
			// La règle de base, elle, fonctionne : elle comprend la portée du template
			// (un composant utilisé seulement dans le balisage n'est PAS signalé) et
			// trouve de vrais morts — imports de composants jamais rendus, fonctions
			// jamais appelées. On l'échange donc plutôt que de renoncer à la détection :
			// une règle désactivée sans remplacement, c'est un contrôle en moins.
			//
			//  ✅ **ELLE NE PLANTE PLUS — vérifié le 29/08/2026**, et c'est
			//  exactement la condition de réactivation écrite ci-dessus. Le relevé
			//  complet tient en **6 signalements** (contre 139 pour la règle de base
			//  en août), dont **4** sont des variables volontairement inutilisées et
			//  préfixées `_` : la convention existait, elle n'était simplement pas
			//  déclarée à l'outil.
			//
			//  On rétablit donc la version TypeScript, qui est la bonne : elle LIT les
			//  annotations de type, là où la règle de base y voyait 59 faux morts —
			//  `export let onUpload: (f: File) => …` lui montrait un `f` jamais employé.
			//  `args: 'none'` était le pansement de cette cécité ; il n'est plus utile,
			//  et il masquait au passage les vrais paramètres morts.
			'@typescript-eslint/no-unused-vars': [
				'error',
				{
					//  Les quatre portées où la convention `_` dit « je sais, et c'est
					//  voulu ». Sans elles, l'outil punit une intention explicite.
					argsIgnorePattern: '^_',
					varsIgnorePattern: '^_',
					caughtErrorsIgnorePattern: '^_',
					//  `{#each xs as _opt, i}` — le tableau est parcouru pour son INDEX,
					//  et c'est nécessaire : dans un formulaire, la liaison doit viser
					//  `options[i].libelle` et non la variable de boucle, sinon
					//  `bind:value` écrit dans une copie locale et la saisie est perdue.
					//  Deux composants le font (`FormulaireSondage`, `prestataires`) ; le
					//  motif est écrit ICI, une fois, et pas en commentaire dans chacun.
					destructuredArrayIgnorePattern: '^_',
				},
			],
			//
			//  ⚠️ MISE À JOUR DU 20/08/2026 — la règle de base ne lit pas TypeScript,
			//  et 59 de ses 139 signalements étaient des NOMS DE PARAMÈTRES DANS DES
			//  ANNOTATIONS DE TYPE : `export let onUpload: (f: File) => Promise<…>`
			//  lui montre un `f` déclaré et jamais employé. `args: 'none'` les écarte
			//  — ce sont des arguments — sans rien perdre des vrais morts.
			//
			//  🔴 Restent alors **74 morts RÉELS**, et ils sont éloquents : 42 imports
			//  laissés derrière par les extractions de composants (18 dans
			//  `espace-cs`, 15 dans `calendrier`), des fonctions devenues orphelines,
			//  et surtout des VALEURS CALCULÉES POUR L'AFFICHAGE ET JAMAIS AFFICHÉES
			//  (`{@const enAttente = …}`, `$: aVote = …`) — même famille que #505,
			//  l'événement dispatché que personne n'écoutait.
			//
			//  La règle est coupée **le temps de ce lot seulement**, et le ménage est
			//  suivi en #550 avec la liste exhaustive. Elle n'est pas coupée parce
			//  qu'elle aurait tort : elle est coupée parce qu'un ménage de 74 sites
			//  dans 24 fichiers ne se glisse pas dans le lot qui allume l'outil — on
			//  ne saurait plus lequel des deux a cassé quoi.
			//
			//  🔴 LA RÈGLE DE BASE EST DÉSORMAIS COUPÉE, et ce n'est pas un renoncement :
			//  c'est la version TypeScript ci-dessus qui la remplace, en strictement
			//  plus fine. Les garder toutes les deux ferait signaler chaque mort DEUX
			//  fois et, pire, ferait dépendre le verdict de la moins informée des deux.
			//  #550 a fait le ménage des 74 morts réels qu'elle avait révélés.
			'no-unused-vars': 'off',

			// ── Trois règles inadaptées À CE PROJET, désactivées sur un fait vérifié ───
			// Aucune n'est éteinte pour le confort ni pour faire baisser un compteur :
			// chacune produit 100 % de faux positifs ici, et la condition de sa
			// réactivation est écrite en toutes lettres.
			//
			// `prefer-svelte-reactivity` (49 signalements) conseille SvelteSet/SvelteMap
			// à la place de Set/Map. Ces classes ne servent QU'EN MODE RUNES ; or aucun
			// des 92 composants n'utilise de rune (vérifié le 17/08/2026 : `$state(`,
			// `$derived(`, `$props(` → 0 fichier). La réactivité passe ici par la
			// réassignation de Svelte 4 (`x = x`), que la règle ne sait pas voir.
			// → À réactiver le jour de la migration aux runes.
			'svelte/prefer-svelte-reactivity': 'off',

			// `no-navigation-without-resolve` (95 signalements) exige `resolve()` autour
			// des `href` et des `goto()`. Cela ne sert qu'à une application servie sous
			// un chemin de base ; `vite.config.ts` ne définit AUCUN `paths.base` et le
			// site est servi à la racine.
			// → À réactiver le jour où un `paths.base` apparaît dans `vite.config.ts`.
			'svelte/no-navigation-without-resolve': 'off',

			// `no-irregular-whitespace` (**7** signalements au 29/08/2026, contre 10)
			// : les sept sont des U+00A0, espaces INSÉCABLES de typographie française
			// dans du texte affiché — « Ex : », « N° 12 », « 45 m² », tous relus un par
			// un ce jour-là. Les retirer abîmerait l'affichage. La règle ignore les
			// chaînes JS par défaut, mais pas le texte d'un template Svelte.
			//
			// ⚠️ Elle est coupée **ici seulement**, sur les `.svelte`. Elle reste ACTIVE
			// sur les `.ts` / `.js` (bloc du haut), où le relevé est à **zéro** et où un
			// caractère invisible n'est jamais de la typographie : c'est là que vivait
			// le U+0008 qui rendait une expression régulière inerte sans que personne
			// puisse le voir. Couper une règle partout parce qu'elle a tort quelque
			// part, c'est perdre les endroits où elle a raison.
			'no-irregular-whitespace': 'off',

			// NB : `@typescript-eslint/no-unused-expressions` (5 signalements) est
			// VOLONTAIREMENT laissée active. On aurait pu la croire du même tonneau —
			// l'idiome réactif `$: dep, action();` — mais un seul des 5 cas en relève
			// (Nav.svelte:86) ; les 4 autres sont des ternaires employés comme
			// instructions. Elle mesure donc quelque chose de réel : elle reste.

			// ⚠️ DÉSACTIVATION ASSUMÉE, ET ELLE LAISSE UN TROU — à lire avant d'y toucher.
			//
			// `svelte/no-at-html-tags` interdit tout `{@html …}`. Ce projet en emploie
			// dans de nombreux fichiers (`npm run lint:html` les compte), et ils sont voulus : les contenus riches (descriptions de
			// tickets, corps de notifications) sont assainis par DOMPurify dans
			// `src/lib/sanitize.ts` avant d'être rendus. La règle ne sait pas distinguer
			// `{@html safeHtml(x)}` de `{@html x}` : elle les condamne les deux, donc elle
			// ne mesure pas ce qui compte ici.
			//
			// ⚠️ MAIS il n'existe AUJOURD'HUI aucun garde-fou automatisé qui vérifie que
			// tout `{@html}` passe bien par une fonction d'assainissement : vérifié le
			// 17/08/2026, aucun `npm run lint:*` ni aucun test d'`api/tests/` ne mentionne
			// `safeHtml`. La seule protection est la règle écrite dans `CLAUDE.md`. Cette
			// ligne n'éteint donc pas un contrôle redondant — elle laisse la place vide.
			// Un `lint:html` doit la combler (cf. #419) : c'est le traitement retenu pour
			// le même cas de figure en #410, où `lint:manuels` a remplacé ce que l'ignore
			// prettier faisait disparaître.
			// ⚠️ MISE À JOUR DU 20/08/2026 — LE TROU EST COMBLÉ, et cette note l'a
			// affirmé faux pendant trois jours. `npm run lint:html` existe depuis le
			// 18/08 et fait exactement ce qui manquait : il exige que tout `{@html}`
			// passe par un assainisseur de `$lib/sanitize`, avec le nom pris dans
			// l'IMPORT (une fonction locale homonyme ne passe pas) et deux exceptions
			// déclarées qui font échouer le contrôle si elles cessent de servir.
			//
			// Une explication juste à l'écriture devient un alibi quand ce qu'elle
			// décrit a changé. C'est la raison pour laquelle elle est corrigée ici
			// plutôt que laissée « puisque la conclusion tient toujours ».
			'svelte/no-at-html-tags': 'off',

			// ── DETTE DÉCLARÉE — relevée le 20/08/2026, suivie en #549 ──────────
			//
			// 🔴 Ces règles sont coupées parce que la dette est trop grosse pour le
			// lot qui met le linter en service, PAS parce qu'elles auraient tort.
			// Chacune porte son compte, et la remise en service se fait règle par
			// règle.
			//
			// ⚠️ C'est la seule forme honnête, et c'est ce que #419 demandait :
			// `--max-warnings <chiffre>` aurait donné du vert en masquant TOUT, y
			// compris ce qu'on ajoutera demain. Ici, toute règle non citée reste
			// active — une nouvelle violation fait échouer la CI dès aujourd'hui.

			// `{#each}` sans clé. La plus intéressante des six : sans clé, Svelte
			// réutilise les nœuds par POSITION, et un élément retiré au milieu d'une
			// liste emporte l'état de son voisin. Classe de bug réelle.
			//
			// 🔴 LE COMPTE N'EST PLUS ÉCRIT ICI, ET C'EST VOULU. Il l'était — « 160 »
			// — et il est resté à 160 pendant que quatre lots le ramenaient à 57 :
			// trois PR successives avaient corrigé le code sans rouvrir ce
			// commentaire. Un chiffre recopié dérive au premier lot, et celui-ci
			// avait l'autorité d'une configuration.
			//
			// Le compte vit dans `scripts/check-each-key.mjs` (`npm run lint:each-key`),
			// qui le MESURE à chaque exécution et refuse aussi bien un dépassement
			// qu'un plafond devenu périmé — donc il ne peut pas mentir dans un sens
			// ni dans l'autre. La règle se rallume ici quand ce plafond atteint zéro.
			'svelte/require-each-key': 'off',

			// ✅ EN SERVICE depuis le 29/08/2026 (#549). Elles étaient coupées au
			// motif qu'« aucune n'est un défaut avéré » — le relevé les avait lues
			// comme des `$:` sans rien à quoi réagir, donc voulus. Les reprendre
			// une à une a montré l'inverse sur la moitié :
			//
			//   • TROIS vues du reporting figeaient l'année de référence, avec juste
			//     au-dessus le commentaire décrivant le rafraîchissement qui n'avait
			//     pas lieu — « un onglet laissé ouvert la nuit du réveillon » ;
			//   • l'écran des prestataires figeait MINUIT, borne du « en retard » :
			//     un onglet ouvert la veille se trompait de jour ;
			//   • le sélecteur de périmètre rendait le défaut d'AVANT le chargement
			//     de l'arbre, donc `null`, et pour toujours ;
			//   • et `infinite-reactive-loop`, qualifiée d'« heuristique », a trouvé
			//     une boucle CERTAINE : sur une copropriété sans compteur, l'onglet
			//     Consommations rappelait l'API sans fin (le cas zéro, invisible ici
			//     puisque cette copropriété-ci a des compteurs).
			//
			// Le reste — huit `$:` qui sont vraiment des constantes — est écrit
			// `const`, la seule forme qui ne mente pas sur son intention.
			// Un seul faux positif subsiste, déclaré sur place avec sa raison.
			'svelte/no-immutable-reactive-statements': 'error',
			'svelte/infinite-reactive-loop': 'error',
			//
			//  🔴 `no-reactive-functions` ne peut PAS être réactivée aujourd'hui, et ce
			//  n'est plus une question de dette : elle FAIT TOMBER ESLINT 10.
			//  Mesuré le 29/08/2026 en tentant de relever son compte —
			//
			//      TypeError: source.isSpaceBetweenTokens is not a function
			//      Occurred while linting …/PerimetrePicker.svelte:99
			//      Rule: "svelte/no-reactive-functions"
			//
			//  Son correcteur automatique appelle une API retirée d'ESLint 10.
			//  → À réactiver quand `eslint-plugin-svelte` aura corrigé son `fix()`.
			//  ⚠️ Tant que ce bug tient, la réactiver rendrait la CI rouge par CRASH,
			//  pas par violation : un échec qu'on lirait comme une panne d'outillage.
			'svelte/no-reactive-functions': 'off',

			// ── ESLint 10 : `no-useless-assignment` ne connaît pas `$:` ──────────
			// Entrée dans le preset « recommended » d'ESLint 10 (27/08/2026, montée
			// 9.39.5 → 10.8.1). Elle produit ici **6 signalements, 6 faux positifs**,
			// tous de la même cause : son analyse de flux lit un composant Svelte 4
			// comme du code linéaire, alors qu'une instruction `$:` **se rejoue** à
			// chaque changement de ses dépendances.
			//
			// Les quatre premiers sont des DRAPEAUX D'INITIALISATION UNIQUE — le
			// motif exact que `profil/+page.svelte` porte depuis le 14/08/2026 pour
			// ne pas écraser une saisie en cours :
			//
			//     let champsInitialises = false;
			//     $: if ($currentUser && !champsInitialises) {
			//         champsInitialises = true;   // ← « valeur jamais relue »
			//         initialiserDepuis($currentUser);
			//     }
			//
			// Elle EST relue : au passage suivant, par la garde du `if`. Suivre la
			// règle supprimerait le drapeau et rendrait le bloc rejouable — c'est
			// exactement le défaut qu'il empêche.
			//
			// Les deux derniers (`recentItems`, `olderItems` au tableau de bord) sont
			// des valeurs initiales `[]` qu'un `$:` remplace avant le premier rendu :
			// techniquement « inutiles », mais les retirer laisserait deux variables
			// non initialisées pour gagner zéro.
			//
			// → Coupée sur les `.svelte` UNIQUEMENT. Elle reste active sur les `.ts`
			//   et les `.js`, où elle mesure ce qu'elle prétend mesurer (relevé :
			//   0 signalement, donc aucune dette masquée).
			// → À réactiver le jour de la migration aux runes, où `$state` remplace
			//   `$:` et où l'analyse de flux redevient juste.
			'no-useless-assignment': 'off',

			// ✅ EN SERVICE depuis le 29/08/2026 (#549). Trois `{'…'}` corrigés :
			// deux espaces devenus des `&nbsp;` (là où c'était bien une espace
			// insécable qu'on voulait) et un libellé de colonnes rendu à sa forme
			// d'attribut. Le motif d'origine — « on n'entre pas dans un fichier de
			// 2 105 lignes pour deux caractères » — ne tient plus : le fichier en
			// fait 1 900 depuis le découpage des compteurs.
			'svelte/no-useless-mustaches': 'error',

			// 4 — `a ? f() : g()` employé comme INSTRUCTION. La note ci-dessus
			// gardait la règle active en comptant sur une correction du code ; les 4
			// cas restants sont tous cette forme-là, lisible et volontaire
			// (`dx > 0 ? precedente() : suivante()`). La règle garde son intérêt sur
			// le reste : une expression calculée puis jetée est presque toujours un
			// `=` oublié — et c'est précisément ce que `no-unused-vars` a trouvé de
			// son côté (#550).
			'@typescript-eslint/no-unused-expressions': [
				'error',
				{ allowTernary: true, allowShortCircuit: true },
			],
		},
	},

	// ── Décisions qui valent PARTOUT, `.ts` comme `.svelte` ─────────────────────
	//
	// ⚠️ Ce bloc vient EN DERNIER, et c'est ce qui le rend efficace : dans une
	// configuration plate, le dernier bloc applicable gagne. Placées seulement dans
	// le bloc Svelte, ces deux règles laissaient 148 signalements dans les `.ts` —
	// le linter refusait de passer au vert et l'erreur ressemblait à de la dette
	// alors que c'était une question de PORTÉE. Une désactivation posée au mauvais
	// niveau ne se voit pas : elle ressemble à une désactivation qui marche.
	{
		//  ⚠️ Le greffon doit être déclaré DANS le bloc qui emploie ses règles :
		//  `defineConfig` n'hérite pas des `plugins` d'un bloc voisin. Sans cette
		//  ligne, ESLint s'arrête sur « the plugin is not defined within the same
		//  configuration object » — un échec net, au moins, et pas un silence.
		files: ['**/*.{js,mjs,ts,svelte}'],
		plugins: { '@typescript-eslint': ts.plugin },
		rules: {
			// AUCUN `any`, nulle part (#1571, 08/10/2026). Le client d'API y était
			// depuis la v2.105.0 (#1572, 119 → 0) ; le reste de `src/` était tenu par
			// un plafond (`check-any.mjs`, 275 → 0), retiré à zéro : il y était muet.
			// Une entité se type sur le client, un champ lu par son nom passe par
			// `champDe`, un composant transmis sans lire ses props par
			// `Component<never>` (`modale-imperative.ts`).
			'@typescript-eslint/no-explicit-any': 'error',

			// Même raison que dans le bloc Svelte : `a ? f() : g()` employé comme
			// instruction est une forme volontaire et lisible de ce dépôt.
			'@typescript-eslint/no-unused-expressions': [
				'error',
				{ allowTernary: true, allowShortCircuit: true },
			],
		},
	},
);
