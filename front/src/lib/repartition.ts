//  Les TEINTES des répartitions croisées du Suivi des affaires (#2043).
//
//  🔴 Une teinte suit l'ENTITÉ, jamais son rang : la catégorie « Panne » porte
//  la même série dans les deux graphiques et d'un jour à l'autre, quel que soit
//  le nombre de pannes. L'ordre des séries est celui des catégories du modèle
//  (`CategorieTicket`, la même liste que le serveur), huit au plus — palette
//  catégorielle validée daltonisme (skill dataviz) ; au-delà, la teinte neutre.
//
//  Les bâtiments, eux, se lisent en paliers de gris : ils sont un second axe, et
//  deux palettes catégorielles côte à côte se confondraient.

import type { TrancheRepartition } from '$lib/api';

/** Les catégories dans l'ordre des séries — celui de `CategorieTicket`. */
const ORDRE_SERIES = [
	'panne',
	'nuisance',
	'espaces_verts',
	'sinistre',
	'etude_travaux',
	'acces_accueil',
	'question',
	'entretien',
] as const;

/** Le nombre de paliers de gris que `BarresCroisees` sait peindre (`--palier-1`…`4`). */
const PALIERS = 4;

/** La teinte d'une tranche de catégorie : `s1`…`s8`, ou `autre`. */
export function teinteCategorie(cle: string): string {
	const i = (ORDRE_SERIES as readonly string[]).indexOf(cle);
	return i === -1 ? 'autre' : `s${i + 1}`;
}

/**  La teinte d'une tranche de bâtiment : la racine en premier palier, les
 *   bâtiments ensuite dans l'ordre servi, « Plusieurs bâtiments » hachurée. */
export function teinteBatiment(cle: string, ordre: readonly string[]): string {
	if (cle === 'plusieurs') return 'plusieurs';
	const i = ordre.indexOf(cle);
	return `p${Math.min(Math.max(i, 0), PALIERS - 1) + 1}`;
}

/** La légende d'un graphique : chaque tranche une fois, dans l'ordre où elles paraissent. */
export function legende(tranches: readonly TrancheRepartition[][]): TrancheRepartition[] {
	const vues = new Map<string, TrancheRepartition>();
	for (const t of tranches.flat()) if (!vues.has(t.cle)) vues.set(t.cle, t);
	return [...vues.values()];
}
