/*
 *  **Admin › Assistant IA : « Lecture des usages… » est une attente, pas un état** (#2975, 24/11/2026).
 *
 *  L'onglet déduisait l'attente d'une liste VIDE (`{#if usages.length === 0}`) : une
 *  lecture en échec laissait « Lecture des usages… » à l'écran pour toujours, sous le
 *  toast d'erreur. Les trois états passent désormais par `EtatListe` — en cours,
 *  échec, liste — et ne se confondent plus.
 */
import { expect, MEMBRE_CS, retenirApi, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
const USAGES = '/api/config/llm-usages';

test('la lecture des usages s’annonce, puis s’efface quand elle aboutit', async ({ page }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	const relacher = await retenirApi(page, (chemin) => chemin === USAGES);
	await page.goto('/admin?onglet=ia');

	const attente = page.getByText('Lecture des usages…');
	await expect(attente).toBeVisible();
	relacher();
	await expect(attente).toHaveCount(0);
});

test('une lecture en échec le dit, et ne promet plus d’attendre', async ({ page }) => {
	await simulerApi(page, (chemin) => (chemin === '/api/auth/me' ? ADMIN : undefined));
	//  Posé APRÈS `simulerApi` : Playwright essaie la dernière route en premier.
	await page.route(
		(url) => url.pathname === USAGES,
		(route) =>
			route.fulfill({
				status: 500,
				contentType: 'application/json',
				body: JSON.stringify({ detail: 'Lecture impossible (témoin)' }),
			}),
	);
	await page.goto('/admin?onglet=ia');

	//  Un 500 se dit par le message générique de `messageErreur` : on lit l'ÉTAT d'échec.
	await expect(page.locator('.etat-erreur')).toContainText(/erreur/i);
	await expect(page.getByText('Lecture des usages…')).toHaveCount(0);
});
