/*
 *  **Un compte sans lot n'a pas d'étage de logement à saisir** (16/10/2026).
 *
 *  Sur la démo, le profil d'`operateur@localhost` listait les trente lots de la
 *  résidence, un champ d'étage par lot : `GET /lots/mes-lots` repliait sur le
 *  patrimoine entier pour un compte d'administration sans lien. La correction
 *  est au serveur (`api/tests/test_mes_lots_sans_repli.py`) ; ce test tient ce
 *  que l'écran en fait — une liste vide ne montre ni la rubrique des étages, ni
 *  la ligne « Lot » des informations du compte. Le cas zéro, un lot rattaché,
 *  prouve que la rubrique sait encore s'afficher.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const OPERATEUR_SANS_LOT = {
	...MEMBRE_CS,
	statut: null,
	role: 'admin',
	roles: ['admin', 'operateur'],
};

const LOGEMENT = {
	id: 3,
	numero: '15',
	batiment_nom: 'Bât. 4',
	type: 'appartement',
	etage: 2,
	est_logement_de_reference: true,
	type_lien: 'propriétaire',
};

async function ouvrirProfil(page: Page, lots: unknown[]) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return OPERATEUR_SANS_LOT;
		if (chemin === '/api/lots/mes-lots') return lots;
	});
	await page.goto('/profil');
	await attendreHydratation(page);
}

const rubriqueEtages = (page: Page) =>
	page.getByText(/^Étages? de (mon|chacun de mes) logements?$/);

test('un opérateur sans lot ne voit aucune rubrique d’étage de logement', async ({ page }) => {
	await ouvrirProfil(page, []);

	await expect(page.locator('#p-etage')).toBeVisible();
	await expect(rubriqueEtages(page)).toHaveCount(0);
	await expect(page.locator('input[id^="p-etage-lot-"]')).toHaveCount(0);
	await expect(page.locator('dt', { hasText: /^Lots?$/ })).toHaveCount(0);
});

test('cas zéro : un lot rattaché montre la rubrique, un champ par logement', async ({ page }) => {
	await ouvrirProfil(page, [LOGEMENT]);

	await expect(rubriqueEtages(page)).toHaveText('Étage de mon logement');
	await expect(page.locator('input[id^="p-etage-lot-"]')).toHaveCount(1);
	await expect(page.locator('dt', { hasText: /^Lot$/ })).toBeVisible();
});
