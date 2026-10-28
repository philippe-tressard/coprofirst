import { defineEnvVars } from '@sveltejs/kit/env';

/**
 * Les variables d'environnement du front, DÉCLARÉES (SvelteKit 3, #2205).
 *
 * `$env/dynamic/public` exposait toute variable préfixée `PUBLIC_` ; son
 * successeur `$app/env/public` n'expose que ce qui est écrit ici — une variable
 * absente de ce fichier y vaut `undefined`, sans un mot. Les deux sont lues à
 * l'EXÉCUTION (jamais `static`) : une image construite par la CI sert les deux
 * nœuds, et c'est l'environnement du conteneur qui les distingue (#1758).
 *
 * Aucune n'est obligatoire : sans `schema`, SvelteKit exigerait qu'elles soient
 * posées au build, où elles ne le sont pas. Le schéma-fonction rend la valeur
 * telle quelle, `undefined` compris.
 */
const facultative = (valeur: string | undefined) => valeur;

export const variables = defineEnvVars({
	/** L'adresse interne de l'API (`api:8000`) — SERVEUR seulement, jamais envoyée au navigateur. */
	PUBLIC_API_URL: { schema: facultative },
	/** Le nœud qui répond (rpi1 / rpi2), montré dans le pied de page. */
	PUBLIC_INSTANCE_ID: { public: true, schema: facultative },
});
