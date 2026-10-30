/*
 *  **Télémétrie : les nombres et les mois se lisent à la française** (#2358,
 *  30/10/2026) — la vue Année affichait « 27054 », « 3864.9 », « Record mois —
 *  2026-05 » et une légende « 2026-04 … 2026-10 » : les valeurs du serveur
 *  rendues telles quelles, là où la règle du projet (CLAUDE.md, Front n° 2)
 *  passe par `fmtNombre` et `fmtMonthYear`. Ce spec lit l'écran RENDU, avec les
 *  valeurs du constat.
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

//  Les clés du serveur, telles qu'il les rend en vue Année (`AAAA-MM`).
const MOIS = ['2026-04', '2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10'];
const VUES = [3120, 4700, 3550, 2980, 3410, 4210, 5084];

async function ouvrir(page: Page) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/telemetry/dashboard')
			return {
				...TABLEAU_TELEMETRIE_VIDE,
				scope: 'annee',
				chart: MOIS.map((label, i) => ({ label, total: VUES[i], uniques: 9 })),
				chart_label: 'Vues par mois (12 mois)',
				kpi: {
					vues: 27054,
					pages: 34,
					mois_actifs: 7,
					moy_vues_mois: 3864.9,
					record_jour: { jour: '2026-05-12', uniques: 14 },
					record_mois: { mois: '2026-05', uniques: 21 },
				},
				top_pages: [
					{ page: '/tickets', total: 7500, uniques: 18 },
					{ page: '/fil', total: 19554, uniques: 20 },
				],
			};
	});
	await page.goto('/admin?onglet=telemetry');
	await attendreHydratation(page);
	await expect(page.locator('.tl-bar-label')).toHaveCount(MOIS.length);
}

/** Un texte lu, chaque espace — insécable compris (`\s` les couvre) — ramené à « ». */
const espaces = (t: string | null) => (t ?? '').replace(/\s/g, ' ');

/** Des textes lus, rognés, les vides écartés. */
const rognes = (t: string[]) => t.map((x) => x.trim()).filter(Boolean);

test('les indicateurs groupent les milliers et prennent la virgule décimale', async ({ page }) => {
	await ouvrir(page);
	const valeurs = page.locator('.tl-kpi-value');
	await expect(valeurs.filter({ hasText: /^\s*27\s054\s*$/ })).toHaveCount(1);
	await expect(valeurs.filter({ hasText: /^\s*3\s864,9\s*$/ })).toHaveCount(1);
});

test('le record du mois et la légende disent le mois en toutes lettres', async ({ page }) => {
	await ouvrir(page);
	await expect(page.getByText('🏆 Record mois — mai 2026')).toBeVisible();
	//  La légende : le mois court sous chaque bâton, l'année au premier et en janvier.
	await expect
		.poll(async () => rognes(await page.locator('.tl-bar-label').allTextContents()))
		.toEqual(['avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.']);
	await expect
		.poll(async () => rognes(await page.locator('.tl-bar-mois').allTextContents()))
		.toEqual(['2026']);
	//  La bulle du bâton le dit aussi en toutes lettres, et ses nombres groupés.
	await expect(page.locator('.tl-bar-col').nth(1)).toHaveAttribute(
		'title',
		/^mai 2026 — 4\s700 vues, 9 uniques$/,
	);
});

test('l’axe et le Top pages groupent les milliers ; aucune clé AAAA-MM à l’écran', async ({
	page,
}) => {
	await ouvrir(page);
	//  Plus haut bâton 5 084 → graduation de 1 300 en 1 300 : « 5 200 » en tête.
	await expect
		.poll(async () => espaces(await page.locator('.tl-y-tick').first().textContent()))
		.toBe('5 200');
	const top = page.locator('.table-wrap').first();
	await expect(top).toContainText(/7\s500/);
	await expect(top).toContainText(/27\s054/);
	await expect(top).toContainText(/27,7\s%/);
	const contenu = page.locator('#contenu');
	await expect(contenu).not.toContainText(/\b\d{4}-\d{2}\b/);
	await expect(contenu).not.toContainText(/\d\.\d/);
});
