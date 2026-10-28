import { goto } from '$app/navigation';
import { toast } from '#lib/components/Toast.svelte';
import type { User } from '#lib/api/index.ts';

/**
 * **Fermer la Communauté à qui n'y a pas accès** — le dire, et renvoyer au
 * tableau de bord.
 *
 * Le MOTIF vient de l'API (`communaute_motif_refus`) : l'écran ne recalcule pas
 * la règle, il choisit le geste. Ce refus était écrit deux fois — la rubrique
 * (`PageCommunaute`) et la fiche d'un sondage — et celle-ci le décidait dans son
 * `onMount`, donc avant de connaître l'utilisateur : un gestionnaire qui ouvrait
 * le lien d'un sondage n'était jamais renvoyé (#1486, 30/09/2026).
 */
export function refuserLaCommunaute(user: User | null): void {
	toast(
		'error',
		user?.communaute_motif_refus ?? "La rubrique Communauté n'est pas accessible à votre profil.",
	);
	goto('/tableau-de-bord', { replaceState: true });
}
