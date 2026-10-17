import type { Handle } from '@sveltejs/kit';
import garde from './garde-demarrage.js?raw';

//  Le garde de démarrage (#1993) prend la place de son repère dans `app.html` :
//  premier script de la page, avant les feuilles de style. Injecté TEL QUEL — la
//  CSP l'admet par le condensat de ce même fichier, calculé dans `svelte.config.js`.
const REPERE_GARDE = /<!-- garde-demarrage .*?-->/;
const SCRIPT_GARDE = `<script>${garde}</script>`;

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
	return resolve(event, {
		transformPageChunk: ({ html }) => html.replace(REPERE_GARDE, () => SCRIPT_GARDE),
	});
};
