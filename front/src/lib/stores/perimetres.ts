/**
 * Arborescence des périmètres — chargée une fois, partagée partout.
 *
 * Le front portait sa propre table de libellés (`PERIMETRE_LABELS` dans
 * `lib/utils.ts`), arrêtée à `bat:4` quand l'API allait jusqu'à `bat:9`. Elle
 * vient maintenant de la base, où l'administration l'édite.
 *
 * Ce module est le SEUL à connaître l'API des périmètres. Le rendu, lui, vit dans
 * `lib/perimetres.ts`, qui n'importe rien : c'est ce qui permet à
 * `perimetreLabel()` de rester synchrone au milieu d'un gabarit.
 */
import { writable } from 'svelte/store';
import { perimetres as perimetresApi } from '#lib/api/index.ts';
import { definirPerimetres, type Perimetre } from '#lib/perimetres/index.ts';

export const perimetresStore = writable<Perimetre[]>([]);

let charge = false;
let enCours: Promise<void> | null = null;

/**
 * Charge l'arborescence si elle ne l'est pas déjà.
 *
 * Les appels concurrents partagent la même promesse : la mise en page et une page
 * qui en a besoin peuvent l'appeler en même temps sans provoquer deux requêtes.
 *
 * Un échec n'est pas propagé : sans arborescence, `perimetreLabel()` retombe sur
 * son libellé calculé et l'application reste utilisable. C'est un affichage, pas
 * une décision d'accès — celles-ci se prennent côté serveur, où l'arbre illisible
 * refuse au lieu d'élargir.
 */
export async function chargerPerimetres(force = false): Promise<void> {
	if (charge && !force) return;
	if (enCours && !force) return enCours;

	enCours = (async () => {
		try {
			const liste = await perimetresApi.list();
			definirPerimetres(liste);
			perimetresStore.set(liste);
			charge = true;
		} catch {
			//  Silencieux volontairement : voir le docstring.
		} finally {
			enCours = null;
		}
	})();
	return enCours;
}

/** À appeler après toute écriture depuis l'écran d'administration. */
export async function rechargerPerimetres(): Promise<void> {
	return chargerPerimetres(true);
}
