/*
 *  **L'atelier de l'état descriptif** — Admin › Imports, source « État descriptif » (#2213).
 *
 *  Trois promesses de l'écran, vérifiées contre l'API simulée (forme RÉELLE du
 *  serveur, le type `EtatDescriptif`) :
 *  - un constat bloquant tient le bouton « Appliquer » fermé, et le dit ;
 *  - la correspondance des lettres part telle qu'elle est saisie — ce que l'écran
 *    MONTRE est ce qui PART ;
 *  - appliquer passe par une confirmation, puis rend compte.
 *
 *  Lots et lettres fictifs.
 */
import type { Page } from '@playwright/test';
import type { BilanEtatDescriptif, EtatDescriptif } from '../src/lib/api/etat-descriptif';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

function etat(applicable: boolean): EtatDescriptif {
	return {
		importe_le: '2026-10-24T10:00:00',
		applique_le: null,
		cles: [{ code: 'generales', libelle: 'Générales', denominateur: 100 }],
		lignes: [
			{
				rang: 2,
				lot: '901',
				batiment: 'X',
				nature: 'T2',
				nature_lue: 'logement',
				numero_usage: null,
				niveau: '1',
				circulation: null,
				lot_origine: null,
				source: null,
				quotes: { generales: 60 },
			},
			{
				rang: 3,
				lot: '902',
				batiment: null,
				nature: 'Parking',
				nature_lue: 'parking',
				numero_usage: '5 & 6',
				niveau: '-2',
				circulation: 'X',
				lot_origine: null,
				source: null,
				quotes: { generales: 40 },
			},
		],
		constats: applicable
			? []
			: [
					{
						code: 'lettre',
						gravite: 'bloquant',
						message: 'Lettre de bâtiment sans correspondance : saisir la lettre de l’acte.',
						lots: [],
					},
				],
		lettres_citees: ['X'],
		batiments: [{ id: 1, libelle: 'Bât. 1', lettre_rcp: applicable ? 'X' : null }],
		applicable,
	};
}

const BILAN: BilanEtatDescriptif = {
	lots: 2,
	cles_creees: 1,
	quotes_modifiees: 2,
	perimetres_modifies: 5,
};

async function ouvrir(page: Page, applicable: boolean) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/lots/admin/etat-descriptif') return etat(applicable);
		if (chemin === '/api/lots/admin/etat-descriptif/lettres') return etat(true);
		if (chemin === '/api/lots/admin/etat-descriptif/appliquer') return BILAN;
	});
	await page.goto('/admin?onglet=imports&source=etat-descriptif');
	await attendreHydratation(page);
}

test('un constat bloquant tient « Appliquer » fermé et le dit', async ({ page }) => {
	await ouvrir(page, false);
	await expect(page.getByText('Sans correspondance : X.')).toBeVisible();
	await expect(page.getByRole('button', { name: 'Appliquer au patrimoine' })).toBeDisabled();
	await expect(page.getByText('Un contrôle bloque')).toBeVisible();
});

test('la lettre saisie est celle qui part', async ({ page }) => {
	await ouvrir(page, false);
	await page.getByLabel('Bât. 1').fill('x');
	const envoi = page.waitForRequest(
		(r) => r.url().endsWith('/api/lots/admin/etat-descriptif/lettres') && r.method() === 'PUT',
	);
	await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
	const corps = (await envoi).postDataJSON();
	expect(corps).toEqual({ correspondances: [{ batiment_id: 1, lettre_rcp: 'x' }] });
	await expect(page.getByRole('button', { name: 'Appliquer au patrimoine' })).toBeEnabled();
});

test('appliquer passe par une confirmation, puis rend compte', async ({ page }) => {
	await ouvrir(page, true);
	await page.getByRole('button', { name: 'Appliquer au patrimoine' }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Appliquer', exact: true }).click();
	await expect(page.locator('.toast-success')).toContainText('2 lot(s) désigné(s)');
});
