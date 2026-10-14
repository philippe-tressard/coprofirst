/*
 *  **Accorder ou retirer le rôle Opérateur** dans Admin › Utilisateurs (#1750).
 *
 *  L'écran propose ce que le serveur accepte, ni plus ni moins —
 *  `gestesOperateur` (`$lib/droits`) contre `_exiger_geste_operateur`
 *  (`api/app/routers/admin/utilisateurs.py`, éprouvé par
 *  `api/tests/test_role_operateur_attribution.py`) :
 *  un opérateur l'accorde à un admin, le retire à un autre opérateur, jamais à
 *  lui-même ; « – Admin » se tait chez un opérateur ; un admin qui n'est pas
 *  opérateur ne voit aucun des deux gestes.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const OPERATEUR = { ...MEMBRE_CS, role: 'admin', roles: ['admin', 'operateur'] };
const ADMIN_SEUL = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

function ligne(id: number, prenom: string, roles: string[]) {
	return {
		id,
		prenom,
		nom: 'Durand',
		email: `${prenom.toLowerCase()}@exemple.test`,
		statut: 'copropriétaire_résident',
		role: roles.includes('admin') ? 'admin' : 'résident',
		roles,
		actif: true,
		batiment_id: null,
	};
}

const COMPTES = [
	ligne(OPERATEUR.id, 'Moi', OPERATEUR.roles),
	ligne(31, 'Alice', ['propriétaire', 'admin']),
	ligne(32, 'Bruno', ['propriétaire', 'admin', 'operateur']),
	ligne(33, 'Chloe', ['propriétaire', 'résident']),
];

async function ouvrir(page: Page, moi: typeof OPERATEUR) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return moi;
		if (chemin === '/api/admin/utilisateurs') return COMPTES;
	});
	await page.goto('/admin?onglet=utilisateurs');
	await attendreHydratation(page);
}

const rangee = (page: Page, prenom: string) =>
	page.locator('table tbody tr').filter({ hasText: `${prenom} DURAND` });

test('un opérateur accorde le rôle à un admin, le retire à un autre, jamais à lui-même', async ({
	page,
}) => {
	await ouvrir(page, OPERATEUR);
	await expect(page.locator('table tbody tr')).toHaveCount(4);

	const alice = rangee(page, 'Alice');
	await expect(alice.getByRole('button', { name: '+ Opérateur' })).toBeVisible();
	await expect(alice.getByRole('button', { name: '– Admin' })).toBeVisible();

	const bruno = rangee(page, 'Bruno');
	await expect(bruno.getByRole('button', { name: '– Opérateur' })).toBeVisible();
	//  Admin ne se retire pas à un opérateur : le serveur le refuse.
	await expect(bruno.getByRole('button', { name: '– Admin' })).toHaveCount(0);

	//  Pas admin : le rôle ne s'accorde pas.
	await expect(rangee(page, 'Chloe').getByRole('button', { name: /Opérateur/ })).toHaveCount(0);
	//  Soi-même : on ne se le retire pas.
	await expect(rangee(page, 'Moi').getByRole('button', { name: /Opérateur/ })).toHaveCount(0);
});

test('le geste demande confirmation et nomme le rôle', async ({ page }) => {
	await ouvrir(page, OPERATEUR);
	await rangee(page, 'Alice').getByRole('button', { name: '+ Opérateur' }).click();
	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('Ajouter le rôle Opérateur');
	await boite.getByRole('button', { name: 'Annuler' }).click();
	await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('un admin qui n’est pas opérateur ne voit aucun geste sur ce rôle', async ({ page }) => {
	await ouvrir(page, ADMIN_SEUL);
	await expect(page.locator('table tbody tr')).toHaveCount(4);
	await expect(page.getByRole('button', { name: /Opérateur/ })).toHaveCount(0);
});
