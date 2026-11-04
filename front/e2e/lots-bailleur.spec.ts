/*
 *  **La vue bailleur de « Mes lots »** (#779, 30/09/2026).
 *
 *  Extraite de `mon-lot/+page.svelte` en `LotsBailleur`. Ce test tient ce que
 *  l'extraction devait conserver : les lots possédés (occupé · vacant), la carte
 *  du locataire avec ses baux, les lots vacants, et le libellé du type d'un lot.
 *  Depuis #2507 ce libellé est SERVI par l'API (`libelle_type_complet`, règle et cas
 *  du type inconnu éprouvés par `api/tests/test_libelles_lot_servis.py`) : l'écran
 *  le lit tel quel, il ne le recompose plus.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const BAILLEUR = {
	...MEMBRE_CS,
	id: 30,
	prenom: 'Claire',
	nom: 'Bailleur',
	statut: 'copropriétaire_bailleur',
	role: 'propriétaire',
	roles: ['propriétaire'],
};

const LOTS = [
	{
		id: 1,
		numero: '12',
		batiment_nom: 'Bât. 2',
		type: 'appartement',
		type_appartement: 'T3',
		etage: 2,
		libelle_type_complet: 'Appartement – T3',
	},
	{
		id: 2,
		numero: '40',
		batiment_nom: 'Bât. 2',
		type: 'local_commercial',
		etage: 0,
		libelle_type_complet: 'Local commercial',
	},
];

const BAIL = {
	id: 7,
	lot_id: 1,
	statut: 'actif',
	locataire_id: 55,
	locataire_prenom: 'Paul',
	locataire_nom: 'Durand',
	locataire_email: 'paul@exemple.test',
	date_entree: '2026-01-01',
};

async function ouvrir(page: Page) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return BAILLEUR;
		if (chemin === '/api/lots/mes-lots') return LOTS;
		if (chemin === '/api/bailleur/mes-baux') return [BAIL];
	});
	await page.goto('/mon-lot');
	await attendreHydratation(page);
}

test('lots possédés, locataire et lots vacants', async ({ page }) => {
	await ouvrir(page);
	await expect(page.getByText('🏢 Lots possédés (2)')).toBeVisible();
	await expect(page.locator('.lot-possede-card.lot-occupe')).toHaveCount(1);
	await expect(page.locator('.lot-possede-card.lot-vacant')).toHaveCount(1);
	await expect(page.getByRole('button', { name: '+ Créer un bail' })).toHaveCount(1);
	await expect(page.locator('.locataire-card')).toContainText('Paul DURAND');
	await expect(page.getByRole('button', { name: /Accès/ })).toBeVisible();
	await expect(page.getByText('🔓 Lots vacants (1)')).toBeVisible();
});

test('le type d’un lot : l’écran lit le libellé que l’API sert', async ({ page }) => {
	await ouvrir(page);
	const cartes = page.locator('.lot-possede-card');
	await expect(cartes.filter({ hasText: '12' })).toContainText('Appartement – T3');
	//  `local_commercial` : le code n'est jamais montré, le libellé servi l'est.
	await expect(cartes.filter({ hasText: '40' })).toContainText('Local commercial');
	await expect(cartes.filter({ hasText: '40' })).not.toContainText('local_commercial');
});

test('chargement direct : un locataire voit son bail (le rôle est attendu)', async ({ page }) => {
	//  Avant #779, ce qui dépend du rôle se chargeait dans `onMount`, AVANT que le
	//  layout ait chargé l'utilisateur : sur un chargement direct, rien ne venait.
	const LOCATAIRE = {
		...BAILLEUR,
		id: 55,
		statut: 'locataire',
		role: 'résident',
		roles: ['résident'],
	};
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return LOCATAIRE;
		if (chemin === '/api/lots/mes-lots') return [];
		if (chemin === '/api/bailleur/mon-bail')
			return { ...BAIL, lot_numero: '12', lot_batiment_nom: 'Bât. 2', lot_type: 'appartement' };
	});
	await page.goto('/mon-lot');
	await attendreHydratation(page);
	await expect(page.getByText('🏠 Lot loué')).toBeVisible();
});
