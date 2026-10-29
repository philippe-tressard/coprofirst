/*
 *  **L'onglet Utilisateurs de l'administration** (#779, 30/09/2026).
 *
 *  Extrait de `admin/+page.svelte` en composant (`OngletUtilisateurs`, et sa
 *  modale d'accueil `ModaleAccueilArrivant`). Ce test tient ce que l'extraction
 *  devait conserver — la liste, la recherche, la modale d'accueil — et ce
 *  qu'elle a corrigé en passant : un chargement en échec restait une liste vide
 *  sans un mot (`try/finally` sans `catch`, invisible à `lint:catch-vide`).
 */
import type { Page } from '@playwright/test';
import { attendreHydratation, expect, MEMBRE_CS, simulerApi, test } from './aides';
import { attendreLisible, forcerTheme } from './contraste-ecran';

const ADMIN = { ...MEMBRE_CS, role: 'admin', roles: ['admin'] };

const COMPTES = [
	{
		id: 21,
		prenom: 'Jeanne',
		nom: 'Martin',
		email: 'jeanne@exemple.test',
		statut: 'copropriétaire_résident',
		role: 'résident',
		roles: ['résident'],
		actif: true,
		batiment_id: null,
	},
	{
		id: 22,
		prenom: 'Paul',
		nom: 'Durand',
		email: 'paul@exemple.test',
		statut: 'locataire',
		role: 'résident',
		roles: ['résident'],
		actif: true,
		batiment_id: null,
	},
];

async function ouvrir(page: Page, echec = false) {
	await simulerApi(page, (chemin) => {
		if (chemin === '/api/auth/me') return ADMIN;
		if (chemin === '/api/admin/utilisateurs') return COMPTES;
	});
	if (echec)
		await page.route(
			(url) => url.pathname === '/api/admin/utilisateurs',
			(route) =>
				route.fulfill({
					status: 500,
					contentType: 'application/json',
					body: JSON.stringify({ detail: 'Panne simulée' }),
				}),
		);
	await page.goto('/admin?onglet=utilisateurs');
	await attendreHydratation(page);
}

test('la liste s’affiche, et la recherche la filtre', async ({ page }) => {
	await ouvrir(page);
	const lignes = page.locator('table tbody tr');
	await expect(lignes).toHaveCount(2);
	await page.getByRole('searchbox').or(page.getByRole('textbox').first()).fill('Durand');
	await expect(lignes).toHaveCount(1);
	await expect(lignes.first()).toContainText('Paul DURAND');
});

test('un chargement en échec le dit, au lieu d’une liste vide', async ({ page }) => {
	await ouvrir(page, true);
	await expect(page.getByText('Impossible d’afficher les utilisateurs')).toBeVisible();
	await expect(page.getByText('Aucun résultat')).toHaveCount(0);
});

test('le bouton 🏠 ouvre l’accueil de l’arrivant, avec ses deux champs', async ({ page }) => {
	await ouvrir(page);
	await page.getByRole('button', { name: 'Accueil nouvel arrivant' }).first().click();
	const boite = page.getByRole('dialog');
	await expect(boite).toContainText('Accueil nouvel arrivant');
	await expect(boite.getByLabel('Bâtiment / logement')).toBeVisible();
	await expect(boite.getByLabel('Ancien résident')).toBeVisible();
	await boite.getByRole('button', { name: 'Annuler' }).click();
	await expect(page.getByRole('dialog')).toHaveCount(0);
});

//  🔴 Sur téléphone, le tableau dépassait l'écran et ses dernières colonnes
//  (rôles, actions) étaient inatteignables : la carte posait `overflow: hidden`,
//  qui annulait le défilement que `.card` reçoit sous 767 px (22/10/2026). On
//  mesure le GESTE — un défilement horizontal sur le tableau —, pas la règle CSS.
//  ⚠️ Pas de `scrollLeft` : le survol de Playwright fait défiler jusqu'à la cible
//  même un conteneur `overflow: hidden`, et ce critère passait sur le défaut.
test('au doigt : le tableau défile jusqu’à sa dernière colonne', async ({ page, isMobile }) => {
	test.skip(!isMobile, 'débordement propre au téléphone');
	await ouvrir(page);
	const tableau = page.locator('table').first();
	await expect(tableau).toBeVisible();
	//  …et les gestes tiennent sur une ligne : comprimée, la cellule d'actions
	//  empilait ses cinq icônes, une ligne de 680 px de haut par compte.
	const ligne = tableau.locator('tbody tr').first();
	await expect.poll(() => ligne.evaluate((e) => e.offsetHeight)).toBeLessThan(150);
	await tableau.locator('thead th').first().hover();
	await page.mouse.wheel(4000, 0);
	const derniere = tableau.locator('thead th').last();
	await expect
		.poll(async () => {
			const boite = await derniere.boundingBox();
			return boite ? boite.x + boite.width : Infinity;
		})
		.toBeLessThanOrEqual(page.viewportSize()!.width + 1);
});

test('@sombre — Admin › Utilisateurs : le tableau des comptes se lit au thème sombre', async ({
	page,
}) => {
	await ouvrir(page);
	await forcerTheme(page, 'sombre');
	await attendreLisible(page, '#contenu');
});
