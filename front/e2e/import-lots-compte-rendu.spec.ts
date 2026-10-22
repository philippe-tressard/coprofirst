/*
 *  **Le compte rendu de l'import des lots** (#1685, 04/10/2026).
 *
 *  `OngletImportLots` lisait `auto_skipped_locataire` / `auto_skipped_no_lot`
 *  après le téléversement, `skipped_locataire` / `skipped_no_lot` après
 *  « Auto-résoudre » ; le serveur rend `auto_sans_occupant`,
 *  `auto_hors_perimetre`, `sans_occupant` et `hors_perimetre`
 *  (`utils/resolution_lots.resoudre_imports`). Les messages d'information ne
 *  s'affichaient donc jamais.
 *
 *  L'API simulée rend ici la forme RÉELLE du serveur — celle des types
 *  `ResultatImportLots` et `ResolutionImportLots` —, jamais celle que l'écran
 *  attendait : c'est l'écart que le test doit voir.
 */
import type { Page } from '@playwright/test';
import type { ResolutionImportLots, ResultatImportLots } from '../src/lib/api/patrimoine';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const STATS = {
	total: 0,
	en_attente: 0,
	utilisateur_lie: 0,
	lot_lie: 0,
	resolu: 0,
	ignore: 0,
	avec_user: 0,
};

const TELEVERSEMENT: ResultatImportLots = {
	importes: 12,
	ignores: 0,
	doublons: 1,
	erreurs: [],
	auto_resolus: 4,
	auto_sans_occupant: 3,
	auto_hors_perimetre: 2,
	auto_erreurs: [],
};

const RESOLUTION: ResolutionImportLots = {
	resolus: 1,
	sans_occupant: 5,
	hors_perimetre: 6,
	erreurs: [],
};

async function ouvrir(page: Page) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/lots/admin/imports/stats') return STATS;
		if (chemin === '/api/lots/admin/imports/upload') return TELEVERSEMENT;
		if (chemin === '/api/lots/admin/imports/auto-resoudre') return RESOLUTION;
	});
	await page.goto('/admin?onglet=imports&source=lots');
	await attendreHydratation(page);
}

test('le téléversement dit combien d’imports restent sans occupant ou hors périmètre', async ({
	page,
}) => {
	await ouvrir(page);
	await page
		.locator('input[type=file]')
		.first()
		.setInputFiles({
			name: 'lots.xlsx',
			mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
			buffer: Buffer.from('PK'),
		});
	await page.getByRole('button', { name: 'Importer', exact: true }).click();
	//  Le geste a bien abouti : sans ce témoin, un clic perdu passerait pour le défaut.
	await expect(page.locator('.toast-success')).toContainText('Import : 12 ajoutés');
	const messages = page.locator('.toast-info');
	await expect(messages.filter({ hasText: /^3 import\(s\) sans occupant/ })).toBeVisible();
	await expect(messages.filter({ hasText: /^2 import\(s\) hors périmètre/ })).toBeVisible();
});

test('« Auto-résoudre » dit combien d’imports restent sans occupant ou hors périmètre', async ({
	page,
}) => {
	await ouvrir(page);
	await page.getByRole('button', { name: /Auto-résoudre copropriétaires/ }).click();
	await expect(page.locator('.toast-success')).toContainText('1 copropriétaire(s) résolu(s)');
	const messages = page.locator('.toast-info');
	await expect(messages.filter({ hasText: /^5 import\(s\) sans occupant/ })).toBeVisible();
	await expect(messages.filter({ hasText: /^6 import\(s\) hors périmètre/ })).toBeVisible();
});
