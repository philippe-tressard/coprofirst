import { request } from 'node:http';
import { PUBLIC_API_URL } from '$app/env/private';

/** Le temps laissé à l'API pour répondre au rendu serveur, avant de rendre `{}`. */
const DELAI_MS = 3000;

/**
 * La configuration du site, lue CÔTÉ SERVEUR (rendu SSR) — une seule écriture.
 *
 * Deux lecteurs : le layout racine, qui la sérialise dans la page (zéro requête
 * au premier rendu), et le manifeste de l'application installée, qui y lit le
 * nom de la résidence (#1725). Le second aurait recopié le premier.
 *
 * 🏢 **Pour l'hôte de la page, jamais pour « l'API »** (#2053). L'API résout la
 * copropriété par l'en-tête `Host` (spec multi-copropriétés §4.1) ; appelée par
 * son nom interne (`PUBLIC_API_URL`, `api:8000`), elle ne désignait la copropriété
 * que tant qu'elle était seule — à deux, elle répond 421, et la page partait
 * sans configuration. La requête porte donc l'hôte de la PAGE, celui que le
 * visiteur a demandé : il désignerait la même copropriété s'il appelait `/api`
 * lui-même, rien n'est élargi.
 *
 * `node:http` et non `fetch` : le `fetch` de Node ignore un `Host` posé à la main
 * (mesuré le 17/10/2026, il envoie celui de l'URL).
 *
 * Sans `PUBLIC_API_URL` (poste de développement) ou sans réponse de l'API, rend
 * `{}` : le client prend le relais, et le manifeste se replie sur le nom neutre.
 */
export async function lireConfigServeur(hote: string): Promise<Record<string, string>> {
	const apiBase = PUBLIC_API_URL;
	if (!apiBase || !hote) return {};
	try {
		return await lireJson(new URL(`${apiBase}/config`), hote);
	} catch {
		/* réseau indisponible : le client chargera la config */
		return {};
	}
}

function lireJson(adresse: URL, hote: string): Promise<Record<string, string>> {
	return new Promise((resoudre, rejeter) => {
		const requete = request(
			adresse,
			{ headers: { host: hote, accept: 'application/json' }, timeout: DELAI_MS },
			(reponse) => {
				let corps = '';
				reponse.setEncoding('utf8');
				reponse.on('data', (morceau: string) => (corps += morceau));
				reponse.on('end', () => {
					if (reponse.statusCode !== 200) return resoudre({});
					try {
						resoudre(JSON.parse(corps));
					} catch (e) {
						rejeter(e);
					}
				});
			},
		);
		requete.on('timeout', () => requete.destroy(new Error('délai dépassé')));
		requete.on('error', rejeter);
		requete.end();
	});
}
