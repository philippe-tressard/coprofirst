/*
 *  **L'hôte commun demande la copropriété, puis y renvoie** (#1894, 17/10/2026).
 *
 *  Sur l'hôte commun d'une installation à plusieurs copropriétés, l'écran de
 *  connexion demande d'abord laquelle — code postal + nom — et le navigateur part
 *  à l'adresse que rend le serveur. Ailleurs, la route répond 404 et l'écran reste
 *  celui de la copropriété. Un échec affiche le message du serveur, tel quel : il
 *  est le même dans tous les cas, c'est ce qui empêche l'énumération.
 *
 *  L'API est simulée : la règle d'aiguillage (correspondance exacte, plafond,
 *  message unique) est tenue côté serveur par `test_installation_commune_aiguillage.py`.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const ECHEC = 'Aucune copropriété ne correspond à ce code postal et ce nom.';

/** L'hôte commun : `GET` s'annonce, `POST` rend `destination` ou l'échec. */
async function hoteCommun(page: Page, destination: string | null) {
	const demandes: unknown[] = [];
	await simulerApi(page);
	await page.route(
		(url) => url.pathname === '/api/plateforme/aiguillage',
		(route) => {
			const requete = route.request();
			if (requete.method() === 'GET') return route.fulfill({ json: { hote_commun: true } });
			demandes.push(requete.postDataJSON());
			return destination
				? route.fulfill({ json: { destination } })
				: route.fulfill({ status: 404, json: { detail: ECHEC } });
		},
	);
	return demandes;
}

test('sur l’hôte commun, la connexion demande la copropriété et y renvoie', async ({ page }) => {
	const destination = new URL('/mentions-legales', test.info().project.use.baseURL).href;
	const demandes = await hoteCommun(page, destination);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);

	await expect(page.getByLabel(/Code postal/)).toBeVisible();
	await expect(page.getByLabel(/^Email/)).toHaveCount(0);
	await page.getByLabel(/Code postal/).fill('75015');
	await page.getByLabel(/Nom de la copropriété/).fill('Les Tilleuls');
	await page.getByRole('button', { name: 'Continuer' }).click();

	await expect(page).toHaveURL(destination);
	expect(demandes).toEqual([{ code_postal: '75015', nom: 'Les Tilleuls' }]);
});

test('un échec affiche le message du serveur, et rien d’autre', async ({ page }) => {
	await hoteCommun(page, null);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);

	await page.getByLabel(/Code postal/).fill('99999');
	await page.getByLabel(/Nom de la copropriété/).fill('Inconnue');
	await page.getByRole('button', { name: 'Continuer' }).click();

	await expect(page.getByRole('alert')).toHaveText(ECHEC);
	await expect(page).toHaveURL(/\/auth\/connexion$/);
});

test('un alias de l’adresse qui ne mène nulle part montre l’aiguillage', async ({ page }) => {
	const demandes = await hoteCommun(page, null);
	await page.goto('/75015-les-tilleuls');
	await attendreHydratation(page);

	await expect(page.getByRole('alert')).toHaveText(ECHEC);
	await expect(page.getByLabel(/Code postal/)).toBeVisible();
	expect(demandes).toEqual([{ alias: '75015-les-tilleuls' }]);
});

test('ailleurs que sur l’hôte commun, la connexion reste celle de la copropriété', async ({
	page,
}) => {
	await simulerApi(page);
	await page.route(
		(url) => url.pathname === '/api/plateforme/aiguillage',
		(route) => route.fulfill({ status: 404, json: { detail: 'Not Found' } }),
	);
	await page.goto('/auth/connexion');
	await attendreHydratation(page);

	await expect(page.getByLabel(/^Email/)).toBeVisible();
	await expect(page.getByLabel(/Code postal/)).toHaveCount(0);
});
