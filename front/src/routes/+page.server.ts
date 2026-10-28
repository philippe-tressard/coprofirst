import { redirect } from '@sveltejs/kit';

import { PARAMETRE_SOURCE } from '#lib/arrivees.ts';
import { CHEMIN_CONNEXION } from '#lib/redirection.ts';

/**
 * Redirection serveur selon l'état de la session.
 * Évite les 2 appels API inutiles (auth.me + tryRefresh) côté client
 * quand l'utilisateur n'est clairement pas connecté.
 */
export const load = ({ cookies, url }) => {
	if (!cookies.get('access_token') && !cookies.get('refresh_token')) {
		//  La racine n'est pas une destination : elle ne fait que trier. Rien à
		//  conserver, donc, mais l'adresse se lit à la source (#1083) — sauf
		//  l'étiquette d'une notification (#1634) : `(app)` la lit, puis renvoie
		//  à la connexion. Perdue ici, l'arrivée par un lien vers l'accueil ne
		//  se compterait jamais.
		const etiquette = url.searchParams.has(PARAMETRE_SOURCE);
		throw redirect(302, etiquette ? `/tableau-de-bord${url.search}` : CHEMIN_CONNEXION);
	}
	// Cookies présents → le client gère la vérification et redirige vers le tableau de bord
	return {};
};
