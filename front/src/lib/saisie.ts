import Saisie from '#lib/components/Saisie.svelte';
import { modaleImperative } from '#lib/modale-imperative.ts';

/**
 * **Demander un texte**, dans la charte du site. Rend la saisie, ou `null` si
 * l'on renonce.
 *
 * ```ts
 * const motif = await demander({
 * 	titre: 'Signaler au conseil syndical',
 * 	message: 'Le motif sera transmis au conseil syndical.',
 * 	libelle: 'Motif du signalement',
 * });
 * if (motif === null) return;
 * ```
 *
 * ## Pourquoi (12/09/2026)
 *
 * Deux gestes du site appelaient `prompt()` — la boîte NATIVE — avec **la même
 * phrase, au caractère près**, dans deux fichiers : `PageCommunaute` et
 * `sondages/[id]`. Les défauts de la boîte native sont ceux que `confirmer()` a
 * retirés le 29/08/2026, plus un : son champ d'une ligne ne dit pas ce qu'on
 * attend, alors que le texte saisi part au conseil syndical.
 *
 * ⚠️ La valeur rendue est **élaguée** (`trim()`), et une réponse vide est
 * refusée par le formulaire tant que `requis` vaut `true` : les deux appelants
 * d'origine écrivaient ce contrôle chacun de son côté, juste après le `prompt()`.
 *
 * ⚠️ `null` signifie **renoncé**, et c'est distinct d'une chaîne vide. Les deux
 * copies natives testaient `motif === null` pour sortir sans rien dire : cette
 * distinction est conservée.
 */
export function demander(options: {
	titre: string;
	message: string;
	libelle: string;
	placeholder?: string;
	libelleValider?: string;
	libelleAnnuler?: string;
	requis?: boolean;
}): Promise<string | null> {
	//  Sans fenêtre (SSR), on renonce : rendre une chaîne enverrait au serveur un
	//  texte que personne n'a écrit.
	return modaleImperative<string | null>(Saisie, { ...options }, null);
}
