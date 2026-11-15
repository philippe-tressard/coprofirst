/*
 *  **On note un prestataire SANS contrat** (14/11/2026) — depuis sa fiche, pas
 *  seulement depuis la carte d'un contrat.
 *
 *  Le geste « ⭐ Noter » n'existait que sur un contrat : une intervention ponctuelle,
 *  hors contrat, ne pouvait pas être notée. Ce test tient :
 *
 *  1. la fiche d'un prestataire qui n'a AUCUN contrat porte « Noter » ;
 *  2. trois états, des cases par nature, un commentaire libre : l'envoi porte l'état,
 *     la phrase composée par les cases PUIS le texte libre, et aucun contrat ;
 *  3. un avis « Mauvais » sans commentaire n'est pas envoyé — cas zéro de la règle.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, simulerApi, test } from './aides';

const OTIS = {
	id: 1,
	nom: 'Ascenseurs Témoin',
	specialite: 'ascenseur',
	type_prestataire: 'maintenance_depannage',
	actif: true,
	archivee: false,
};

const NOTATION = {
	id: 77,
	prestataire_id: 1,
	note: 5,
	etat: 'excellent',
	commentaire: 'Points forts : délai respecté.\nTrès réactif.',
	contrat_id: null,
	auteur_id: 1,
	auteur_nom: null,
	cree_le: '2026-11-14T10:00:00',
};

async function ouvrirLaFiche(page: Page) {
	const envoyes: Record<string, unknown>[] = [];
	await simulerApi(page, (api) => {
		if (api === '/api/prestataires') return [OTIS];
		if (api === '/api/prestataires/contrats') return []; //  aucun contrat
		if (api === '/api/prestataires/affaires-a-noter')
			return [
				{
					id: 42,
					titre: 'Barillet de la porte du parking',
					statut: 'resolu',
					intervient: true,
					intervenants: 'Ascenseurs Témoin',
				},
				{
					id: 43,
					titre: 'Fuite sur le chauffe-eau',
					statut: 'ouvert',
					intervient: false,
					intervenants: '',
				},
			];
	});
	//  La création : une route plus récente, essayée avant celle du simulateur.
	await page.route('**/api/prestataires/notations', (route) => {
		if (route.request().method() !== 'POST') return route.fallback();
		envoyes.push(route.request().postDataJSON());
		return route.fulfill({
			status: 201,
			contentType: 'application/json',
			body: JSON.stringify(NOTATION),
		});
	});
	await page.goto('/prestataires');
	await attendreHydratation(page);
	const carte = page.locator('#presta-1');
	await carte.getByText('Ascenseurs Témoin').first().click();
	return { carte, envoyes };
}

test('la fiche d’un prestataire sans contrat se note : état, cases et commentaire libre', async ({
	page,
}) => {
	const { carte, envoyes } = await ouvrirLaFiche(page);
	await expect(carte.getByText('Contrats').first()).toBeVisible(); //  la fiche est dépliée
	expect(envoyes).toEqual([]); //  cas zéro : rien n'est parti

	await carte.getByRole('button', { name: '⭐ Noter' }).click();
	await carte.getByRole('button', { name: 'Excellent', exact: true }).click();
	await carte.getByLabel('délai respecté').check();
	await carte.getByLabel('Commentaire libre').fill('Très réactif.');
	await carte.getByRole('button', { name: 'Enregistrer' }).click();

	await expect.poll(() => envoyes.length).toBe(1);
	expect(envoyes[0]).toMatchObject({
		prestataire_id: 1,
		etat: 'excellent',
		commentaire: 'Points forts : délai respecté.\nTrès réactif.',
	});
	//  Une fiche, pas un contrat : rien ne rattache la note à un contrat.
	expect(envoyes[0]).not.toHaveProperty('contrat_id');
});

test('un avis « Mauvais » sans commentaire n’est pas envoyé', async ({ page }) => {
	const { carte, envoyes } = await ouvrirLaFiche(page);

	await carte.getByRole('button', { name: '⭐ Noter' }).click();
	await carte.getByRole('button', { name: 'Mauvais', exact: true }).click();
	await carte.getByRole('button', { name: 'Enregistrer' }).click();

	await expect(page.locator('.toast-error')).toContainText('doit être justifié');
	expect(envoyes).toEqual([]);

	//  Justifié, il part.
	await carte.getByLabel('retard').check();
	await carte.getByRole('button', { name: 'Enregistrer' }).click();
	await expect.poll(() => envoyes.length).toBe(1);
	expect(envoyes[0]).toMatchObject({ etat: 'mauvais', commentaire: 'Points faibles : retard.' });
});

test('on note le couple prestataire / affaire : l’affaire choisie part avec l’avis', async ({
	page,
}) => {
	const { carte, envoyes } = await ouvrirLaFiche(page);

	await carte.getByRole('button', { name: '⭐ Noter' }).click();
	await carte
		.getByLabel('Affaire concernée')
		.selectOption({ label: 'Barillet de la porte du parking' });
	await carte.getByRole('button', { name: 'Neutre', exact: true }).click();
	await carte.getByRole('button', { name: 'Enregistrer' }).click();

	await expect.poll(() => envoyes.length).toBe(1);
	expect(envoyes[0]).toMatchObject({ prestataire_id: 1, etat: 'neutre', ticket_id: 42 });
});

test('une affaire où le prestataire n’intervient pas exige la confirmation de son ajout', async ({
	page,
}) => {
	const { carte, envoyes } = await ouvrirLaFiche(page);

	await carte.getByRole('button', { name: '⭐ Noter' }).click();
	await carte.getByLabel('Affaire concernée').selectOption({ label: 'Fuite sur le chauffe-eau' });
	await carte.getByRole('button', { name: 'Neutre', exact: true }).click();
	await carte.getByRole('button', { name: 'Enregistrer' }).click();
	//  Pas de confirmation : rien n'est envoyé.
	await expect(page.locator('.toast-error')).toContainText("Confirmez l'ajout");
	expect(envoyes).toEqual([]);

	await carte.getByLabel(/Ajouter Ascenseurs Témoin comme intervenant/).check();
	await carte.getByRole('button', { name: 'Enregistrer' }).click();
	await expect.poll(() => envoyes.length).toBe(1);
	expect(envoyes[0]).toMatchObject({ ticket_id: 43, confirmer_ajout: true });
});
