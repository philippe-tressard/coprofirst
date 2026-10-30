import { lireConfigServeur } from '#lib/server/config-site.ts';

/**
 * Pré-charge la configuration du site côté serveur (SSR).
 * Les données sont sérialisées dans le HTML → zéro requête réseau côté client au premier rendu.
 * En développement local sans PUBLIC_API_URL, on retourne {} et le client prend le relais.
 */
export const load = async ({ url, setHeaders, locals }) => {
	//  L'hôte de la PAGE désigne la copropriété (`lireConfigServeur`, #2053).
	//  Déjà lue par `hooks.server.ts` pour une page (la palette, #2379) : pas deux fois.
	const siteConfig = locals.siteConfig ?? (await lireConfigServeur(url.host));
	//  La démo publique ne s'indexe pas (#1906) : `X-Robots-Tag` couvre aussi ce que
	//  la balise `robots` du layout ne voit pas, et rien n'est servi à part pour elle.
	if (siteConfig['mode_demo'] === '1') setHeaders({ 'x-robots-tag': 'noindex, nofollow' });
	return { siteConfig };
};
