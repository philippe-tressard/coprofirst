/*
 *  **Le corps déplié d'une carte d'affaire se charge au geste, sans saut**
 *  (12/10/2026, #1860).
 *
 *  `CarteTicket` importait tout ce que seul le dépliage affiche — fil, synthèse,
 *  transferts, fiche de lecture, panneau d'options : la page Affaires le
 *  téléchargeait à l'ouverture. Il vit dans `CorpsCarteTicket`, chargé par
 *  `ChargementDiffere` et PRÉCHARGÉ quand la main s'approche de la carte.
 *  `lint:poids-ouverture` tient le build ; ce test tient ce que seul un écran
 *  montre :
 *
 *  1. l'ouverture ne le demande pas ; le survol le demande, avant le clic ;
 *  2. retenu, le corps est déjà là — c'est lui qui entre en fondu — et
 *     l'attente s'annonce DEDANS ; relâché, la fiche s'y rend.
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, estLeModule, expect, retenirModule, simulerApi, test } from './aides';

const AFFAIRE = {
	id: 7,
	numero: 'TK-124301',
	titre: 'Porte du local vélos',
	description: 'La gâche ne tient plus.',
	categorie: 'panne',
	statut: 'ouvert',
	priorite: 'normale',
	auteur_id: 1,
	auteur_nom: 'CS Témoin',
	perimetre_cible: ['résidence'],
	photos_urls: [],
	fichiers_urls: [],
	archivee: false,
	natures: ['activite'],
	cree_le: '2026-09-20T10:00:00',
	mis_a_jour_le: '2026-09-20T10:00:00',
};

const CORPS = 'CorpsCarteTicket.svelte';

async function ouvrirAffaires(page: Page) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/tickets') return [AFFAIRE];
		if (chemin === '/api/tickets/7') return AFFAIRE;
		if (chemin === '/api/tickets/7/evolutions') return [];
	});
}

test('l’ouverture ne télécharge pas le corps ; le survol le précharge', async ({ page }) => {
	await ouvrirAffaires(page);
	const demandes: string[] = [];
	page.on('request', (r) => {
		if (estLeModule(r.url(), CORPS)) demandes.push(r.url());
	});
	await page.goto('/tickets');
	await attendreHydratation(page);
	const titre = page.locator('.carte-liste').first().getByText(AFFAIRE.titre);
	await expect(titre).toBeVisible();
	expect(demandes, 'le corps est demandé dès l’ouverture').toHaveLength(0);

	await titre.hover();
	await expect.poll(() => demandes.length, 'le survol ne précharge pas le corps').toBe(1);

	await titre.click();
	await expect(page.locator('.carte-liste .carte-corps')).toContainText(AFFAIRE.description);
	await expect(page.locator('.carte-liste .carte-corps')).toContainText('Créée le');
});

test('retenu, le corps entre d’abord et annonce son attente dedans', async ({ page }) => {
	await ouvrirAffaires(page);
	const relacher = await retenirModule(page, CORPS);
	await page.goto('/tickets');
	await attendreHydratation(page);
	await page.locator('.carte-liste').first().getByText(AFFAIRE.titre).click();

	//  Le conteneur est là : c'est LUI qui porte le fondu d'entrée (#1579).
	const corps = page.locator('.carte-liste .carte-corps');
	await expect(corps).toBeAttached();
	await expect(corps.locator('.attente-differee')).toBeAttached();

	relacher();
	await expect(corps.locator('.attente-differee')).toHaveCount(0);
	await expect(corps).toContainText(AFFAIRE.description);
});
