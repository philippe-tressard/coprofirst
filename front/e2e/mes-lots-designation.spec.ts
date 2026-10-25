/*
 *  **« Mes lots » dit où est un lot et ce qu'il emporte** (#2215).
 *
 *  Un résident du bâtiment 1 qui détient une place desservie par le bâtiment 3 :
 *  la carte de la place dit « Desservi par Bât. 3 › Ascenseur », jamais « Bât. 3 »
 *  en « Situé dans », ses tantièmes et la phrase qui explique la charge — rendue
 *  telle que le serveur l'écrit. Lots FICTIFS ; l'API simulée rend la forme réelle
 *  de `LotRead` (type `MonLot`).
 */
import type { Page } from '@playwright/test';
import type { MonLot } from '../src/lib/api/patrimoine';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';

const RESIDENT = { ...MEMBRE_CS, role: 'résident', roles: ['résident'] };
const BAILLEUR = {
	...MEMBRE_CS,
	statut: 'copropriétaire_bailleur',
	role: 'propriétaire',
	roles: ['propriétaire'],
};

const PHRASE =
	'Cette place (SS 2) est desservie par Bât. 3 › Ascenseur et Bât. 3 › Escaliers. ' +
	'Elle contribue aux charges Générales pour 8/10 000.';

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
		perimetres: [
			{ code: 'bat:1', libelle: 'Bât. 1', relation: 'situe_dans', derive: true },
			{
				code: 'bat:1/escaliers',
				libelle: 'Bât. 1 › Escaliers',
				relation: 'desservi_par',
				derive: true,
			},
		],
		quotes_parts: [],
		explication: 'Ce logement est desservi par Bât. 1 › Escaliers.',
		alertes: [],
		...champs,
	};
}

const PLACE = lot({
	id: 2,
	numero: '902',
	type: 'parking',
	type_appartement: null,
	etage: -2,
	batiment_id: null,
	batiment_nom: null,
	est_logement_de_reference: false,
	nature: 'parking',
	numero_usage: '5 & 6',
	perimetres: [
		{
			code: 'bat:3/ascenseur',
			libelle: 'Bât. 3 › Ascenseur',
			relation: 'desservi_par',
			derive: true,
		},
		{
			code: 'bat:3/escaliers',
			libelle: 'Bât. 3 › Escaliers',
			relation: 'desservi_par',
			derive: true,
		},
	],
	quotes_parts: [
		{
			cle: 'generales',
			libelle: 'Générales',
			numerateur: 8,
			denominateur: 10000,
			perimetre: null,
			nb_lots: 174,
			somme: 10000,
		},
	],
	explication: PHRASE,
});

async function ouvrir(page: Page, compte: object) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return compte;
		if (chemin === '/api/lots/mes-lots') return [lot({}), PLACE];
	});
	await page.goto('/mon-lot');
	await attendreHydratation(page);
}

test('la place desservie par un autre bâtiment dit sa circulation, sa part et pourquoi', async ({
	page,
}) => {
	await ouvrir(page, RESIDENT);
	const carte = page.locator('.carte-lot');
	await expect(carte.getByText('Situé dans')).toBeVisible();
	await page.getByRole('button', { name: /902/ }).click();
	await expect(carte.getByText('Bât. 3 › Ascenseur, Bât. 3 › Escaliers')).toBeVisible();
	await expect(carte.getByText('Situé dans')).toHaveCount(0);
	await expect(carte.getByText('5 & 6')).toBeVisible();
	await expect(carte.getByText(PHRASE)).toBeVisible();
	await expect(carte.getByRole('table', { name: /charges/i })).toContainText('Générales');
});

test('la carte du bailleur porte la même phrase', async ({ page }) => {
	await ouvrir(page, BAILLEUR);
	await expect(page.getByText(PHRASE)).toBeVisible();
});
