#!/usr/bin/env node
/**
 *  Un test qui mesure le défilement de la page est joué sous WebKit : il porte
 *  l'étiquette `@mise-en-page` à la fin de son titre (#2640, 11/11/2026).
 *
 *  ## Le défaut que ce contrôle retire
 *
 *  La CI ne jouait que Chromium. Le 10/11, la liste des heures de la sauvegarde
 *  faisait 22 px sous Safari contre 37 pour son voisin (#2639) : le spec passait
 *  sous Chromium, échouait sous WebKit, et c'est l'auteur qui l'a vu à l'écran.
 *  Les profils `webkit-bureau` et `webkit-mobile` ne jouent que les tests
 *  étiquetés (`e2e/mise-en-page.ts`) : un test de mise en page neuf qui
 *  oublierait l'étiquette ne serait joué que sous Chromium, sans un mot.
 *
 *  ## Ce qu'il refuse
 *
 *  Un appel à `attendreSansDefilementHorizontal` (`e2e/defilement.ts`, la seule
 *  mesure du défilement de la page, `lint:defilement`) dans un test dont le
 *  titre ne finit pas par l'étiquette. Les autres mesures de mise en page —
 *  hauteurs, cibles tactiles — s'étiquettent à la main : elles n'ont pas d'aide
 *  unique à reconnaître.
 *
 *  Lancer : node scripts/check-e2e-mise-en-page.mjs [--selftest]
 */
import { neutraliserCommentaires } from './lib-commentaires.mjs';
import { controler } from './lib-source-unique.mjs';

const ETIQUETTE = '@mise-en-page';
const MESURE = /attendreSansDefilementHorizontal\(/g;
const DEBUT_DE_TEST = /(?<![\w.])test\(\s*/g;

/** Le titre littéral qui commence à `i` (guillemet, apostrophe ou accent grave), sans ses délimiteurs. */
function titreA(texte, i) {
	const q = texte[i];
	if (!`'"\``.includes(q)) return null;
	for (let j = i + 1; j < texte.length; j++) {
		if (texte[j] === '\\') j++;
		else if (texte[j] === q) return texte.slice(i + 1, j);
	}
	return null;
}

/** Les lignes des mesures dont le test englobant n'est pas étiqueté. PURE. */
export function mesuresNonEtiquetees(source) {
	const texte = neutraliserCommentaires(source);
	const fautes = [];
	for (const m of texte.matchAll(MESURE)) {
		const avant = texte.slice(0, m.index);
		//  La définition et l'import de l'aide ne sont pas des mesures.
		if (/(function\s+|import\s*\{[^}]*|import\s+type\s*\{[^}]*)$/.test(avant)) continue;
		const debuts = [...avant.matchAll(DEBUT_DE_TEST)];
		const dernier = debuts.at(-1);
		const titre = dernier ? titreA(texte, dernier.index + dernier[0].length) : null;
		if (titre?.trimEnd().endsWith(ETIQUETTE)) continue;
		fautes.push(avant.split('\n').length);
	}
	return fautes;
}

process.exit(
	controler({
		racine: 'e2e',
		extensions: ['.spec.ts'],
		temoin: null,
		fautes: mesuresNonEtiquetees,
		cas: [
			//  🔴 Le cas fautif : la mesure dans un test sans étiquette.
			[
				"test('la page tient', async ({ page }) => {\n\tawait attendreSansDefilementHorizontal(page);\n});",
				1,
			],
			//  La forme voulue, sur une ligne puis coupée par Prettier.
			[
				"test('la page tient @mise-en-page', async ({ page }) => {\n\tawait attendreSansDefilementHorizontal(page);\n});",
				0,
			],
			[
				"test(\n\t'un long titre @mise-en-page',\n\tasync ({ page }) => {\n\t\tawait attendreSansDefilementHorizontal(page);\n\t},\n);",
				0,
			],
			//  Un titre gabarit, dans une boucle.
			[
				'\ttest(`${chemin} : sans débord @mise-en-page`, async ({ page }) => {\n\t\tawait attendreSansDefilementHorizontal(page);',
				0,
			],
			[
				'\ttest(`${chemin} : sans débord`, async ({ page }) => {\n\t\tawait attendreSansDefilementHorizontal(page);',
				1,
			],
			//  L'étiquette au milieu du titre n'est pas lue comme telle ici.
			[
				"test('@mise-en-page au début', async ({ page }) => {\n\tawait attendreSansDefilementHorizontal(page);",
				1,
			],
			//  Un `describe` étiqueté ne suffit pas : c'est le test qui compte.
			[
				"test.describe('x @mise-en-page', () => {\n\ttest('y', async ({ page }) => {\n\t\tawait attendreSansDefilementHorizontal(page);",
				1,
			],
			//  Une mesure hors de tout test (aide locale) : refusée, elle ne serait jamais étiquetée.
			['async function verifier(page) {\n\tawait attendreSansDefilementHorizontal(page);\n}', 1],
			//  L'import et un commentaire ne mesurent rien.
			["import { attendreSansDefilementHorizontal } from './defilement';", 0],
			["test('x', async () => {\n\t// attendreSansDefilementHorizontal(page) plus tard", 0],
		],
		ok: 'Tests de mise en page : chaque mesure du défilement est étiquetée, donc jouée sous WebKit',
		ko: 'mesure(s) du défilement dans un test sans l’étiquette @mise-en-page',
		conseil:
			'Finir le titre du test par « @mise-en-page » (`e2e/mise-en-page.ts`) : il sera joué aussi sous WebKit (profils webkit-bureau et webkit-mobile).',
	}),
);
