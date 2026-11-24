/*
 *  **Un sondage ouvert montre ses résultats provisoires avant le vote** (16/11/2026).
 *
 *  Demandé à l'écran : en cliquant sur un sondage, voir où en est le décompte. Quand
 *  l'auteur a laissé les résultats visibles avant la clôture (`resultats_visibles`,
 *  décidé par l'API), la fiche montre les barres AU-DESSUS du formulaire de vote,
 *  marquées « provisoires » ; elles remplacent le « N votes » posé à côté de chaque
 *  choix. Case décochée : rien avant la clôture, l'API n'envoie pas les décomptes.
 *  Sondage clos : les mêmes barres, sans la mention.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const OPTIONS_COMPTEES = [
	//  `part` est SERVIE par l'API (#3060) : l'écran ne la recalcule plus.
	{
		id: 31,
		libelle: 'Beige',
		ordre: 0,
		champ_libre: false,
		nb_votes: 2,
		part: 67,
		reponses_libres: [],
	},
	{
		id: 32,
		libelle: 'Gris perle',
		ordre: 1,
		champ_libre: false,
		nb_votes: 1,
		part: 33,
		reponses_libres: [],
	},
];

const FICHE = {
	id: 7,
	question: 'Peinture du hall ?',
	description: null,
	cloture_le: null,
	cloture_forcee: false,
	resultats_publics: true,
	auteur_id: 2,
	cree_le: '2026-10-01T10:00:00',
	perimetre_cible: ['résidence'],
	public_cible: ['résidents'],
	options: OPTIONS_COMPTEES,
	mon_vote: null,
	cloture: false,
	commentaires: [],
	resultats_visibles: true,
	nouveau: false,
};

async function ouvrir(page: Page, fiche: object): Promise<void> {
	await simulerApi(page, (chemin) => (chemin === '/api/sondages/7' ? fiche : undefined));
	await page.goto('/sondages/7');
	await attendreHydratation(page);
}

const PROVISOIRES = 'Résultats provisoires : le sondage est encore ouvert.';

test('ouvert, résultats visibles : les barres provisoires précèdent le vote', async ({ page }) => {
	await ouvrir(page, FICHE);
	await expect(page.getByText(PROVISOIRES)).toBeVisible();
	await expect(page.getByText('67 %')).toBeVisible();
	await expect(page.getByText('33 %')).toBeVisible();
	//  Le vote reste offert, sous les barres.
	await expect(page.getByRole('radio')).toHaveCount(2);
	await expect(page.getByRole('button', { name: 'Voter' })).toBeVisible();
	const barres = await page.getByText(PROVISOIRES).boundingBox();
	const premierChoix = await page.getByRole('radio').first().boundingBox();
	expect(barres!.y).toBeLessThan(premierChoix!.y);
	//  Le décompte ne se dit plus deux fois : rien à côté des choix.
	await expect(page.locator('.option-label').filter({ hasText: /vote/ })).toHaveCount(0);
});

test('ouvert, résultats masqués : rien avant la clôture, le vote seul', async ({ page }) => {
	await ouvrir(page, {
		...FICHE,
		resultats_publics: false,
		resultats_visibles: false,
		options: OPTIONS_COMPTEES.map(({ id, libelle, ordre, champ_libre }) => ({
			id,
			libelle,
			ordre,
			champ_libre,
		})),
	});
	await expect(page.getByRole('radio')).toHaveCount(2);
	await expect(page.getByText(PROVISOIRES)).toHaveCount(0);
	await expect(page.getByText(/%$/)).toHaveCount(0);
});

test('la part affichée est celle que l’API sert, jamais recalculée des votes (#3060)', async ({
	page,
}) => {
	//  2 votes sur 3 feraient 67 % ; l'API dit 60 : l'écran lit l'API.
	await ouvrir(page, {
		...FICHE,
		options: [
			{ ...OPTIONS_COMPTEES[0], part: 60 },
			{ ...OPTIONS_COMPTEES[1], part: 40 },
		],
	});
	await expect(page.getByText('60 %')).toBeVisible();
	await expect(page.getByText('40 %')).toBeVisible();
	await expect(page.getByText('67 %')).toHaveCount(0);
	await expect(page.locator('.result-bar').first()).toHaveAttribute('style', /width:\s*60%/);
});

test('clos : les résultats, sans la mention « provisoires »', async ({ page }) => {
	await ouvrir(page, { ...FICHE, cloture: true, cloture_forcee: true });
	await expect(page.getByText('67 %')).toBeVisible();
	await expect(page.getByText(PROVISOIRES)).toHaveCount(0);
	await expect(page.getByRole('radio')).toHaveCount(0);
});
