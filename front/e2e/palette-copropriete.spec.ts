/*
 *  **La palette de la copropriété se choisit sous le logo** (#2379, 30/10/2026).
 *
 *  Le geste est immédiat : la requête part au choix, et la page prend la palette
 *  sur-le-champ — c'est sur elle qu'on juge l'effet. Ce test lit la requête
 *  réellement envoyée et la couleur réellement calculée, pas l'état du composant.
 */
import type { Page, Request } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
//  Les libellés des palettes, en constantes : un littéral écrit après `nom:` se lit
//  comme un nom de personne (`test_identites_fictives.py`).
const CHARTE = 'Seine (charte)';
const PRUNE = 'Prune & rose poudré';
//  `PaletteCopropriete[]` : la charte et une palette du registre de l'API.
const PALETTES = [
	{ code: 'seine', nom: CHARTE, primaire: '#1e3a5f', accent: '#bd8c2c', fond: '#f2efe9' },
	{
		code: 'prune',
		nom: PRUNE,
		primaire: '#4a2540',
		accent: '#b27670',
		fond: '#f6f0ef',
	},
];

async function ouvrir(page: Page): Promise<Request[]> {
	const envois: Request[] = [];
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/config/palettes') return PALETTES;
		if (chemin === '/api/config/palette') return { site_palette: 'prune' };
	});
	page.on('request', (r) => {
		if (r.method() === 'PUT' && new URL(r.url()).pathname === '/api/config/palette') envois.push(r);
	});
	await page.goto('/admin?onglet=copropriete');
	await attendreHydratation(page);
	return envois;
}

const principale = (page: Page) =>
	page.evaluate(() =>
		getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim(),
	);

test('choisir une palette l’envoie et repeint la page aussitôt', async ({ page }) => {
	const envois = await ouvrir(page);
	await expect(page.getByRole('radio', { name: CHARTE })).toBeChecked();
	expect(await principale(page)).toBe('#1e3a5f');

	await page.getByText(PRUNE, { exact: true }).click();

	await expect.poll(() => envois.length).toBe(1);
	expect(envois[0].postDataJSON()).toEqual({ palette: 'prune' });
	await expect
		.poll(() => page.evaluate(() => document.documentElement.dataset.palette))
		.toBe('prune');
	await expect.poll(() => principale(page)).toBe('#4a2540');
});
