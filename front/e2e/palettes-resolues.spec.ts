/**
 *  Les palettes RÉSOLUES que publie `tables-clients.json` sont celles que le site
 *  PEINT (#2754).
 *
 *  `palettesResolues` refait, une fois pour les apps, la cascade du site et ses
 *  `var(--…)` (`scripts/tables-clients.derivees.mjs`). Le self-test du générateur
 *  juge le calcul sur des cas posés ; ce spec juge le RÉSULTAT contre le navigateur :
 *  chaque jeton de chaque palette, au clair et au sombre, appliqué en `color` sur la
 *  page servie, doit rendre la couleur de la table. Une feuille qui change l'ordre de
 *  la cascade, un sélecteur que le greffon de build réécrit, un `color-mix` mal
 *  calculé : la table mentirait aux apps, et c'est ici que ça se voit.
 *
 *  L'écran de connexion est public et charge la feuille principale comme tout écran.
 */
import { readFileSync } from 'node:fs';
import { attendreHydratation, expect, test } from './aides';

type Jetons = Record<string, string>;
const PALETTES: Record<string, { clair: Jetons; sombre: Jetons }> = JSON.parse(
	readFileSync(new URL('../tables-clients.json', import.meta.url), 'utf8'),
).tables.palettesResolues.valeur;

/** `#rrggbb`, `rgba(…)`, `rgb(…)` ou `color(srgb …)` → [r, g, b, a] sur 0–255. */
function canaux(couleur: string): number[] {
	if (couleur.startsWith('#'))
		return [1, 3, 5].map((i) => parseInt(couleur.slice(i, i + 2), 16)).concat(1);
	const n = (couleur.match(/[\d.]+/g) ?? []).map(Number);
	if (couleur.startsWith('color(srgb')) return n.slice(0, 3).map((v) => v * 255).concat(n[3] ?? 1);
	return n.length === 3 ? n.concat(1) : n;
}

test('chaque jeton résolu est la couleur que le site rend, palette par palette', async ({
	page,
}) => {
	await page.emulateMedia({ colorScheme: 'light' });
	await page.goto('/auth/connexion');
	await attendreHydratation(page);

	const ecarts: string[] = [];
	let compares = 0;
	for (const [code, themes] of Object.entries(PALETTES))
		for (const [theme, jetons] of Object.entries(themes)) {
			const rendus = await page.evaluate(
				({ code, sombre, noms }) => {
					const racine = document.documentElement;
					if (code === 'seine') racine.removeAttribute('data-palette');
					else racine.setAttribute('data-palette', code);
					racine.setAttribute('data-theme', sombre ? 'dark' : 'light');
					const temoin = document.createElement('i');
					document.body.append(temoin);
					const lus = noms.map((nom) => {
						temoin.style.color = `var(${nom})`;
						return getComputedStyle(temoin).color;
					});
					temoin.remove();
					return lus;
				},
				{ code, sombre: theme === 'sombre', noms: Object.keys(jetons) },
			);
			Object.entries(jetons).forEach(([nom, attendu], i) => {
				compares++;
				const a = canaux(attendu);
				const r = canaux(rendus[i]);
				if (a.some((v, k) => Math.abs(v - r[k]) > (k === 3 ? 0.01 : 1)))
					ecarts.push(`${code}/${theme} ${nom} : table ${attendu}, site ${rendus[i]}`);
			});
		}

	//  Cas zéro : une table vide comparerait zéro jeton et passerait.
	expect(compares).toBeGreaterThan(500);
	expect(ecarts).toEqual([]);
});
