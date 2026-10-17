import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

//  Le condensat du garde de démarrage (#1993), calculé sur le fichier que
//  `hooks.server.ts` injecte tel quel : le modifier suffit, rien ne se recopie.
const GARDE_DEMARRAGE = `sha256-${createHash('sha256')
	.update(readFileSync(new URL('./src/garde-demarrage.js', import.meta.url), 'utf8'))
	.digest('base64')}`;

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
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
	},
};

export default config;
