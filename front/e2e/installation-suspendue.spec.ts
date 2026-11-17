/*
 *  **L'installation suspendue, à l'écran (R6 #1882, spec multi-copropriétés §4.11, D20).**
 *
 *  `GET /config` dit `installation_suspendue`, calculée par le serveur depuis le bail ;
 *  le bandeau « lecture seule » se lit sur la connexion ET dans l'application — avant
 *  qu'une écriture refusée l'apprenne à quelqu'un. Hors suspension, aucun bandeau.
 *
 *  API simulée.
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

async function suspendue(page: import('@playwright/test').Page, oui: boolean) {
	await simulerApi(page, (chemin) =>
		chemin === '/api/config' ? { installation_suspendue: oui ? '1' : '0' } : undefined,
	);
}

const BANDEAU = 'Installation suspendue';

test('suspendue, la connexion le dit et garde son formulaire', async ({ page }) => {
	await suspendue(page, true);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);

	await expect(page.getByRole('note').filter({ hasText: BANDEAU })).toBeVisible();
	await expect(page.locator('form input[type="email"]')).toBeVisible();
});

test('suspendue, le bandeau se lit aussi dans l’application', async ({ page }) => {
	await suspendue(page, true);
	await page.goto('/tableau-de-bord');
	await attendreHydratation(page);
	await expect(page.getByRole('note').filter({ hasText: BANDEAU })).toBeVisible();
});

test('hors suspension, aucun bandeau', async ({ page }) => {
	await suspendue(page, false);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);
	await expect(page.locator('form input[type="email"]')).toBeVisible();
	await expect(page.getByRole('note').filter({ hasText: BANDEAU })).toHaveCount(0);
});
