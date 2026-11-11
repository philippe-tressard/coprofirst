/**
 * Le TRACÉ des pictogrammes du site (Lucide, `icones-svg.json`) : les attributs du
 * `<svg>` qu'`Icon.svelte` pose autour de chaque tracé. L'app iOS dessine ses
 * pictogrammes avec les mêmes : le trait suit le site.
 */

//  🔒 Table PUBLIÉE aux clients (`tables-clients.json`, #2634) — littérale ; la retirer
//  ou en changer la forme s'annonce (`npm run lint:tables-clients`).
export const ATTRIBUTS_TRACE = {
	viewBox: '0 0 24 24',
	fill: 'none',
	'stroke-width': '1.5',
	'stroke-linecap': 'round',
	'stroke-linejoin': 'round',
} as const;
