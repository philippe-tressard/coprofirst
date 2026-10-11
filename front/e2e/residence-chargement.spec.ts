/*
 *  **Ma résidence : la Fiche en une vague, et seulement sur la Fiche (#1841).**
 *
 *  La Fiche se chargeait en trois vagues — les catégories de document, puis les
 *  plans, le règlement et les CR d'AG par l'identifiant de leur catégorie, puis
 *  les règles au montage de leur section : +411 ms au lieu de +149. Et ouverte
 *  sur le Carnet, la page lançait quand même ses huit appels.
 *
 *  1. Les catégories RETENUES, les trois rubriques et les règles sont déjà
 *     demandées : rien n'attend plus la liste des catégories.
 *  2. Sur le Carnet, la Fiche n'est pas lue ; elle l'est au passage sur son onglet.
 */
import type { Page } from '@playwright/test';
import { expect, retenirApi, simulerApi, test } from './aides';

const RUBRIQUES = ['plan_residence', 'reglement_copropriete', 'pv_ag'];

/** Simule l'API et note chaque lecture, paramètres compris. */
async function simuler(page: Page) {
	const demandes: string[] = [];
	page.on('request', (r) => {
		const url = new URL(r.url());
		if (url.pathname.startsWith('/api/')) demandes.push(url.pathname + url.search);
	});
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/copropriete') return { id: 1, nom: 'Résidence témoin' };
	});
	return demandes;
}

test('Fiche : rubriques et règles partent sans attendre les catégories', async ({ page }) => {
	const demandes = await simuler(page);
	const relacher = await retenirApi(page, (chemin) => chemin === '/api/documents/categories');
	await page.goto('/residence');
	//  Cas zéro : les catégories sont demandées — et toujours retenues.
	await expect.poll(() => demandes.includes('/api/documents/categories')).toBe(true);
	for (const code of RUBRIQUES)
		await expect.poll(() => demandes.includes(`/api/documents?categorie=${code}`)).toBe(true);
	await expect.poll(() => demandes.includes('/api/regles-residence')).toBe(true);
	relacher();
	await expect(page.getByRole('heading', { name: /Résidence témoin/ })).toBeVisible();
});

test('Carnet : la Fiche n’est lue qu’au passage sur son onglet', async ({ page }) => {
	const demandes = await simuler(page);
	await page.goto('/residence/carnet');
	await expect.poll(() => demandes.some((d) => d.startsWith('/api/carnet'))).toBe(true);
	expect(
		demandes.filter((d) => d === '/api/copropriete' || d.startsWith('/api/documents')),
	).toEqual([]);
	await page.getByRole('tablist').getByRole('link', { name: /Fiche/ }).click();
	await expect(page.getByRole('heading', { name: /Résidence témoin/ })).toBeVisible();
	expect(demandes).toContain('/api/regles-residence');
});
