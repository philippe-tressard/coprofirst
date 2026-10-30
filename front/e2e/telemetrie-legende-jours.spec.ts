/*
 *  **Télémétrie, vue Mois : la légende du graphe** (04/10/2026) — trente dates
 *  complètes se superposaient et devenaient illisibles. Le bâton dit désormais
 *  le numéro du jour, le mois seulement au premier bâton et au 1ᵉʳ du mois, et
 *  le jour le plus actif porte le 🏆 sur SON bâton (la ligne qui le disait est
 *  supprimée). Le pic se mesure en utilisateurs : ce n'est pas le bâton le plus
 *  haut, et le test le garde ainsi.
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
import { attendreLisible, forcerTheme } from './contraste-ecran';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

//  Du 4 septembre au 3 octobre 2026 : le mois change au milieu.
const VUES = [
	140, 620, 410, 320, 345, 320, 470, 545, 548, 315, 340, 395, 455, 240, 555, 195, 330, 420, 450,
	465, 500, 420, 420, 630, 500, 415, 460, 280, 330, 495,
];
const JOURS = VUES.map((total, i) => {
	const d = new Date(Date.UTC(2026, 8, 4 + i));
	const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
	const jj = String(d.getUTCDate()).padStart(2, '0');
	return { label: `${mm}-${jj}`, total, uniques: 3 };
});

//  La vue Année : un bâton LARGE par mois, sous la clé du serveur (« AAAA-MM »).
const MOIS = VUES.slice(0, 12).map((total, i) => ({
	label: `2026-${String(i + 1).padStart(2, '0')}`,
	total,
	uniques: 3,
}));

async function ouvrir(page: Page, jourPointe: string, annee = false) {
	const chart = annee ? MOIS : JOURS;
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/telemetry/dashboard')
			return {
				...TABLEAU_TELEMETRIE_VIDE,
				scope: annee ? 'annee' : 'mois',
				chart,
				chart_label: annee ? 'Vues par mois (12 mois)' : 'Vues par jour (30 j)',
				kpi: {
					vues: 12000,
					utilisateurs: 6,
					pages: 20,
					jour_pointe: { jour: jourPointe, uniques: 6 },
				},
			};
	});
	await page.goto('/admin?onglet=telemetry');
	await attendreHydratation(page);
	//  L'onglet se charge au geste depuis la v2.133.1 : l'hydratation ne dit pas que
	//  le graphe est rendu, et une lecture immédiate (`allTextContents`) le voyait vide.
	await expect(page.locator('.tl-bar-label')).toHaveCount(chart.length);
}

test('le 🏆 est sur le bâton du jour le plus actif, la ligne qui le disait a disparu', async ({
	page,
}) => {
	await ouvrir(page, '2026-09-29');
	const pic = page.locator('.tl-bar-col', { has: page.locator('.tl-pic') });
	await expect(pic).toHaveCount(1);
	await expect(pic.locator('.tl-bar-label')).toHaveText('29');
	await expect(pic.locator('.tl-bulle')).toContainText('29');
	await expect(pic.locator('.tl-bulle')).toContainText('6 utilisateurs');
	await expect(page.getByText('Jour le plus actif —')).toHaveCount(0);
	//  Ni le grand bloc « Pic d'utilisateurs » : le même chiffre est déjà en première ligne.
	await expect(page.getByText("Pic d'utilisateurs en un jour")).toHaveCount(0);
	//  Le pic n'est PAS le bâton le plus haut (27/09) : il se mesure en utilisateurs.
	await expect(page.locator('.tl-bar-pic')).toHaveCount(1);
});

test('légende : un numéro par jour, le mois au premier bâton et au 1ᵉʳ seulement', async ({
	page,
}) => {
	await ouvrir(page, '2026-09-29');
	const jours = await page.locator('.tl-bar-label').allTextContents();
	expect(jours).toHaveLength(30);
	expect(jours.every((t) => /^\d{1,2}$/.test(t.trim()))).toBe(true);
	const mois = (await page.locator('.tl-bar-mois').allTextContents())
		.map((t) => t.trim())
		.filter(Boolean);
	expect(mois).toEqual(['sept.', 'oct.']);
});

test('la bulle et le mois ne rallongent jamais la zone du graphe', async ({ page }) => {
	//  Au téléphone, trente bâtons de 16 px + leurs écarts + la marge font déjà 544 px
	//  et la zone défile, comme avant : c'est ce plancher-là, et rien de plus.
	const NATUREL = 30 * 16 + 29 * 2 + 4;
	for (const jour of ['2026-09-04', '2026-09-27', '2026-10-03']) {
		await ouvrir(page, jour);
		const { large, contenu } = await page
			.locator('.tl-chart')
			.evaluate((el) => ({ large: el.clientWidth, contenu: el.scrollWidth }));
		expect(contenu, `pic au ${jour}`).toBeLessThanOrEqual(Math.max(large, NATUREL) + 1);
	}
});

test('@sombre — Télémétrie : le graphe des vues par jour, son 🏆 et sa bulle se lit au thème sombre', async ({
	page,
}) => {
	await ouvrir(page, '2026-09-29');
	await forcerTheme(page, 'sombre');
	//  Les marques du graphique sont claires exprès au sombre : mesurées à 3:1.
	await attendreLisible(page, '#contenu', { marques: '.tl-bar' });
});

//  Les bâtons LARGES (Année, Total) étaient en `--color-primary-light` : 1,1:1 sur la
//  carte dans les deux thèmes (#2296). Ils se mesurent à 3:1, au clair et au sombre.
for (const theme of ['clair', 'sombre'] as const)
	test(`@${theme} — Télémétrie : les bâtons de la vue Année se voient sur la carte`, async ({
		page,
	}) => {
		await ouvrir(page, '2026-09-29', true);
		await expect(page.locator('.tl-bar-large')).toHaveCount(MOIS.length);
		await forcerTheme(page, theme);
		await attendreLisible(page, '#contenu', { marques: '.tl-bar' });
	});
