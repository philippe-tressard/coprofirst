/*
 *  **« Mes lots » en dit le plus possible à son copropriétaire** (#2215).
 *
 *  Ce que l'état descriptif a rendu — la clé, ce qu'elle finance, la part en
 *  dix-millièmes et en pourcentage, le nombre de lots qui y contribuent — et ce qu'il faut
 *  en savoir : les alertes du lot, jamais bloquantes. Pour qui possède plusieurs lots, une
 *  même clé pèse pour la SOMME de ses parts. Lots FICTIFS ; l'API simulée rend la forme
 *  réelle de `LotRead` (type `MonLot`).
 */
import type { Page } from '@playwright/test';
import type { MonLot } from '../src/lib/api/patrimoine';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const PROPRIETAIRE = { ...MEMBRE_CS, role: 'résident', roles: ['résident'] };
const BAILLEUR = {
	...MEMBRE_CS,
	statut: 'copropriétaire_bailleur',
	role: 'propriétaire',
	roles: ['propriétaire'],
};

function lot(champs: Partial<MonLot>): MonLot {
	return {
		id: 1,
		numero: '901',
		type: 'appartement',
		type_appartement: 'T3',
		etage: 1,
		superficie: null,
		batiment_id: 1,
		batiment_nom: 'Bât. 1',
		est_logement_de_reference: true,
		type_lien: 'propriétaire',
		nature: 'logement',
		numero_usage: null,
		circulation: null,
		perimetres: [{ code: 'bat:1', libelle: 'Bât. 1', relation: 'situe_dans', derive: true }],
		quotes_parts: [
			{
				cle: 'generales',
				libelle: 'Charges générales',
				numerateur: 91,
				denominateur: 10006,
				perimetre: null,
				nb_lots: 174,
				somme: 10006,
			},
			{
				cle: 'ascenseur-a',
				libelle: 'Ascenseur A',
				numerateur: 34,
				denominateur: 10000,
				perimetre: 'Bât. 4 › Ascenseur',
				nb_lots: 38,
				somme: 9900,
			},
		],
		explication: 'Ce logement contribue aux charges Charges générales pour 91/10 006.',
		alertes: [
			{
				code: 'cle_en_ecart',
				gravite: 'avertissement',
				message: '« Ascenseur A » : les parts lues totalisent 9 900 pour 10 000.',
				lots: [],
			},
		],
		...champs,
	};
}

const PLACE = lot({
	id: 2,
	numero: '902',
	type: 'parking',
	type_appartement: null,
	etage: -2,
	est_logement_de_reference: false,
	nature: 'parking',
	numero_usage: '5 & 6',
	quotes_parts: [
		{
			cle: 'ascenseur-a',
			libelle: 'Ascenseur A',
			numerateur: 6,
			denominateur: 10000,
			perimetre: 'Bât. 4 › Ascenseur',
			nb_lots: 38,
			somme: 9900,
		},
	],
	explication: null,
	alertes: [],
});

async function ouvrir(page: Page, compte: object, lots: MonLot[]) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return compte;
		if (chemin === '/api/lots/mes-lots') return lots;
	});
	await page.goto('/mon-lot');
	await attendreHydratation(page);
}

test('les charges d’un lot se lisent clé par clé, en dix-millièmes et en pourcentage', async ({
	page,
}) => {
	await ouvrir(page, PROPRIETAIRE, [lot({})]);
	const charges = page.locator('.carte-lot').getByRole('table', { name: /charges/i });
	const ascenseur = charges.getByRole('row', { name: /Ascenseur A/ });
	await expect(ascenseur).toContainText('Bât. 4 › Ascenseur');
	await expect(ascenseur).toContainText('38 lots y contribuent');
	await expect(ascenseur).toContainText('34/10 000');
	await expect(ascenseur).toContainText('0,34 %');
	await expect(charges.getByRole('row', { name: /Charges générales/ })).toContainText('0,91 %');
});

test('l’alerte d’un lot se dit sur sa carte, sans rien bloquer', async ({ page }) => {
	await ouvrir(page, PROPRIETAIRE, [lot({})]);
	const carte = page.locator('.carte-lot');
	await expect(carte.getByText('À savoir')).toBeVisible();
	await expect(carte.getByText(/totalisent 9 900 pour 10 000/)).toBeVisible();
});

test('un lot sans alerte n’affiche aucun bloc d’alerte', async ({ page }) => {
	await ouvrir(page, PROPRIETAIRE, [lot({ alertes: [] })]);
	await expect(page.locator('.carte-lot').getByText('À savoir')).toHaveCount(0);
});

test('plusieurs lots : une même clé pèse pour la somme de mes parts', async ({ page }) => {
	await ouvrir(page, PROPRIETAIRE, [lot({}), PLACE]);
	const totaux = page.getByRole('region', { name: 'Mes charges, tous mes lots' });
	const ascenseur = totaux.getByRole('row', { name: /Ascenseur A/ });
	//  34 + 6 = 40 dix-millièmes, sur deux de mes lots.
	await expect(ascenseur).toContainText('40/10 000');
	await expect(ascenseur).toContainText('2 de mes lots');
	await expect(ascenseur).toContainText('0,40 %');
});

test('un seul lot : pas de total, il redirait la fiche du lot', async ({ page }) => {
	await ouvrir(page, PROPRIETAIRE, [lot({})]);
	await expect(page.getByRole('region', { name: 'Mes charges, tous mes lots' })).toHaveCount(0);
});

test('la carte du bailleur porte la désignation, les charges et les alertes', async ({ page }) => {
	await ouvrir(page, BAILLEUR, [lot({}), PLACE]);
	const carte = page.locator('.lot-possede-card', { hasText: '902' });
	await expect(carte).toContainText('Porte ou place 5 & 6');
	await expect(carte.getByRole('table', { name: /charges/i })).toContainText('0,06 %');
	const premiere = page.locator('.lot-possede-card', { hasText: '901' });
	await expect(premiere.getByText(/totalisent 9 900 pour 10 000/)).toBeVisible();
	await expect(page.getByRole('region', { name: 'Mes charges, tous mes lots' })).toBeVisible();
});
