import adapter from '@sveltejs/adapter-node';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, type Plugin } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';
import { execSync } from 'child_process';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

//  Le condensat du garde de démarrage (#1993), calculé sur le fichier que
//  `hooks.server.ts` injecte tel quel : le modifier suffit, rien ne se recopie.
const GARDE_DEMARRAGE: `sha256-${string}` = `sha256-${createHash('sha256')
	.update(readFileSync(new URL('./src/garde-demarrage.js', import.meta.url), 'utf8'))
	.digest('base64')}`;

//  Seul le greffon de BUILD de `vite-plugin-pwa` ne s'applique qu'à l'environnement CLIENT.
//
//  SvelteKit 3 construit par ENVIRONNEMENTS Vite — le serveur d'abord, puis le
//  client. `vite-plugin-pwa:build` ne distingue que `build.ssr` de la configuration
//  racine, qui vaut `false` dans les deux : il générait donc le service worker à la
//  fin du build SERVEUR, avant que `.svelte-kit/output/client` existe, et le build
//  tombait sur « Couldn't find configuration for either precaching or runtime
//  caching » (workbox ne trouvait aucun fichier à précacher, #2205).
//  Les autres greffons (le module virtuel `virtual:pwa-register`, que le build
//  serveur résout aussi en important `MajDisponible`) restent actifs partout.
//  `npm run lint:sw` vérifie le précache sur le bundle construit.
function clientSeul(plugins: Plugin[]): Plugin[] {
	return plugins.map((p) =>
		p.name === 'vite-plugin-pwa:build'
			? { ...p, applyToEnvironment: (env) => env.name === 'client' }
			: p,
	);
}

function gitHash(): string {
	// En build Docker, VITE_GIT_HASH est injecté via ARG/ENV
	if (process.env.VITE_GIT_HASH && process.env.VITE_GIT_HASH !== 'dev') {
		return process.env.VITE_GIT_HASH;
	}
	try {
		return execSync('git rev-parse --short HEAD').toString().trim();
	} catch {
		return 'dev';
	}
}

function buildDate(): string {
	// Horodatage de build affiché dans le footer, en heure de PARIS.
	//
	// `new Date().toISOString()` est toujours en UTC : le footer annonçait
	// « 2026/07/26-08:48 » pour une MEP réellement effectuée à 10:48 (constaté le
	// 26/07/2026), soit 2 h de moins, et sans aucune mention du fuseau — donc lu
	// comme une heure locale fausse. Même classe que le bug des mois en anglais du
	// même jour : une date montrée à l'utilisateur qui ne suit pas la convention
	// Europe/Paris du projet (cf. `$lib/date.ts`).
	//
	// `formatToParts` plutôt qu'un `replace` sur une chaîne localisée : on
	// recompose explicitement, sans dépendre du format d'une locale.
	const parts = new Intl.DateTimeFormat('fr-FR', {
		timeZone: 'Europe/Paris',
		year: 'numeric',
		month: '2-digit',
		day: '2-digit',
		hour: '2-digit',
		minute: '2-digit',
		hour12: false,
	}).formatToParts(new Date());
	const p = (type: string) => parts.find((x) => x.type === type)?.value ?? '00';
	return `${p('year')}/${p('month')}/${p('day')}-${p('hour')}:${p('minute')}`;
}

export default defineConfig({
	define: {
		'import.meta.env.VITE_GIT_HASH': JSON.stringify(gitHash()),
		'import.meta.env.VITE_BUILD_DATE': JSON.stringify(buildDate()),
	},
	plugins: [
		//  Depuis SvelteKit 3 (#2205), la configuration du framework vit ICI :
		//  `svelte.config.js` n'est plus lu. Les options sont à plat, sans `kit: {}`.
		sveltekit({
			//  Les feuilles CSS de moins de 2 Ko voyagent DANS la page (11/10/2026).
			//
			//  Chaque composant a sa feuille : l'écran Affaires en demandait 35 à
			//  l'ouverture, dont 26 de moins de 2 Ko — autant de requêtes et
			//  d'analyses pour 13 Ko au total. Intégrées à la page, elles retirent
			//  15 à 30 ms à l'« Ouverture du site » d'un téléphone moyen (mesuré :
			//  processeur ralenti ×4, API simulée). Les grosses restent des fichiers,
			//  que le cache et le service worker gardent d'une visite à l'autre.
			//
			//  ⚠️ Permis par la CSP de Caddy (`style-src 'self' 'unsafe-inline'`) ;
			//  celle de SvelteKit ne pose pas de `style-src`. Le jour où l'une des
			//  deux le resserre, ce réglage le casse en premier.
			inlineStyleThreshold: 2048,
			adapter: adapter({
				out: 'build',
				precompress: true,
			}),
			alias: {
				$lib: 'src/lib',
			},
			//  🔒 CSP — `script-src` en mode BLOQUANT, ce que Caddy ne pouvait pas faire (#770).
			//
			//  SvelteKit sert DEUX scripts inline par page (hydratation) : ils
			//  totalisaient 370 des 404 violations du relevé. Poser `script-src 'self'`
			//  dans le Caddyfile aurait rendu le site blanc — seul le framework connaît
			//  le contenu de ses scripts, donc seul lui peut en calculer le condensat.
			//
			//  Mode `hash` et non `nonce` : un nonce doit être unique par réponse, ce
			//  qui interdit toute mise en cache de la page. Les condensats, eux, sont
			//  déterministes par build et traversent le cache Cloudflare.
			csp: {
				mode: 'hash',
				directives: {
					'script-src': ['self', GARDE_DEMARRAGE],
				},
			},
		}),
		...clientSeul(
			VitePWA({
				// `prompt` et non `autoUpdate` : en `autoUpdate`, workbox prend la main
				// (`skipWaiting` + `clientsClaim`) et la page se recharge d'elle-même dès
				// qu'une version est trouvée — un formulaire en cours de saisie serait
				// perdu sans avertissement. Ici le nouveau service worker reste en attente
				// et `$lib/components/MajDisponible.svelte` propose le rechargement.
				registerType: 'prompt',
				// Enregistrement explicite par ce même composant, qui a besoin des
				// callbacks (`onNeedRefresh`) et pose le contrôle périodique. `auto`
				// laisserait le plugin injecter en plus son propre script selon qu'il
				// détecte ou non l'import du module virtuel.
				injectRegister: null,
				// URL ABSOLUE du service worker. Sans ces deux options, le plugin hérite du
				// `base` de Vite — vide sous SvelteKit — et génère
				// `new Workbox('./sw.js', { scope: './' })` : l'enregistrement vise alors
				// `/auth/sw.js` depuis `/auth/connexion` et échoue en 404. Constaté en
				// production le 26/07/2026 (v2.24.0) : plus AUCUN service worker enregistré,
				// donc ni cache hors ligne ni bandeau de mise à jour, sur toute route autre
				// que la racine. Vérifié par `npm run lint:sw` sur le bundle construit.
				base: '/',
				//  Le dossier CLIENT de SvelteKit, nommé : le greffon lit `build.outDir` de la
				//  configuration RACINE, qui vaut `dist` depuis SvelteKit 3 (le client n'a plus son
				//  propre `build.outDir` qu'en tant qu'environnement). Sans cela, workbox cherchait
				//  ses fichiers dans un dossier vide : « Couldn't find configuration for either
				//  precaching or runtime caching » (#2205). Le service worker y est écrit, puis
				//  l'adaptateur copie ce dossier tel quel dans `build/client`.
				outDir: '.svelte-kit/output/client',
				scope: '/',
				strategies: 'generateSW',
				// PAS de manifeste généré : il est SERVI par `routes/manifest.webmanifest`,
				// qui y écrit le nom de la résidence lu dans sa configuration (#1725). Un
				// manifeste figé au build portait « 5Hostachy » pour toute installation.
				manifest: false,
				workbox: {
					// PAS de repli de navigation. `vite-plugin-pwa` suppose une SPA et pose
					// par défaut `navigateFallback: 'index.html'` : le service worker répond
					// alors à CHAQUE navigation en servant cet `index.html` depuis son
					// precache. Or SvelteKit en `adapter-node` rend les pages côté serveur
					// et ne produit aucun `index.html` — le fichier n'est donc pas dans le
					// precache, et workbox lève `non-precached-url :: [{"url":"index.html"}]`.
					//
					// Conséquence observée en production le 14/08/2026, signalée par
					// l'utilisateur : sur /profil rechargée directement, la navigation
					// cliente échoue, l'hydratation ne se termine pas, et les champs
					// (prénom, nom, e-mail) restent VIDES — « Enregistrer » aurait écrasé
					// les vraies valeurs par du vide. Le défaut est intermittent, parce
					// qu'il dépend de l'état du cache et du chemin d'arrivée sur la page :
					// il a donc survécu à tous les post-checks, qui regardaient la racine.
					//
					// `null` rend les navigations au serveur, ce qui est exactement ce
					// qu'on veut d'un site rendu côté serveur. Le precache des ressources
					// statiques (js, css, icônes) n'est pas touché. `npm run lint:sw`
					// vérifie sur le bundle CONSTRUIT que le repli n'est pas réapparu.
					navigateFallback: null,
					// PAS de HTML dans le precache (09/10/2026). Le seul fichier HTML du build
					// est le manuel (`static/manuel-utilisateur.html`), et le precache le sert
					// D'ABORD, sans consulter le serveur : un navigateur dont le service worker
					// n'avait pas été remplacé affichait le manuel v2.38 quand le serveur
					// servait la v2.58 — même `fetch(…, { cache: 'no-store' })`. Caddy le sert
					// en `no-cache` exprès (`handle /manuel-utilisateur.html`) : le precache
					// contredisait cette intention. Le manuel n'est donc plus lisible hors
					// ligne ; il lit d'ailleurs le nom de la résidence sur le réseau.
					// `npm run lint:sw` refuse un `.html` dans le precache construit.
					globPatterns: ['**/*.{js,css,ico,png,svg,woff2}'],
					// PAS de mise en cache des réponses d'API — et donc pas de
					// `runtimeCaching` du tout.
					//
					// `/api/lots` et `/api/publications` étaient servis en
					// `StaleWhileRevalidate` pendant une heure. Or les deux exigent
					// `get_current_user` et leur contenu est filtré par utilisateur et
					// par périmètre (`api/app/routers/lots.py`,
					// `api/app/routers/publications/crud.py`) : ce cache contenait des
					// réponses authentifiées et personnalisées.
					//
					// `StaleWhileRevalidate` rend le cache D'ABORD et revalide ensuite,
					// en arrière-plan. Une session expirée continuait donc d'afficher du
					// contenu applicatif, et c'est la revalidation — après le rendu — qui
					// prenait le 401 : l'écran affirmait une session qui n'existait plus
					// (#379). Un cache applicatif qui survit à l'expiration de la session
					// rejoue le même tour à chaque expiration.
					//
					// Ce qui n'est PAS touché : le precache des ressources statiques (js,
					// css, icônes, polices) porté par `globPatterns` — c'est lui qui fait
					// l'installation PWA et le bandeau de mise à jour. Ce qui disparaît,
					// c'est la lecture hors ligne des actualités et des lots : une
					// capacité qu'aucun écran n'annonçait, et qui ne peut pas être rendue
					// correctement tant qu'elle sert du contenu authentifié depuis un
					// cache que rien ne purge à la déconnexion.
					//
					// `npm run lint:sw` vérifie sur le bundle CONSTRUIT qu'aucune route
					// `/api/` n'est remise en cache — la valeur fautive pouvant revenir
					// d'un défaut du plugin autant que d'une ligne écrite à la main.
				},
			}),
		),
	],
	//  Les dépendances chargées par un `import()` DYNAMIQUE (#1421, 28/09/2026).
	//  Le pré-scan de Vite ne les suit pas : à cache froid, il les découvre au
	//  premier écran qui les appelle, les optimise, puis RECHARGE toutes les pages
	//  ouvertes. En développement c'est un clignement ; en e2e, des tests qui
	//  tombent au hasard (« Execution context was destroyed »). Les déclarer ici
	//  les fait optimiser au démarrage. La CI nomme toute nouvelle venue : l'étape
	//  « Tests de navigateur » échoue quand Vite recharge une page en plein test.
	optimizeDeps: {
		include: [
			'dompurify', // $lib/sanitize.ts, chargé côté navigateur seulement
			'@tiptap/core', // l'éditeur riche, chargé à la demande
			'@tiptap/starter-kit',
			'@tiptap/extension-placeholder',
			//  Import STATIQUE, mais d'un écran que le pré-scan n'atteint qu'à la
			//  visite (`QRCode`, l'annuaire) : le premier e2e qui y est allé l'a
			//  fait découvrir en plein test (#779, 01/10/2026).
			'qrcode-generator',
			//  Le rendu Markdown des conditions d'inscription, chargé à l'affichage
			//  (`$lib/markdown`, #1930) : découvert en plein e2e, il rechargeait la page.
			'marked',
		],
	},
	server: {
		proxy: {
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, ''),
			},
		},
	},
});
