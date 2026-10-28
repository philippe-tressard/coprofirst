import { defineParams } from '@sveltejs/kit/params';

/**
 * Les matcheurs de segment de route (`[alias=alias]`) — un seul fichier depuis
 * SvelteKit 3, qui ne lit plus `src/params/<nom>.ts`.
 *
 * `alias` : l'alias d'une copropriété dans un chemin de l'hôte commun :
 * `/75015-les-tilleuls` (#1894). Même forme que côté serveur
 * (`installation_commune/alias.MOTIF_ALIAS`) : cinq chiffres puis au moins un
 * mot — aucun chemin du site ne commence ainsi.
 */
export const params = defineParams({
	alias: (param) => (/^\d{5}(-[a-z0-9]+)+$/.test(param) ? param : undefined),
});
