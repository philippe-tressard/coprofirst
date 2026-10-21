import { redirect } from '@sveltejs/kit';
import { adresseActuelleAdmin } from '$lib/admin-adresses';

/**
 * Une ancienne clé d'onglet (`?onglet=import_tc`, `?onglet=site`) part en 308
 * vers l'onglet qui la sert depuis le rangement par niveau (#2062) — les
 * courriels déjà envoyés et les favoris continuent de mener au bon écran.
 */
export const load = ({ url }) => {
	const cible = adresseActuelleAdmin(url);
	if (cible) throw redirect(308, cible);
};
