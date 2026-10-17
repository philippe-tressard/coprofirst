import type { ParamMatcher } from '@sveltejs/kit';

/**
 * L'alias d'une copropriété dans un chemin de l'hôte commun : `/75015-les-tilleuls`
 * (#1894). Même forme que côté serveur (`installation_commune/alias.MOTIF_ALIAS`) :
 * cinq chiffres puis au moins un mot — aucun chemin du site ne commence ainsi.
 */
export const match: ParamMatcher = (param) => /^\d{5}(-[a-z0-9]+)+$/.test(param);
