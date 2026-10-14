import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';
import { execSync } from 'child_process';

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
		sveltekit(),
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
