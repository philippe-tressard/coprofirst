/*
 *  **Un courriel qu'aucune affaire ne désigne se classe dans Espace CS › Courriels (#2555).**
 *
 *  Le 05/11/2026, « Re: Portillon Hostachy » d'un membre du conseil était refusé —
 *  « rien ne permet de dire à quel ticket » — alors que l'affaire du portillon était
 *  ouverte. Il attend désormais : sa ligne dit « À classer », son aperçu et les
 *  affaires proches se lisent à l'ouverture, et chaque geste part avec ce qu'il dit.
 *  Le vrai onglet, API simulée.
 */
import { expect, simulerApi, test } from './aides';
import { attendreSansDefilementHorizontal } from './defilement';

const A_CLASSER = {
	id: 9,
	releve_le: '2026-11-05T11:33:00',
	envoye_le: '2026-11-05T11:29:00',
	expediteur: 'Membre du conseil',
	objet: 'Re: Portillon Hostachy',
	decision: 'a_classer',
	motif: 'aucune affaire n’est désignée : le message attend d’être classé ci-dessous',
	ticket_id: null,
	affaire: null,
	a_classer: {
		id: 3,
		statut: 'a_classer',
		apercu: 'Le portillon est de nouveau bloqué ce matin.',
		suggestions: [{ id: 12, numero: 'TK-570894', titre: 'Portillon bd Hostachy bloque ferme' }],
	},
};

const CLASSE = {
	...A_CLASSER,
	id: 8,
	objet: 'Fuite au 3e',
	motif: 'affaire #TK-600001 créée par Paul M.',
	ticket_id: 13,
	affaire: 'TK-600001',
	a_classer: { id: 2, statut: 'cree', apercu: '', suggestions: [] },
};

test('Espace CS › Courriels : un message à classer se rattache à l’affaire proposée', async ({
	page,
}) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/courriels-affaires') return { limite: 20, messages: [A_CLASSER, CLASSE] };
		if (chemin.startsWith('/api/courriels-affaires/a-classer/'))
			return { bilan: 'rattaché à l’affaire #TK-570894 par Paul M.', ticket_id: 12 };
		return undefined;
	});
	await page.goto('/espace-cs/courriels');

	const lignes = page.locator('.jv-ligne');
	await expect(lignes).toHaveCount(2);
	await expect(lignes.nth(0).locator('summary .badge')).toHaveText('À classer');
	await expect(lignes.nth(0).locator('summary .badge')).toHaveClass(/badge-orange/);
	//  Classé, la ligne dit ce qui a été fait — et n'offre plus de geste.
	await expect(lignes.nth(1).locator('summary .badge')).toHaveText('Affaire créée');

	await lignes.nth(0).locator('summary').click();
	await expect(lignes.nth(0).locator('blockquote')).toHaveText(
		'Le portillon est de nouveau bloqué ce matin.',
	);
	const proposee = lignes.nth(0).getByRole('button', { name: /Rattacher à #TK-570894/ });
	await expect(proposee).toBeVisible();
	await expect(lignes.nth(0).getByRole('button', { name: 'Créer une affaire' })).toBeVisible();
	await expect(lignes.nth(0).getByRole('button', { name: 'Écarter' })).toBeVisible();
	await expect(
		lignes.nth(0).getByRole('button', { name: 'Rattacher', exact: true }),
	).toBeDisabled();

	await attendreSansDefilementHorizontal(page, 'dans l’onglet Courriels, message à classer ouvert');
	await lignes.nth(0).screenshot({
		path: `test-results/courriel-a-classer-${test.info().project.name}.png`,
	});

	//  Le geste part vers la route du rattachement, avec le numéro proposé.
	const envoi = page.waitForRequest(
		(r) =>
			r.method() === 'POST' && r.url().includes('/api/courriels-affaires/a-classer/3/rattacher'),
	);
	await proposee.click();
	expect((await envoi).postDataJSON()).toEqual({ numero: 'TK-570894' });

	await lignes.nth(1).locator('summary').click();
	await expect(lignes.nth(1).getByRole('button', { name: 'Créer une affaire' })).toHaveCount(0);
});

test('Espace CS › Courriels : un autre numéro se tape, Entrée le rattache', async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/courriels-affaires') return { limite: 20, messages: [A_CLASSER] };
		if (chemin.startsWith('/api/courriels-affaires/a-classer/'))
			return { bilan: 'rattaché à l’affaire #TK-300601 par Paul M.', ticket_id: 14 };
		return undefined;
	});
	await page.goto('/espace-cs/courriels');
	await page.locator('.jv-ligne summary').click();
	const champ = page.getByLabel('Autre affaire');
	await champ.fill('TK-300601');
	const envoi = page.waitForRequest((r) => r.method() === 'POST' && r.url().includes('/rattacher'));
	await champ.press('Enter');
	expect((await envoi).postDataJSON()).toEqual({ numero: 'TK-300601' });
});
