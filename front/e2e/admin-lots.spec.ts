/*
 *  **Admin › Copropriété › Lots** (#2216) — constats en tête, un seul lot déplié,
 *  un périmètre dérivé ne se retire pas, un périmètre posé à la main si. Les clés de
 *  charges se règlent comme le syndic les appelle (#2252).
 *  Lots FICTIFS ; l'API simulée rend la forme réelle (`MonLot`, `ConstatPatrimoine`).
 */
import type { Page } from '@playwright/test';
import type { ConstatPatrimoine } from '../src/lib/api/etat-descriptif';
import type { CleDeChargesReglee } from '../src/lib/api/lots-admin';
import type { MonLot } from '../src/lib/api/patrimoine';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const PLACE: MonLot = {
	id: 2,
	numero: '902',
	type: 'parking',
	type_appartement: null,
	etage: -2,
	superficie: null,
	batiment_id: null,
	batiment_nom: null,
	est_logement_de_reference: false,
	type_lien: null,
	nature: 'parking',
	numero_usage: '5 & 6',
	circulation: null,
	perimetres: [
		{
			code: 'bat:3/ascenseur',
			libelle: 'Bât. 3 › Ascenseur',
			relation: 'desservi_par',
			derive: true,
		},
		{ code: 'bat:3/toit', libelle: 'Bât. 3 › Toit', relation: 'desservi_par', derive: false },
	],
	quotes_parts: [{ cle: 'generales', libelle: 'Générales', numerateur: 8, denominateur: 10000 }],
	explication: null,
};

const CONSTATS: ConstatPatrimoine[] = [
	{
		code: 'sans_proprietaire',
		gravite: 'avertissement',
		message: 'Lot sans propriétaire actif : personne n’y est rattaché comme copropriétaire.',
		lots: ['902'],
	},
];

const CLE: CleDeChargesReglee = {
	id: 7,
	code: 'escalier-x',
	libelle: 'Escalier X',
	denominateur: 10000,
	description: 'L’escalier du bâtiment X',
	appelee: true,
	libelle_syndic: null,
};

async function ouvrir(page: Page) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/lots/admin/tous') return [PLACE];
		if (chemin === '/api/lots/admin/constats') return CONSTATS;
		if (chemin === '/api/lots/admin/cles') return [CLE];
		if (chemin === '/api/lots/admin/cles/7') return { ...CLE, appelee: false };
	});
	await page.goto('/admin?onglet=lots');
	await attendreHydratation(page);
}

test('les constats en tête, et le détail d’un lot distingue dérivé et posé à la main', async ({
	page,
}) => {
	await ouvrir(page);
	await expect(page.getByText('Lot sans propriétaire actif')).toBeVisible();
	await expect(page.getByRole('cell', { name: 'Bât. 3 › Ascenseur, Bât. 3 › Toit' })).toBeVisible();
	await page.getByRole('button', { name: 'Périmètres du lot 902' }).click();
	await expect(page.getByRole('button', { name: 'Retirer Bât. 3 › Toit' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Retirer Bât. 3 › Ascenseur' })).toHaveCount(0);
	await expect(page.getByText('Tantièmes : Générales 8/10000')).toBeVisible();
});

test('une clé de charges se règle comme le syndic l’appelle, chaque réglage part seul', async ({
	page,
}) => {
	await ouvrir(page);
	const reglage = page.locator('section.config-section', {
		has: page.getByRole('heading', { name: 'Clés de charges' }),
	});
	await expect(reglage).toContainText('L’escalier du bâtiment X');

	const appel = page.waitForRequest(
		(r) => r.method() === 'PATCH' && r.url().endsWith('/api/lots/admin/cles/7'),
	);
	await reglage.getByRole('checkbox', { name: 'Appelée par le syndic' }).uncheck();
	expect((await appel).postDataJSON()).toEqual({ appelee: false });

	const libelle = page.waitForRequest(
		(r) => r.method() === 'PATCH' && r.url().endsWith('/api/lots/admin/cles/7'),
	);
	const champ = reglage.getByLabel('Sur l’appel de fonds');
	await champ.fill('CHARGES ESCALIER X');
	await champ.blur();
	expect((await libelle).postDataJSON()).toEqual({ libelle_syndic: 'CHARGES ESCALIER X' });
});
