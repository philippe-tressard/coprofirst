/*
 *  **L'administration dit à quel titre on agit (31/10/2026).**
 *
 *  Un compte qui cumule Admin et Opérateur passait d'un onglet sur sa résidence
 *  à un onglet sur toute l'instance sans que rien ne le dise. `PorteeOnglet`
 *  (`#lib/portee`) le dit ; ce test rend le vrai écran, API simulée :
 *
 *  1. le cumulard lit « opérateur de l'instance » sur Installation et
 *     Maintenance, « administrateur de … » sur Utilisateurs ;
 *  2. un administrateur seul ne lit aucun bandeau (cas zéro : il n'a qu'un titre) ;
 *  3. sur une instance commune, Utilisateurs n'offre plus « + Opérateur ».
 */
import type { Page } from '@playwright/test';
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, id: 1, role: 'admin', roles: ['admin'], actif: true };
const ADMIN_OPERATEUR = { ...ADMIN, roles: ['admin', 'operateur'] };
const AUTRE_ADMIN = {
	...ADMIN,
	id: 2,
	email: 'autre-admin@exemple.example',
	statut: 'copropriétaire_résident',
};

async function ouvrir(page: Page, adresse: string, moi: object, commune = false) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return moi;
		if (chemin === '/api/config')
			return { site_nom: 'Les Tilleuls', operateur_par_exploitant: commune ? '1' : '0' };
		if (chemin === '/api/admin/installation')
			return { role: 'reference', libelle: 'Référence', branche: 'main', etat: 'non_verifie' };
		if (chemin === '/api/admin/utilisateurs') return [moi, AUTRE_ADMIN];
		return undefined;
	});
	await page.goto(adresse);
}

const bandeau = (page: Page) => page.locator('.portee-onglet');

test('le cumulard lit sa portée sur chaque sorte d’onglet', async ({ page }) => {
	await ouvrir(page, '/admin?onglet=installation', ADMIN_OPERATEUR);
	await expect(bandeau(page)).toContainText('opérateur de l’instance');
	await ouvrir(page, '/admin?onglet=maintenance', ADMIN_OPERATEUR);
	await expect(bandeau(page)).toContainText('opérateur de l’instance');
	await ouvrir(page, '/admin?onglet=utilisateurs', ADMIN_OPERATEUR);
	await expect(bandeau(page)).toContainText('administrateur de la copropriété « Les Tilleuls »');
});

test('cas zéro : un administrateur seul ne lit aucun bandeau', async ({ page }) => {
	await ouvrir(page, '/admin?onglet=utilisateurs', ADMIN);
	await expect(page.locator('.legende-roles')).toBeVisible();
	await expect(bandeau(page)).toHaveCount(0);
});

test('instance commune : « + Opérateur » ne s’offre plus', async ({ page }) => {
	await ouvrir(page, '/admin?onglet=utilisateurs', ADMIN_OPERATEUR, true);
	await expect(page.locator('.legende-roles')).toContainText('l’exploitant du serveur le désigne');
	await expect(page.locator('.ajouter-operateur')).toHaveCount(0);
	await expect(page.getByText('Opérateur désigné par l’exploitant').first()).toBeVisible();
});

test('instance propre : « + Opérateur » s’offre à un autre administrateur', async ({ page }) => {
	await ouvrir(page, '/admin?onglet=utilisateurs', ADMIN_OPERATEUR);
	await expect(page.locator('.ajouter-operateur').first()).toBeVisible();
});
