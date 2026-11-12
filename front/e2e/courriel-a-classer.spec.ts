/*
 *  **Un courriel qu'aucune affaire ne désigne se classe dans Espace CS › Courriels (#2555).**
 *
 *  Le 05/11/2026, « Re: Portillon Hostachy » d'un membre du conseil était refusé —
 *  « rien ne permet de dire à quel ticket » — alors que l'affaire du portillon était
 *  ouverte. Il attend désormais : sa ligne dit « À classer », son aperçu et les
 *  affaires proches se lisent à l'ouverture, et chaque geste part avec ce qu'il dit.
 *  Le vrai onglet, API simulée.
 *
 *  🔴 12/11/2026 — un seul bouton plein. Toucher une proposition rattachait sur-le-champ,
 *  et « Créer une affaire » devenait plein quand rien n'était proposé. Désormais une
 *  proposition se RETIENT (`aria-pressed`), « Rattacher à #… » — inactif tant que rien
 *  n'est choisi — conclut, et créer comme écarter se confirment.
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

test('Espace CS › Courriels : un message à classer se rattache à l’affaire proposée @mise-en-page', async ({
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
	const ligne = lignes.nth(0);
	const proposee = ligne.locator('.suggestion', { hasText: '#TK-570894' });
	const principal = ligne.locator('.btn-primary');
	await expect(proposee).toBeVisible();
	//  UN seul bouton plein, inactif tant que rien n'est choisi ; les autres issues
	//  sont secondaires.
	await expect(principal).toHaveCount(1);
	await expect(principal).toHaveText('Rattacher à l’affaire choisie');
	await expect(principal).toBeDisabled();
	await expect(proposee).toHaveAttribute('aria-pressed', 'false');
	for (const nom of ['Créer une affaire', 'Écarter'])
		await expect(ligne.getByRole('button', { name: nom })).toHaveClass(/btn-outline/);

	await attendreSansDefilementHorizontal(page, 'dans l’onglet Courriels, message à classer ouvert');

	//  Toucher la proposition la RETIENT, sans rien envoyer : le bouton la nomme.
	let envois = 0;
	page.on('request', (r) => {
		if (r.method() === 'POST' && r.url().includes('/a-classer/')) envois += 1;
	});
	await proposee.click();
	await expect(proposee).toHaveAttribute('aria-pressed', 'true');
	await expect(principal).toBeEnabled();
	await expect(principal).toHaveText('Rattacher à #TK-570894 · Portillon bd Hostachy bloque ferme');
	expect(envois, 'toucher une proposition n’envoie rien').toBe(0);

	//  L'alignement, mesuré (demandé le 05/11/2026) : la proposition, le champ du
	//  numéro et le bouton principal ont le même bord droit ; les deux autres
	//  issues, la même hauteur.
	const bloc = ligne.locator('.classer');
	const mesures = await bloc.evaluate((el) => {
		const r = (s: string) => el.querySelector(s)!.getBoundingClientRect();
		const issues = [...el.querySelectorAll('.autres-issues .btn')].map((b) =>
			b.getBoundingClientRect(),
		);
		return {
			droites: [r('.suggestion').right, r('.champ-numero input').right, r('.rattacher').right],
			issues: issues.map((b) => b.height),
		};
	});
	expect(Math.abs(mesures.droites[0] - mesures.droites[1]), 'champ décalé').toBeLessThan(1);
	expect(Math.abs(mesures.droites[0] - mesures.droites[2]), 'bouton décalé').toBeLessThan(1);
	expect(Math.abs(mesures.issues[0] - mesures.issues[1]), 'issues inégales').toBeLessThan(1);
	await ligne.screenshot({
		path: `test-results/courriel-a-classer-${test.info().project.name}.png`,
	});

	//  Créer une affaire se confirme, et « Revenir » ne fait rien partir.
	await ligne.getByRole('button', { name: 'Créer une affaire' }).click();
	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('une affaire à part');
	await boite.getByRole('button', { name: 'Revenir' }).click();
	await expect(boite).toHaveCount(0);
	expect(envois).toBe(0);

	//  Le bouton principal part vers la route du rattachement, avec le numéro retenu.
	const envoi = page.waitForRequest(
		(r) =>
			r.method() === 'POST' && r.url().includes('/api/courriels-affaires/a-classer/3/rattacher'),
	);
	await principal.click();
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
	await champ.fill('#TK-300601');
	//  Le numéro tapé l'emporte sur toute proposition : le bouton le nomme.
	await expect(page.locator('.classer .btn-primary')).toHaveText('Rattacher à #TK-300601');
	const envoi = page.waitForRequest((r) => r.method() === 'POST' && r.url().includes('/rattacher'));
	await champ.press('Enter');
	expect((await envoi).postDataJSON()).toEqual({ numero: 'TK-300601' });
});
