/**
 * **Rendre une longue liste par paquets** (#1840).
 *
 * Affaires rendait TOUTE sa liste d'un coup dès que `/api/tickets` répondait :
 * 96 cartes, +320 ms de rendu après l'arrivée des données à CPU ÷4 — la
 * puissance d'un téléphone moyen —, et un coût qui croît avec chaque affaire.
 *
 * Seul le RENDU est progressif : les filtres, la recherche et les compteurs
 * portent toujours sur la liste complète, en mémoire (`ux-patterns` §5 — le
 * compteur dit la liste filtrée, jamais la liste rendue). Les `PREMIERS`
 * éléments se rendent d'emblée ; un témoin posé après le dernier rendu en
 * ajoute un `PAQUET` dès qu'il approche de l'écran (`quandProche`).
 *
 * ⚠️ Un élément visé par un lien profond n'est peut-être pas encore rendu :
 * `aRendre` reçoit l'indice du dernier élément qu'il FAUT montrer (une carte
 * dépliée), et la limite s'étend jusqu'à lui.
 */

/** Les éléments rendus d'emblée : ce qui tient à l'écran, et une marge. */
export const PREMIERS = 20;
/** Les éléments ajoutés à chaque approche du bas. */
export const PAQUET = 40;
/** L'avance du témoin : le paquet suivant se rend avant qu'on atteigne le bas. */
const AVANCE = '0px 0px 800px 0px';

/** Combien d'éléments rendre sur `total` : `limite`, jamais moins qu'il ne faut
 *  pour montrer l'élément d'indice `requis` (−1 : aucun). PURE. */
export function aRendre(total: number, limite: number, requis = -1): number {
	return Math.min(total, Math.max(limite, requis + 1));
}

/**
 * Action Svelte : appelle `rappel` quand le nœud approche de l'écran.
 *
 * Un observateur ne se redéclenche pas tant que sa cible reste visible : le
 * témoin se pose donc dans un `{#key}` sur le nombre rendu, et chaque paquet
 * en monte un neuf — qui, s'il est encore proche, en demande un autre.
 */
export function quandProche(noeud: HTMLElement, rappel: () => void) {
	//  Sans observateur (rendu serveur, très vieux navigateur) : tout se rend.
	if (typeof IntersectionObserver === 'undefined') {
		rappel();
		return {};
	}
	let appeler = rappel;
	const vues = new IntersectionObserver(
		(entrees) => {
			if (entrees.some((e) => e.isIntersecting)) appeler();
		},
		{ rootMargin: AVANCE },
	);
	vues.observe(noeud);
	return {
		update(suivant: () => void) {
			appeler = suivant;
		},
		destroy() {
			vues.disconnect();
		},
	};
}
