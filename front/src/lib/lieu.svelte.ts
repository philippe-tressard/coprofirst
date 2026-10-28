import type { ReadonlyURL } from '$app/state';
import type { Readable } from 'svelte/store';
import { page } from '$app/state';

/**
 * Le lieu courant (`url`, `params`) pour un composant au mode historique
 * (`$:`), où `page` de `$app/state` ne se suit pas (#2205, lot 1).
 *
 * Un `$:` ne se réexécute que pour les variables qu'il nomme et qui peuvent
 * changer ; `page`, import immuable, n'en fait pas partie — la navigation
 * laissait la valeur périmée, sans erreur (ESLint
 * `svelte/no-immutable-reactive-statements` l'a relevé). Ce store fait entrer
 * `page` dans le graphe : `$: id = Number($lieu.params.id)`.
 *
 * Hors `$:` (fonction, gestionnaire, gabarit), `page` se lit directement.
 * Ce pont tombe avec le dernier `$:` qui s'en sert.
 */
export interface Lieu {
	url: ReadonlyURL;
	params: Record<string, string | undefined>;
}

const instantane = (): Lieu => ({ url: page.url, params: page.params });

export const lieu: Readable<Lieu> = {
	subscribe(abonne) {
		abonne(instantane());
		return $effect.root(() => {
			$effect.pre(() => abonne(instantane()));
		});
	},
};
