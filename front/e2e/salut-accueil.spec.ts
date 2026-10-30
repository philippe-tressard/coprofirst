/*
 *  **Le salut de l'accueil garde ses espaces** (#2356, 30/10/2026).
 *
 *  `EnteteAccueil` compose « Bonsoir Prénom — Bât. …, 2ème · Copropriétaire
 *  résident » : le logement et les rôles y entrent par deux `{#if}` en ligne.
 *  Svelte 5 retire l'espace en TÊTE et en FIN d'un bloc : le retour à la ligne
 *  qui précédait chaque `<span>` disparaissait, et l'écran lisait
 *  « Prénom— Bât. … 2ème· Copropriétaire ». Ce que l'on vérifie est le texte
 *  RENDU, celui qu'on lit et qu'un lecteur d'écran prononce.
 *
 *  Et en fenêtre étroite, la ligne se coupait APRÈS un séparateur :
 *  « … résident · » puis « Conseil syndical · Admin ». L'espace d'avant chaque
 *  séparateur est insécable : on mesure, sur le rendu, qu'aucun ne finit une ligne.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const LOTS = [
	{
		id: 1,
		type: 'appartement',
		batiment_nom: 'Bât. 4 (A)',
		type_appartement: 'T4',
		etage: 2,
	},
];

const ADMIN_CS = { ...MEMBRE_CS, roles: ['conseil_syndical', 'admin'] };

async function accueil(page: Page) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/lots/mes-lots') return LOTS;
		if (chemin === '/api/auth/me') return ADMIN_CS;
		return undefined;
	});
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
	const salut = page.locator('.hero-greeting');
	await expect(salut).toContainText('Bât. 4 (A)');
	return salut;
}

test('le salut sépare le prénom, le logement et les rôles par une espace', async ({ page }) => {
	const salut = await accueil(page);
	await expect
		.poll(async () => ((await salut.textContent()) ?? '').replace(/[ \t\n]+/g, ' ').trim())
		.toMatch(
			/ CS —\u00a0Bât\. 4 \(A\), T4, 2ème ·\u00a0Copropriétaire résident ·\u00a0Conseil syndical ·\u00a0Admin$/,
		);
});

test('en fenêtre étroite, aucun séparateur ne finit une ligne', async ({ page }) => {
	await page.setViewportSize({ width: 360, height: 740 });
	const salut = await accueil(page);
	//  Pour chaque séparateur, le caractère visible suivant est-il sur la même ligne ?
	//  Un séparateur suivi d'un saut de ligne a son voisin plus bas que lui.
	const mesure = async () =>
		salut.evaluate((h1) => {
			const car: { c: string; haut: number }[] = [];
			const parcours = document.createTreeWalker(h1, NodeFilter.SHOW_TEXT);
			for (let n = parcours.nextNode(); n; n = parcours.nextNode()) {
				const texte = n.textContent ?? '';
				for (let i = 0; i < texte.length; i++) {
					if (/\s/.test(texte[i])) continue;
					const r = document.createRange();
					r.setStart(n, i);
					r.setEnd(n, i + 1);
					const rect = r.getBoundingClientRect();
					car.push({ c: texte[i], haut: rect.top + rect.height / 2 });
				}
			}
			const lignes = new Set(car.map((x) => Math.round(x.haut))).size;
			const fautifs = car
				.slice(0, -1)
				.filter((x, i) => /[—·]/.test(x.c) && car[i + 1].haut - x.haut > 4)
				.map((x) => x.c);
			return { lignes, fautifs };
		});
	await expect.poll(async () => (await mesure()).lignes).toBeGreaterThan(1);
	expect((await mesure()).fautifs).toEqual([]);
});
