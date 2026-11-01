#!/usr/bin/env node
/**
 *  « La page ne défile pas en largeur » se mesure par `e2e/defilement.ts`, et
 *  nulle part ailleurs (#2437, 01/11/2026).
 *
 *  ## Le défaut que ce contrôle retire
 *
 *  Trente specs écrivaient la mesure en ligne, de quatre façons :
 *  `scrollWidth > clientWidth` lu une fois, la même avec un pixel de tolérance
 *  (`squelette`), `scrollWidth <= clientWidth` dans une aide locale
 *  (`import-recherche`, `bilan-carnet`), et `scrollWidth <= 360` contre une
 *  largeur recopiée (`repondre-depuis-la-carte`). Toutes lisaient l'INSTANT —
 *  ce que `lint:e2e-lectures` refuse ailleurs — et aucune ne pouvait élargir le
 *  texte : le débordement d'Admin › Lots, que seules les polices de macOS et
 *  d'iOS révélaient, leur échappait à toutes.
 *
 *  ## Ce qu'il refuse
 *
 *  Une lecture de `scrollWidth` sur la page entière (`document.documentElement`,
 *  `document.body`, `scrollingElement`) hors de `e2e/defilement.ts`. La mesure
 *  d'un ÉLÉMENT (`el.scrollWidth - el.clientWidth` sur une rangée, une zone qui
 *  défile) pose une autre question et n'est pas concernée.
 *
 *  Lancer : node scripts/check-defilement.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

const SOURCE = 'e2e/defilement.ts';

/**  `document.documentElement.scrollWidth`, `document.body.scrollWidth`,
 *   `document.scrollingElement.scrollWidth` : la largeur de la page entière. */
const COPIE = /\bdocument\s*\.\s*(?:documentElement|body|scrollingElement!?)\s*\.\s*scrollWidth\b/;

process.exit(
	controler({
		racine: 'e2e',
		extensions: ['.ts'],
		temoin: SOURCE,
		fautes: lignesPortant(COPIE),
		cas: [
			['\t\t() => document.documentElement.scrollWidth > document.documentElement.clientWidth,', 1],
			['\t\tpage: document.documentElement.scrollWidth,', 1],
			['\t.poll(() => page.evaluate(() => document.body.scrollWidth))', 1],
			['\tconst l = document.scrollingElement!.scrollWidth;', 1],
			//  La forme voulue.
			['\tawait attendreSansDefilementHorizontal(page);', 0],
			//  La mesure d'un élément : une autre question.
			['\tconst debord = await tags.evaluate((el) => el.scrollWidth - el.clientWidth);', 0],
			//  Un commentaire qui cite la forme refusée.
			['\t//  on lisait document.documentElement.scrollWidth ici', 0],
		],
		ok: 'Défilement de la page : mesuré par `e2e/defilement.ts` seul',
		ko: 'mesure(s) du défilement de la page écrite(s) en ligne',
		conseil:
			'Employer `attendreSansDefilementHorizontal(page)` (`e2e/defilement.ts`), précédé de `elargirLeTexte(page)` pour un tableau ou une longue rangée.',
	}),
);
