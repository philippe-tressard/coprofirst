/*
 *  **La page des prestataires, découpée en onglets (#779, 01/10/2026).**
 *
 *  La page passait 788 lignes ; chaque onglet possède désormais ce qu'il
 *  affiche (`OngletContrats`, `OngletPrestataires`). Une extraction préserve la
 *  SURFACE — les mêmes composants, les mêmes props — sans garantir le
 *  COMPORTEMENT : ce test tient les trois gestes que la découpe a déplacés.
 *
 *  1. un seul bloc déplié à la fois, dans chaque onglet — c'étaient deux `Set`,
 *     devenus `basculer` (`#lib/accordeon`) ;
 *  2. le bouton « + Nouveau … » de l'en-tête de la PAGE ouvre et referme la
 *     boîte de création que possède l'ONGLET ;
 *  3. le lien profond `#presta-<id>` venu d'un autre onglet conduit à la fiche,
 *     dépliée.
 *
 *  Et, depuis le 02/10/2026 (#1539), la correction EN PLACE que les deux cartes
 *  tiennent de `CarteModifiable` : la boîte s'ouvre dans la carte, le crayon
 *  dit le mode, et le titre ne replie pas une carte en correction — la règle
 *  du contrat, que le prestataire n'avait pas.
 */
import type { Page } from '@playwright/test';
import { expect, simulerApi, test } from './aides';

const PRESTATAIRES = [
	{ id: 1, nom: 'Otis', specialite: 'ascenseur', type_prestataire: 'maintenance_depannage' },
	{ id: 2, nom: 'Sicli', specialite: 'extincteurs', type_prestataire: 'maintenance_depannage' },
];
const CONTRATS = [1, 2].map((id) => ({
	id: 10 + id,
	prestataire_id: id,
	copropriete_id: 1,
	type_equipement: id === 1 ? 'ascenseur' : 'extincteurs',
	libelle: id === 1 ? 'Ascenseur' : 'Extincteurs',
	date_debut: '2025-01-01',
	perimetre_cible: ['résidence'],
	actif: true,
}));

async function ouvrir(page: Page, chemin: string) {
	await simulerApi(page, (api) => {
		if (api === '/api/prestataires') return PRESTATAIRES;
		if (api === '/api/prestataires/contrats') return CONTRATS;
		if (api === '/api/prestataires/notations') return [];
		if (api.startsWith('/api/documents')) return [];
	});
	await page.goto(chemin);
}

const deplie = (page: Page, id: string) => page.locator(`#${id}.expanded`);

test('annuaire : déplier une fiche replie l’autre', async ({ page }) => {
	await ouvrir(page, '/prestataires');
	await expect(page.locator('#presta-1')).toBeVisible(); //  cas zéro
	await page.locator('#presta-1').click();
	await expect(deplie(page, 'presta-1')).toBeVisible();
	await page.locator('#presta-2').click();
	await expect(deplie(page, 'presta-2')).toBeVisible();
	await expect(deplie(page, 'presta-1')).toHaveCount(0);
});

test('contrats : déplier un contrat replie l’autre', async ({ page }) => {
	await ouvrir(page, '/prestataires/contrats');
	await expect(page.locator('#contrat-11')).toBeVisible(); //  cas zéro
	await page.locator('#contrat-11').click();
	await expect(deplie(page, 'contrat-11')).toBeVisible();
	await page.locator('#contrat-12').click();
	await expect(deplie(page, 'contrat-12')).toBeVisible();
	await expect(deplie(page, 'contrat-11')).toHaveCount(0);
});

for (const [chemin, libelle] of [
	['/prestataires', 'Nouveau prestataire'],
	['/prestataires/contrats', 'Nouveau contrat'],
] as const) {
	test(`le bouton de la page ouvre et referme la création de l’onglet (${libelle})`, async ({
		page,
	}) => {
		await ouvrir(page, chemin);
		const boite = page.getByRole('heading', { name: libelle });
		await expect(boite).toHaveCount(0);
		await page.getByRole('button', { name: libelle }).click();
		await expect(boite).toBeVisible();
		await page
			.getByRole('button', { name: /Annuler/ })
			.first()
			.click();
		await expect(boite).toHaveCount(0);
	});
}

test('un lien #presta venu des contrats conduit à la fiche, dépliée', async ({ page }) => {
	await ouvrir(page, '/prestataires/contrats#presta-2');
	await expect(page).toHaveURL(/\/prestataires#presta-2$/);
	await expect(deplie(page, 'presta-2')).toBeVisible();
	await expect(deplie(page, 'presta-1')).toHaveCount(0);
});

for (const [chemin, carte, modifier] of [
	['/prestataires', 'presta-1', 'Modifier le prestataire'],
	['/prestataires/contrats', 'contrat-11', 'Modifier le contrat'],
] as const) {
	test(`la correction s’ouvre dans la carte, le titre ne la replie pas (${carte})`, async ({
		page,
	}) => {
		await ouvrir(page, chemin);
		const fiche = page.locator(`#${carte}`);
		await fiche.getByRole('button', { name: modifier }).click();
		const boite = fiche.getByRole('group', { name: modifier });
		await expect(boite).toBeVisible();
		const crayon = fiche.getByRole('button', { name: 'Annuler la correction' });
		await expect(crayon).toHaveAttribute('aria-pressed', 'true');

		await fiche.locator('.ec-titre-btn').click();
		await expect(boite).toBeVisible();

		await crayon.click();
		await expect(boite).toHaveCount(0);
		//  Le clic sur le titre n'a rien basculé en silence : la carte se replie.
		await expect(page.locator(`#${carte}.expanded`)).toHaveCount(0);
		await expect(fiche.getByRole('button', { name: modifier })).toHaveAttribute(
			'aria-pressed',
			'false',
		);
	});
}
