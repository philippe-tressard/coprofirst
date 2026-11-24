/**
 *  Les valeurs TRANCHÉES de la charte — interdites sans plafond, partout.
 *
 *  Extrait de `check-charte-valeurs.mjs` le 24/11/2026 (#2946) : le contrôle
 *  passait 500 lignes en apprenant à lire `rgb()` et `hsl()`. Cette notion-ci est
 *  entière et sans dépendance — une table de remplacements et la fonction qui les
 *  relève ; le contrôle l'importe et la réexporte.
 */
/**
 *  ## Ce qui est INTERDIT, sans plafond (arbitré le 27/09/2026, sur maquette)
 *
 *  Le plafond tolère une dette ; ces valeurs-ci ont été TRANCHÉES, elles ne se
 *  tolèrent plus nulle part — ni dans un composant, ni dans `src/styles/`.
 *
 *  - une taille hors échelle se range au cran SUPÉRIEUR : aucun texte ne
 *    rétrécit en se normalisant (lisibilité au pouce) ;
 *  - une couleur d'ÉTAT vient de la charte, jamais de la palette de Tailwind —
 *    le bloc des urgences de l'accueil portait deux rouges côte à côte ;
 *  - le texte sur un fond d'avertissement prend `--color-warning-texte` :
 *    `--color-warning` (3,62 sur blanc) ne sert pas au texte.
 *
 *  Le tableau dit la valeur de REMPLACEMENT : le message d'échec la donne.
 *
 *  ⚠️ Les palettes CATÉGORIELLES ne sont pas des états et restent hors de ce
 *  contrôle : la teinte d'un type du fil (`#lib/flux`), d'un périmètre
 *  (`#lib/perimetres/teinte`), d'une colonne de kanban, d'une nature
 *  (`--nature-fort`), l'orange de l'urgence, `.badge-yellow` (#495).
 */
//  Sous 1 rem, la valeur suffit à dire le cran ; au-dessus, c'est la NATURE de
//  l'élément (titre, pictogramme, chiffre) qui le choisit — le refus du plafond
//  à zéro donne alors l'échelle à lire dans `socle.css` (#2313).
export const TAILLES_HORS_ECHELLE = {
	0.6: '--fs-3xs',
	0.62: '--fs-3xs',
	0.66: '--fs-2xs',
	0.68: '--fs-2xs',
	0.7: '--fs-2xs',
	0.74: '--fs-xs',
	0.76: '--fs-sm',
	0.78: '--fs-sm',
	0.82: '--fs-md',
	0.83: '--fs-md',
	0.84: '--fs-md',
	0.86: '--fs-base',
	0.875: '--fs-base',
	0.88: '--fs-base',
	0.92: '--fs-lg',
	0.975: '--fs-xl',
};

/**
 *  La DÉFINITION d'un jeton de palette catégorielle (`--fil-rouge: #b91c1c;`,
 *  #2174 S2) est la seule place où ces teintes s'écrivent : ce ne sont pas des
 *  états. Partout ailleurs, la même valeur reste refusée.
 */
const DEFINITION_CATEGORIELLE = /--(?:fil|teinte|kanban)-[\w-]+\s*:\s*#[0-9a-fA-F]{6}\s*;/g;

export const COULEURS_ETAT_ETRANGERES = {
	'#dc2626': '--color-danger',
	'#b91c1c': '--color-danger',
	'#991b1b': '--color-danger',
	'#7f1d1d': '--color-danger',
	'#ef4444': '--color-danger',
	'#fef2f2': '--color-danger-fond',
	'#fee2e2': '--color-danger-fond',
	'#fecaca': '--color-danger-bordure',
	'#16a34a': '--color-success',
	'#15803d': '--color-success',
	'#22c55e': '--color-success',
	'#166534': '--color-success',
	'#065f46': '--color-success',
	'#059669': '--color-success',
	'#10b981': '--color-success',
	'#f0fdf4': '--color-success-fond',
	'#dcfce7': '--color-success-fond',
	'#d1fae5': '--color-success-fond',
	'#ecfdf5': '--color-success-fond',
	'#bbf7d0': '--color-success-bordure',
	'#f59e0b': '--color-warning',
	'#d97706': '--color-warning',
	'#fbbf24': '--color-warning',
	'#b45309': '--color-warning',
	'#92400e': '--color-warning-texte',
	'#78350f': '--color-warning-texte',
	'#fffbeb': '--color-warning-fond',
	'#fef3c7': '--color-warning-fond',
	'#fde68a': '--color-warning-bordure',
	'#fcd34d': '--color-warning-bordure',
};

/** Les mêmes rouges, verts et ambres écrits en `rgb()` / `rgba()`. */
const RGB_ETAT =
	/rgba?\(\s*(220\s*,\s*38\s*,\s*38|239\s*,\s*68\s*,\s*68|22\s*,\s*163\s*,\s*74|245\s*,\s*158\s*,\s*11|217\s*,\s*119\s*,\s*6)\b/g;

/**
 *  Ce qui est interdit dans une source, commentaires retirés — le HISTORIQUE
 *  d'une couleur (« elle était `#f59e0b` ») reste lisible en commentaire.
 *  Les couleurs sont cherchées dans TOUT le fichier : une chaîne de style
 *  composée en JavaScript rend autant qu'un `<style>`.
 */
export function interditsDe(source) {
	const code = source
		.replace(DEFINITION_CATEGORIELLE, '')
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/\/\*[\s\S]*?\*\//g, '')
		.replace(/(^|[^:'"])\/\/.*$/gm, '$1');
	const trouves = [];
	for (const m of code.matchAll(/font-size\s*:\s*([0-9]*\.?[0-9]+)rem/g)) {
		const jeton = TAILLES_HORS_ECHELLE[parseFloat(m[1])];
		if (jeton) trouves.push([`${m[1]}rem`, `var(${jeton})`]);
	}
	for (const m of code.matchAll(/#[0-9a-fA-F]{6}\b/g)) {
		const jeton = COULEURS_ETAT_ETRANGERES[m[0].toLowerCase()];
		if (jeton) trouves.push([m[0], `var(${jeton})`]);
	}
	for (const m of code.matchAll(RGB_ETAT))
		trouves.push([m[0] + '…)', 'color-mix(… var(--color-…) …)']);
	return trouves;
}
