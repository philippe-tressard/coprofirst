/*
 *  **Admin › Maintenance : la conservation des affaires, en constat (#2014, L1).**
 *
 *  Le VRAI onglet, API simulée. L'administrateur lit, par exercice et par type, ce
 *  qui partira et quand — et l'écran dit que rien n'est encore retiré. Sur bureau
 *  et sur téléphone, sans défilement horizontal.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';
import type { ConstatConservation } from '../src/lib/api';
import { attendreSansDefilementHorizontal } from './defilement';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const CONSTAT: ConstatConservation = {
	mois_debut_exercice: null,
	application_active: false,
	echeances: [
		{
			type: 'breves',
			libelle: 'Actualités et questions',
			exercices: 2,
			fondement: 'rien à prouver : minimisation des données',
			exercice_cloture: '2025',
			dernier_exercice_garde: '2027',
			echoit_le: '2028-01-01',
			affaires: 12,
			fichiers: 4,
			octets: 2_400_000,
			absents: 0,
		},
		{
			type: 'travaux',
			libelle: 'Travaux et sinistres',
			exercices: 10,
			fondement: 'garantie décennale (C. civ. art. 1792-4-1)',
			exercice_cloture: '2025',
			dernier_exercice_garde: '2035',
			echoit_le: '2036-01-01',
			affaires: 3,
			fichiers: 9,
			octets: 5_100_000,
			absents: 1,
		},
	],
};

test('Maintenance : le constat de conservation dit ce qui partira, et que rien ne part encore', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/conservation-affaires') return CONSTAT;
		return undefined;
	});
	await page.goto('/admin?onglet=maintenance');

	const carte = page.locator('#conservation-affaires');
	await expect(carte.getByText(/Constat seul/)).toBeVisible();
	await expect(carte.getByText(/est l’année civile/)).toBeVisible();
	const lignes = carte.locator('tbody tr');
	await expect(lignes).toHaveCount(2);
	await expect(lignes.nth(0)).toContainText('1 janv. 2028');
	await expect(lignes.nth(0)).toContainText('Actualités et questions');
	await expect(lignes.nth(1)).toContainText('(1 absente du disque)');
	await expect(carte.getByText(/garantie décennale/)).toBeVisible();

	await carte.screenshot({ path: `test-results/conservation-${test.info().project.name}.png` });
	await attendreSansDefilementHorizontal(page, 'dans l’onglet Maintenance');
});
