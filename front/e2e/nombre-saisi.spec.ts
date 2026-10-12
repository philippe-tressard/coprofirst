/*
 *  **Un nombre vidé s'enregistre vide, un 0 saisi reste 0** (#1516, 01/10/2026).
 *
 *  Un `<input type="number" bind:value>` vidé rend `null` (Svelte), pas `''`.
 *  Le relevé de consommation testait `index !== ''` : un index tapé puis effacé
 *  partait en `Number(null)`, soit **0 m³**, et faussait les consommations
 *  calculées. Toutes les conversions de saisie passent désormais par
 *  `nombreOuNull` (`lint:nombre-saisi`) ; ce test tient le comportement, sur la
 *  requête réellement envoyée.
 */
import type { Page, Request } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const COMPTEUR = { id: 1, type_compteur: 'eau', label: 'Eau froide', prestataire_id: null };

async function nouveauReleve(page: Page): Promise<Request[]> {
	const envois: Request[] = [];
	await simulerApi(page, (chemin) =>
		chemin === '/api/prestataires/compteurs-config' ? [COMPTEUR] : undefined,
	);
	await page.route(
		(url) => url.pathname === '/api/prestataires/releves',
		(route) => {
			if (route.request().method() !== 'POST') return route.fallback();
			envois.push(route.request());
			return route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({ id: 50, ...route.request().postDataJSON() }),
			});
		},
	);
	await page.goto('/prestataires/consommations');
	await attendreHydratation(page);
	await page.getByRole('button', { name: /Nouveau relevé/ }).click();
	return envois;
}

test('un index tapé puis effacé part vide, pas à 0', async ({ page }) => {
	const envois = await nouveauReleve(page);
	const index = page.getByLabel(/Index/);
	await index.fill('47047');
	await index.fill('');
	await page.getByRole('button', { name: /Enregistrer/ }).click();
	await expect.poll(() => envois.length).toBe(1);
	expect(envois[0].postDataJSON().index).toBeNull();
});

test('un index de 0 — un compteur neuf — reste 0', async ({ page }) => {
	const envois = await nouveauReleve(page);
	await page.getByLabel(/Index/).fill('0');
	await page.getByRole('button', { name: /Enregistrer/ }).click();
	await expect.poll(() => envois.length).toBe(1);
	expect(envois[0].postDataJSON().index).toBe(0);
});
