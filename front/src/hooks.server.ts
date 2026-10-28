import type { Handle } from '@sveltejs/kit/hooks';
import garde from './garde-demarrage.js?raw';

//  Le garde de démarrage (#1993) prend la place de son repère dans `app.html` :
//  premier script de la page, avant les feuilles de style. Injecté TEL QUEL — la
//  CSP l'admet par le condensat de ce même fichier, calculé dans `vite.config.ts`.
const REPERE_GARDE = /<!-- garde-demarrage .*?-->/;
//  Le repère est un COMMENTAIRE : SvelteKit compte ceux de la page avant et après
//  `transformPageChunk` et avertit (`transform_page_chunk_comments`) quand le
//  remplacement en retire un — ce qui peut défaire l'hydratation. Le remplacement
//  en garde donc un, compact, devant le script.
const SCRIPT_GARDE = `<!-- garde-demarrage --><script>${garde}</script>`;

export const handle: Handle = async ({ event, resolve }) => {
	//  L'authentification est portée par des cookies `HttpOnly` que ce hook
	//  n'inspecte pas : il laisse passer, et c'est voulu.
	//
	//  🔴 Il a longtemps affirmé que « la protection des routes se fait dans
	//  +page.server.ts de chaque section ». C'était FAUX : un seul fichier en
	//  porte une, `routes/+page.server.ts` — la racine, qui trie —, et elle n'y
	//  sert qu'à éviter deux appels d'API à un visiteur manifestement déconnecté.
	//  Celle de `prestataires/` est partie (#1845) : elle ne protégeait rien, et
	//  son existence faisait demander `__data.json` à chaque arrivée sur l'écran.
	//
	//  La protection réelle est ailleurs, et à trois niveaux :
	//    • `(app)/+layout.svelte` — la garde centrale, qui charge l'utilisateur
	//      et renvoie à la mire en conservant la page demandée ;
	//    • les gardes d'écran, qui attendent `$authResolue` avant de refuser
	//      sur un rôle (`check-gardes-auth.mjs`) ;
	//    • **l'API**, seule à décider pour de bon : un écran masqué n'est pas
	//      un accès refusé (`standards/03` §1).
	//
	//  ⚠️ Un commentaire qui décrit une protection inexistante est pire qu'un
	//  silence : il se lit comme une garantie (#1083, 22/09/2026).
	const reponse = await resolve(event, {
		transformPageChunk: ({ html }) => html.replace(REPERE_GARDE, () => SCRIPT_GARDE),
	});
	return sansCopieConservee(reponse);
};

/**
 *  Une page HTML ne se garde pas dans le navigateur (24/10/2026).
 *
 *  Les pages partaient sans `Cache-Control` : le navigateur était libre d'en
 *  garder une copie et de la ressortir sans redemander au serveur — à la
 *  restauration d'un onglet, à l'historique. Une tablette a ainsi réaffiché un
 *  matin `/tableau-de-bord` dans sa version du 06/09, consultée à jour la
 *  veille au soir : page brute, ses feuilles et son code aux noms hachés
 *  n'existant plus. `no-store` impose de redemander la page à chaque fois ; ce
 *  n'est pas un coût, rien ne la revalidait (ni `ETag` ni `Last-Modified`). Et
 *  une page authentifiée n'a rien à faire sur le disque d'un appareil partagé.
 *
 *  Seulement le HTML que rend SvelteKit : les fichiers `/_app/immutable/…` sont
 *  servis avant ce hook, avec leur cache d'un an — leur nom change à chaque
 *  build. Un en-tête posé par une route n'est jamais écrasé.
 *  🔒 `e2e/garde-demarrage.spec.ts`.
 */
function sansCopieConservee(reponse: Response): Response {
	const type = reponse.headers.get('content-type') ?? '';
	if (type.startsWith('text/html') && !reponse.headers.has('cache-control'))
		reponse.headers.set('cache-control', 'no-store');
	return reponse;
}
