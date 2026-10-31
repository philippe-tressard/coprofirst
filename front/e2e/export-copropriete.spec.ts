/*
 *  **L'export vérifié** (#1749) : le vrai onglet Maintenance, API simulée.
 *  - « Vérifier la restauration » dit qu'une base se restaure, chiffres à l'appui,
 *    et nomme ce qui n'est pas exporté ;
 *  - un refus se lit comme un refus, avec ses écarts ;
 *  - le dernier export du volume des sauvegardes se lit sous les boutons.
 */
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

async function ouvrir(page, verification) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/export-copropriete/dernier')
			return {
				archive: 'export_copropriete_20261009_041500_paris.tar.gz',
				octets: 104857600,
				cree_le: '2026-10-09T02:15:00',
				tables: 86,
				lignes: 18432,
				fichiers: 412,
			};
		if (chemin === '/api/admin/export-copropriete/verifier') return verification;
		return undefined;
	});
	await page.goto('/admin?onglet=maintenance');
	const carte = page.locator('section.config-section', {
		has: page.getByText('Export vérifié', { exact: true }),
	});
	await expect(carte).toBeVisible();
	return carte;
}

test('Export vérifié : la base se restaure à l’identique', async ({ page }) => {
	const carte = await ouvrir(page, {
		restaurable: true,
		tables: 86,
		lignes: 18432,
		revision: '0271',
		ignorees: ['ancienne_table'],
		ecarts: [],
		duree_secondes: 3.4,
	});
	await expect(carte.getByText(/export_copropriete_20261009_041500_paris\.tar\.gz/)).toBeVisible();
	await expect(carte.getByText('Jamais vérifiée depuis cet écran.')).toBeVisible();
	await carte.getByRole('button', { name: 'Vérifier la restauration' }).click();
	await expect(carte.getByText(/Se restaure à l’identique —\u00a086 tables/)).toBeVisible();
	await expect(
		carte.getByText(/Non exportées \(absentes des modèles\).*ancienne_table/),
	).toBeVisible();
	const deborde = await page.evaluate(
		() => document.documentElement.scrollWidth > document.documentElement.clientWidth,
	);
	expect(deborde, 'défilement horizontal dans l’onglet Maintenance').toBe(false);
	await carte.screenshot({
		path: `test-results/export-copropriete-${test.info().project.name}.png`,
	});
});

test('Export vérifié : un refus se lit comme un refus', async ({ page }) => {
	const carte = await ouvrir(page, {
		restaurable: false,
		tables: 0,
		lignes: 0,
		revision: null,
		ignorees: [],
		ecarts: ['faq_item : contenu différent de l’archive (empreinte)'],
		duree_secondes: 1.2,
	});
	await carte.getByRole('button', { name: 'Vérifier la restauration' }).click();
	await expect(carte.getByText(/Ne se restaure pas.*faq_item/)).toBeVisible();
	await expect(carte.getByText(/Se restaure à l’identique/)).toHaveCount(0);
});
