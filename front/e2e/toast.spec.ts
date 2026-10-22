/*
 *  **Le toast** (#2168, audit `apple-design` du 23/10/2026).
 *
 *  Une erreur partait au bout de 4 s, sans moyen de la garder ni de la fermer :
 *  qui ne regardait pas l'écran à cet instant ne la lisait jamais. Elle reste
 *  désormais jusqu'à ce qu'on la ferme ; un message de réussite part seul, mais
 *  son compte à rebours s'arrête tant que le pointeur est dessus.
 *
 *  L'horloge est simulée (`page.clock`) : avancer de dix secondes ne coûte rien,
 *  et le test ne dépend pas de la vitesse du poste.
 *
 *  Le geste qui fait parler le toast est l'import des lots : son téléversement
 *  rend à la fois une réussite et une erreur (`OngletImportLots`).
 */
import type { Page } from '@playwright/test';
import type { ResultatImportLots } from '../src/lib/api/patrimoine';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };
const ERREUR = 'Ligne 3 : lot inconnu';

const TELEVERSEMENT: ResultatImportLots = {
	importes: 2,
	ignores: 0,
	doublons: 0,
	erreurs: [ERREUR],
	auto_resolus: 0,
	auto_sans_occupant: 0,
	auto_hors_perimetre: 0,
	auto_erreurs: [],
};

async function importer(page: Page) {
	await page.clock.install();
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/lots/admin/imports/upload') return TELEVERSEMENT;
	});
	await page.goto('/admin?onglet=imports&source=lots');
	await attendreHydratation(page);
	await page
		.locator('input[type=file]')
		.first()
		.setInputFiles({
			name: 'lots.xlsx',
			mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
			buffer: Buffer.from('PK'),
		});
	await page.getByRole('button', { name: 'Importer', exact: true }).click();
	//  Le pointeur loin des messages : sinon le survol suspendrait les comptes à rebours.
	await page.mouse.move(5, 5);
	await expect(page.locator('.toast-success')).toBeVisible();
	await expect(page.locator('.toast-error')).toHaveText(ERREUR);
}

test('une erreur reste affichée jusqu’à ce qu’on la ferme, et s’annonce sur-le-champ', async ({
	page,
}) => {
	await importer(page);
	await expect(page.locator('.annonce-toast[aria-live="assertive"]')).toHaveText(ERREUR);

	await page.clock.runFor(10_000);
	await expect(page.locator('.toast-success')).toHaveCount(0);
	await expect(page.locator('.toast-error')).toBeVisible();

	await page.locator('.toast-error').getByRole('button', { name: 'Fermer le message' }).click();
	await expect(page.locator('.toast-error')).toHaveCount(0);
});

test('le survol suspend le départ d’un message de réussite', async ({ page }) => {
	await importer(page);
	await page.locator('.toast-success').hover();
	await page.clock.runFor(6_000);
	await expect(page.locator('.toast-success')).toBeVisible();

	await page.mouse.move(5, 5);
	await page.clock.runFor(5_000);
	await expect(page.locator('.toast-success')).toHaveCount(0);
});
