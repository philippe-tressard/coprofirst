/*
 *  Admin › Copropriété › **Périmètres** et **Équipements** — la même tête de
 *  liste (01/11/2026, signalé à l'écran : le bouton et la recherche n'étaient
 *  pas alignés, et Périmètres n'avait pas de recherche).
 *
 *  Ce que seul l'écran rendu peut dire :
 *   - « + Nouveau … » est sur sa rangée, AU-DESSUS de la recherche, à gauche,
 *     sur l'axe de la liste (`.actions-onglet`) ;
 *   - il s'efface pendant la saisie (`BoutonNouveau`) ;
 *   - la recherche des périmètres garde les ancêtres d'un nœud trouvé.
 */
import type { Page } from '@playwright/test';
import {
	attendreHydratation,
	EQUIPEMENTS_TEMOINS,
	expect,
	MEMBRE_CS,
	simulerApi,
	test,
} from './aides';
import { noeud } from './perimetres-temoins';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const ARBRE = [
	noeud({ id: 1, code: 'batiments', libelle: 'Bâtiments', selectionnable: false }),
	noeud({ id: 2, code: 'bat:1', libelle: 'Bâtiment 1', parent: 'batiments', profondeur: 1 }),
	noeud({ id: 3, code: 'bat:1/toit', libelle: 'Toit', parent: 'bat:1', profondeur: 2 }),
	noeud({ id: 4, code: 'parking', libelle: 'Parking' }),
];

async function ouvrir(page: Page, onglet: 'perimetres' | 'equipements') {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/perimetres') return ARBRE;
		if (chemin === '/api/equipements') return EQUIPEMENTS_TEMOINS;
		return undefined;
	});
	await page.goto(`/admin?onglet=${onglet}`);
	await attendreHydratation(page);
}

for (const [onglet, libelle] of [
	['perimetres', 'Nouveau périmètre'],
	['equipements', 'Nouvel équipement'],
] as const) {
	test(`${onglet} : l’action au-dessus de la recherche, effacée pendant la saisie`, async ({
		page,
	}) => {
		await ouvrir(page, onglet);
		const bouton = page.getByRole('button', { name: `+ ${libelle}` });
		const recherche = page.getByRole('searchbox');
		const liste = page.locator('.ref-list, .carte-liste').first();
		await expect(bouton).toBeVisible();
		await expect(recherche).toBeVisible();

		const b = (await bouton.boundingBox())!;
		const r = (await recherche.boundingBox())!;
		const l = (await liste.boundingBox())!;
		expect(b.y + b.height).toBeLessThanOrEqual(r.y);
		//  Sur l'axe gauche de la liste — à droite, il dépassait la saisie plafonnée.
		expect(Math.abs(b.x - l.x)).toBeLessThanOrEqual(1);

		await bouton.click();
		await expect(bouton).toHaveCount(0);
		await expect(page.getByRole('button', { name: 'Annuler' })).toBeVisible();
	});
}

test('périmètres : la recherche garde les ancêtres du nœud trouvé', async ({ page }) => {
	await ouvrir(page, 'perimetres');
	const titres = page.locator('.ref-titre');
	await expect(titres).toHaveText(['Bâtiments', 'Bâtiment 1', 'Toit', 'Parking']);

	await page.getByRole('searchbox').fill('toit');
	await expect(titres).toHaveText(['Bâtiments', 'Bâtiment 1', 'Toit']);

	await page.getByRole('searchbox').fill('piscine');
	await expect(page.getByText('Aucun périmètre ne correspond')).toBeVisible();

	await page.getByRole('button', { name: 'Effacer la saisie' }).click();
	await expect(titres).toHaveCount(4);
});
