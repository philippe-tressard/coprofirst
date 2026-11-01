/**
 * Les équipements — chargés une fois, partagés partout (#2442).
 *
 * Le seul module qui connaît `GET /equipements`. Le rendu vit dans
 * `#lib/equipements`, qui n'importe rien : c'est ce qui garde `equipLabel()`
 * synchrone au milieu d'un gabarit. Même motif que `stores/perimetres.ts`.
 */
import { derived, writable } from 'svelte/store';
import { equipements as equipementsApi } from '#lib/api/index.ts';
import {
	classeEquipement,
	definirEquipements,
	equipLabel,
	type Equipement,
} from '#lib/equipements.ts';

export const equipementsStore = writable<Equipement[]>([]);

/**  `$libelleEquipement(code)` dans un gabarit : le libellé, REPEINT quand la liste
 *   arrive. `equipLabel` seul lit un cache de module que Svelte ne surveille pas —
 *   un écran rendu avant la liste garderait le code brut (le défaut de #947 sur
 *   les périmètres). Le store dérivé est la dépendance qui manquait. */
export const libelleEquipement = derived(equipementsStore, () => equipLabel);

/**  `$classeDEquipement(code)` : la marque de gouttière, repeinte de même. */
export const classeDEquipement = derived(equipementsStore, () => classeEquipement);

let charge = false;
let enCours: Promise<void> | null = null;

/**
 * Charge la liste si elle ne l'est pas déjà ; les appels concurrents partagent
 * la même promesse.
 *
 * Un échec n'est pas propagé : sans liste, `equipLabel()` rend le code brut et
 * l'écran reste utilisable. C'est un affichage — ce qui s'accepte à la saisie,
 * le serveur le décide (`utils/equipements.exiger_equipement`).
 */
export async function chargerEquipements(force = false): Promise<void> {
	if (charge && !force) return;
	if (enCours && !force) return enCours;

	enCours = (async () => {
		try {
			const liste = await equipementsApi.list();
			definirEquipements(liste);
			equipementsStore.set(liste);
			charge = true;
		} catch {
			//  Silencieux volontairement : voir le docstring.
		} finally {
			enCours = null;
		}
	})();
	return enCours;
}

/**
 * Relit la liste — l'écran d'administration, au montage et après chaque écriture.
 *
 * ⚠️ Lui PROPAGE son échec : un écran d'administration qui afficherait « aucun
 * équipement » faute de les avoir lus inviterait à recréer ce qui existe (#816).
 */
export async function rechargerEquipements(): Promise<Equipement[]> {
	const liste = await equipementsApi.list();
	definirEquipements(liste);
	equipementsStore.set(liste);
	charge = true;
	return liste;
}
