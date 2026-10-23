#!/usr/bin/env node
/**
 *  Un TEXTE d'avertissement s'écrit en `--color-warning-texte` (#2167, 23/10/2026).
 *
 *  La charte le dit depuis le 27/09/2026 (arbitrage n° 59, `ux-patterns` §18) :
 *  `--color-warning` fait 3,29 sur son fond d'avertissement et 3,62 sur blanc,
 *  sous le seuil AA de 4,5 — il sert au cadre, à l'icône, à l'aplat, jamais au
 *  texte. `lint:charte-valeurs` refuse les valeurs EN DUR, et laissait donc
 *  passer le jeton lui-même : l'audit `apple-design` en a trouvé quatre, dans un
 *  toast, une modale, une section de formulaire et le chiffre d'un KPI.
 *
 *  Ce qu'il refuse : la propriété `color` à `var(--color-warning)`, dans les
 *  composants et les feuilles. `border-color`, `background` et les dérivés
 *  (`-texte`, `-fond`, `-bordure`) ne sont pas concernés.
 *
 *  Les PICTOGRAMMES ne sont pas du texte (3:1 leur suffit) : ils se déclarent
 *  ci-dessous, avec leur raison, et l'exception échoue si elle cesse de servir.
 *
 *  Lancer : node scripts/check-texte-avertissement.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

const TEXTE_AMBRE = /(?<![-\w])color\s*:\s*var\(--color-warning\)/;

process.exitCode = controler({
	extensions: ['.svelte', '.css'],
	exceptions: {
		'src/lib/components/NoteEtoiles.svelte':
			'les ÉTOILES de la note, des pictogrammes — le chiffre reste en couleur de texte (n° 59, proposition B)',
		'src/lib/components/SyntheseChronologie.svelte':
			'la PUCE d’un jalon en alerte, un pictogramme du fil — le libellé reste en couleur de texte',
	},
	fautes: lignesPortant(TEXTE_AMBRE),
	cas: [
		['.a { color: var(--color-warning); }', 1],
		['.a {\n  color:var(--color-warning);\n}', 1],
		['.a { color: var(--color-warning-texte); }', 0],
		['.a { border-color: var(--color-warning); }', 0],
		['.a { background-color: var(--color-warning); }', 0],
		['.a { border-left: 3px solid var(--color-warning); }', 0],
		['/* color: var(--color-warning); */', 0],
	],
	ok: 'Texte d’avertissement : aucun en --color-warning',
	ko: 'texte(s) écrit(s) en --color-warning (contraste sous 4,5:1)',
	conseil:
		'Écrire `color: var(--color-warning-texte)` ; un pictogramme se déclare dans les exceptions.',
});
