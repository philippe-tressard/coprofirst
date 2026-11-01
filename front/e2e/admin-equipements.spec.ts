/*
 *  **Admin › Copropriété › Équipements** (#2442, 01/11/2026) — l'écran qui rend
 *  les équipements administrables, sur la maquette C arbitrée par l'utilisateur :
 *  la fiche, l'APERÇU en direct, ce qui le cite.
 *
 *  Ce que la route garantit est éprouvé côté serveur (`test_equipements_admin.py`).
 *  Ici, ce que seul l'écran peut montrer :
 *   - l'aperçu SUIT la saisie — le libellé, le mot abrégé de la gouttière ;
 *   - ce qui part est ce que la fiche montre — code déduit, icône choisie ;
 *   - un équipement système ne s'offre pas au retrait (📦) ;
 *   - 🗑️ ne s'offre qu'aux Retirés, et seulement quand rien ne le cite.
 */
import type { Page, Request } from '@playwright/test';
import {
	attendreHydratation,
	EQUIPEMENTS_TEMOINS,
	expect,
	MEMBRE_CS,
	simulerApi,
	test,
} from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

/** Un équipement retiré, que plus rien ne cite. */
const PISCINE = {
	...EQUIPEMENTS_TEMOINS[0],
	id: 99,
	code: 'piscine',
	libelle: 'Piscine',
	icone: 'droplet',
	abreviation: 'PISC.',
	actif: false,
};

async function ouvrir(page: Page): Promise<Request[]> {
	const ecritures: Request[] = [];
	page.on('request', (r) => {
		if (r.url().includes('/api/equipements') && r.method() !== 'GET') ecritures.push(r);
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/equipements') return [...EQUIPEMENTS_TEMOINS, PISCINE];
		if (/^\/api\/equipements\/\d+\/usages$/.test(chemin))
			return { contrats: 0, affaires: 0, prestataires: 0 };
		return undefined;
	});
	await page.goto('/admin?onglet=equipements');
	await attendreHydratation(page);
	return ecritures;
}

test('la liste montre les équipements, un système porte son cadenas et pas de 📦', async ({
	page,
}) => {
	await ouvrir(page);
	const assurance = page.locator('#equipement-assurance');
	await expect(assurance).toContainText('Assurance');
	await expect(assurance).toContainText('Système');
	await expect(assurance.getByRole('button', { name: 'Archiver' })).toHaveCount(0);
	await expect(
		page.locator('#equipement-ascenseur').getByRole('button', { name: 'Archiver' }),
	).toHaveCount(1);
});

test('créer : l’aperçu suit la saisie, et ce qui part est ce que la fiche montre', async ({
	page,
}) => {
	const ecritures = await ouvrir(page);
	await page.getByRole('button', { name: /Nouvel équipement/ }).click();
	await page.locator('form input[type="text"]').first().fill('Porte de garage');

	const apercu = page.getByRole('complementary', { name: 'Aperçu' });
	await expect(apercu).toContainText('Contrat d’entretien — Porte de garage');
	//  Le premier mot du libellé, jamais un mot coupé au hasard.
	await expect(apercu.locator('abbr')).toHaveText('PORTE');
	await expect(page.getByText('porte_de_garage')).toBeVisible();

	await page.getByRole('button', { name: 'Parking', exact: true }).click();
	await page.getByLabel('Abréviation').fill('garage');
	await expect(apercu.locator('abbr')).toHaveText('GARAGE');

	await page.getByRole('button', { name: 'Enregistrer' }).click();
	await expect.poll(() => ecritures.length).toBe(1);
	expect(ecritures[0].method()).toBe('POST');
	expect(ecritures[0].postDataJSON()).toMatchObject({
		code: 'porte_de_garage',
		libelle: 'Porte de garage',
		icone: 'square-parking',
		abreviation: 'GARAGE',
		perimetres: [],
	});
});

test('🗑️ ne s’offre qu’aux Retirés, une fois lu que rien ne cite l’équipement', async ({
	page,
}) => {
	await ouvrir(page);
	await expect(page.getByRole('button', { name: 'Supprimer l’équipement' })).toHaveCount(0);
	await page
		.getByText(/Archives/)
		.first()
		.click();
	const piscine = page.locator('#equipement-piscine');
	await expect(piscine.getByRole('button', { name: 'Restaurer' })).toBeVisible();
	await piscine.getByText('Piscine').first().click();
	await expect(piscine.getByRole('button', { name: 'Supprimer l’équipement' })).toBeVisible();
});
