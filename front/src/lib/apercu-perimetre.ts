/**
 * **Le lieu d'une SAISIE, nommé par le serveur** — `POST /perimetres/libelle`
 * (#2633), par le mécanisme commun `#lib/apercu-serveur` (délai, réponse périmée
 * ignorée, dernier libellé gardé pendant l'attente et hors ligne).
 *
 * Un objet ENREGISTRÉ n'en a pas besoin : son lieu est servi avec lui
 * (`perimetre_libelle`, `perimetre_precise_libelle`, `perimetres_libelle`).
 */
import { derived } from 'svelte/store';
import { perimetres, type LibellePerimetre } from '#lib/api/index.ts';
import { apercuServi } from '#lib/apercu-serveur.ts';
import { perimetreEntree } from '#lib/perimetres/index.ts';

const servi = apercuServi<string[], LibellePerimetre>(
	(codes) => perimetres.libelle(codes),
	(codes) => JSON.stringify([...codes].sort()),
);

/** `$libellePerimetre(codes, place)` — le lieu en clair, MÊME par défaut ; `''`
 *  sans code, ou tant que le serveur n'a pas répondu une première fois. */
export const libellePerimetre = derived(
	servi.store,
	(lire) =>
		(codes: string[] | null | undefined, place: string): string =>
			codes?.length ? (lire(codes, place)?.libelle ?? '') : '',
);

/** `$entreeNommee(…)` — `perimetreEntree` (`#lib/perimetres/arbre`), le lieu hérité
 *  d'une Suite nommé par le serveur ; le gabarit la relit quand il répond. */
export const entreeNommee = derived(
	libellePerimetre,
	(nommer) =>
		(...args: Parameters<typeof perimetreEntree> extends [...infer A, unknown] ? A : never) =>
			perimetreEntree(...args, (codes) => nommer(codes, 'suite-perimetre-actuel')),
);
