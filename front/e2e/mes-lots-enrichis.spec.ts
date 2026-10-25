/*
 *  **« Mes lots » : mes charges en un seul tableau croisé** (#2215, #2251 — maquette A du
 *  25/10/2026).
 *
 *  Ce qu'on lit : une ligne par clé, une colonne par lot (nommé), le total et le
 *  pourcentage ; sous chaque clé, ce qu'elle finance et combien de lots y contribuent ;
 *  l'écart d'une clé dit UNE fois sous le tableau, plus sur chaque carte ; la mention que
 *  seul le syndic fait foi ; des cartes de lot qui ne répètent plus les chiffres et
 *  renvoient à leur colonne. Aligné sur l'appel de fonds (#2252) : le libellé du syndic
 *  sous la clé, les clés non appelées repliées avec leur part, « Contacter le syndic ».
 *  Lots FICTIFS ; l'API simulée rend la forme réelle de `LotRead`.
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
const NOTE =
	'Les parts que le règlement attribue à l’ensemble des lots totalisent 9 900 pour 10 000.';

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
				description: 'Le sol et les parties communes générales',
				note: null,
			},
			{
				cle: 'escalier-a',
				libelle: 'Escalier A',
				numerateur: 34,
				denominateur: 10000,
				perimetre: null,
				nb_lots: 38,
				somme: 9900,
				description: 'L’escalier du bâtiment A, du rez-de-chaussée aux étages',
				note: NOTE,
			},
		],
		explication: null,
		alertes: [
			{
				code: 'sans_numero_usage',
				gravite: 'information',
				message: 'Le numéro de la place ou de la cave n’est pas renseigné.',
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
			cle: 'escalier-a-prime',
			libelle: "Escalier A'",
			numerateur: 6,
			denominateur: 10000,
			perimetre: null,
			nb_lots: 41,
			somme: 10000,
			description: 'L’escalier qui dessert les deux niveaux de sous-sol',
			note: null,
		},
		{
			cle: 'generales',
			libelle: 'Charges générales',
			numerateur: 9,
			denominateur: 10006,
			perimetre: null,
			nb_lots: 174,
			somme: 10006,
			description: 'Le sol et les parties communes générales',
			note: null,
		},
	],
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

const charges = (page: Page) =>
	page.getByRole('region', { name: 'Mes charges selon le règlement' });

test('plusieurs lots : une colonne par lot nommé, le total et ce que finance chaque clé', async ({
	page,
}) => {
	await ouvrir(page, PROPRIETAIRE, [lot({}), PLACE]);
	const tableau = charges(page).getByRole('table');
	await expect(tableau.getByRole('columnheader', { name: 'Logement 901' })).toBeVisible();
	await expect(tableau.getByRole('columnheader', { name: 'Place 902' })).toBeVisible();
	const generales = tableau.getByRole('row', { name: /Charges générales/ });
	//  91 + 9 = 100 dix-millièmes, au total.
	await expect(generales).toContainText('100/10 006');
	await expect(generales).toContainText('Le sol et les parties communes générales');
	await expect(generales).toContainText('174 lots y contribuent');
	//  La place ne contribue pas à l'escalier des étages : « — », pas un zéro.
	const etages = tableau.getByRole('row', { name: /^Escalier A L’escalier du bâtiment A/ });
	await expect(etages).toContainText('—');
	await expect(tableau.getByRole('row', { name: /Escalier A'/ })).toContainText(
		'L’escalier qui dessert les deux niveaux de sous-sol',
	);
});

test('l’écart d’une clé se dit une fois sous le tableau, et seul le syndic fait foi', async ({
	page,
}) => {
	await ouvrir(page, PROPRIETAIRE, [lot({}), PLACE]);
	await expect(charges(page).getByText(NOTE)).toHaveCount(1);
	await expect(charges(page)).toContainText(
		'seuls les appels de fonds et les comptes tenus par le syndic',
	);
	//  La carte ne porte plus l'écart : il concerne la copropriété, pas le lot.
	await expect(page.locator('.carte-lot').getByText(NOTE)).toHaveCount(0);
});

test('un seul lot : pas de colonne Total, sa colonne porte la part entière', async ({ page }) => {
	await ouvrir(page, PROPRIETAIRE, [lot({})]);
	const tableau = charges(page).getByRole('table');
	await expect(tableau.getByRole('columnheader', { name: 'Total' })).toHaveCount(0);
	await expect(tableau.getByRole('row', { name: /Charges générales/ })).toContainText('91/10 006');
	await expect(tableau.getByRole('row', { name: /Charges générales/ })).toContainText('0,91 %');
});

test('la carte d’un lot ne répète plus les chiffres et renvoie à sa colonne', async ({ page }) => {
	await ouvrir(page, PROPRIETAIRE, [lot({})]);
	const carte = page.locator('.carte-lot');
	await expect(carte.getByRole('table')).toHaveCount(0);
	await expect(carte.getByText('À savoir')).toHaveCount(0); // une information, pas une alerte
	await carte.getByRole('link', { name: /Voir sa colonne dans le tableau des charges/ }).click();
	await expect(charges(page).getByRole('columnheader', { name: 'Logement 901' })).toHaveClass(
		/surligne/,
	);
});

test('la vue du bailleur porte le même tableau, et ses cartes renvoient à leur colonne', async ({
	page,
}) => {
	await ouvrir(page, BAILLEUR, [lot({}), PLACE]);
	await expect(charges(page).getByRole('columnheader', { name: 'Place 902' })).toBeVisible();
	const carte = page.locator('.lot-possede-card', { hasText: '902' });
	await expect(carte).toContainText('Porte ou place 5 & 6');
	await expect(carte.getByRole('table')).toHaveCount(0);
	await expect(carte.getByRole('link', { name: /Voir sa colonne/ })).toBeVisible();
});

test('sur smartphone, au-delà de deux lots : une clé par bloc, le détail par lot dessous', async ({
	page,
}) => {
	await page.setViewportSize({ width: 390, height: 844 });
	const cave = lot({
		...PLACE,
		id: 3,
		numero: '903',
		type: 'cave',
		nature: 'cave',
		numero_usage: null,
		quotes_parts: PLACE.quotes_parts?.map((q) => ({ ...q, numerateur: 1 })) ?? null,
	});
	await ouvrir(page, PROPRIETAIRE, [lot({}), PLACE, cave]);
	await expect(charges(page).getByRole('table')).toBeHidden();
	const bloc = charges(page).locator('li', { hasText: "Escalier A'" });
	await expect(bloc).toContainText('L’escalier qui dessert les deux niveaux de sous-sol');
	await expect(bloc).toContainText('Place 902 : 6 · Cave 903 : 1');
});

test('aligné sur l’appel de fonds : le libellé du syndic, les clés non appelées repliées', async ({
	page,
}) => {
	const [generales, escalier] = lot({}).quotes_parts ?? [];
	await ouvrir(page, PROPRIETAIRE, [
		lot({
			quotes_parts: [
				{ ...generales, appelee: true, libelle_syndic: 'CHARGES COMMUNES X' },
				{ ...escalier, appelee: false, libelle_syndic: null },
			],
		}),
	]);
	const tableau = charges(page).getByRole('table');
	await expect(tableau.getByRole('row', { name: /Charges générales/ })).toContainText(
		'Sur l’appel de fonds : CHARGES COMMUNES X',
	);
	//  Non appelée : hors du tableau, jamais cachée — repliée, avec sa part.
	await expect(tableau.getByRole('row', { name: /Escalier A/ })).toHaveCount(0);
	const repli = charges(page).locator('details', {
		hasText: 'Prévues au règlement, non appelées actuellement (1)',
	});
	await repli.locator('summary').click();
	await expect(repli).toContainText('Escalier A');
	await expect(repli).toContainText('34/10 000');
	await expect(charges(page).getByRole('link', { name: 'Contacter le syndic' })).toHaveAttribute(
		'href',
		'/annuaire#syndic',
	);
});
