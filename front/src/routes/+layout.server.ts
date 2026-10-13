import { lireConfigServeur } from '$lib/server/config-site';

/**
 * Pré-charge la configuration du site côté serveur (SSR).
 * Les données sont sérialisées dans le HTML → zéro requête réseau côté client au premier rendu.
 * En développement local sans PUBLIC_API_URL, on retourne {} et le client prend le relais.
 */
export const load = async ({ fetch, setHeaders }) => {
	const siteConfig = await lireConfigServeur(fetch);
	//  La démo publique ne s'indexe pas (#1906) : `X-Robots-Tag` couvre aussi ce que
	//  la balise `robots` du layout ne voit pas, et rien n'est servi à part pour elle.
	if (siteConfig['mode_demo'] === '1') setHeaders({ 'x-robots-tag': 'noindex, nofollow' });
	return { siteConfig };
};
