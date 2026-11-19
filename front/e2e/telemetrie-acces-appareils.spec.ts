/*
 *  **Télémétrie : l'accès se déplie sur ses types d'appareil** (#2774).
 *
 *  L'API sert, sous chaque canal, ses classes d'appareil avec leur part du canal ; le
 *  bloc « Accès » les montre quand on déplie le canal. Un canal dont aucune vue ne dit
 *  son appareil (« Non précisé » seul) ne se déplie pas : il n'y a rien à détailler.
 *  API simulée.
 */
import type { Page } from '@playwright/test';
import {
	attendreHydratation,
	expect,
	MEMBRE_CS,
	simulerApi,
	TABLEAU_TELEMETRIE_VIDE,
	test,
} from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const CANAUX = [
	{
		canal: 'site',
		libelle: 'Web',
		vues: 6,
		part: 60,
		visiteurs: 2,
		appareils: [{ appareil: 'non_precise', libelle: 'Non précisé', vues: 6, part: 100 }],
	},
	{
		canal: 'ios',
		libelle: 'App Apple',
		vues: 4,
		part: 40,
		visiteurs: 1,
		appareils: [
			{ appareil: 'iphone', libelle: 'iPhone', vues: 3, part: 75 },
			{ appareil: 'ipad', libelle: 'iPad', vues: 1, part: 25 },
		],
	},
];

async function ouvrir(page: Page) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/telemetry/dashboard')
			return {
				...TABLEAU_TELEMETRIE_VIDE,
				scope: 'jour',
				kpi: { vues: 10, utilisateurs: 3, pages: 1 },
				top_pages: [{ page: '/tickets', total: 10, uniques: 3 }],
				canaux: CANAUX,
			};
	});
	await page.goto('/admin?onglet=telemetry');
	await attendreHydratation(page);
}

test('un canal se déplie sur ses appareils, avec leur part du canal', async ({ page }) => {
	await ouvrir(page);
	const deplier = page.getByRole('button', { name: /App Apple/ });
	await expect(deplier).toHaveAttribute('aria-expanded', 'false');
	await expect(page.getByRole('cell', { name: 'iPad', exact: true })).toHaveCount(0);

	await deplier.click();
	await expect(deplier).toHaveAttribute('aria-expanded', 'true');
	await expect(page.getByRole('row', { name: /iPhone\s+3\s+75 % du canal/ })).toBeVisible();
	await expect(page.getByRole('row', { name: /iPad\s+1\s+25 % du canal/ })).toBeVisible();

	await deplier.click();
	await expect(page.getByRole('cell', { name: 'iPad', exact: true })).toHaveCount(0);
});

test('un canal sans appareil précisé ne se déplie pas', async ({ page }) => {
	await ouvrir(page);
	await expect(page.getByRole('cell', { name: 'Web', exact: true })).toBeVisible();
	await expect(page.getByRole('button', { name: /^Web$/ })).toHaveCount(0);
});
