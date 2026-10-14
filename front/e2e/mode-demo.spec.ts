/*
 *  **La démo publique, à l'écran (#1906, spec `mode-demo.md` §8).**
 *
 *  `GET /config` dit `mode_demo` ; le reste suit de lui seul :
 *  - la connexion garde son FORMULAIRE — les identifiants sont publiés sur le site
 *    vitrine (#1932) — sans « Créer un compte » ni « Mot de passe oublié » ;
 *  - le bandeau « Démonstration » se lit sur la connexion ET dans l'application ;
 *  - chaque boîte de formulaire rappelle que la saisie se lit par les autres
 *    visiteurs (§9, #1907) ;
 *  - hors démo, rien de cela : le formulaire est là, aucun bandeau.
 *
 *  API simulée.
 */
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

async function enDemo(page: import('@playwright/test').Page, demo: boolean, moi?: object) {
	await simulerApi(page, (chemin) => {
		if (moi && chemin === '/api/auth/me') return moi;
		if (chemin === '/api/config') return { mode_demo: demo ? '1' : '0' };
		return undefined;
	});
}

test('en démo, la connexion garde le formulaire, sans inscription ni oubli', async ({ page }) => {
	await enDemo(page, true);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);

	await expect(page.getByRole('note').filter({ hasText: 'Démonstration' })).toBeVisible();
	await expect(page.locator('form input[type="email"]')).toBeVisible();
	await expect(page.locator('form input[type="password"]')).toBeVisible();
	await expect(page.getByRole('link', { name: 'Créer un compte' })).toHaveCount(0);
	await expect(page.getByRole('link', { name: 'Mot de passe oublié ?' })).toHaveCount(0);
});

test('hors démo, la connexion garde son formulaire et aucun bandeau', async ({ page }) => {
	await enDemo(page, false);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);

	await expect(page.locator('form input[type="email"]')).toBeVisible();
	await expect(page.getByRole('link', { name: 'Créer un compte' })).toBeVisible();
	await expect(page.getByRole('note').filter({ hasText: 'Démonstration' })).toHaveCount(0);
});

test('en démo, le bandeau se lit aussi dans l’application', async ({ page }) => {
	await enDemo(page, true);
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
	await expect(page.getByRole('note').filter({ hasText: 'Démonstration' })).toBeVisible();
});

for (const demo of [true, false]) {
	test(`${demo ? 'en' : 'hors'} démo, une boîte de création ${demo ? 'rappelle' : 'ne rappelle pas'} que la saisie est partagée`, async ({
		page,
	}) => {
		await enDemo(page, demo, MEMBRE_CS);
		await page.goto('/delegations');
		await attendreHydratation(page);
		await page.getByRole('button', { name: '+ Nouvelle délégation' }).click();
		const boite = page.getByRole('group', { name: 'Nouvelle délégation aidant' });
		await expect(boite).toBeVisible();
		await expect(
			boite.getByRole('note').filter({ hasText: 'visible des autres visiteurs' }),
		).toHaveCount(demo ? 1 : 0);
	});
}
