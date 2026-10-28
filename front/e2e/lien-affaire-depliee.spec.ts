/*
 *  **Le lien d'une affaire montre SA CARTE, dépliée** (15/10/2026).
 *
 *  Signalé à l'écran : *« quand je transmets un lien d'une affaire, cette
 *  affaire est affichée d'une manière différente du fil d'actualité ou de la
 *  page actualité »*. `/tickets/42` rendait une fiche à part — en-tête, boutons
 *  « Changer le statut », Historique. Il rend désormais la carte de la liste,
 *  seule et dépliée, par la même porte (`#lib/affaires-en-liste`).
 *
 *  Ce test vérifie ce que l'écran MONTRE — API simulée, compte témoin :
 *  - une seule carte, dépliée d'emblée, et son corps (le fil de la carte) ;
 *  - aucun reste de la fiche (« Changer le statut ») ;
 *  - « Saisi par … pour … » (au conseil) et l'envoi au syndic sont DANS la
 *    carte — ils ne vivaient que sur la fiche ;
 *  - le titre plie la carte, comme dans la liste ;
 *  - le fil des messages reste sous la carte, avec son « Répondre ».
 */
import { attendreHydratation, expect, simulerApi, test } from './aides';

const AFFAIRE = {
	id: 7,
	numero: 'TK-109008',
	titre: 'Portillon bloqué',
	description: 'Le portillon du parking ne se referme plus.',
	categorie: 'etude_travaux',
	statut: 'en_cours',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	cree_le: '2026-09-29T10:00:00',
	mis_a_jour_le: '2026-09-29T10:00:00',
	perimetre_cible: [],
	photos_urls: [],
	fichiers_urls: [],
	saisi_pour_affichage: 'Mme Durand',
	destinataire_syndic: true,
};
const SUITE = {
	id: 31,
	ticket_id: 7,
	type: 'commentaire',
	contenu: '<p>Devis demandé au serrurier.</p>',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	cree_le: '2026-09-30T09:00:00',
};

test.beforeEach(async ({ page }) => {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets/7') return AFFAIRE;
		if (chemin === '/api/tickets/7/evolutions') return [SUITE];
		if (chemin === '/api/tickets/7/messages') return [];
	});
	await page.goto('/tickets/7');
	await attendreHydratation(page);
});

test('une seule carte, dépliée, sans les restes de la fiche', async ({ page }) => {
	const cartes = page.locator('.carte-liste');
	await expect(cartes).toHaveCount(1);
	await expect(cartes.first()).toHaveClass(/(^|\s)expanded(\s|$)/);
	await expect(cartes.first().locator('.carte-corps')).toContainText('Devis demandé au serrurier.');
	await expect(page.getByText('Changer le statut')).toHaveCount(0);
	const corps = cartes.first().locator('.carte-corps');
	await expect(corps).toContainText('Saisi par CS Témoin pour Mme Durand');
	await expect(corps).toContainText('Envoyé au syndic');
	await page.screenshot({
		path: `test-results/lien-affaire-depliee-${test.info().project.name}.png`,
		fullPage: true,
	});
});

test('le titre plie la carte, comme dans la liste', async ({ page }) => {
	const carte = page.locator('.carte-liste').first();
	await carte.getByRole('button', { name: /Portillon bloqué/ }).click();
	await expect(carte).not.toHaveClass(/(^|\s)expanded(\s|$)/);
	await expect(carte.locator('.carte-corps')).toHaveCount(0);
});

test('le fil des messages reste sous la carte', async ({ page }) => {
	await expect(page.locator('.affaire-seule ~ .messages .carte-repondre')).toBeVisible();
});
