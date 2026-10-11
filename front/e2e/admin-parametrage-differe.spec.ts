/*
 *  **Admin : les files de « À traiter » n'attendent pas le paramétrage (#1842).**
 *
 *  L'onglet par défaut de l'administration lisait, EN SÉRIE, la configuration
 *  de la coquille, `/config/admin` puis `/config/legal` — trois lectures qui ne
 *  servent qu'aux onglets de réglage — avant de demander ses propres listes :
 *  +225 ms à chaque ouverture. Ce test RETIENT les deux lectures de paramétrage
 *  et vérifie que les files s'affichent quand même.
 *
 *  Et l'inverse, qui est le verrou de #1459 : tant que le paramétrage n'est pas
 *  lu, un onglet de réglage ne monte PAS son formulaire — monté sur les
 *  défauts, il effacerait la configuration à l'enregistrement. Il attend, puis
 *  s'ouvre sur les valeurs lues.
 */
import type { Page } from '@playwright/test';
import { expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
const COMMANDES = [
	{ id: 1, user_id: 7, type: 'badge', lot_id: 12, cree_le: '2026-10-11T10:00:00' },
];

/** Retient `/config/admin` et `/config/legal` jusqu'à `relacher()`. */
async function retenirParametrage(page: Page) {
	let relacher: () => void = () => {};
	const relache = new Promise<void>((r) => (relacher = r));
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/commandes-acces') return COMMANDES;
		return undefined;
	});
	//  Déclarée APRÈS `simulerApi` : Playwright essaie les routes de la plus
	//  récente à la plus ancienne.
	await page.route(
		(url) => url.pathname === '/api/config/admin' || url.pathname === '/api/config/legal',
		async (route) => {
			await relache;
			const corps = route.request().url().endsWith('/legal')
				? { mentions_legales: '<p>Mentions lues</p>' }
				: { site_nom: 'Résidence témoin' };
			await route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify(corps),
			});
		},
	);
	return () => relacher();
}

test('Admin › À traiter : les files s’affichent sans attendre le paramétrage', async ({ page }) => {
	const relacher = await retenirParametrage(page);
	await page.goto('/admin');
	//  Le paramétrage est toujours retenu : la file est là quand même.
	await expect(page.getByRole('cell', { name: '#7' })).toBeVisible();
	relacher();
});

test('Admin › onglet de réglage : il attend le paramétrage, puis s’ouvre sur ses valeurs', async ({
	page,
}) => {
	const relacher = await retenirParametrage(page);
	await page.goto('/admin?onglet=legal');
	await expect(page.locator('.etat-chargement')).toBeVisible();
	await expect(page.locator('.tiptap, .ProseMirror')).toHaveCount(0);
	relacher();
	await expect(page.locator('.etat-chargement')).toHaveCount(0);
	await expect(page.getByText('Mentions lues')).toBeVisible();
});
