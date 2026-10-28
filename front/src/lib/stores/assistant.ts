/**
 *  L'assistant IA est-il disponible pour les formulaires ? — lu UNE fois,
 *  partagé par toutes les sections Description ouvertes (#985).
 *
 *  Même forme que `stores/perimetres` : les appels concurrents partagent la
 *  même promesse, et un échec n'est pas propagé — sans réponse, l'icône ✨ ne
 *  s'affiche pas, et le formulaire reste utilisable. C'est un confort
 *  d'affichage, pas une décision d'accès : celle-ci vit côté serveur.
 *
 *  🔴 Ne s'appelle QUE pour le conseil syndical et l'administration : la route
 *  refuse aux autres, et interroger pour recevoir un 403 serait une requête
 *  par formulaire ouvert, pour rien. L'appelant vérifie `$isCS` avant.
 */
import { writable } from 'svelte/store';
import { assistant as assistantApi } from '#lib/api/index.ts';

export interface DisponibiliteAssistant {
	description: boolean;
}

/** `null` tant qu'on n'a pas demandé — ce n'est pas « indisponible ». */
export const assistantStore = writable<DisponibiliteAssistant | null>(null);

let enCours: Promise<void> | null = null;

export async function chargerAssistant(force = false): Promise<void> {
	if (enCours && !force) return enCours;
	enCours = (async () => {
		try {
			assistantStore.set(await assistantApi.disponible());
		} catch {
			//  Sans réponse, rien ne s'affiche : voir l'en-tête.
			assistantStore.set({ description: false });
		}
	})();
	return enCours;
}

/** Après un enregistrement de l'administration : la disponibilité a pu changer. */
export function oublierAssistant(): void {
	enCours = null;
	assistantStore.set(null);
}
